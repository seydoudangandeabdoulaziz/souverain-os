"""
Tests d'intégration du rôle souverain_monitoring (Étape 4b —
Observabilité, migration 0005).

Même discipline que test_tenant_governance.py : tests d'intégration
SKIPPÉS (pas en échec) si PostgreSQL n'est pas joignable ou si le
rôle n'existe pas encore (migration 0005 non appliquée).

Contrairement à souverain_gouvernance_cli/souverain_brique8_audit,
souverain_monitoring n'a AUCUN module de connexion Python dédié en
production : aucun code applicatif de ce projet ne se connecte jamais
sous ce rôle — seul postgres-exporter (binaire Go, hors Python) le
fait. Créer un module `monitoring_connection.py` de production pour
le seul usage de ces tests serait du code mort — le pool est donc
construit directement ici, à usage de test uniquement.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import asyncpg
import pytest
from brique_01_postgresql.config import get_settings
from brique_01_postgresql.connection import close_pool, create_pool


@pytest.fixture
async def pool_admin_ou_skip() -> AsyncIterator[asyncpg.Pool]:
    try:
        pool = await create_pool()
    except ConnectionRefusedError:
        pytest.skip("PostgreSQL non joignable.")
    else:
        yield pool
        await close_pool()


@pytest.fixture
async def pool_monitoring_ou_skip(
    pool_admin_ou_skip: asyncpg.Pool,
) -> AsyncIterator[asyncpg.Pool]:
    pg = get_settings()
    utilisateur = os.environ.get("MONITORING_DB_USER", "souverain_monitoring")
    mot_de_passe = os.environ.get("MONITORING_DB_PASSWORD", "change_me_monitoring")
    dsn = f"postgresql://{utilisateur}:{mot_de_passe}@{pg.host}:{pg.port}/{pg.db}"

    try:
        pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=2)
    except (OSError, asyncpg.PostgresError):
        pytest.skip(
            "Rôle souverain_monitoring non joignable — appliquer la "
            "migration 0005 de la Brique 1 (vérifier aussi que "
            "MONITORING_DB_PASSWORD correspond au mot de passe réel du "
            "rôle en base)."
        )
    else:
        yield pool
        await pool.close()


async def test_role_souverain_monitoring_existe(pool_admin_ou_skip: asyncpg.Pool) -> None:
    async with pool_admin_ou_skip.acquire() as connexion:
        existe = await connexion.fetchval(
            "SELECT 1 FROM pg_roles WHERE rolname = 'souverain_monitoring'"
        )
    assert existe == 1


async def test_role_est_membre_de_pg_monitor(pool_admin_ou_skip: asyncpg.Pool) -> None:
    async with pool_admin_ou_skip.acquire() as connexion:
        membre = await connexion.fetchval(
            "SELECT pg_has_role('souverain_monitoring', 'pg_monitor', 'MEMBER')"
        )
    assert membre is True


async def test_role_n_est_pas_superuser(pool_admin_ou_skip: asyncpg.Pool) -> None:
    """pg_monitor donne un accès de lecture large, jamais un accès
    superuser — vérifié explicitement, pas supposé."""
    async with pool_admin_ou_skip.acquire() as connexion:
        est_superuser = await connexion.fetchval(
            "SELECT rolsuper FROM pg_roles WHERE rolname = 'souverain_monitoring'"
        )
    assert est_superuser is False


async def test_role_peut_se_connecter_a_la_base(
    pool_monitoring_ou_skip: asyncpg.Pool,
) -> None:
    """Vérifie explicitement le privilège CONNECT, plutôt que de
    dépendre implicitement du comportement par défaut de PostgreSQL."""
    async with pool_monitoring_ou_skip.acquire() as connexion:
        resultat = await connexion.fetchval("SELECT 1")
    assert resultat == 1


async def test_role_ne_peut_pas_ecrire(
    pool_monitoring_ou_skip: asyncpg.Pool,
) -> None:
    """Défense en profondeur : pg_monitor est un rôle de lecture par
    définition PostgreSQL, mais on vérifie le comportement réel,
    jamais supposé depuis la documentation seule."""
    async with pool_monitoring_ou_skip.acquire() as connexion:
        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
            await connexion.execute(
                "INSERT INTO shared.tenants_registry "
                "(tenant_code, schema_name, country_code) "
                "VALUES ('ZZ', 'tenant_test_monitoring_refuse', 'NE')"
            )


async def test_role_ne_peut_pas_lire_donnees_tenant(
    pool_monitoring_ou_skip: asyncpg.Pool,
) -> None:
    """pg_monitor ne doit fuiter aucune donnée métier — vérifié contre
    shared.tenants_registry elle-même (déjà présente, aucun besoin de
    provisionner un tenant de test pour ce cas précis)."""
    async with pool_monitoring_ou_skip.acquire() as connexion:
        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
            await connexion.fetch("SELECT * FROM shared.tenants_registry")
