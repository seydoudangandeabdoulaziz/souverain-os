"""Tests PostgreSQL P0; ne s'exécutent que contre une base de test dédiée.

La fixture n'applique pas de migration. Préparer explicitement une base
`souverain_isolation_test`, y appliquer 0008, puis y créer les données
`isolation_probe` et les secrets jetables indiqués dans l'environnement.
"""

from __future__ import annotations

import json
import os
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import asyncpg
import pytest
from brique_01_postgresql.tenant_credentials import role_name_for_tenant
from brique_01_postgresql.tenant_roles import provision_tenant_role


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        pytest.skip(f"{name} absent; tests P0 réservés à une base PostgreSQL isolée")
    return value


def _test_dsn() -> str:
    dsn = _required("SOUVERAIN_ISOLATION_TEST_DSN")
    if urlsplit(dsn).path.lstrip("/") != "souverain_isolation_test":
        pytest.fail("Refus d'exécuter le test P0 hors de souverain_isolation_test")
    return dsn


def _tenants() -> tuple[tuple[UUID, str], tuple[UUID, str]]:
    a = (
        UUID(_required("SOUVERAIN_ISOLATION_TENANT_A_ID")),
        _required("SOUVERAIN_ISOLATION_TENANT_A_SCHEMA"),
    )
    b = (
        UUID(_required("SOUVERAIN_ISOLATION_TENANT_B_ID")),
        _required("SOUVERAIN_ISOLATION_TENANT_B_SCHEMA"),
    )
    return a, b


def _password(tenant_id: UUID, purpose: str) -> str:
    credentials = json.loads(_required("TENANT_DB_CREDENTIALS_JSON"))
    key = "data_password" if purpose == "data" else "audit_password"
    password = credentials[str(tenant_id)][key]
    assert len(password) >= 32
    return password


async def _connect(tenant_id: UUID, purpose: str = "data") -> asyncpg.Connection:
    return await asyncpg.connect(
        _test_dsn(),
        user=role_name_for_tenant(tenant_id, purpose),
        password=_password(tenant_id, purpose),
    )


@pytest.mark.asyncio
async def test_role_tenant_lit_uniquement_son_schema_et_ses_lignes() -> None:
    (tenant_a, schema_a), (tenant_b, schema_b) = _tenants()
    conn = await _connect(tenant_a)
    try:
        rows = await conn.fetch(f"SELECT tenant_id, marker FROM {schema_a}.isolation_probe")
        assert rows and all(row["tenant_id"] == tenant_a for row in rows)
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.fetch(f"SELECT * FROM {schema_b}.isolation_probe")

        users = await conn.fetch("SELECT tenant_id FROM shared.users")
        assert users and all(row["tenant_id"] == tenant_a for row in users)

        # Les GUC sont définissables par le client, mais n'interviennent
        # jamais dans les politiques : l'identité de session fait foi.
        await conn.fetchval("SELECT set_config('app.tenant_id', $1, false)", str(tenant_b))
        users_after_guc = await conn.fetch("SELECT tenant_id FROM shared.users")
        assert users_after_guc and all(row["tenant_id"] == tenant_a for row in users_after_guc)

        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.execute(f"SET ROLE {role_name_for_tenant(tenant_b, 'data')}")
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_role_audit_est_tenant_et_ne_peut_pas_modifier_audit_log() -> None:
    (tenant_a, schema_a), (tenant_b, schema_b) = _tenants()
    conn = await _connect(tenant_a, "audit")
    try:
        rows = await conn.fetch(f"SELECT tenant_id FROM {schema_a}.audit_log")
        assert all(row["tenant_id"] == tenant_a for row in rows)
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.fetch(f"SELECT * FROM {schema_b}.audit_log")
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.execute(f"UPDATE {schema_a}.audit_log SET tenant_id = tenant_id")
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.execute(f"DELETE FROM {schema_a}.audit_log")
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_role_de_controle_ne_lit_aucune_donnee_de_tenant() -> None:
    dsn = _required("SOUVERAIN_ISOLATION_CONTROL_DSN")
    if urlsplit(dsn).path.lstrip("/") != "souverain_isolation_test":
        pytest.fail("Refus d'utiliser le rôle de contrôle hors de la base PostgreSQL isolée")
    conn = await asyncpg.connect(dsn)
    _, schema_b = _tenants()[1]
    try:
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.fetch("SELECT * FROM shared.users")
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.fetch(f"SELECT * FROM {schema_b}.isolation_probe")
        # Les métadonnées de routage seules restent visibles au contrôle.
        assert await conn.fetchval("SELECT count(*) FROM shared.tenants_registry") >= 2
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_provisionnement_nettoie_les_acl_et_appartenances_residuelles() -> None:
    """Un rôle homonyme préexistant ne garde aucun accès inter-tenant."""
    (tenant_a, schema_a), (_, schema_b) = _tenants()
    conn = await asyncpg.connect(_test_dsn())
    group_role = f"p0_leak_{tenant_a.hex[:8]}_{uuid4().hex[:8]}"
    try:
        async with conn.transaction():
            await conn.execute(f'CREATE ROLE "{group_role}" NOLOGIN')
            await conn.execute(
                f"GRANT {group_role} TO {role_name_for_tenant(tenant_a, 'data')}"
            )
            await conn.execute(
                f"GRANT USAGE ON SCHEMA {schema_b} "
                f"TO {role_name_for_tenant(tenant_a, 'data')}"
            )

            await provision_tenant_role(conn, tenant_a, schema_a, "data")
            await provision_tenant_role(conn, tenant_a, schema_a, "data")

            role = role_name_for_tenant(tenant_a, "data")
            assert not await conn.fetchval(
                "SELECT has_schema_privilege($1, $2, 'USAGE')", role, schema_b
            )
            assert not await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM pg_auth_members m "
                "JOIN pg_roles member ON member.oid=m.member "
                "WHERE member.rolname=$1)",
                role,
            )
            attributes = await conn.fetchrow(
                "SELECT rolinherit, rolsuper, rolcreatedb, rolcreaterole, rolbypassrls "
                "FROM pg_roles WHERE rolname=$1",
                role,
            )
            assert attributes is not None
            assert all(
                attributes[name] is False
                for name in (
                    "rolinherit",
                    "rolsuper",
                    "rolcreatedb",
                    "rolcreaterole",
                    "rolbypassrls",
                )
            )
    finally:
        await conn.execute(
            f"REVOKE {group_role} FROM {role_name_for_tenant(tenant_a, 'data')}"
        )
        await conn.execute(f'DROP ROLE IF EXISTS "{group_role}"')
        role = role_name_for_tenant(tenant_a, "data")
        password = _password(tenant_a, "data")
        statement = await conn.fetchval(
            "SELECT format('ALTER ROLE %I LOGIN PASSWORD %L', $1::text, $2::text)",
            role,
            password,
        )
        await conn.execute(statement)
        await conn.close()
