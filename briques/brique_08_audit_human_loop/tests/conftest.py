"""Fixtures partagées pour les tests d'intégration de la Brique 8.

Même pattern que conftest.py de la Brique 7 : une vraie alerte via le
pipeline Brique 4 -> Brique 5 déjà validé, jamais d'insertion SQL à la
main. Deux différences propres à cette brique :

1. tenant_provisionne accorde EN PLUS les privilèges du rôle
   souverain_brique8_audit sur le schéma éphémère du test — la
   migration 0001 ne couvre que les tenants déjà enregistrés AU MOMENT
   de son exécution (même limite documentée pour les Briques 3/4/5), et
   un tenant de test est créé APRÈS coup. Sans ce GRANT explicite ici,
   pool_audit échouerait sur un tenant qui n'existait pas encore lors
   de la migration.
2. Une fixture pool_audit distincte du pool admin (create_pool) —
   c'est PRÉCISÉMENT ce que ces tests doivent vérifier : que le rôle
   restreint suffit à fermer une alerte et écrire l'audit, mais pas à
   autre chose.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import asyncpg
import pytest_asyncio
from brique_01_postgresql.connection import close_pool, create_pool
from brique_01_postgresql.tenant_provisioning import provision_tenant_schema
from brique_02_auth_rbac.password_hashing import hash_password
from brique_02_auth_rbac.repository import UserRecord, create_user
from brique_02_auth_rbac.souverain_id import generate_souverain_id
from brique_04_detection.modeles import DetectionEvent
from brique_04_detection.persistence import enregistrer_detections
from brique_05_scoring_alertes.modeles import ScoreCompte
from brique_05_scoring_alertes.persistence import enregistrer_scores
from brique_08_audit_human_loop.connection import close_audit_pool, create_audit_pool

TENANT_TEST = "tenant_test_audit"
TENANT_CODE_TEST = "YY"
EMAIL_ANALYST_TEST = "audit-analyst-test@example.com"
EMAIL_AUDITOR_TEST = "audit-auditor-test@example.com"
MOT_DE_PASSE_TEST = "mot-de-passe-de-test-suffisamment-long"
COMPTE_ALERTE_TEST = "compte_test_audit_01"


@pytest_asyncio.fixture
async def pool() -> AsyncIterator[asyncpg.Pool]:
    p = await create_pool()
    try:
        yield p
    finally:
        await close_pool()


@pytest_asyncio.fixture
async def pool_audit(
    tenant_provisionne: tuple[UUID, str],
) -> AsyncIterator[asyncpg.Pool]:
    """Pool avec le rôle RESTREINT souverain_brique8_audit — dépend de
    tenant_provisionne pour garantir que les GRANT du tenant de test
    (voir cette fixture) ont déjà eu lieu avant toute connexion.
    """
    p = await create_audit_pool()
    try:
        yield p
    finally:
        await close_audit_pool()


@pytest_asyncio.fixture
async def tenant_provisionne(pool: asyncpg.Pool) -> AsyncIterator[tuple[UUID, str]]:
    """(tenant_id, schema_name) éphémères, nettoyés après le test.

    Accorde explicitement au rôle souverain_brique8_audit les mêmes
    privilèges que la migration 0001 accorde aux tenants existants au
    moment de son exécution — nécessaire car ce tenant n'existait pas
    encore à ce moment-là (même limite déjà documentée pour les
    migrations des Briques 3/4/5).
    """
    async with pool.acquire() as connexion:
        tenant_id: UUID = await connexion.fetchval(
            """
            INSERT INTO shared.tenants_registry
                (tenant_code, country_code, schema_name, data_classification, is_active)
            VALUES ($1, 'NE', $2, 'confidential', true)
            ON CONFLICT (schema_name) DO UPDATE SET is_active = true
            RETURNING tenant_id
            """,
            TENANT_CODE_TEST,
            TENANT_TEST,
        )
        await provision_tenant_schema(connexion, TENANT_TEST)

        # audit_log est créée à la demande par persistence.py (auto-
        # réparation via le pool admin) — pas de GRANT anticipé ici.
        #
        # ⚠️ GRANT sur alertes retiré d'ici : {tenant}.alertes n'existe
        # PAS encore à ce stade (provision_tenant_schema ne crée que le
        # schéma + transactions — alertes est créée paresseusement par
        # enregistrer_scores() de la Brique 5, même limite déjà
        # rencontrée et documentée pour TenantSansDonnees en Brique 7).
        # Tenter le GRANT ici échouait avec UndefinedTableError. Le
        # GRANT sur alertes est donc déplacé dans la fixture
        # alerte_test, juste après la création réelle de la table.
        await connexion.execute(f"GRANT USAGE ON SCHEMA {TENANT_TEST} TO souverain_brique8_audit")

    try:
        yield tenant_id, TENANT_TEST
    finally:
        async with pool.acquire() as connexion:
            await connexion.execute("DELETE FROM shared.users WHERE tenant_id = $1", tenant_id)
            await connexion.execute(f"DROP SCHEMA IF EXISTS {TENANT_TEST} CASCADE")
            await connexion.execute(
                "DELETE FROM shared.tenants_registry WHERE schema_name = $1", TENANT_TEST
            )


@pytest_asyncio.fixture
async def utilisateur_analyst_test(
    pool: asyncpg.Pool, tenant_provisionne: tuple[UUID, str]
) -> UserRecord:
    tenant_id, _ = tenant_provisionne
    async with pool.acquire() as connexion:
        return await create_user(
            connexion,
            tenant_id=tenant_id,
            souverain_id=generate_souverain_id(TENANT_CODE_TEST, EMAIL_ANALYST_TEST),
            email=EMAIL_ANALYST_TEST,
            password_hash=hash_password(MOT_DE_PASSE_TEST),
            role="analyst",
        )


@pytest_asyncio.fixture
async def utilisateur_auditor_test(
    pool: asyncpg.Pool, tenant_provisionne: tuple[UUID, str]
) -> UserRecord:
    tenant_id, _ = tenant_provisionne
    async with pool.acquire() as connexion:
        return await create_user(
            connexion,
            tenant_id=tenant_id,
            souverain_id=generate_souverain_id(TENANT_CODE_TEST, EMAIL_AUDITOR_TEST),
            email=EMAIL_AUDITOR_TEST,
            password_hash=hash_password(MOT_DE_PASSE_TEST),
            role="auditor",
        )


@pytest_asyncio.fixture
async def alerte_test(
    pool: asyncpg.Pool, tenant_provisionne: tuple[UUID, str]
) -> UUID:
    """Une vraie alerte 'ouverte', via le pipeline Brique 4 -> Brique 5.

    compte_pivot (30) + micro_fractionnement (20) = 50 = SEUIL_ALERTE.
    Retourne alerte_id (nécessaire pour cibler la fermeture).
    """
    _, schema_name = tenant_provisionne
    maintenant = datetime.now(UTC)

    evenements = [
        DetectionEvent(
            pattern_type="compte_pivot",
            transaction_ids=[uuid4(), uuid4()],
            fenetre_debut=maintenant - timedelta(minutes=30),
            fenetre_fin=maintenant,
            compte_pivot=COMPTE_ALERTE_TEST,
        ),
        DetectionEvent(
            pattern_type="micro_fractionnement",
            transaction_ids=[uuid4(), uuid4()],
            fenetre_debut=maintenant - timedelta(minutes=30),
            fenetre_fin=maintenant,
            compte_pivot=COMPTE_ALERTE_TEST,
        ),
    ]
    await enregistrer_detections(pool, schema_name, evenements)

    async with pool.acquire() as connexion:
        lignes = await connexion.fetch(
            f"SELECT detection_id FROM {schema_name}.detections WHERE compte_pivot = $1",
            COMPTE_ALERTE_TEST,
        )
    detection_ids_reels = [ligne["detection_id"] for ligne in lignes]
    assert len(detection_ids_reels) == 2

    score = ScoreCompte(
        compte_pivot=COMPTE_ALERTE_TEST,
        score=50,
        pattern_types_impliques=["compte_pivot", "micro_fractionnement"],
        detection_ids=detection_ids_reels,
        fenetre_debut=maintenant - timedelta(days=7),
        fenetre_fin=maintenant,
        details={"compte_pivot": 30, "micro_fractionnement": 20},
    )
    await enregistrer_scores(pool, schema_name, [score])

    # {tenant}.alertes existe désormais réellement (créée par
    # enregistrer_scores ci-dessus) — c'est SEULEMENT maintenant que le
    # GRANT sur cette table peut réussir. Tenter ce GRANT plus tôt (dans
    # tenant_provisionne, avant que la table existe) échouait avec
    # UndefinedTableError — voir le commentaire retiré de cette fixture.
    async with pool.acquire() as connexion:
        await connexion.execute(
            f"GRANT SELECT, UPDATE ON {schema_name}.alertes TO souverain_brique8_audit"
        )

    async with pool.acquire() as connexion:
        alerte_id: UUID = await connexion.fetchval(
            f"SELECT alerte_id FROM {schema_name}.alertes WHERE compte_pivot = $1",
            COMPTE_ALERTE_TEST,
        )
    return alerte_id
