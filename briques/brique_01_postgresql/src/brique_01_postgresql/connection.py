"""
Pool de connexions asynchrone vers PostgreSQL (asyncpg).

Pourquoi un pool plutôt qu'une connexion unique ?
Analogie : une connexion unique, c'est un seul guichet pour tout le
monde — tout le monde fait la queue. Un pool, c'est plusieurs guichets
ouverts en même temps, réutilisés au fur et à mesure. FastAPI (async)
recevra potentiellement plusieurs requêtes simultanées dès la Brique 4 ;
le pool est donc posé dès maintenant, même si cette brique ne l'utilise
encore que pour le healthcheck.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

import asyncpg

from brique_01_postgresql.config import (
    PostgresSettings,
    RuntimePostgresSettings,
    get_runtime_settings,
    get_settings,
)
from brique_01_postgresql.tenant_credentials import get_tenant_role_credentials

# Le pool est un singleton au niveau du module : une seule instance
# partagée par toute l'application, créée à la demande.
_pool: asyncpg.Pool | None = None
_runtime_pool: asyncpg.Pool | None = None
_tenant_pools: dict[tuple[UUID, str], asyncpg.Pool] = {}


async def create_pool(settings: PostgresSettings | None = None) -> asyncpg.Pool:
    """
    Crée (ou retourne) le pool de connexions global.

    Args:
        settings: configuration à utiliser. Si None, chargée depuis
                  l'environnement via get_settings().

    Raises:
        ConnectionRefusedError: si PostgreSQL n'est pas joignable
            (message reformulé pour être compréhensible sans connaître
            asyncpg en détail).
    """
    global _pool

    if _pool is not None:
        return _pool

    resolved_settings = settings or get_settings()

    try:
        _pool = await asyncpg.create_pool(
            dsn=resolved_settings.dsn,
            min_size=resolved_settings.pool_min_size,
            max_size=resolved_settings.pool_max_size,
        )
    except (OSError, asyncpg.PostgresError) as exc:
        raise ConnectionRefusedError(
            f"Impossible de joindre PostgreSQL sur "
            f"{resolved_settings.host}:{resolved_settings.port} — "
            f"vérifier que le conteneur est démarré "
            f"(docker compose --profile postgres up)."
        ) from exc

    return _pool


async def close_pool() -> None:
    """Ferme proprement le pool global, s'il existe."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def create_runtime_pool(
    settings: RuntimePostgresSettings | None = None,
) -> asyncpg.Pool:
    """Pool applicatif web séparé du pool d'administration/migration."""
    global _runtime_pool

    if _runtime_pool is not None:
        return _runtime_pool

    resolved_settings = settings or get_runtime_settings()
    try:
        _runtime_pool = await asyncpg.create_pool(
            dsn=resolved_settings.dsn,
            min_size=resolved_settings.pool_min_size,
            max_size=resolved_settings.pool_max_size,
        )
    except (OSError, asyncpg.PostgresError) as exc:
        raise ConnectionRefusedError(
            "Impossible de joindre PostgreSQL avec le rôle applicatif souverain_app. "
            "Vérifier APP_POSTGRES_USER/PASSWORD et la migration 0006."
        ) from exc
    return _runtime_pool


async def close_runtime_pool() -> None:
    """Ferme le pool web séparément du pool admin utilisé par les CLI."""
    global _runtime_pool
    if _runtime_pool is not None:
        await _runtime_pool.close()
        _runtime_pool = None


async def create_tenant_pool(tenant_id: UUID) -> asyncpg.Pool:
    """Pool métier limité par PostgreSQL au schéma d'un tenant."""
    key = (tenant_id, "data")
    if key in _tenant_pools:
        return _tenant_pools[key]

    runtime = get_runtime_settings()
    credentials = get_tenant_role_credentials(tenant_id, "data")
    try:
        pool = await asyncpg.create_pool(
            host=runtime.host,
            port=runtime.port,
            database=runtime.db,
            user=credentials.username,
            password=credentials.password.get_secret_value(),
            min_size=runtime.pool_min_size,
            max_size=runtime.pool_max_size,
        )
    except (OSError, asyncpg.PostgresError) as exc:
        raise ConnectionRefusedError(
            "Connexion PostgreSQL refusée pour l'identité du tenant demandé. "
            "Vérifier son provisioning et son entrée TENANT_DB_CREDENTIALS_JSON."
        ) from exc
    _tenant_pools[key] = pool
    return pool


async def create_tenant_audit_pool(tenant_id: UUID) -> asyncpg.Pool:
    """Pool d'audit propre au tenant, sans UPDATE/DELETE sur audit_log."""
    key = (tenant_id, "audit")
    if key in _tenant_pools:
        return _tenant_pools[key]

    runtime = get_runtime_settings()
    credentials = get_tenant_role_credentials(tenant_id, "audit")
    try:
        pool = await asyncpg.create_pool(
            host=runtime.host,
            port=runtime.port,
            database=runtime.db,
            user=credentials.username,
            password=credentials.password.get_secret_value(),
            min_size=1,
            max_size=min(5, runtime.pool_max_size),
            statement_cache_size=0,
        )
    except (OSError, asyncpg.PostgresError) as exc:
        raise ConnectionRefusedError(
            "Connexion PostgreSQL audit refusée pour le tenant demandé. "
            "Vérifier son provisioning et TENANT_DB_CREDENTIALS_JSON."
        ) from exc
    _tenant_pools[key] = pool
    return pool


async def create_tenant_pool_for_schema(schema_name: str) -> asyncpg.Pool:
    """Résout un schéma actif via le rôle de contrôle puis ouvre son pool limité."""
    from brique_01_postgresql.tenant_provisioning import validate_schema_name

    validated = validate_schema_name(schema_name)
    control_pool = await create_runtime_pool()
    async with control_pool.acquire() as connection:
        tenant_id = await connection.fetchval(
            "SELECT tenant_id FROM shared.tenants_registry "
            "WHERE schema_name = $1 AND is_active = true",
            validated,
        )
    if tenant_id is None:
        raise ValueError(f"Tenant actif introuvable pour le schéma {validated!r}")
    return await create_tenant_pool(tenant_id)


async def close_tenant_pools() -> None:
    """Ferme les pools tenant à l'arrêt du processus ou des tests."""
    for pool in tuple(_tenant_pools.values()):
        await pool.close()
    _tenant_pools.clear()


@asynccontextmanager
async def acquire_connection(
    settings: PostgresSettings | None = None,
) -> AsyncIterator[asyncpg.Connection]:
    """
    Context manager pratique pour obtenir une connexion depuis le pool.

    Usage :
        async with acquire_connection() as conn:
            await conn.fetch("SELECT 1")
    """
    pool = await create_pool(settings)
    async with pool.acquire() as connection:
        yield connection
