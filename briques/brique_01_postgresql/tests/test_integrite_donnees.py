"""
Tests de la protection d'intégrité des données métier (Brique 1,
Étape 2 — Event Trigger PostgreSQL).

Même discipline que test_tenant_governance.py : SKIP (pas d'échec) si
PostgreSQL n'est pas joignable ou si les migrations 0003/0004 n'ont
pas été appliquées.

Certains points de la conception validée (résilience search_path face
à une injection réelle, comportement exact en cas d'erreur interne au
handler) sont documentés ici mais mieux vérifiés manuellement sur la
machine réelle — voir le LISEZ_MOI du delta pour la procédure engagée
à la main, plutôt qu'un harnais de test artificiellement complexe pour
un scénario difficile à simuler proprement.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import asyncpg
import pytest
from brique_01_postgresql.connection import close_pool, create_pool

TENANT_CODE_TEST = "YT"
SCHEMA_TEST = "tenant_test_integrite"
SCHEMA_NON_TENANT = "public"  # existe toujours, jamais dans tenants_registry


@pytest.fixture
async def pool_ou_skip() -> AsyncIterator[asyncpg.Pool]:
    try:
        pool = await create_pool()
    except ConnectionRefusedError:
        pytest.skip("PostgreSQL non joignable.")
    else:
        yield pool
        await close_pool()


async def _event_trigger_existe(pool: asyncpg.Pool) -> bool:
    async with pool.acquire() as connexion:
        return bool(
            await connexion.fetchval(
                "SELECT EXISTS (SELECT 1 FROM pg_event_trigger "
                "WHERE evtname = 'trg_event_integrite_donnees')"
            )
        )


@pytest.fixture
async def migrations_appliquees_ou_skip(pool_ou_skip: asyncpg.Pool) -> None:
    if not await _event_trigger_existe(pool_ou_skip):
        pytest.skip(
            "Migrations 0003/0004 (Étape 2 — intégrité) non appliquées — "
            "l'event trigger trg_event_integrite_donnees n'existe pas."
        )


async def _nettoyer_tenant_test(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as connexion:
        await connexion.execute(f"DROP SCHEMA IF EXISTS {SCHEMA_TEST} CASCADE")
        await connexion.execute(
            "DELETE FROM shared.tenants_registry WHERE schema_name = $1", SCHEMA_TEST
        )


@pytest.fixture
async def tenant_test_provisionne(
    pool_ou_skip: asyncpg.Pool, migrations_appliquees_ou_skip: None
) -> AsyncIterator[UUID]:
    """Tenant minimal, provisionné SANS passer par create_tenant() (Brique
    1 V2) — juste le strict nécessaire (schéma + enregistrement) pour
    isoler ce test de la gouvernance de tenants, déjà testée ailleurs."""
    await _nettoyer_tenant_test(pool_ou_skip)

    async with pool_ou_skip.acquire() as connexion:
        tenant_id = await connexion.fetchval(
            "INSERT INTO shared.tenants_registry (tenant_code, country_code, schema_name) "
            "VALUES ($1, 'YT', $2) RETURNING tenant_id",
            TENANT_CODE_TEST,
            SCHEMA_TEST,
        )
        await connexion.execute(f"CREATE SCHEMA {SCHEMA_TEST}")

    try:
        yield tenant_id
    finally:
        await _nettoyer_tenant_test(pool_ou_skip)


async def test_un_role_non_superutilisateur_ne_peut_pas_toucher_l_event_trigger(
    pool_ou_skip: asyncpg.Pool, migrations_appliquees_ou_skip: None
) -> None:
    """Test de privilège réel : créer/modifier/supprimer un event trigger
    exige un superutilisateur — souverain_brique8_audit (restreint,
    déjà existant) ne l'est pas."""
    async with pool_ou_skip.acquire() as connexion:
        pg = await connexion.fetchrow(
            "SELECT rolsuper FROM pg_roles WHERE rolname = 'souverain_brique8_audit'"
        )
    if pg is None:
        pytest.skip("Rôle souverain_brique8_audit absent — Brique 8 non provisionnée ici.")
    assert pg["rolsuper"] is False  # confirme que ce rôle NE PEUT PAS créer d'event trigger


async def test_creation_table_alertes_attache_automatiquement_le_trigger(
    pool_ou_skip: asyncpg.Pool, tenant_test_provisionne: UUID
) -> None:
    """LE test central : Brique 1 ne crée jamais alertes elle-même —
    on simule ici le CREATE TABLE IF NOT EXISTS que Brique 5 exécute
    réellement (même DDL minimal, sans dupliquer sa logique complète),
    et on vérifie que l'event trigger a attaché la protection tout seul."""
    async with pool_ou_skip.acquire() as connexion:
        await connexion.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA_TEST}.alertes (
                alerte_id UUID PRIMARY KEY,
                compte_pivot TEXT NOT NULL,
                statut TEXT NOT NULL DEFAULT 'ouverte'
            )
            """
        )

        trigger_attache = await connexion.fetchval(
            "SELECT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_integrite_alertes' "
            "AND tgrelid = $1::regclass)",
            f"{SCHEMA_TEST}.alertes",
        )
        assert trigger_attache is True

        table_log_existe = await connexion.fetchval(
            "SELECT to_regclass($1) IS NOT NULL", f"{SCHEMA_TEST}.integrite_donnees_log"
        )
        assert table_log_existe is True


async def test_modification_directe_est_journalisee(
    pool_ou_skip: asyncpg.Pool, tenant_test_provisionne: UUID
) -> None:
    async with pool_ou_skip.acquire() as connexion:
        await connexion.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA_TEST}.alertes (
                alerte_id UUID PRIMARY KEY,
                compte_pivot TEXT NOT NULL,
                statut TEXT NOT NULL DEFAULT 'ouverte'
            )
            """
        )

        alerte_id = uuid4()
        await connexion.execute(
            f"INSERT INTO {SCHEMA_TEST}.alertes (alerte_id, compte_pivot) VALUES ($1, 'test')",
            alerte_id,
        )
        # INSERT ne doit JAMAIS être journalisé (détection UPDATE/DELETE
        # uniquement, décision verrouillée) :
        compte_apres_insert = await connexion.fetchval(
            f"SELECT count(*) FROM {SCHEMA_TEST}.integrite_donnees_log"
        )
        assert compte_apres_insert == 0

        # Modification directe, hors de tout code applicatif connu :
        await connexion.execute(
            f"UPDATE {SCHEMA_TEST}.alertes SET statut = 'fermee' WHERE alerte_id = $1",
            alerte_id,
        )

        entree = await connexion.fetchrow(
            f"SELECT * FROM {SCHEMA_TEST}.integrite_donnees_log WHERE ligne_id = $1",
            str(alerte_id),
        )
        assert entree is not None
        assert entree["operation"] == "UPDATE"
        # JSONB non décodé automatiquement par asyncpg (aucun codec
        # enregistré sur ce pool) — même piège déjà documenté et
        # corrigé dans brique_07_dashboard.lecture, reproduit ici par
        # erreur dans le test lui-même (pas dans le mécanisme SQL,
        # confirmé par les deux assertions précédentes qui passent).
        donnees_avant = json.loads(entree["donnees_avant"])
        donnees_apres = json.loads(entree["donnees_apres"])
        assert donnees_avant["statut"] == "ouverte"
        assert donnees_apres["statut"] == "fermee"
        assert entree["role_postgresql"] == "souverain_admin"


async def test_table_hors_perimetre_n_est_jamais_instrumentee(
    pool_ou_skip: asyncpg.Pool, tenant_test_provisionne: UUID
) -> None:
    """Une table nommée 'alertes' hors d'un schéma tenant enregistré ne
    doit recevoir AUCUNE protection — confirme le filtrage strict."""
    nom_table_hors_perimetre = f"alertes_hors_perimetre_{uuid4().hex[:8]}"
    async with pool_ou_skip.acquire() as connexion:
        try:
            await connexion.execute(
                f"CREATE TABLE public.{nom_table_hors_perimetre} (id UUID PRIMARY KEY)"
            )
            trigger_attache = await connexion.fetchval(
                "SELECT EXISTS (SELECT 1 FROM pg_trigger "
                "WHERE tgname = 'trg_integrite_alertes' AND tgrelid = $1::regclass)",
                f"public.{nom_table_hors_perimetre}",
            )
            assert trigger_attache is False
        finally:
            await connexion.execute(f"DROP TABLE IF EXISTS public.{nom_table_hors_perimetre}")


async def test_reexecution_create_table_if_not_exists_est_sans_effet(
    pool_ou_skip: asyncpg.Pool, tenant_test_provisionne: UUID
) -> None:
    """Idempotence : ré-exécuter CREATE TABLE IF NOT EXISTS (comme le
    fait Brique 5 à chaque cycle) ne doit jamais dupliquer le trigger
    ni lever d'erreur."""
    ddl = f"""
        CREATE TABLE IF NOT EXISTS {SCHEMA_TEST}.detections (
            detection_id UUID PRIMARY KEY,
            pattern_type TEXT NOT NULL
        )
    """
    async with pool_ou_skip.acquire() as connexion:
        await connexion.execute(ddl)
        await connexion.execute(ddl)  # rejoué, table déjà existante cette fois

        nb_triggers = await connexion.fetchval(
            "SELECT count(*) FROM pg_trigger WHERE tgname = 'trg_integrite_detections' "
            "AND tgrelid = $1::regclass",
            f"{SCHEMA_TEST}.detections",
        )
        assert nb_triggers == 1  # jamais dupliqué


async def test_rattrapage_ne_plante_pas_si_tables_absentes(
    pool_ou_skip: asyncpg.Pool, tenant_test_provisionne: UUID
) -> None:
    """Rejoue EXACTEMENT la logique de rattrapage de la migration 0004
    (vérifier l'existence via to_regclass AVANT d'appeler
    assurer_protection_integrite) sur un tenant qui n'a NI alertes NI
    detections (cas réel de tenant_sn_test au moment de la migration).

    Point important, vérifié ici plutôt que simplement affirmé :
    assurer_protection_integrite() elle-même N'EST PAS protégée contre
    une table cible absente — CREATE TRIGGER ... ON une table qui
    n'existe pas lève une vraie erreur PostgreSQL. C'est à l'appelant
    (la boucle de rattrapage, ou l'event trigger qui ne l'invoque
    qu'après un CREATE TABLE réel) de garantir que la table existe
    avant d'appeler cette fonction — pas à la fonction elle-même de
    s'en protéger silencieusement.
    """
    async with pool_ou_skip.acquire() as connexion:
        # Le motif réel de la migration 0004 : vérifier avant d'appeler.
        existe = await connexion.fetchval(
            "SELECT to_regclass($1) IS NOT NULL", f"{SCHEMA_TEST}.alertes"
        )
        assert existe is False  # confirmé : la table n'existe pas ici

        if existe:
            await connexion.execute(
                "SELECT shared.assurer_protection_integrite($1, 'alertes')", SCHEMA_TEST
            )
        # Rien appelé — comportement voulu, aucune exception, la
        # protection sera posée automatiquement par l'event trigger
        # dès la première vraie création de cette table par Brique 5.

    # Contre-preuve explicite : appeler SANS la vérification préalable
    # lève bien une erreur — confirme que la garantie vient de
    # l'appelant, pas d'une protection interne à la fonction.
    async with pool_ou_skip.acquire() as connexion:
        with pytest.raises(asyncpg.PostgresError):
            await connexion.execute(
                "SELECT shared.assurer_protection_integrite($1, 'alertes')", SCHEMA_TEST
            )
