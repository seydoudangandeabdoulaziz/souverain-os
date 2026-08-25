"""Orchestration : lecture PostgreSQL → projection dans Neo4j.

Résout le tenant_id réel (UUID), lit les transactions, délègue la
projection à garde_isolation.synchroniser_transactions() — ce module
ne contient aucun Cypher, uniquement de l'orchestration.
"""

from __future__ import annotations

from dataclasses import dataclass

import asyncpg
from neo4j import AsyncDriver

from brique_06_neo4j import garde_isolation
from brique_06_neo4j.lecture import lire_tenant_id, lire_transactions


@dataclass(frozen=True)
class ResultatSynchronisation:
    tenant_id: str
    nb_transactions_lues: int
    nb_transactions_envoyees: int


async def synchroniser(
    pool: asyncpg.Pool, driver: AsyncDriver, nom_schema_tenant: str
) -> ResultatSynchronisation:
    """Cycle complet de synchronisation pour un tenant.

    Portée MVP (validée à l'analyse) : relit et reprojette l'intégralité
    de {tenant}.transactions à chaque exécution — voir le commentaire
    détaillé dans garde_isolation.synchroniser_transactions().
    """
    tenant_id = await lire_tenant_id(pool, nom_schema_tenant)
    transactions = await lire_transactions(pool, nom_schema_tenant)

    nb_envoyees = await garde_isolation.synchroniser_transactions(
        driver, str(tenant_id), transactions
    )

    return ResultatSynchronisation(
        tenant_id=str(tenant_id),
        nb_transactions_lues=len(transactions),
        nb_transactions_envoyees=nb_envoyees,
    )
