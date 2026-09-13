"""
Pool de connexions PostgreSQL DÉDIÉ au CLI de gouvernance de tenants.

Distinct du pool admin (create_pool(), souverain_admin — propriétaire
de toutes les tables) : ce pool utilise le rôle restreint
souverain_gouvernance_cli (voir migration 0002), qui a le privilège
CREATE nécessaire à provision_tenant_schema() mais JAMAIS UPDATE/DELETE
sur shared.gouvernance_audit_log.

Toutes les opérations de create_tenant()/activate_tenant()/
deactivate_tenant() passent par CE pool, jamais par create_pool() de
connection.py (le pool admin).
"""

from __future__ import annotations

import asyncpg

from brique_01_postgresql.config import get_settings
from brique_01_postgresql.gouvernance_cli_config import get_gouvernance_cli_db_settings

_pool: asyncpg.Pool | None = None


def _build_dsn() -> str:
    pg = get_settings()
    gouvernance = get_gouvernance_cli_db_settings()
    return f"postgresql://{gouvernance.user}:{gouvernance.password}@{pg.host}:{pg.port}/{pg.db}"


async def create_gouvernance_cli_pool() -> asyncpg.Pool:
    """Crée (ou retourne) le pool dédié global, avec le rôle restreint CLI."""
    global _pool

    if _pool is not None:
        return _pool

    settings = get_gouvernance_cli_db_settings()

    try:
        _pool = await asyncpg.create_pool(
            dsn=_build_dsn(),
            min_size=settings.pool_min_size,
            max_size=settings.pool_max_size,
        )
    except (OSError, asyncpg.PostgresError) as exc:
        raise ConnectionRefusedError(
            "Impossible de se connecter à PostgreSQL avec le rôle "
            "souverain_gouvernance_cli — vérifier que la migration 0002 "
            "de la Brique 1 a été appliquée (le rôle doit exister) et que "
            "GOUVERNANCE_CLI_DB_PASSWORD correspond au mot de passe réel "
            "du rôle en base."
        ) from exc

    return _pool


async def close_gouvernance_cli_pool() -> None:
    """Ferme proprement le pool dédié global, s'il existe."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
