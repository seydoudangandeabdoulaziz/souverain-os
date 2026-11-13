"""Pool d'audit PostgreSQL scindé par identité de tenant."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from brique_01_postgresql.connection import (
    close_tenant_pools,
    create_tenant_audit_pool,
)


async def create_audit_pool(tenant_id: UUID) -> asyncpg.Pool:
    """Retourne le pool d'audit non partageable avec un autre tenant."""
    return await create_tenant_audit_pool(tenant_id)


async def close_audit_pool() -> None:
    """Ferme tous les pools tenant, y compris leurs pools d'audit."""
    await close_tenant_pools()
