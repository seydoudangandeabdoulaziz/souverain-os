"""Test d'intégration bout-en-bout de la Brique 5.

Scénarios calqués sur le comportement réellement observé en exécution
manuelle le 16/08/2026 sur tenant_ne :
- des détections multi-types sur un même compte_pivot produisent un
  score cumulé et une alerte si le seuil est franchi ;
- une ré-exécution sans nouvelle détection ne crée aucun doublon (Q5) ;
- un compte_pivot NULL est exclu et journalisé (Correction 2) ;
- is_synthetic suit la règle "100% sinon false" (Correction 1).

ATTENTION : les colonnes exactes de {tenant}.transactions utilisées
ci-dessous (transaction_id, occurred_at, montant, is_synthetic) n'ont
pas été reconfirmées contre le vrai schéma de la Brique 1 dans cette
session — à ajuster si les noms réels diffèrent.
"""

from __future__ import annotations

import uuid

import asyncpg
import pytest

from souverain_scoring.cli import executer_cycle_scoring
from souverain_scoring.config import ParametresScoring

TENANT_ID = uuid.uuid4()  # UUID fixe pour toute la session de test


async def _inserer_transaction(
    connexion: asyncpg.Connection, schema: str, is_synthetic: bool
) -> uuid.UUID:
    transaction_id = uuid.uuid4()
    await connexion.execute(
        f"""
        INSERT INTO {schema}.transactions
            (transaction_id, tenant_id, country_code, data_classification,
             amount, currency, sender_account, receiver_account, channel,
             occurred_at, is_synthetic)
        VALUES ($1, $2, 'NE', 'restricted', 1000, 'XOF',
                'test_sender', 'test_receiver', 'orange_money', now(), $3)
        """,
        transaction_id,
        TENANT_ID,
        is_synthetic,
    )
    return transaction_id


async def _inserer_detection(
    connexion: asyncpg.Connection,
    schema: str,
    compte_pivot: str | None,
    pattern_type: str,
    transaction_ids: list[uuid.UUID],
) -> uuid.UUID:
    detection_id = uuid.uuid4()
    await connexion.execute(
        f"""
        INSERT INTO {schema}.detections
            (detection_id, tenant_id, country_code, data_classification,
             pattern_type, transaction_ids, compte_pivot,
             fenetre_debut, fenetre_fin, detected_at, details)
        VALUES ($1, $2, 'NE', 'restricted', $3, $4, $5,
                now(), now(), now(), '{{}}'::jsonb)
        """,
        detection_id,
        TENANT_ID,
        pattern_type,
        transaction_ids,
        compte_pivot,
    )
    return detection_id


@pytest.mark.asyncio
async def test_cycle_complet_cree_une_alerte(
    pool: asyncpg.Pool, schema_tenant_ephemere: str
) -> None:
    """Deux détections de types distincts sur un compte déclenchent une alerte."""
    schema = schema_tenant_ephemere
    async with pool.acquire() as connexion:
        tx1 = await _inserer_transaction(connexion, schema, is_synthetic=True)
        tx2 = await _inserer_transaction(connexion, schema, is_synthetic=True)
        await _inserer_detection(connexion, schema, "cp_test_1", "compte_pivot", [tx1])
        await _inserer_detection(
            connexion, schema, "cp_test_1", "transactions_nocturnes", [tx2]
        )

    parametres = ParametresScoring(seuil_alerte=35)
    nombre = await executer_cycle_scoring(
        pool, schema, TENANT_ID, "NE", "restricted", parametres
    )
    assert nombre == 1

    async with pool.acquire() as connexion:
        ligne = await connexion.fetchrow(
            f"SELECT score, statut FROM {schema}.alertes WHERE compte_pivot = 'cp_test_1'"
        )
    assert ligne is not None
    assert ligne["score"] == 40  # 30 (compte_pivot) + 10 (transactions_nocturnes)
    assert ligne["statut"] == "ouverte"


@pytest.mark.asyncio
async def test_reexecution_sans_nouvelle_detection_ne_duplique_pas(
    pool: asyncpg.Pool, schema_tenant_ephemere: str
) -> None:
    """Comportement vérifié manuellement le 16/08/2026 sur tenant_ne :
    une deuxième exécution sans détection nouvelle laisse le nombre
    de lignes alertes inchangé (anti-doublon Q5).
    """
    schema = schema_tenant_ephemere
    async with pool.acquire() as connexion:
        tx1 = await _inserer_transaction(connexion, schema, is_synthetic=True)
        tx2 = await _inserer_transaction(connexion, schema, is_synthetic=True)
        await _inserer_detection(connexion, schema, "cp_test_2", "compte_pivot", [tx1])
        await _inserer_detection(
            connexion, schema, "cp_test_2", "transactions_nocturnes", [tx2]
        )

    parametres = ParametresScoring(seuil_alerte=35)
    premier = await executer_cycle_scoring(
        pool, schema, TENANT_ID, "NE", "restricted", parametres
    )
    assert premier == 1

    second = await executer_cycle_scoring(
        pool, schema, TENANT_ID, "NE", "restricted", parametres
    )
    assert second == 0

    async with pool.acquire() as connexion:
        total = await connexion.fetchval(f"SELECT count(*) FROM {schema}.alertes")
    assert total == 1


@pytest.mark.asyncio
async def test_compte_pivot_null_est_exclu(
    pool: asyncpg.Pool, schema_tenant_ephemere: str
) -> None:
    """Une détection avec compte_pivot NULL n'apparaît dans aucune alerte."""
    schema = schema_tenant_ephemere
    async with pool.acquire() as connexion:
        tx = await _inserer_transaction(connexion, schema, is_synthetic=True)
        await _inserer_detection(connexion, schema, None, "compte_pivot", [tx])

    parametres = ParametresScoring(seuil_alerte=35)
    nombre = await executer_cycle_scoring(
        pool, schema, TENANT_ID, "NE", "restricted", parametres
    )
    assert nombre == 0

    async with pool.acquire() as connexion:
        total = await connexion.fetchval(f"SELECT count(*) FROM {schema}.alertes")
    assert total == 0


@pytest.mark.asyncio
async def test_is_synthetic_mixte_donne_false(
    pool: asyncpg.Pool, schema_tenant_ephemere: str
) -> None:
    """Détections dont les transactions liées mélangent réel et synthétique."""
    schema = schema_tenant_ephemere
    async with pool.acquire() as connexion:
        tx_reel = await _inserer_transaction(connexion, schema, is_synthetic=False)
        tx_synth = await _inserer_transaction(connexion, schema, is_synthetic=True)
        await _inserer_detection(connexion, schema, "cp_test_3", "compte_pivot", [tx_reel])
        await _inserer_detection(
            connexion, schema, "cp_test_3", "transactions_nocturnes", [tx_synth]
        )

    parametres = ParametresScoring(seuil_alerte=35)
    await executer_cycle_scoring(pool, schema, TENANT_ID, "NE", "restricted", parametres)

    async with pool.acquire() as connexion:
        is_synthetic = await connexion.fetchval(
            f"SELECT is_synthetic FROM {schema}.alertes WHERE compte_pivot = 'cp_test_3'"
        )
    assert is_synthetic is False
