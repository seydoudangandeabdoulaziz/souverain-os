"""
Tests de la gouvernance de tenants (Brique 1 V2).

Même discipline que test_connection.py : tests unitaires sans DB,
tests d'intégration SKIPPÉS (pas en échec) si PostgreSQL n'est pas
joignable ou si le rôle souverain_gouvernance_cli n'existe pas encore
(migration 0002 non appliquée).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import asyncpg
import pytest
from brique_01_postgresql.connection import close_pool, create_pool
from brique_01_postgresql.gouvernance_cli_connection import (
    close_gouvernance_cli_pool,
    create_gouvernance_cli_pool,
)
from brique_01_postgresql.tenant_governance import (
    TenantDejaExistant,
    TenantIntrouvable,
    activate_tenant,
    create_tenant,
    deactivate_tenant,
)

TENANT_CODE_TEST = "ZZ"
SCHEMA_TEST = "tenant_test_gouvernance"


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
async def pool_cli_ou_skip(
    pool_admin_ou_skip: asyncpg.Pool,
) -> AsyncIterator[asyncpg.Pool]:
    try:
        pool = await create_gouvernance_cli_pool()
    except ConnectionRefusedError:
        pytest.skip(
            "Rôle souverain_gouvernance_cli non joignable — "
            "appliquer la migration 0002 de la Brique 1."
        )
    else:
        yield pool
        await close_gouvernance_cli_pool()


@pytest.fixture
async def nettoyage_tenant_test(pool_admin_ou_skip: asyncpg.Pool) -> AsyncIterator[None]:
    """Nettoie le tenant de test avant ET après, quel que soit le résultat du test."""

    async def _nettoyer() -> None:
        async with pool_admin_ou_skip.acquire() as connexion:
            await connexion.execute(f"DROP SCHEMA IF EXISTS {SCHEMA_TEST} CASCADE")
            await connexion.execute(
                "DELETE FROM shared.tenants_registry WHERE schema_name = $1", SCHEMA_TEST
            )

    await _nettoyer()
    yield
    await _nettoyer()


async def test_create_tenant_est_atomique_registre_et_schema_physique(
    pool_admin_ou_skip: asyncpg.Pool,
    pool_cli_ou_skip: asyncpg.Pool,
    nettoyage_tenant_test: None,
) -> None:
    async with pool_cli_ou_skip.acquire() as connexion:
        tenant_id = await create_tenant(
            connexion,
            tenant_code=TENANT_CODE_TEST,
            country_code="ZZ",
            schema_name=SCHEMA_TEST,
            data_classification="confidential",
            acteur_declare="test automatisé",
        )

    async with pool_admin_ou_skip.acquire() as connexion:
        ligne = await connexion.fetchrow(
            "SELECT is_active FROM shared.tenants_registry WHERE tenant_id = $1", tenant_id
        )
        assert ligne is not None
        assert ligne["is_active"] is True

        schema_existe = await connexion.fetchval(
            "SELECT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = $1)",
            SCHEMA_TEST,
        )
        assert schema_existe is True

        entree_audit = await connexion.fetchrow(
            """
            SELECT domaine, action, acteur_type, acteur_declare
            FROM shared.gouvernance_audit_log
            WHERE cible_id = $1 AND domaine = 'tenant' AND action = 'tenant_creation'
            """,
            tenant_id,
        )
        assert entree_audit is not None
        assert entree_audit["acteur_type"] == "cli_non_authentifie"
        assert entree_audit["acteur_declare"] == "test automatisé"


async def test_create_tenant_rejette_tenant_code_deja_pris(
    pool_admin_ou_skip: asyncpg.Pool,
    pool_cli_ou_skip: asyncpg.Pool,
    nettoyage_tenant_test: None,
) -> None:
    async with pool_cli_ou_skip.acquire() as connexion:
        await create_tenant(
            connexion,
            tenant_code=TENANT_CODE_TEST,
            country_code="ZZ",
            schema_name=SCHEMA_TEST,
            data_classification="confidential",
            acteur_declare="test automatisé",
        )

        with pytest.raises(TenantDejaExistant):
            await create_tenant(
                connexion,
                tenant_code=TENANT_CODE_TEST,  # collision volontaire
                country_code="ZZ",
                schema_name="tenant_test_gouvernance_bis",
                data_classification="confidential",
                acteur_declare="test automatisé",
            )

    # Vérifie l'absence de schéma orphelin pour la tentative échouée.
    async with pool_admin_ou_skip.acquire() as connexion:
        orphelin = await connexion.fetchval(
            "SELECT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = $1)",
            "tenant_test_gouvernance_bis",
        )
        assert orphelin is False


async def test_deactivate_tenant_ne_supprime_jamais_le_schema_physique(
    pool_admin_ou_skip: asyncpg.Pool,
    pool_cli_ou_skip: asyncpg.Pool,
    nettoyage_tenant_test: None,
) -> None:
    async with pool_cli_ou_skip.acquire() as connexion:
        await create_tenant(
            connexion,
            tenant_code=TENANT_CODE_TEST,
            country_code="ZZ",
            schema_name=SCHEMA_TEST,
            data_classification="confidential",
            acteur_declare="test automatisé",
        )
        await deactivate_tenant(
            connexion, schema_name=SCHEMA_TEST, acteur_declare="test automatisé"
        )

    async with pool_admin_ou_skip.acquire() as connexion:
        is_active = await connexion.fetchval(
            "SELECT is_active FROM shared.tenants_registry WHERE schema_name = $1", SCHEMA_TEST
        )
        assert is_active is False

        schema_existe_toujours = await connexion.fetchval(
            "SELECT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = $1)",
            SCHEMA_TEST,
        )
        assert schema_existe_toujours is True  # jamais supprimé


async def test_activate_tenant_reactive_un_tenant_desactive(
    pool_admin_ou_skip: asyncpg.Pool,
    pool_cli_ou_skip: asyncpg.Pool,
    nettoyage_tenant_test: None,
) -> None:
    async with pool_cli_ou_skip.acquire() as connexion:
        await create_tenant(
            connexion,
            tenant_code=TENANT_CODE_TEST,
            country_code="ZZ",
            schema_name=SCHEMA_TEST,
            data_classification="confidential",
            acteur_declare="test automatisé",
        )
        await deactivate_tenant(
            connexion, schema_name=SCHEMA_TEST, acteur_declare="test automatisé"
        )
        await activate_tenant(
            connexion, schema_name=SCHEMA_TEST, acteur_declare="test automatisé"
        )

    async with pool_admin_ou_skip.acquire() as connexion:
        is_active = await connexion.fetchval(
            "SELECT is_active FROM shared.tenants_registry WHERE schema_name = $1", SCHEMA_TEST
        )
        assert is_active is True


async def test_activate_tenant_leve_tenant_introuvable_si_inexistant(
    pool_cli_ou_skip: asyncpg.Pool,
    nettoyage_tenant_test: None,
) -> None:
    async with pool_cli_ou_skip.acquire() as connexion:
        with pytest.raises(TenantIntrouvable):
            await activate_tenant(
                connexion, schema_name="tenant_qui_n_existe_pas", acteur_declare="test"
            )


async def test_role_gouvernance_cli_ne_peut_pas_modifier_l_audit(
    pool_cli_ou_skip: asyncpg.Pool,
    nettoyage_tenant_test: None,
) -> None:
    """LE test de la protection par privilège réel — même principe que
    la Brique 8 : le rôle souverain_gouvernance_cli ne doit jamais
    pouvoir UPDATE/DELETE shared.gouvernance_audit_log, même en
    contournant tenant_governance.py et en exécutant du SQL directement.
    """
    async with pool_cli_ou_skip.acquire() as connexion:
        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
            await connexion.execute("UPDATE shared.gouvernance_audit_log SET details = NULL")

        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
            await connexion.execute("DELETE FROM shared.gouvernance_audit_log")
