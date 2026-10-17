"""Tests de régression B8 — tenant créé APRÈS la migration, sans GRANT manuel.

Contexte : `create_tenant()` (Brique 1) ne connaît pas la Brique 8. Un tenant
ainsi créé n'a ni `audit_log`, ni aucun privilège pour le rôle restreint
`souverain_brique8_audit` (pas même USAGE sur le schéma). PostgreSQL lève alors
`InsufficientPrivilegeError` (42501), que ni `lecture.py` ni `persistence.py`
n'interceptent : HTTP 500 sur la page de détail d'une alerte.

Les fixtures de `conftest.py` masquent ce défaut (elles accordent USAGE à la
main) : ce fichier a donc ses propres fixtures, qui passent par le VRAI
`create_tenant()` et ne font AUCUN GRANT.

État attendu AVANT le correctif (tous rouges, pour la bonne raison) :
  - R1 : InsufficientPrivilegeError (l'app relève l'exception, pas de 503)
  - R2, R4, R5 : ImportError sur `provisionner_audit` (fonction à créer)
  - R3 : InsufficientPrivilegeError (écriture : aucune réparation tentée)
Le garde-fou de la fixture `tenant_neuf` doit, lui, déjà passer : sinon le
rouge serait dû à une fixture mal posée, pas au défaut.

API supposée par R2/R4/R5 (voir ADR-005 D1, statut Proposed) :
`provisionner_audit(nom_schema_tenant: str) -> list[str]` — liste des éléments
réparés, vide si le schéma était déjà conforme.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import asyncpg
import pytest
import pytest_asyncio
from brique_01_postgresql.connection import close_pool, create_pool
from brique_01_postgresql.gouvernance_cli_connection import (
    close_gouvernance_cli_pool,
    create_gouvernance_cli_pool,
)
from brique_01_postgresql.tenant_governance import create_tenant
from brique_02_auth_rbac.config import get_jwt_settings
from brique_02_auth_rbac.jwt_tokens import create_access_token
from brique_02_auth_rbac.password_hashing import hash_password
from brique_02_auth_rbac.repository import UserRecord, create_user
from brique_02_auth_rbac.souverain_id import generate_souverain_id
from brique_04_detection.modeles import DetectionEvent
from brique_04_detection.persistence import enregistrer_detections
from brique_05_scoring_alertes.modeles import ScoreCompte
from brique_05_scoring_alertes.persistence import enregistrer_scores
from brique_07_dashboard.config import get_dashboard_settings
from brique_08_audit_human_loop.config import get_audit_db_settings
from brique_08_audit_human_loop.connection import close_audit_pool, create_audit_pool
from brique_08_audit_human_loop.lecture import lire_historique_audit
from brique_08_audit_human_loop.modeles import MotifFermeture
from brique_08_audit_human_loop.persistence import fermer_alerte_avec_audit
from httpx import ASGITransport, AsyncClient
from souverain_app.main import creer_application_complete

TENANT_NEUF = "tenant_test_neuf"
TENANT_CODE_NEUF = "YX"
EMAIL_AUDITOR_NEUF = "neuf-auditor-test@example.com"
MOT_DE_PASSE_TEST = "mot-de-passe-de-test-suffisamment-long"
COMPTE_ALERTE_NEUF = "compte_test_neuf_01"


def _role_b8() -> str:
    return get_audit_db_settings().user


async def _nettoyer(pool: asyncpg.Pool) -> None:
    """Supprime le tenant de test, quel que soit son état (idempotent)."""
    async with pool.acquire() as connexion:
        await connexion.execute(
            "DELETE FROM shared.users WHERE tenant_id IN "
            "(SELECT tenant_id FROM shared.tenants_registry WHERE schema_name = $1)",
            TENANT_NEUF,
        )
        await connexion.execute(f"DROP SCHEMA IF EXISTS {TENANT_NEUF} CASCADE")
        await connexion.execute(
            "DELETE FROM shared.tenants_registry WHERE schema_name = $1", TENANT_NEUF
        )


@pytest_asyncio.fixture
async def pool() -> AsyncIterator[asyncpg.Pool]:
    p = await create_pool()
    try:
        yield p
    finally:
        await close_pool()


@pytest_asyncio.fixture
async def tenant_neuf(pool: asyncpg.Pool) -> AsyncIterator[UUID]:
    """Tenant créé par le VRAI `create_tenant()`, sans aucun GRANT manuel.

    Le setup est dans le `try` : si une assertion de garde échoue, le nettoyage
    s'exécute quand même (pas de tenant orphelin dans le registre).
    """
    await _nettoyer(pool)
    pool_cli = await create_gouvernance_cli_pool()
    try:
        async with pool_cli.acquire() as connexion:
            tenant_id = await create_tenant(
                connexion,
                tenant_code=TENANT_CODE_NEUF,
                country_code="NE",
                schema_name=TENANT_NEUF,
                data_classification="confidential",
                acteur_declare="test automatisé (test_tenant_neuf)",
            )

        # Garde-fou : l'état de départ est bien celui d'un tenant neuf.
        async with pool.acquire() as connexion:
            usage = await connexion.fetchval(
                "SELECT has_schema_privilege($1, $2, 'USAGE')", _role_b8(), TENANT_NEUF
            )
            audit_log = await connexion.fetchval(
                "SELECT to_regclass($1)::text", f"{TENANT_NEUF}.audit_log"
            )
        assert usage is False, "garde-fou : le rôle B8 a déjà USAGE, ce n'est pas un tenant neuf"
        assert audit_log is None, "garde-fou : audit_log existe déjà"

        yield tenant_id
    finally:
        await _nettoyer(pool)
        await close_gouvernance_cli_pool()


@pytest_asyncio.fixture
async def pool_audit_neuf(tenant_neuf: UUID) -> AsyncIterator[asyncpg.Pool]:
    p = await create_audit_pool()
    try:
        yield p
    finally:
        await close_audit_pool()


@pytest_asyncio.fixture
async def client_auditor_neuf(pool: asyncpg.Pool, tenant_neuf: UUID) -> AsyncIterator[AsyncClient]:
    """Client HTTP (app assemblée) authentifié en `auditor` sur le tenant neuf."""
    async with pool.acquire() as connexion:
        utilisateur: UserRecord = await create_user(
            connexion,
            tenant_id=tenant_neuf,
            souverain_id=generate_souverain_id(TENANT_CODE_NEUF, EMAIL_AUDITOR_NEUF),
            email=EMAIL_AUDITOR_NEUF,
            password_hash=hash_password(MOT_DE_PASSE_TEST),
            role="auditor",
        )
    jeton = create_access_token(
        user_id=utilisateur.user_id,
        tenant_id=utilisateur.tenant_id,
        role=utilisateur.role,
        token_version=utilisateur.token_version,
        settings=get_jwt_settings(),
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=creer_application_complete()),
            base_url="http://test",
            cookies={get_dashboard_settings().cookie_name: jeton},
        ) as ac:
            yield ac
    finally:
        # Pool dédié B8 = singleton créé par la route ; un pool par boucle asyncio de test.
        await close_audit_pool()


async def _creer_alerte(pool: asyncpg.Pool, schema_name: str) -> UUID:
    """Vraie alerte 'ouverte' via le pipeline B4 -> B5, SANS aucun GRANT B8.

    Contrairement à `alerte_test` (conftest), aucun GRANT sur `alertes` n'est
    fait ici : c'est précisément la situation d'un tenant neuf.
    """
    maintenant = datetime.now(UTC)
    evenements = [
        DetectionEvent(
            pattern_type=pattern,
            transaction_ids=[uuid4(), uuid4()],
            fenetre_debut=maintenant - timedelta(minutes=30),
            fenetre_fin=maintenant,
            compte_pivot=COMPTE_ALERTE_NEUF,
        )
        for pattern in ("compte_pivot", "micro_fractionnement")
    ]
    await enregistrer_detections(pool, schema_name, evenements)

    async with pool.acquire() as connexion:
        lignes = await connexion.fetch(
            f"SELECT detection_id FROM {schema_name}.detections WHERE compte_pivot = $1",
            COMPTE_ALERTE_NEUF,
        )
    detection_ids = [ligne["detection_id"] for ligne in lignes]
    assert len(detection_ids) == 2

    await enregistrer_scores(
        pool,
        schema_name,
        [
            ScoreCompte(
                compte_pivot=COMPTE_ALERTE_NEUF,
                score=50,
                pattern_types_impliques=["compte_pivot", "micro_fractionnement"],
                detection_ids=detection_ids,
                fenetre_debut=maintenant - timedelta(days=7),
                fenetre_fin=maintenant,
                details={"compte_pivot": 30, "micro_fractionnement": 20},
            )
        ],
    )
    async with pool.acquire() as connexion:
        alerte_id: UUID = await connexion.fetchval(
            f"SELECT alerte_id FROM {schema_name}.alertes WHERE compte_pivot = $1",
            COMPTE_ALERTE_NEUF,
        )
    return alerte_id


@pytest.mark.asyncio
async def test_r1_lecture_sur_tenant_non_provisionne_repond_503(
    client_auditor_neuf: AsyncClient,
) -> None:
    """R1 — le GET du fragment ne doit ni lever, ni répondre 500, ni 200 « vide »."""
    reponse = await client_auditor_neuf.get(f"/alertes/{uuid4()}/fermeture")

    assert reponse.status_code == 503
    corps = reponse.text.lower()
    assert "permission" not in corps
    assert TENANT_NEUF not in corps
    assert _role_b8() not in corps


@pytest.mark.asyncio
async def test_r2_provisionner_audit_est_idempotent_et_debloque_la_lecture(
    client_auditor_neuf: AsyncClient,
) -> None:
    """R2 — après provisioning : lecture 200 (historique vide), seconde exécution sans effet."""
    from brique_08_audit_human_loop.persistence import provisionner_audit

    premiere = await provisionner_audit(TENANT_NEUF)
    seconde = await provisionner_audit(TENANT_NEUF)

    assert premiere, "la première exécution devait réparer au moins un élément"
    assert seconde == [], "la seconde exécution doit être sans effet (déjà conforme)"

    reponse = await client_auditor_neuf.get(f"/alertes/{uuid4()}/fermeture")
    assert reponse.status_code == 200
    assert "<form" not in reponse.text  # auditor : historique seul


@pytest.mark.asyncio
async def test_r3_fermeture_reussit_sur_tenant_neuf_sans_grant_manuel(
    pool: asyncpg.Pool, pool_audit_neuf: asyncpg.Pool, tenant_neuf: UUID
) -> None:
    """R3 — `alertes` créée après coup par B5 : la fermeture doit réussir et écrire l'audit."""
    alerte_id = await _creer_alerte(pool, TENANT_NEUF)

    resultat = await fermer_alerte_avec_audit(
        pool_audit_neuf,
        TENANT_NEUF,
        alerte_id=alerte_id,
        tenant_id=tenant_neuf,
        user_id=uuid4(),
        motif=MotifFermeture.FAUX_POSITIF,
        commentaire="régression tenant neuf",
    )
    assert resultat.alerte_id == alerte_id

    async with pool.acquire() as connexion:
        statut = await connexion.fetchval(
            f"SELECT statut FROM {TENANT_NEUF}.alertes WHERE alerte_id = $1", alerte_id
        )
        nb_audit = await connexion.fetchval(
            f"SELECT count(*) FROM {TENANT_NEUF}.audit_log WHERE alerte_id = $1", alerte_id
        )
    assert statut == "fermee"
    assert nb_audit == 1


@pytest.mark.asyncio
async def test_r4_le_provisioning_n_accorde_jamais_update_ni_delete_sur_audit_log(
    pool: asyncpg.Pool, tenant_neuf: UUID
) -> None:
    """R4 — invariant d'immuabilité : INSERT/SELECT seulement, jamais UPDATE/DELETE/TRUNCATE."""
    from brique_08_audit_human_loop.persistence import provisionner_audit

    await provisionner_audit(TENANT_NEUF)

    cible = f"{TENANT_NEUF}.audit_log"
    async with pool.acquire() as connexion:
        for privilege in ("INSERT", "SELECT"):
            assert await connexion.fetchval(
                "SELECT has_table_privilege($1, $2, $3)", _role_b8(), cible, privilege
            ), f"{privilege} devrait être accordé"
        for privilege in ("UPDATE", "DELETE", "TRUNCATE"):
            assert not await connexion.fetchval(
                "SELECT has_table_privilege($1, $2, $3)", _role_b8(), cible, privilege
            ), f"{privilege} ne doit JAMAIS être accordé sur audit_log"


@pytest.mark.asyncio
async def test_r5_une_erreur_de_permission_n_est_jamais_masquee_en_historique_vide(
    pool: asyncpg.Pool, pool_audit_neuf: asyncpg.Pool, tenant_neuf: UUID
) -> None:
    """R5 — USAGE retiré après provisioning : la lecture doit échouer, jamais renvoyer []."""
    from brique_08_audit_human_loop.persistence import provisionner_audit

    await provisionner_audit(TENANT_NEUF)
    async with pool.acquire() as connexion:
        await connexion.execute(f"REVOKE USAGE ON SCHEMA {TENANT_NEUF} FROM {_role_b8()}")

    try:
        resultat = await lire_historique_audit(pool_audit_neuf, TENANT_NEUF, uuid4())
    except Exception as exc:  # noqa: BLE001
        assert isinstance(exc, asyncpg.InsufficientPrivilegeError) or (
            type(exc).__name__ == "AuditNonProvisionne"
        ), f"exception inattendue : {type(exc).__name__}"
    else:
        pytest.fail(f"erreur de permission masquée : la lecture a retourné {resultat!r}")
