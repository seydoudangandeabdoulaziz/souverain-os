"""
Pool de connexions PostgreSQL DÉDIÉ aux routes web de gouvernance des
utilisateurs — rôle souverain_gouvernance_web (voir migrations/0002).

Distinct du pool admin (souverain_admin) : DML uniquement sur
shared.users, INSERT/SELECT uniquement (jamais UPDATE/DELETE) sur
shared.gouvernance_audit_log.
"""

from __future__ import annotations

import asyncpg
from brique_01_postgresql.config import get_settings

from brique_02_auth_rbac.gouvernance.config import get_gouvernance_web_db_settings

_pool: asyncpg.Pool | None = None


def _build_dsn() -> str:
    pg = get_settings()
    web = get_gouvernance_web_db_settings()
    return f"postgresql://{web.user}:{web.password}@{pg.host}:{pg.port}/{pg.db}"


async def create_gouvernance_web_pool() -> asyncpg.Pool:
    global _pool

    if _pool is not None:
        return _pool

    settings = get_gouvernance_web_db_settings()

    try:
        _pool = await asyncpg.create_pool(
            dsn=_build_dsn(),
            min_size=settings.pool_min_size,
            max_size=settings.pool_max_size,
            # Même précaution que le pool dédié de la Brique 8 : évite
            # InvalidCachedStatementError si des tenants/schémas
            # éphémères sont recréés pendant les tests d'intégration.
            statement_cache_size=0,
        )
    except (OSError, asyncpg.PostgresError) as exc:
        raise ConnectionRefusedError(
            "Impossible de se connecter à PostgreSQL avec le rôle "
            "souverain_gouvernance_web — vérifier que la migration 0002 "
            "de la Brique 2 a été appliquée et que GOUVERNANCE_WEB_DB_PASSWORD "
            "correspond au mot de passe réel du rôle en base."
        ) from exc

    return _pool


async def close_gouvernance_web_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
