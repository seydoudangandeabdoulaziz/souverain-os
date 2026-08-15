"""Fixtures partagées pour les tests de la Brique 3.

CORRECTIF : réutilise create_pool()/close_pool() de la Brique 1 (au lieu
d'une connexion DATABASE_URL autonome). Provisionne un tenant ÉPHÉMÈRE
dédié aux tests ("tenant_test_generateur"), enregistré et nettoyé à
chaque test — même logique que test_provision_tenant_schema_is_idempotent
dans la Brique 1 (tests/test_connection.py), pour ne jamais dépendre
d'un état préexistant (tenant_ne) ni le polluer avec des données de test.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import uuid4

import asyncpg
import pytest_asyncio
from brique_01_postgresql.connection import close_pool, create_pool
from brique_01_postgresql.tenant_provisioning import provision_tenant_schema

TENANT_TEST = "tenant_test_generateur"


@pytest_asyncio.fixture
async def pool() -> AsyncIterator[asyncpg.Pool]:
    pool_connexions = await create_pool()
    try:
        yield pool_connexions
    finally:
        await close_pool()


@pytest_asyncio.fixture
async def tenant_provisionne(pool: asyncpg.Pool) -> AsyncIterator[str]:
    """Provisionne un tenant de test complet (schéma + registre), nettoyé après.

    Contourne volontairement l'absence de create_tenant() (réservé Brique 8) :
    insertion directe dans shared.tenants_registry, scopée aux tests, jamais
    utilisée en dehors de ce fichier. Ne pas reproduire ce pattern ailleurs —
    voir scripts/bootstrap_tenant_ne.sql pour l'explication du même choix
    appliqué au tenant Niger MVP.
    """
    async with pool.acquire() as connexion:
        await connexion.execute(
            """
            INSERT INTO shared.tenants_registry
                (tenant_code, country_code, schema_name, data_classification, is_active)
            VALUES ($1, 'NE', $2, 'confidential', true)
            ON CONFLICT (schema_name) DO NOTHING
            """,
            f"TEST-{uuid4().hex[:8]}",
            TENANT_TEST,
        )
        await provision_tenant_schema(connexion, TENANT_TEST)

    try:
        yield TENANT_TEST
    finally:
        async with pool.acquire() as connexion:
            await connexion.execute(f"DROP SCHEMA IF EXISTS {TENANT_TEST} CASCADE")
            await connexion.execute(
                "DELETE FROM shared.tenants_registry WHERE schema_name = $1", TENANT_TEST
            )
