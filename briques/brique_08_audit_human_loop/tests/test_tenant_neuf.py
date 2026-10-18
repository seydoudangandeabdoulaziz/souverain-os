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

import asyncio
import logging
from collections.abc import AsyncIterator
from dataclasses import replace
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
from brique_08_audit_human_loop import cli
from brique_08_audit_human_loop.config import get_audit_db_settings
from brique_08_audit_human_loop.connection import close_audit_pool, create_audit_pool
from brique_08_audit_human_loop.diagnostic import DiagnosticAudit
from brique_08_audit_human_loop.lecture import lire_historique_audit
from brique_08_audit_human_loop.modeles import (
    AlerteNonFermable,
    AuditNonProvisionne,
    MotifFermeture,
    RaisonAudit,
)
from brique_08_audit_human_loop.persistence import fermer_alerte_avec_audit
from httpx import ASGITransport, AsyncClient
from souverain_app.main import creer_application_complete

TENANT_NEUF = "tenant_test_neuf"
TENANT_CODE_NEUF = "YX"
EMAIL_AUDITOR_NEUF = "neuf-auditor-test@example.com"
MOT_DE_PASSE_TEST = "mot-de-passe-de-test-suffisamment-long"
COMPTE_ALERTE_NEUF = "compte_test_neuf_01"
SENTINELLE_COMMENTAIRE = "SENTINELLE-COMMENTAIRE-NE-DOIT-PAS-FUITER"

_DIAG_CONFORME = DiagnosticAudit(
    role_existe=True,
    schema_existe=True,
    audit_log_existe=True,
    alertes_existe=True,
    usage_schema=True,
    audit_log_insert=True,
    audit_log_select=True,
    audit_log_update=False,
    audit_log_delete=False,
    audit_log_truncate=False,
    alertes_select=True,
    alertes_update=True,
)


async def _ne_rien_fermer() -> None:
    """Remplace cli.close_pool dans les tests : la CLI ferme le pool admin
    singleton, que la fixture `pool` (et le nettoyage) utilisent encore."""


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


# ---------------------------------------------------------------------------
# Tests d'acceptation (ADR-005, D2 à D6) : verrou, concurrence, anomalie,
# classement des erreurs, journaux, CLI. Même tenant neuf, même fixtures.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a1_verrou_tenu_donne_un_timeout_sans_rien_modifier(
    pool: asyncpg.Pool, tenant_neuf: UUID
) -> None:
    """Verrou advisory déjà tenu : VERROU_TIMEOUT, rien créé, verrou ré-acquérable après."""
    from brique_08_audit_human_loop.persistence import provisionner_audit

    async with pool.acquire() as autre, autre.transaction():
        await autre.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended($1::text, 0))",
            f"souverain:b8_audit:{TENANT_NEUF}",
        )
        with pytest.raises(AuditNonProvisionne) as info:
            await provisionner_audit(TENANT_NEUF)
    assert info.value.raison is RaisonAudit.VERROU_TIMEOUT

    async with pool.acquire() as connexion:
        audit_log = await connexion.fetchval(
            "SELECT to_regclass($1)::text", f"{TENANT_NEUF}.audit_log"
        )
    assert audit_log is None, "un timeout ne doit rien avoir créé"
    assert await provisionner_audit(TENANT_NEUF), "le verrou doit être libre après le timeout"


@pytest.mark.asyncio
async def test_a2_provisionnements_concurrents_ne_reparent_qu_une_fois(
    tenant_neuf: UUID,
) -> None:
    from brique_08_audit_human_loop.persistence import provisionner_audit

    resultats = await asyncio.gather(*[provisionner_audit(TENANT_NEUF) for _ in range(5)])

    assert sum(1 for r in resultats if r) == 1, "une seule exécution doit réparer"
    assert sum(1 for r in resultats if not r) == 4, "les autres doivent trouver l'état conforme"


@pytest.mark.asyncio
async def test_a3_anomalie_preexistante_est_refusee_sans_rien_reparer(
    pool: asyncpg.Pool, tenant_neuf: UUID
) -> None:
    from brique_08_audit_human_loop.persistence import provisionner_audit

    await provisionner_audit(TENANT_NEUF)
    async with pool.acquire() as connexion:
        await connexion.execute(f"REVOKE USAGE ON SCHEMA {TENANT_NEUF} FROM {_role_b8()}")
        await connexion.execute(f"GRANT DELETE ON {TENANT_NEUF}.audit_log TO {_role_b8()}")

    with pytest.raises(AuditNonProvisionne) as info:
        await provisionner_audit(TENANT_NEUF)
    assert info.value.raison is RaisonAudit.ANOMALIE_PRIVILEGE

    async with pool.acquire() as connexion:
        usage = await connexion.fetchval(
            "SELECT has_schema_privilege($1, $2, 'USAGE')", _role_b8(), TENANT_NEUF
        )
    assert usage is False, "aucune réparation ne doit être appliquée sur une anomalie"


@pytest.mark.asyncio
async def test_a5_tenant_neuf_sans_table_alertes_donne_alerte_non_fermable(
    pool: asyncpg.Pool, pool_audit_neuf: asyncpg.Pool, tenant_neuf: UUID
) -> None:
    """Après réparation de l'audit, l'absence d'`alertes` est un 409, pas une panne."""
    with pytest.raises(AlerteNonFermable):
        await fermer_alerte_avec_audit(
            pool_audit_neuf,
            TENANT_NEUF,
            alerte_id=uuid4(),
            tenant_id=tenant_neuf,
            user_id=uuid4(),
            motif=MotifFermeture.CONFIRME,
            commentaire=None,
        )
    async with pool.acquire() as connexion:
        assert await connexion.fetchval(
            "SELECT to_regclass($1) IS NULL", f"{TENANT_NEUF}.alertes"
        ), "B8 ne doit jamais créer `alertes`"


@pytest.mark.asyncio
async def test_a6_journaux_et_reponse_sans_donnees_sensibles(
    caplog: pytest.LogCaptureFixture,
    pool: asyncpg.Pool,
    pool_audit_neuf: asyncpg.Pool,
    tenant_neuf: UUID,
    client_auditor_neuf: AsyncClient,
) -> None:
    """Valeurs sentinelles : ni identifiants d'alerte, ni e-mail, ni commentaire,
    ni texte brut d'exception dans les journaux de B8."""
    caplog.set_level(logging.DEBUG)
    alerte_id = await _creer_alerte(pool, TENANT_NEUF)

    reponse = await client_auditor_neuf.get(f"/alertes/{alerte_id}/fermeture")  # lecture : 503
    assert reponse.status_code == 503
    await fermer_alerte_avec_audit(  # écriture : réparation puis succès
        pool_audit_neuf,
        TENANT_NEUF,
        alerte_id=alerte_id,
        tenant_id=tenant_neuf,
        user_id=uuid4(),
        motif=MotifFermeture.FAUX_POSITIF,
        commentaire=SENTINELLE_COMMENTAIRE,
    )

    journal_b8 = "\n".join(
        r.getMessage() for r in caplog.records if r.name.startswith("brique_08_audit_human_loop")
    )
    assert "b8." in journal_b8, "des événements B8 devaient être journalisés"
    for interdit in (
        str(alerte_id),
        EMAIL_AUDITOR_NEUF,
        SENTINELLE_COMMENTAIRE,
        MOT_DE_PASSE_TEST,
        "permission denied",
    ):
        assert interdit not in journal_b8, f"fuite dans les journaux : {interdit!r}"
        assert interdit not in reponse.text


@pytest.mark.asyncio
async def test_d1_audit_log_absente_avec_usage_donne_liste_vide(
    pool: asyncpg.Pool, pool_audit_neuf: asyncpg.Pool, tenant_neuf: UUID
) -> None:
    """Seul cas légitime de liste vide : schéma et rôle présents, audit_log absente."""
    from brique_08_audit_human_loop.persistence import provisionner_audit

    await provisionner_audit(TENANT_NEUF)
    async with pool.acquire() as connexion:
        await connexion.execute(f"DROP TABLE {TENANT_NEUF}.audit_log")

    assert await lire_historique_audit(pool_audit_neuf, TENANT_NEUF, uuid4()) == []


@pytest.mark.asyncio
async def test_d2_table_absente_pour_une_autre_cause_n_est_pas_masquee(
    pool: asyncpg.Pool,
    pool_audit_neuf: asyncpg.Pool,
    tenant_neuf: UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Diagnostic simulé « schéma absent » : l'erreur remonte, jamais []."""
    from brique_08_audit_human_loop.persistence import provisionner_audit

    await provisionner_audit(TENANT_NEUF)
    async with pool.acquire() as connexion:
        await connexion.execute(f"DROP TABLE {TENANT_NEUF}.audit_log")

    async def faux_diagnostic(_schema: str) -> DiagnosticAudit:
        return replace(_DIAG_CONFORME, schema_existe=False, audit_log_existe=False)

    monkeypatch.setattr("brique_08_audit_human_loop.lecture.diagnostiquer_audit", faux_diagnostic)
    with pytest.raises(asyncpg.exceptions.UndefinedTableError):
        await lire_historique_audit(pool_audit_neuf, TENANT_NEUF, uuid4())


@pytest.mark.asyncio
async def test_d3_erreur_de_permission_avec_contrat_complet_remonte_brute(
    pool: asyncpg.Pool,
    pool_audit_neuf: asyncpg.Pool,
    tenant_neuf: UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Diagnostic simulé « contrat complet » : la cause est autre, on ne devine pas."""
    from brique_08_audit_human_loop.persistence import provisionner_audit

    await provisionner_audit(TENANT_NEUF)
    async with pool.acquire() as connexion:
        await connexion.execute(f"REVOKE USAGE ON SCHEMA {TENANT_NEUF} FROM {_role_b8()}")

    async def faux_diagnostic(_schema: str) -> DiagnosticAudit:
        return _DIAG_CONFORME

    monkeypatch.setattr("brique_08_audit_human_loop.lecture.diagnostiquer_audit", faux_diagnostic)
    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        await lire_historique_audit(pool_audit_neuf, TENANT_NEUF, uuid4())


@pytest.mark.asyncio
async def test_c1_usage_et_identification_donnent_le_code_2(
    pool: asyncpg.Pool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "close_pool", _ne_rien_fermer)

    assert await cli._executer("Bad-Name", False) == cli.CODE_USAGE
    assert await cli._executer("tenant_inconnu_zzz", False) == cli.CODE_USAGE


@pytest.mark.asyncio
async def test_c2_tenant_desactive_est_refuse_avec_le_code_3(
    pool: asyncpg.Pool, tenant_neuf: UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "close_pool", _ne_rien_fermer)
    async with pool.acquire() as connexion:
        await connexion.execute(
            "UPDATE shared.tenants_registry SET is_active = false WHERE schema_name = $1",
            TENANT_NEUF,
        )

    assert await cli._executer(TENANT_NEUF, False) == cli.CODE_INACTIF

    async with pool.acquire() as connexion:
        audit_log = await connexion.fetchval(
            "SELECT to_regclass($1)::text", f"{TENANT_NEUF}.audit_log"
        )
    assert audit_log is None, "un refus ne doit rien modifier"


@pytest.mark.asyncio
async def test_c3_tenant_actif_est_repare_puis_conforme_avec_le_code_0(
    pool: asyncpg.Pool,
    tenant_neuf: UUID,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "close_pool", _ne_rien_fermer)

    assert await cli._executer(TENANT_NEUF, False) == cli.CODE_OK
    assert f"{TENANT_NEUF} : réparé" in capsys.readouterr().out

    assert await cli._executer(TENANT_NEUF, False) == cli.CODE_OK  # idempotence
    assert f"{TENANT_NEUF} : conforme" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_c4_tous_continue_apres_un_echec_et_retourne_le_code_1(
    pool: asyncpg.Pool,
    tenant_neuf: UUID,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Le premier tenant échoue (simulé) ; TOUS les autres sont quand même traités.
    La fonction réelle est remplacée : les vrais tenants ne sont jamais modifiés."""
    monkeypatch.setattr(cli, "close_pool", _ne_rien_fermer)
    appeles: list[str] = []

    async def faux_provisionner(schema: str) -> list[str]:
        appeles.append(schema)
        if len(appeles) == 1:
            raise AuditNonProvisionne(RaisonAudit.SCHEMA_ABSENT)
        return []

    monkeypatch.setattr(cli, "provisionner_audit", faux_provisionner)
    async with pool.acquire() as connexion:
        nb_actifs = await connexion.fetchval(
            "SELECT count(*) FROM shared.tenants_registry WHERE is_active"
        )
    assert nb_actifs >= 2, "il faut au moins deux tenants actifs pour ce scénario"

    assert await cli._executer(None, True) == cli.CODE_ECHEC

    sortie = capsys.readouterr()
    assert "échec (SCHEMA_ABSENT)" in sortie.err
    assert "1 échec(s)" in sortie.out
    assert len(appeles) == nb_actifs, "un échec ne doit pas interrompre les tenants suivants"


@pytest.mark.asyncio
async def test_c5_tous_ignore_les_tenants_inactifs(
    pool: asyncpg.Pool,
    tenant_neuf: UUID,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "close_pool", _ne_rien_fermer)
    appeles: list[str] = []

    async def faux_provisionner(schema: str) -> list[str]:
        appeles.append(schema)
        return []

    monkeypatch.setattr(cli, "provisionner_audit", faux_provisionner)
    async with pool.acquire() as connexion:
        await connexion.execute(
            "UPDATE shared.tenants_registry SET is_active = false WHERE schema_name = $1",
            TENANT_NEUF,
        )

    assert await cli._executer(None, True) == cli.CODE_OK

    assert f"{TENANT_NEUF} : ignoré (inactif)" in capsys.readouterr().out
    assert TENANT_NEUF not in appeles


class _AnnulerTransaction(Exception):
    """Sert à forcer un ROLLBACK dans un test sans rien laisser derrière soi."""


@pytest.mark.asyncio
async def test_h5_transaction_read_only_rejette_ddl_et_grant_meme_pour_l_admin(
    pool: asyncpg.Pool, tenant_neuf: UUID
) -> None:
    """ADR-005 (H5) : c'est le SERVEUR qui garantit qu'un diagnostic ne répare rien."""
    async with pool.acquire() as connexion:
        for requete in (
            f"GRANT USAGE ON SCHEMA {TENANT_NEUF} TO {_role_b8()}",
            f"CREATE TABLE {TENANT_NEUF}.h5_sonde (i int)",
        ):
            with pytest.raises(asyncpg.exceptions.ReadOnlySQLTransactionError):
                async with connexion.transaction(readonly=True):
                    await connexion.execute(requete)

        usage = await connexion.fetchval(
            "SELECT has_schema_privilege($1, $2, 'USAGE')", _role_b8(), TENANT_NEUF
        )
        sonde = await connexion.fetchval("SELECT to_regclass($1)::text", f"{TENANT_NEUF}.h5_sonde")
    assert usage is False
    assert sonde is None


@pytest.mark.asyncio
async def test_h7_un_grant_non_valide_est_visible_dans_la_meme_transaction(
    pool: asyncpg.Pool, tenant_neuf: UUID
) -> None:
    """ADR-005 (H7) : le contrôle final de `provisionner_audit` repose sur ce comportement."""
    async with pool.acquire() as connexion:
        with pytest.raises(_AnnulerTransaction):
            async with connexion.transaction():
                await connexion.execute(f"GRANT USAGE ON SCHEMA {TENANT_NEUF} TO {_role_b8()}")
                vu = await connexion.fetchval(
                    "SELECT has_schema_privilege($1, $2, 'USAGE')", _role_b8(), TENANT_NEUF
                )
                assert vu is True, "le GRANT non validé doit être visible dans la transaction"
                raise _AnnulerTransaction

        apres = await connexion.fetchval(
            "SELECT has_schema_privilege($1, $2, 'USAGE')", _role_b8(), TENANT_NEUF
        )
    assert apres is False, "le ROLLBACK doit annuler le GRANT"
