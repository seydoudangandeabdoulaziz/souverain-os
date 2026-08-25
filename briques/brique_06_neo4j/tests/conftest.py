"""Fixtures partagées pour les tests de la Brique 6.

Pas de dépendance à PostgreSQL ici : les tests d'isolation et de
requêtes construisent leurs propres TransactionAImporter en mémoire et
les projettent directement via garde_isolation — l'isolation est une
propriété du graphe Neo4j lui-même, pas besoin d'un vrai tenant
PostgreSQL pour la valider.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest_asyncio
from brique_06_neo4j.connexion import close_driver, create_driver
from neo4j import AsyncDriver


@pytest_asyncio.fixture
async def driver() -> AsyncIterator[AsyncDriver]:
    d = await create_driver()
    try:
        yield d
    finally:
        await close_driver()


@pytest_asyncio.fixture
async def deux_tenants_de_test(driver: AsyncDriver) -> AsyncIterator[tuple[str, str]]:
    """Deux tenant_id éphémères, nettoyés après le test (nœuds + relations).

    Retourne (tenant_a, tenant_b) — deux UUID distincts, sans lien avec
    de vrais tenants PostgreSQL.
    """
    tenant_a = str(uuid4())
    tenant_b = str(uuid4())
    try:
        yield tenant_a, tenant_b
    finally:
        async with driver.session() as session:
            await session.run(
                "MATCH (n:Compte) WHERE n.tenant_id IN [$a, $b] DETACH DELETE n",
                a=tenant_a,
                b=tenant_b,
            )
