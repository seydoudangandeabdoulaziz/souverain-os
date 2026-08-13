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

import asyncpg

from brique_01_postgresql.config import PostgresSettings, get_settings

# Le pool est un singleton au niveau du module : une seule instance
# partagée par toute l'application, créée à la demande.
_pool: asyncpg.Pool | None = None


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
