"""Provisionnement idempotent des rôles PostgreSQL propres à un tenant."""

from __future__ import annotations

from uuid import UUID

import asyncpg

from brique_01_postgresql.tenant_credentials import role_name_for_tenant


async def _execute_formatted(
    connection: asyncpg.Connection, template: str, *values: str
) -> None:
    placeholders = ", ".join(
        f"${index}::text" for index in range(2, len(values) + 2)
    )
    query = f"SELECT format($1, {placeholders})" if placeholders else "SELECT format($1)"
    statement = await connection.fetchval(query, template, *values)
    await connection.execute(statement)


async def provision_tenant_role(
    connection: asyncpg.Connection,
    tenant_id: UUID,
    schema: str,
    purpose: str,
) -> str:
    """Crée le mapping et les ACL minimales, sans activer de secret de rôle."""
    if purpose not in {"data", "audit"}:
        raise ValueError("purpose doit valoir 'data' ou 'audit'")
    role = role_name_for_tenant(tenant_id, purpose)
    exists = await connection.fetchval(
        "SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname=$1)", role
    )
    if not exists:
        await _execute_formatted(
            connection,
            "CREATE ROLE %I NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB "
            "NOCREATEROLE NOREPLICATION NOBYPASSRLS",
            role,
        )
    # Ne jamais réutiliser silencieusement un rôle qui possède des objets :
    # son ownership contournerait les REVOKE et pourrait donner un accès
    # transversal impossible à corriger sans transfert explicite.
    owns_objects = await connection.fetchval(
        "SELECT EXISTS ("
        " SELECT 1 FROM pg_class WHERE relowner = (SELECT oid FROM pg_roles WHERE rolname=$1)"
        " UNION ALL"
        " SELECT 1 FROM pg_namespace WHERE nspowner = (SELECT oid FROM pg_roles WHERE rolname=$1)"
        ")",
        role,
    )
    if owns_objects:
        raise RuntimeError(
            f"Le rôle tenant {role} possède déjà des objets; intervention manuelle requise"
        )

    # Le rôle est un login dédié sans héritage. Cela neutralise aussi les
    # attributs d'un rôle homonyme préexistant avant de lui accorder ses ACL.
    await _execute_formatted(
        connection,
        "ALTER ROLE %I NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB "
        "NOCREATEROLE NOREPLICATION NOBYPASSRLS",
        role,
    )
    memberships = await connection.fetch(
        "SELECT granted.rolname FROM pg_auth_members m "
        "JOIN pg_roles granted ON granted.oid=m.roleid "
        "JOIN pg_roles member ON member.oid=m.member "
        "WHERE member.rolname=$1",
        role,
    )
    for membership in memberships:
        await _execute_formatted(
            connection, "REVOKE %I FROM %I", membership["rolname"], role
        )

    # Un rôle réutilisé ne doit garder aucun ACL dans un autre schéma,
    # notamment celui d'un autre tenant. Les droits minimaux sont rétablis
    # plus bas après ce nettoyage.
    schemas = await connection.fetch(
        "SELECT nspname FROM pg_namespace "
        "WHERE nspname !~ '^pg_' AND nspname <> 'information_schema'"
    )
    for namespace in schemas:
        schema_name = namespace["nspname"]
        for object_kind in ("SCHEMA", "TABLES", "SEQUENCES", "FUNCTIONS"):
            if object_kind == "SCHEMA":
                statement = "REVOKE ALL ON SCHEMA %I FROM %I"
            else:
                statement = f"REVOKE ALL PRIVILEGES ON ALL {object_kind} IN SCHEMA %I FROM %I"
            await _execute_formatted(connection, statement, schema_name, role)
    await _execute_formatted(
        connection,
        "REVOKE CREATE ON DATABASE %I FROM %I",
        await connection.fetchval("SELECT current_database()"),
        role,
    )
    await connection.execute(
        "INSERT INTO shared.tenant_login_map(role_name,tenant_id,purpose) "
        "VALUES($1,$2,$3) ON CONFLICT(role_name) DO UPDATE "
        "SET tenant_id=EXCLUDED.tenant_id,purpose=EXCLUDED.purpose",
        role,
        tenant_id,
        purpose,
    )
    database = await connection.fetchval("SELECT current_database()")
    await _execute_formatted(connection, "GRANT CONNECT ON DATABASE %I TO %I", database, role)

    if purpose == "data":
        grants = (
            ("GRANT USAGE,CREATE ON SCHEMA %I TO %I", schema, role),
            ("GRANT SELECT,INSERT,UPDATE ON ALL TABLES IN SCHEMA %I TO %I", schema, role),
            ("GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA %I TO %I", schema, role),
            ("GRANT USAGE ON SCHEMA shared TO %I", role),
            ("GRANT SELECT,INSERT,UPDATE ON shared.users TO %I", role),
            ("GRANT SELECT ON shared.tenants_registry TO %I", role),
            ("GRANT SELECT,INSERT ON shared.gouvernance_audit_log TO %I", role),
            ("GRANT EXECUTE ON FUNCTION shared.current_login_tenant_id() TO %I", role),
        )
        for grant in grants:
            await _execute_formatted(connection, *grant)
        if await connection.fetchval("SELECT to_regclass($1) IS NOT NULL", f"{schema}.audit_log"):
            await _execute_formatted(
                connection, "REVOKE ALL ON TABLE %I.audit_log FROM %I", schema, role
            )
    else:
        audit_grants = (
            ("GRANT USAGE ON SCHEMA %I TO %I", schema, role),
            ("GRANT USAGE ON SCHEMA shared TO %I", role),
            ("GRANT SELECT ON shared.users TO %I", role),
            ("GRANT EXECUTE ON FUNCTION shared.current_login_tenant_id() TO %I", role),
        )
        for grant in audit_grants:
            await _execute_formatted(connection, *grant)
        if await connection.fetchval("SELECT to_regclass($1) IS NOT NULL", f"{schema}.audit_log"):
            await _execute_formatted(
                connection,
                "GRANT SELECT,INSERT ON TABLE %I.audit_log TO %I",
                schema,
                role,
            )
        if await connection.fetchval("SELECT to_regclass($1) IS NOT NULL", f"{schema}.alertes"):
            await _execute_formatted(
                connection, "GRANT SELECT,UPDATE ON TABLE %I.alertes TO %I", schema, role
            )
    return role
