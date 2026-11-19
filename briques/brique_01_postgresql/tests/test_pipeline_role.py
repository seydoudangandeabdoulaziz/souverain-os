"""Tests du rôle PostgreSQL `pipeline` (API d'ingestion/scoring).

Deux familles :
- tests unitaires (sans base) : nommage et secrets du but `pipeline`, et
  non-régression de `data` / `audit` ;
- tests PostgreSQL (mêmes variables que test_tenant_isolation.py, base
  `souverain_isolation_test` uniquement, migration 0009 appliquée) : droits
  minimaux, absence de DDL, aucun accès inter-tenant, rôle `data` inchangé.
"""

from __future__ import annotations

import json
import os
import secrets
from collections.abc import AsyncIterator
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import asyncpg
import pytest
import pytest_asyncio
from brique_01_postgresql.tenant_credentials import (
    TenantCredentialSettings,
    get_tenant_role_credentials,
    role_name_for_tenant,
)
from brique_01_postgresql.tenant_roles import provision_tenant_role

# ---------------------------------------------------------------- unitaires


def test_noms_de_roles_par_but() -> None:
    tenant = UUID("12345678-1234-5678-1234-567812345678")
    assert role_name_for_tenant(tenant, "data") == "sov_t_" + tenant.hex
    assert role_name_for_tenant(tenant, "audit") == "sov_a_" + tenant.hex
    assert role_name_for_tenant(tenant, "pipeline") == "sov_p_" + tenant.hex
    # PostgreSQL tronque à 63 caractères : le nom doit tenir.
    assert len(role_name_for_tenant(tenant, "pipeline")) <= 63


@pytest.mark.parametrize("purpose", ["", "admin", "PIPELINE", "pipeline ", "data;"])
def test_but_inconnu_refuse(purpose: str) -> None:
    with pytest.raises(ValueError):
        role_name_for_tenant(uuid4(), purpose)


def test_secret_pipeline_est_lu_sous_sa_propre_cle() -> None:
    tenant = uuid4()
    data_pw, audit_pw, pipe_pw = (secrets.token_hex(32) for _ in range(3))
    settings = TenantCredentialSettings(  # type: ignore[call-arg]
        credentials_json=json.dumps(
            {
                str(tenant): {
                    "data_password": data_pw,
                    "audit_password": audit_pw,
                    "pipeline_password": pipe_pw,
                }
            }
        )
    )
    for purpose, expected in (("data", data_pw), ("audit", audit_pw), ("pipeline", pipe_pw)):
        creds = get_tenant_role_credentials(tenant, purpose, settings=settings)
        assert creds.password.get_secret_value() == expected
        assert creds.username == role_name_for_tenant(tenant, purpose)
        assert expected not in repr(creds)


def test_secret_pipeline_absent_ou_court_refuse() -> None:
    tenant = uuid4()
    sans = TenantCredentialSettings(  # type: ignore[call-arg]
        credentials_json=json.dumps({str(tenant): {"data_password": "x" * 40}})
    )
    with pytest.raises(ValueError):
        get_tenant_role_credentials(tenant, "pipeline", settings=sans)
    court = TenantCredentialSettings(  # type: ignore[call-arg]
        credentials_json=json.dumps({str(tenant): {"pipeline_password": "court"}})
    )
    with pytest.raises(ValueError):
        get_tenant_role_credentials(tenant, "pipeline", settings=court)


# --------------------------------------------------------------- PostgreSQL


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        pytest.skip(f"{name} absent; tests réservés à une base PostgreSQL isolée")
    return value


def _dsn() -> str:
    dsn = _required("SOUVERAIN_ISOLATION_TEST_DSN")
    if urlsplit(dsn).path.lstrip("/") != "souverain_isolation_test":
        pytest.fail("Refus d'exécuter ce test hors de souverain_isolation_test")
    return dsn


def _tenants() -> tuple[tuple[UUID, str], tuple[UUID, str]]:
    return (
        (
            UUID(_required("SOUVERAIN_ISOLATION_TENANT_A_ID")),
            _required("SOUVERAIN_ISOLATION_TENANT_A_SCHEMA"),
        ),
        (
            UUID(_required("SOUVERAIN_ISOLATION_TENANT_B_ID")),
            _required("SOUVERAIN_ISOLATION_TENANT_B_SCHEMA"),
        ),
    )


async def _privileges_data_role(conn: asyncpg.Connection, tenant: UUID, schema: str) -> dict:
    role = role_name_for_tenant(tenant, "data")
    return {
        "usage": await conn.fetchval("SELECT has_schema_privilege($1,$2,'USAGE')", role, schema),
        "create": await conn.fetchval("SELECT has_schema_privilege($1,$2,'CREATE')", role, schema),
        "users_update": await conn.fetchval(
            "SELECT has_table_privilege($1,'shared.users','UPDATE')", role
        ),
        "attrs": tuple(
            await conn.fetchrow(
                "SELECT rolcanlogin, rolinherit, rolsuper, rolbypassrls FROM pg_roles "
                "WHERE rolname=$1",
                role,
            )
        ),
    }


@pytest_asyncio.fixture
async def pipeline_a() -> AsyncIterator[tuple[asyncpg.Connection, str]]:
    """Provisionne `pipeline` pour le tenant A et rend (admin, mot de passe)."""
    (tenant_a, schema_a), (tenant_b, schema_b) = _tenants()
    admin = await asyncpg.connect(_dsn())
    password = secrets.token_hex(32)
    role = role_name_for_tenant(tenant_a, "pipeline")
    try:
        await provision_tenant_role(admin, tenant_a, schema_a, "pipeline")
        # Le rôle pipeline de B existe (NOLOGIN) : le SET ROLE inter-tenant
        # est ainsi refusé pour une vraie raison de privilège.
        await provision_tenant_role(admin, tenant_b, schema_b, "pipeline")
        stmt = await admin.fetchval(
            "SELECT format('ALTER ROLE %I LOGIN PASSWORD %L', $1::text, $2::text)", role, password
        )
        await admin.execute(stmt)
        yield admin, password
    finally:
        stmt = await admin.fetchval(
            "SELECT format('ALTER ROLE %I NOLOGIN PASSWORD NULL', $1::text)", role
        )
        await admin.execute(stmt)
        await admin.close()


async def _connect_pipeline(password: str) -> asyncpg.Connection:
    (tenant_a, _), _ = _tenants()
    return await asyncpg.connect(
        _dsn(), user=role_name_for_tenant(tenant_a, "pipeline"), password=password
    )


class _Rollback(Exception):
    """Annule la transaction de test : le provisionnement ne persiste pas."""


@pytest.mark.asyncio
async def test_provisionnement_pipeline_est_nologin_par_defaut_et_idempotent() -> None:
    (tenant_a, schema_a), _ = _tenants()
    admin = await asyncpg.connect(_dsn())
    role = role_name_for_tenant(tenant_a, "pipeline")
    try:
        with pytest.raises(_Rollback):
            async with admin.transaction():
                await provision_tenant_role(admin, tenant_a, schema_a, "pipeline")
                await provision_tenant_role(admin, tenant_a, schema_a, "pipeline")
                attrs = await admin.fetchrow(
                    "SELECT rolcanlogin, rolinherit, rolsuper, rolcreatedb, rolcreaterole, "
                    "rolreplication, rolbypassrls FROM pg_roles WHERE rolname=$1",
                    role,
                )
                assert attrs is not None
                assert all(value is False for value in attrs.values()), dict(attrs)
                mapping = await admin.fetchrow(
                    "SELECT tenant_id, purpose FROM shared.tenant_login_map WHERE role_name=$1",
                    role,
                )
                assert mapping is not None
                assert mapping["tenant_id"] == tenant_a and mapping["purpose"] == "pipeline"
                raise _Rollback
    finally:
        await admin.close()


@pytest.mark.asyncio
async def test_pipeline_ne_peut_creer_aucun_objet(
    pipeline_a: tuple[asyncpg.Connection, str],
) -> None:
    (_, schema_a), (_, schema_b) = _tenants()
    admin, password = pipeline_a
    (tenant_a, _), _ = _tenants()
    role = role_name_for_tenant(tenant_a, "pipeline")
    assert not await admin.fetchval("SELECT has_schema_privilege($1,$2,'CREATE')", role, schema_a)
    assert not await admin.fetchval("SELECT has_schema_privilege($1,'shared','CREATE')", role)
    assert not await admin.fetchval(
        "SELECT has_database_privilege($1, current_database(), 'CREATE')", role
    )
    conn = await _connect_pipeline(password)
    try:
        for statement in (
            f"CREATE TABLE {schema_a}.pipeline_intrus (id int)",
            f"CREATE TABLE {schema_b}.pipeline_intrus (id int)",
            "CREATE TABLE shared.pipeline_intrus (id int)",
            "CREATE TABLE public.pipeline_intrus (id int)",
            "CREATE SCHEMA pipeline_intrus",
        ):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await conn.execute(statement)
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_pipeline_n_accede_ni_aux_utilisateurs_ni_a_la_gouvernance_ni_a_l_audit(
    pipeline_a: tuple[asyncpg.Connection, str],
) -> None:
    (tenant_a, schema_a), _ = _tenants()
    _, password = pipeline_a
    conn = await _connect_pipeline(password)
    try:
        for statement in (
            "SELECT * FROM shared.users",
            "UPDATE shared.users SET role = role",
            "INSERT INTO shared.users (user_id) VALUES (gen_random_uuid())",
            "SELECT * FROM shared.gouvernance_audit_log",
            "SELECT * FROM shared.tenant_login_map",
            f"SELECT * FROM {schema_a}.audit_log",
        ):
            with pytest.raises((asyncpg.InsufficientPrivilegeError, asyncpg.UndefinedTableError)):
                await conn.execute(statement)
        # Registre : uniquement la ligne de son propre tenant (RLS).
        rows = await conn.fetch("SELECT tenant_id FROM shared.tenants_registry")
        assert rows and {row["tenant_id"] for row in rows} == {tenant_a}
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_pipeline_aucun_acces_inter_tenant_ni_changement_de_role(
    pipeline_a: tuple[asyncpg.Connection, str],
) -> None:
    (tenant_a, _), (tenant_b, schema_b) = _tenants()
    _, password = pipeline_a
    conn = await _connect_pipeline(password)
    try:
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.fetch(f"SELECT * FROM {schema_b}.isolation_probe")
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.fetch(f"SELECT * FROM {schema_b}.transactions")
        # Un GUC forgé ne change pas l'identité de session.
        await conn.fetchval("SELECT set_config('app.tenant_id', $1, false)", str(tenant_b))
        rows = await conn.fetch("SELECT tenant_id FROM shared.tenants_registry")
        assert {row["tenant_id"] for row in rows} == {tenant_a}
        for other in (
            role_name_for_tenant(tenant_a, "data"),
            role_name_for_tenant(tenant_a, "audit"),
            role_name_for_tenant(tenant_b, "pipeline"),
            role_name_for_tenant(tenant_b, "data"),
        ):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await conn.execute(f"SET ROLE {other}")
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_pipeline_droits_limites_a_la_liste_blanche(
    pipeline_a: tuple[asyncpg.Connection, str],
) -> None:
    (tenant_a, schema_a), _ = _tenants()
    admin, password = pipeline_a
    role = role_name_for_tenant(tenant_a, "pipeline")
    attendu = {
        "transactions": {"SELECT", "INSERT"},
        "detections": {"SELECT", "INSERT"},
        "alertes": {"SELECT", "INSERT", "UPDATE"},
        "ingestion_keys": {"SELECT", "INSERT"},
        "pipeline_cursor": {"SELECT", "INSERT", "UPDATE"},
    }
    toutes = ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")
    tables = await admin.fetch(
        "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname=$1 AND c.relkind IN ('r','p')",
        schema_a,
    )
    presentes = {row["relname"] for row in tables}
    for table in presentes:
        droits = {
            p
            for p in toutes
            if await admin.fetchval(
                "SELECT has_table_privilege($1, $2, $3)", role, f"{schema_a}.{table}", p
            )
        }
        assert droits == attendu.get(table, set()), (table, droits)

    conn = await _connect_pipeline(password)
    try:
        for table in presentes & {"transactions", "detections", "alertes"}:
            for statement in (f"DELETE FROM {schema_a}.{table}", f"TRUNCATE {schema_a}.{table}"):
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    await conn.execute(statement)
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_provisionner_pipeline_ne_change_pas_le_role_data(
    pipeline_a: tuple[asyncpg.Connection, str],
) -> None:
    """Garantie P0 : `data` garde exactement ses droits et ses attributs."""
    (tenant_a, schema_a), (tenant_b, schema_b) = _tenants()
    admin, _ = pipeline_a
    avant_a = await _privileges_data_role(admin, tenant_a, schema_a)
    avant_b = await _privileges_data_role(admin, tenant_b, schema_b)
    # Reprovisionner `pipeline` pour A ne doit toucher aucun rôle `data`.
    await provision_tenant_role(admin, tenant_a, schema_a, "pipeline")
    assert await _privileges_data_role(admin, tenant_a, schema_a) == avant_a
    assert await _privileges_data_role(admin, tenant_b, schema_b) == avant_b
    assert avant_a["create"] is True and avant_a["users_update"] is True  # état P0 connu
