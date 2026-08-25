"""Tests d'idempotence de la synchronisation — MERGE, pas de duplication au rejeu.

⚠️ NON VÉRIFIÉ dans l'environnement de génération (pas de Neo4j
disponible) — à exécuter sur ta machine réelle.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from brique_06_neo4j import garde_isolation
from brique_06_neo4j.modeles import TransactionAImporter
from neo4j import AsyncDriver


def _transaction(sender: str, receiver: str) -> TransactionAImporter:
    return TransactionAImporter(
        transaction_id=uuid4(),
        sender_account=sender,
        receiver_account=receiver,
        amount=Decimal("500.00"),
        currency="XOF",
        channel="airtel_money",
        occurred_at=datetime.now(UTC),
        is_synthetic=True,
    )


async def _compter_noeuds_et_relations(driver: AsyncDriver, tenant_id: str) -> tuple[int, int]:
    async with driver.session() as session:
        resultat_noeuds = await session.run(
            "MATCH (n:Compte {tenant_id: $t}) RETURN count(n) AS n", t=tenant_id
        )
        nb_noeuds = (await resultat_noeuds.single())["n"]

        resultat_relations = await session.run(
            "MATCH ()-[r:ENVOIE {tenant_id: $t}]->() RETURN count(r) AS n", t=tenant_id
        )
        nb_relations = (await resultat_relations.single())["n"]

    return nb_noeuds, nb_relations


@pytest.mark.asyncio
async def test_rejouer_la_meme_synchronisation_ne_duplique_rien(
    driver: AsyncDriver, deux_tenants_de_test: tuple[str, str]
) -> None:
    tenant_a, _ = deux_tenants_de_test
    transactions = [_transaction("cpt_a", "cpt_b"), _transaction("cpt_b", "cpt_c")]

    await garde_isolation.synchroniser_transactions(driver, tenant_a, transactions)
    nb_noeuds_1, nb_relations_1 = await _compter_noeuds_et_relations(driver, tenant_a)

    # Rejeu strictement identique — mêmes transaction_id.
    await garde_isolation.synchroniser_transactions(driver, tenant_a, transactions)
    nb_noeuds_2, nb_relations_2 = await _compter_noeuds_et_relations(driver, tenant_a)

    assert nb_noeuds_1 == nb_noeuds_2 == 3
    assert nb_relations_1 == nb_relations_2 == 2


@pytest.mark.asyncio
async def test_transactions_distinctes_entre_memes_comptes_creent_deux_relations(
    driver: AsyncDriver, deux_tenants_de_test: tuple[str, str]
) -> None:
    """transaction_id comme clé de relation : deux transactions différentes
    entre les deux mêmes comptes doivent produire deux relations distinctes,
    pas une seule écrasée."""
    tenant_a, _ = deux_tenants_de_test
    transactions = [_transaction("cpt_x", "cpt_y"), _transaction("cpt_x", "cpt_y")]

    await garde_isolation.synchroniser_transactions(driver, tenant_a, transactions)
    nb_noeuds, nb_relations = await _compter_noeuds_et_relations(driver, tenant_a)

    assert nb_noeuds == 2  # un seul cpt_x, un seul cpt_y
    assert nb_relations == 2  # deux relations distinctes malgré les mêmes comptes


@pytest.mark.asyncio
async def test_contraintes_creees_de_maniere_idempotente(driver: AsyncDriver) -> None:
    """assurer_contraintes() rejouable sans erreur (IF NOT EXISTS)."""
    await garde_isolation.assurer_contraintes(driver)
    await garde_isolation.assurer_contraintes(driver)  # ne doit pas lever
