"""Provisionne les rôles PostgreSQL tenant après la migration 0008.

À lancer manuellement avec le rôle admin. Le script n'est jamais appelé
par l'application. Les secrets sont gardés dans .env (mode 0600) et ne
sont jamais affichés.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
from pathlib import Path
from uuid import UUID

import asyncpg
from brique_01_postgresql.config import PostgresSettings
from brique_01_postgresql.tenant_roles import provision_tenant_role


def _env_path(explicit_path: Path | None = None) -> Path:
    if explicit_path is not None:
        candidate = explicit_path.expanduser().resolve()
        if not candidate.is_file():
            raise FileNotFoundError("Fichier .env indiqué introuvable")
        return candidate
    for parent in Path(__file__).resolve().parents:
        candidate = parent / ".env"
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError("Fichier .env local introuvable")


def _read_mapping(path: Path) -> tuple[list[str], dict[str, dict[str, str]]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    current = next(
        (
            line.partition("=")[2].strip().strip("'\"")
            for line in lines
            if line.startswith("TENANT_DB_CREDENTIALS_JSON=")
        ),
        "{}",
    )
    mapping = json.loads(current)
    if not isinstance(mapping, dict):
        raise ValueError("TENANT_DB_CREDENTIALS_JSON doit être un objet JSON")
    return lines, mapping


def _write_mapping(
    path: Path, lines: list[str], mapping: dict[str, dict[str, str]]
) -> None:
    value = json.dumps(mapping, sort_keys=True, separators=(",", ":"))
    replacement = "TENANT_DB_CREDENTIALS_JSON='" + value + "'"
    output: list[str] = []
    found = False
    for line in lines:
        if line.startswith("TENANT_DB_CREDENTIALS_JSON="):
            if not found:
                output.append(replacement)
                found = True
        else:
            output.append(line)
    if not found:
        output.extend(
            ["", "# Secrets par UUID tenant; gérer via le provisioning B1.", replacement]
        )
    temp = path.with_name(path.name + ".tenant-roles.tmp")
    temp.write_text("\n".join(output) + "\n", encoding="utf-8")
    os.chmod(temp, 0o600)
    os.replace(temp, path)
    os.chmod(path, 0o600)


async def _execute_formatted(
    connection: asyncpg.Connection, template: str, *values: str
) -> None:
    params = ", ".join(
        f"${index}::text" for index in range(2, len(values) + 2)
    )
    query = f"SELECT format($1, {params})" if params else "SELECT format($1)"
    statement = await connection.fetchval(query, template, *values)
    await connection.execute(statement)


async def _ensure_role(
    connection: asyncpg.Connection, tenant_id: UUID, schema: str, purpose: str
) -> str:
    return await provision_tenant_role(connection, tenant_id, schema, purpose)


async def main(expected_database: str, env_file: Path | None = None) -> None:
    path = _env_path(env_file)
    lines, mapping = _read_mapping(path)
    original = path.read_bytes()
    settings = PostgresSettings(_env_file=path)  # type: ignore[call-arg]
    if settings.db != expected_database:
        raise ValueError(
            "La base configurée ne correspond pas à --expected-database; aucun changement effectué"
        )
    connection = await asyncpg.connect(dsn=settings.dsn)
    provisioned = 0
    try:
        current_database = await connection.fetchval("SELECT current_database()")
        if current_database != expected_database:
            raise ValueError(
                "La base connectée ne correspond pas à --expected-database; "
                "aucun changement effectué"
            )
        async with connection.transaction():
            tenants = await connection.fetch(
                "SELECT tenant_id,schema_name FROM shared.tenants_registry ORDER BY tenant_id"
            )
            for tenant in tenants:
                key = str(tenant["tenant_id"])
                entry = mapping.setdefault(key, {})
                for purpose, key_name in (
                    ("data", "data_password"),
                    ("audit", "audit_password"),
                ):
                    role = await _ensure_role(
                        connection, tenant["tenant_id"], tenant["schema_name"], purpose
                    )
                    password = entry.get(key_name)
                    if not isinstance(password, str) or len(password) < 32:
                        password = secrets.token_hex(32)
                    entry[key_name] = password
                    await _execute_formatted(
                        connection,
                        "ALTER ROLE %I LOGIN PASSWORD %L NOINHERIT NOSUPERUSER "
                        "NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS",
                        role,
                        password,
                    )
                    provisioned += 1
            _write_mapping(path, lines, mapping)
    except Exception:
        if path.read_bytes() != original:
            temp = path.with_name(path.name + ".restore.tmp")
            temp.write_bytes(original)
            os.chmod(temp, 0o600)
            os.replace(temp, path)
        raise
    finally:
        await connection.close()
    print(f"Rôles tenant configurés : {provisioned}; aucun secret affiché.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--expected-database",
        required=True,
        help="Nom exact de la base attendue; vérifié avant tout provisionnement.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        help="Fichier de configuration local; .env à la racine par défaut.",
    )
    arguments = parser.parse_args()
    asyncio.run(main(arguments.expected_database, arguments.env_file))
