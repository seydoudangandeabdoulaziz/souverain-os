"""Fixtures partagées pour les tests d'intégration de la Brique 5.

Exposées comme fixtures pytest (pas comme import direct
`from tests.conftest import ...`) : le dépôt a un dossier tests/ à la
racine du workspace, qui entre en collision avec celui de cette brique
quand pytest est invoqué depuis la racine — même précaution que
conftest.py de la Brique 4.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import uuid4

import asyncpg
import pytest_asyncio
from brique_01_postgresql.connection import close_pool, create_pool
from brique_01_postgresql.tenant_provisioning import provision_tenant_schema

TENANT_TEST = "tenant_test_scoring"


@pytest_asyncio.fixture
async def pool() -> AsyncIterator[asyncpg.Pool]:
    pool_connexions = await create_pool()
    try:
        yield pool_connexions
    finally:
        await close_pool()


@pytest_asyncio.fixture
async def tenant_provisionne(pool: asyncpg.Pool) -> AsyncIterator[str]:
    """Tenant éphémère, provisionné et nettoyé à chaque test.

    Ne dépend jamais de tenant_ne ni ne le pollue — même pattern que
    les Briques 3 et 4.
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
        await connexion.execute(
            f"ALTER TABLE {TENANT_TEST}.transactions "
            "ADD COLUMN IF NOT EXISTS is_synthetic BOOLEAN NOT NULL DEFAULT false;"
        )
        # Le DDL est préparé par la fixture admin comme la migration B5 en
        # environnement réel. Le rôle métier tenant ne crée ni table ni index.
        await connexion.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TENANT_TEST}.alertes (
                alerte_id UUID PRIMARY KEY,
                tenant_id UUID NOT NULL,
                country_code TEXT NOT NULL,
                data_classification TEXT NOT NULL,
                compte_pivot TEXT NOT NULL,
                score INTEGER NOT NULL,
                statut TEXT NOT NULL DEFAULT 'ouverte'
                    CHECK (statut IN ('ouverte', 'fermee')),
                pattern_types_impliques TEXT[] NOT NULL,
                detection_ids UUID[] NOT NULL,
                fenetre_debut TIMESTAMPTZ NOT NULL,
                fenetre_fin TIMESTAMPTZ NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                details JSONB
            )
            """
        )
        await connexion.execute(
            f"CREATE UNIQUE INDEX IF NOT EXISTS idx_{TENANT_TEST}_alertes_ouverte_compte "
            f"ON {TENANT_TEST}.alertes (compte_pivot) WHERE statut = 'ouverte'"
        )

    try:
        yield TENANT_TEST
    finally:
        async with pool.acquire() as connexion:
            await connexion.execute(f"DROP SCHEMA IF EXISTS {TENANT_TEST} CASCADE")
            await connexion.execute(
                "DELETE FROM shared.tenants_registry WHERE schema_name = $1", TENANT_TEST
            )
