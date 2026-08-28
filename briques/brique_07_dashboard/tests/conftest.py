"""Fixtures partagées pour les tests de la Brique 7.

Utilise brique_04_detection.persistence.enregistrer_detections() et
brique_05_scoring_alertes.persistence.enregistrer_scores() — déjà
validées — pour produire une vraie alerte plutôt que d'insérer des
lignes SQL à la main : les données de test traversent le même chemin
que les données réelles.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import asyncpg
import pytest_asyncio
from brique_01_postgresql.connection import close_pool, create_pool
from brique_01_postgresql.tenant_provisioning import provision_tenant_schema
from brique_02_auth_rbac.config import get_jwt_settings
from brique_02_auth_rbac.jwt_tokens import create_access_token
from brique_02_auth_rbac.password_hashing import hash_password
from brique_02_auth_rbac.repository import UserRecord, create_user
from brique_02_auth_rbac.souverain_id import generate_souverain_id
from brique_04_detection.modeles import DetectionEvent
from brique_04_detection.persistence import enregistrer_detections
from brique_05_scoring_alertes.modeles import ScoreCompte
from brique_05_scoring_alertes.persistence import enregistrer_scores
from brique_06_neo4j.connexion import close_driver, create_driver
from brique_07_dashboard.app import creer_application
from brique_07_dashboard.config import get_dashboard_settings
from httpx import ASGITransport, AsyncClient
from neo4j import AsyncDriver

TENANT_TEST = "tenant_test_dashboard"
TENANT_CODE_TEST = "ZZ"
EMAIL_TEST = "dashboard-test@example.com"
MOT_DE_PASSE_TEST = "mot-de-passe-de-test-suffisamment-long"
COMPTE_ALERTE_TEST = "compte_test_dashboard_01"


@pytest_asyncio.fixture
async def pool() -> AsyncIterator[asyncpg.Pool]:
    p = await create_pool()
    try:
        yield p
    finally:
        await close_pool()


@pytest_asyncio.fixture
async def driver() -> AsyncIterator[AsyncDriver]:
    d = await create_driver()
    try:
        yield d
    finally:
        await close_driver()


@pytest_asyncio.fixture
async def tenant_provisionne(pool: asyncpg.Pool) -> AsyncIterator[tuple[UUID, str]]:
    """(tenant_id, schema_name) éphémères, nettoyés après le test."""
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
async def utilisateur_test(
    pool: asyncpg.Pool, tenant_provisionne: tuple[UUID, str]
) -> UserRecord:
    tenant_id, _ = tenant_provisionne
    async with pool.acquire() as connexion:
        return await create_user(
            connexion,
            tenant_id=tenant_id,
            souverain_id=generate_souverain_id(TENANT_CODE_TEST, EMAIL_TEST),
            email=EMAIL_TEST,
            password_hash=hash_password(MOT_DE_PASSE_TEST),
            role="analyst",
        )


@pytest_asyncio.fixture
async def alerte_test(
    pool: asyncpg.Pool, tenant_provisionne: tuple[UUID, str]
) -> None:
    """Une vraie alerte au-dessus du seuil, via le pipeline Brique 4 -> Brique 5.

    compte_pivot (30) + micro_fractionnement (20) = 50 = SEUIL_ALERTE.
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

    # ScoreCompte.detection_ids doit référencer les vrais detection_id
    # générés par enregistrer_detections() (UUID créés côté persistence,
    # pas exposés en retour) — PAS les transaction_id des événements
    # sources. Relecture explicite pour récupérer les identifiants réels.
    async with pool.acquire() as connexion:
        lignes = await connexion.fetch(
            f"SELECT detection_id FROM {schema_name}.detections WHERE compte_pivot = $1",
            COMPTE_ALERTE_TEST,
        )
    detection_ids_reels = [ligne["detection_id"] for ligne in lignes]
    assert len(detection_ids_reels) == 2  # une ligne par DetectionEvent inséré

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


@pytest_asyncio.fixture
async def alertes_table_creee_sans_alerte(
    pool: asyncpg.Pool, tenant_provisionne: tuple[UUID, str]
) -> None:
    """Force la création de {tenant}.alertes SANS y insérer aucune ligne
    (score volontairement sous SEUIL_ALERTE) — distinct du cas où la
    table n'existe pas du tout (TenantSansDonnees, voir lecture.py).

    enregistrer_scores([]) ne crée PAS la table (retour anticipé côté
    Brique 5) — un score réel mais sous le seuil est nécessaire pour
    déclencher _assurer_tables() sans produire de ligne alerte.
    """
    _, schema_name = tenant_provisionne
    maintenant = datetime.now(UTC)

    score = ScoreCompte(
        compte_pivot="compte_jamais_alerte",
        score=10,  # < SEUIL_ALERTE (50) : table créée, aucune ligne insérée
        pattern_types_impliques=["flux_frontalier"],
        detection_ids=[],
        fenetre_debut=maintenant - timedelta(days=7),
        fenetre_fin=maintenant,
        details={"flux_frontalier": 10},
    )
    await enregistrer_scores(pool, schema_name, [score])


@pytest_asyncio.fixture
async def client(
    utilisateur_test: UserRecord,
) -> AsyncIterator[AsyncClient]:
    """Client HTTP authentifié — cookie de session déjà posé.

    Construit le vrai jeton via create_access_token (Brique 2), pas un
    faux jeton — le test passe par le même mécanisme que la vraie
    connexion.

    ⚠️ close_driver() en teardown, découvert nécessaire après un bug
    réel de validation locale (voir avancement.md) : create_driver()
    (Brique 6) est un singleton. Chaque test pytest-asyncio tourne dans
    sa propre boucle asyncio (scope function, par défaut) ; un driver
    Neo4j créé dans la boucle d'un test et jamais fermé fuit vers le
    test suivant, lié à une boucle déjà détruite — échec de session.run()
    sans rapport avec la logique métier testée. Masqué tant qu'un seul
    test de ce fichier touchait Neo4j via `client` ; révélé dès qu'un
    second l'a fait. Même précaution que la fixture `driver` elle-même,
    manquante ici jusqu'à cette correction.
    """
    app = creer_application()
    jwt_settings = get_jwt_settings()
    dashboard_settings = get_dashboard_settings()

    jeton = create_access_token(
        user_id=utilisateur_test.user_id,
        tenant_id=utilisateur_test.tenant_id,
        role=utilisateur_test.role,
        token_version=utilisateur_test.token_version,
        settings=jwt_settings,
    )

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            cookies={dashboard_settings.cookie_name: jeton},
        ) as ac:
            yield ac
    finally:
        await close_driver()
