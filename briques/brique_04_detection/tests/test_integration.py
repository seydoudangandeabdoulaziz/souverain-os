"""Test d'intégration — insertion réelle en base (pas de mock).

⚠️ NON VÉRIFIÉ dans l'environnement de génération (pas de PostgreSQL
disponible) — à exécuter sur ta machine réelle, comme pour la Brique 3.

Prérequis :
- Container PostgreSQL démarré
- Migrations Briques 1 et 3 appliquées
- tenant_ne bootstrapé et provisionné (Brique 3)
- Idéalement : les 5000 transactions de la Brique 3 déjà en base
  (test_detecte_sur_transactions_existantes ne fonctionne que si c'est le cas)
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio
from brique_01_postgresql.connection import close_pool, create_pool
from brique_01_postgresql.tenant_provisioning import provision_tenant_schema
from brique_04_detection.lecture import lire_transactions_ordonnees
from brique_04_detection.moteur import detecter_sequentiellement
from brique_04_detection.persistence import enregistrer_detections, recuperer_metadonnees_tenant

TENANT_TEST = "tenant_test_detection"


@pytest_asyncio.fixture
async def pool() -> AsyncIterator[asyncpg.Pool]:
    pool_connexions = await create_pool()
    try:
        yield pool_connexions
    finally:
        await close_pool()


@pytest_asyncio.fixture
async def tenant_provisionne(pool: asyncpg.Pool) -> AsyncIterator[str]:
    """Même pattern que la Brique 3 : tenant éphémère, provisionné et
    nettoyé à chaque test, pour ne jamais dépendre de tenant_ne ni le
    polluer avec des données de test de la Brique 4.
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

    try:
        yield TENANT_TEST
    finally:
        async with pool.acquire() as connexion:
            await connexion.execute(f"DROP SCHEMA IF EXISTS {TENANT_TEST} CASCADE")
            await connexion.execute(
                "DELETE FROM shared.tenants_registry WHERE schema_name = $1", TENANT_TEST
            )


@pytest.mark.asyncio
async def test_pipeline_complet_lecture_detection_ecriture(
    pool: asyncpg.Pool, tenant_provisionne: str
) -> None:
    """Insère quelques transactions directement (sans passer par la Brique 3,
    pour ne pas ajouter une dépendance runtime), fait tourner le moteur,
    vérifie l'écriture des détections.
    """
    metadonnees = await recuperer_metadonnees_tenant(pool, tenant_provisionne)

    from datetime import datetime, timedelta, timezone

    fuseau = timezone(timedelta(hours=1))
    base = datetime(2026, 3, 1, 10, 0, 0, tzinfo=fuseau)

    async with pool.acquire() as connexion:
        for i in range(8):
            await connexion.execute(
                f"""
                INSERT INTO {tenant_provisionne}.transactions
                    (transaction_id, tenant_id, country_code, data_classification,
                     amount, currency, sender_account, receiver_account, channel,
                     occurred_at, is_synthetic)
                VALUES ($1, $2, $3, $4, $5, 'XOF', 'hub_999999', $6, 'orange_money', $7, true)
                """,
                uuid4(),
                metadonnees.tenant_id,
                metadonnees.country_code,
                metadonnees.data_classification,
                50_000.0,
                f"cpt_{100000 + i}",
                base + timedelta(minutes=i * 5),
            )

    transactions = await lire_transactions_ordonnees(pool, tenant_provisionne)
    assert len(transactions) == 8

    evenements = detecter_sequentiellement(transactions)
    assert len(evenements) == 1
    assert evenements[0].pattern_type == "structure_etoile"

    nb_insere = await enregistrer_detections(pool, tenant_provisionne, evenements)
    assert nb_insere == 1

    async with pool.acquire() as connexion:
        compte = await connexion.fetchval(
            f"SELECT count(*) FROM {tenant_provisionne}.detections"
        )
    assert compte == 1


@pytest.mark.asyncio
async def test_detecte_sur_transactions_existantes_tenant_ne(pool: asyncpg.Pool) -> None:
    """Test de vérité : fait tourner le moteur sur les 5000 transactions
    réelles déjà générées par la Brique 3 pour tenant_ne. Suppose que
    `uv run souverain-generer --tenant tenant_ne` a déjà été exécuté.
    """
    transactions = await lire_transactions_ordonnees(pool, "tenant_ne")
    if not transactions:
        pytest.skip("Aucune transaction pour tenant_ne — lance d'abord la Brique 3.")

    evenements = detecter_sequentiellement(transactions)
    print(f"\n{len(transactions)} transactions lues, {len(evenements)} détections")

    from collections import Counter

    repartition = Counter(e.pattern_type for e in evenements)
    for pattern_type, nb in sorted(repartition.items()):
        print(f"  - {pattern_type} : {nb}")

    # Pas d'assertion stricte ici — ce test sert surtout à observer les
    # résultats réels et ajuster les seuils si besoin (décision actée :
    # seuils validés "tels quels", à ajuster après résultats réels).
    assert isinstance(evenements, list)
