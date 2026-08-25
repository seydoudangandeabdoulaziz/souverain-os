"""Tests de requetes.py — traduction Record → objets typés, cas vide.

⚠️ NON VÉRIFIÉ dans l'environnement de génération (pas de Neo4j
disponible) — à exécuter sur ta machine réelle.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from brique_06_neo4j import garde_isolation, requetes
from brique_06_neo4j.modeles import Chemin, ComptePont, TransactionAImporter
from neo4j import AsyncDriver


def _transaction(sender: str, receiver: str) -> TransactionAImporter:
    return TransactionAImporter(
        transaction_id=uuid4(),
        sender_account=sender,
        receiver_account=receiver,
        amount=Decimal("750.00"),
        currency="XOF",
        channel="moov_money",
        occurred_at=datetime.now(UTC),
        is_synthetic=True,
    )


@pytest.mark.asyncio
async def test_comptes_alertes_vide_retourne_liste_vide_via_requetes(
    driver: AsyncDriver, deux_tenants_de_test: tuple[str, str]
) -> None:
    """Exigence explicite de l'analyse : b) et c) gèrent proprement le cas
    {tenant}.alertes vide (situation réelle actuelle sur tenant_ne) — liste
    vide en sortie, jamais une erreur. Vérifié ici au niveau de la couche
    de présentation, pas seulement dans garde_isolation.py."""
    tenant_a, _ = deux_tenants_de_test

    assert await requetes.comptes_pont(driver, tenant_a, []) == []
    assert await requetes.plus_courts_chemins_entre_alertes(driver, tenant_a, []) == []


@pytest.mark.asyncio
async def test_chaines_redistribution_retourne_des_chemin_types(
    driver: AsyncDriver, deux_tenants_de_test: tuple[str, str]
) -> None:
    tenant_a, _ = deux_tenants_de_test
    comptes = ["r_001", "r_002", "r_003", "r_004"]
    transactions = [_transaction(comptes[i], comptes[i + 1]) for i in range(len(comptes) - 1)]
    await garde_isolation.synchroniser_transactions(driver, tenant_a, transactions)

    chaines = await requetes.chaines_redistribution(driver, tenant_a)

    assert len(chaines) >= 1
    chemin = chaines[0]
    assert isinstance(chemin, Chemin)
    assert all(isinstance(tid, UUID) for tid in chemin.transaction_ids)
    assert chemin.nb_sauts == len(chemin.transaction_ids)


@pytest.mark.asyncio
async def test_comptes_pont_retourne_des_objets_types(
    driver: AsyncDriver, deux_tenants_de_test: tuple[str, str]
) -> None:
    tenant_a, _ = deux_tenants_de_test
    await garde_isolation.synchroniser_transactions(
        driver,
        tenant_a,
        [_transaction("src_alerte", "compte_pont"), _transaction("compte_pont", "cible_alerte")],
    )

    ponts = await requetes.comptes_pont(driver, tenant_a, ["src_alerte", "cible_alerte"])

    assert len(ponts) == 1
    pont = ponts[0]
    assert isinstance(pont, ComptePont)
    assert pont.compte_pont == "compte_pont"
    assert isinstance(pont.transaction_entrante_id, UUID)
    assert isinstance(pont.transaction_sortante_id, UUID)
