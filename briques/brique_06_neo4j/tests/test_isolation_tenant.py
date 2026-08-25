"""Test d'isolation multi-tenant — le PREMIER test de cette brique,
avant tout autre (exigence explicite de l'analyse).

⚠️ NON VÉRIFIÉ dans l'environnement de génération (pas de Neo4j
disponible) — à exécuter sur ta machine réelle, comme pour les tests
d'intégration des briques précédentes.

Neo4j Community Edition ne supporte qu'une seule base de données :
l'isolation est logique (tenant_id), jamais physique. Ces tests
valident que cette isolation logique tient réellement, avec le
scénario le plus défavorable délibérément construit : deux tenants
utilisant EXACTEMENT les mêmes compte_id (réutilisation des préfixes
du générateur Brique 3 à l'export UEMOA — voir garde_isolation.py).
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
        amount=Decimal("1000.00"),
        currency="XOF",
        channel="orange_money",
        occurred_at=datetime.now(UTC),
        is_synthetic=True,
    )


@pytest.mark.asyncio
async def test_meme_compte_id_dans_deux_tenants_cree_deux_noeuds_distincts(
    driver: AsyncDriver, deux_tenants_de_test: tuple[str, str]
) -> None:
    """Le scénario de collision identifié à l'analyse : deux tenants avec
    le même compte_id (réutilisation de préfixe générateur) ne doivent
    JAMAIS fusionner en un seul nœud physique. C'est la contrainte
    composite (tenant_id, compte_id) qui le garantit, pas une simple
    discipline de code."""
    tenant_a, tenant_b = deux_tenants_de_test

    await garde_isolation.synchroniser_transactions(
        driver, tenant_a, [_transaction("hub_001", "hub_002")]
    )
    await garde_isolation.synchroniser_transactions(
        driver, tenant_b, [_transaction("hub_001", "hub_002")]
    )

    async with driver.session() as session:
        resultat = await session.run(
            "MATCH (n:Compte {compte_id: 'hub_001'}) WHERE n.tenant_id IN [$a, $b] "
            "RETURN n.tenant_id AS tenant_id",
            a=tenant_a,
            b=tenant_b,
        )
        lignes = [record["tenant_id"] async for record in resultat]

    assert sorted(lignes) == sorted([tenant_a, tenant_b])
    assert len(lignes) == 2  # deux nœuds distincts, jamais fusionnés


@pytest.mark.asyncio
async def test_chaines_redistribution_ne_fuient_pas_entre_tenants(
    driver: AsyncDriver, deux_tenants_de_test: tuple[str, str]
) -> None:
    """Deux tenants construisent CHACUN une chaîne de 4 sauts avec les
    mêmes compte_id (cpt_001 -> ... -> cpt_005). Interroger tenant_a ne
    doit retourner QUE la chaîne de tenant_a, jamais celle de tenant_b,
    même si elles portent des noms de compte identiques."""
    tenant_a, tenant_b = deux_tenants_de_test
    comptes = ["cpt_001", "cpt_002", "cpt_003", "cpt_004", "cpt_005"]
    transactions = [_transaction(comptes[i], comptes[i + 1]) for i in range(len(comptes) - 1)]

    await garde_isolation.synchroniser_transactions(driver, tenant_a, transactions)
    # Transactions différentes (nouveaux transaction_id) mais mêmes comptes.
    transactions_b = [_transaction(comptes[i], comptes[i + 1]) for i in range(len(comptes) - 1)]
    await garde_isolation.synchroniser_transactions(driver, tenant_b, transactions_b)

    chaines_a = await garde_isolation.detecter_chaines_redistribution(driver, tenant_a)

    assert len(chaines_a) >= 1
    ids_transactions_a = {str(tx.transaction_id) for tx in transactions}
    for chaine in chaines_a:
        for tid in chaine["transaction_ids"]:
            assert tid in ids_transactions_a  # jamais un transaction_id de tenant_b


@pytest.mark.asyncio
async def test_comptes_pont_ne_fuient_pas_entre_tenants(
    driver: AsyncDriver, deux_tenants_de_test: tuple[str, str]
) -> None:
    """Même scénario que ci-dessus, pour la requête b) : source -> pont -> cible,
    mêmes compte_id dans les deux tenants."""
    tenant_a, tenant_b = deux_tenants_de_test

    tx_a = [_transaction("alerte_src", "pont"), _transaction("pont", "alerte_cible")]
    tx_b = [_transaction("alerte_src", "pont"), _transaction("pont", "alerte_cible")]
    await garde_isolation.synchroniser_transactions(driver, tenant_a, tx_a)
    await garde_isolation.synchroniser_transactions(driver, tenant_b, tx_b)

    comptes_alertes = ["alerte_src", "alerte_cible"]
    ponts_a = await garde_isolation.detecter_comptes_pont(driver, tenant_a, comptes_alertes)

    assert len(ponts_a) == 1
    ids_transactions_a = {str(t.transaction_id) for t in tx_a}
    assert ponts_a[0]["transaction_entrante_id"] in ids_transactions_a
    assert ponts_a[0]["transaction_sortante_id"] in ids_transactions_a


@pytest.mark.asyncio
async def test_plus_court_chemin_ne_fuit_pas_entre_tenants(
    driver: AsyncDriver, deux_tenants_de_test: tuple[str, str]
) -> None:
    """shortestPath scopée à tenant_a ne doit jamais emprunter un nœud/relation de tenant_b,
    même si tenant_b a un chemin structurellement identique entre les mêmes noms de compte."""
    tenant_a, tenant_b = deux_tenants_de_test

    tx_a = [_transaction("alerte_1", "intermediaire"), _transaction("intermediaire", "alerte_2")]
    tx_b = [_transaction("alerte_1", "intermediaire"), _transaction("intermediaire", "alerte_2")]
    await garde_isolation.synchroniser_transactions(driver, tenant_a, tx_a)
    await garde_isolation.synchroniser_transactions(driver, tenant_b, tx_b)

    chemins_a = await garde_isolation.chemin_le_plus_court_entre_alertes(
        driver, tenant_a, ["alerte_1", "alerte_2"]
    )

    assert len(chemins_a) == 1
    ids_transactions_a = {str(t.transaction_id) for t in tx_a}
    for tid in chemins_a[0]["transaction_ids"]:
        assert tid in ids_transactions_a


@pytest.mark.asyncio
async def test_comptes_alertes_vide_retourne_liste_vide_sans_erreur(
    driver: AsyncDriver, deux_tenants_de_test: tuple[str, str]
) -> None:
    """Cas réel actuel de tenant_ne (aucune alerte créée) : b) et c) ne doivent
    jamais lever d'erreur, ni exécuter de requête inutile contre une liste vide."""
    tenant_a, _ = deux_tenants_de_test

    assert await garde_isolation.detecter_comptes_pont(driver, tenant_a, []) == []
    assert await garde_isolation.chemin_le_plus_court_entre_alertes(driver, tenant_a, []) == []
    # Un seul compte alerté : pas de paire possible, même comportement.
    assert await garde_isolation.detecter_comptes_pont(driver, tenant_a, ["seul_compte"]) == []
    assert (
        await garde_isolation.chemin_le_plus_court_entre_alertes(driver, tenant_a, ["seul_compte"])
        == []
    )
