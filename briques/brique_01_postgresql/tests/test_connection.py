"""
Tests de la Brique 1.

Deux catégories, clairement séparées :

1. Tests UNITAIRES — ne nécessitent aucune base de données. Ils
   valident la logique pure : validation des noms de schéma, rendu
   du template SQL, parsing de la configuration.

2. Tests d'INTÉGRATION — nécessitent une vraie instance PostgreSQL
   démarrée (docker compose --profile postgres up -d). S'ils ne
   trouvent pas de base joignable, ils sont automatiquement SKIPPÉS
   (pas EN ÉCHEC) — car l'absence de Docker dans un environnement
   donné n'est pas un bug du code.
"""

from __future__ import annotations

import pytest
from brique_01_postgresql.config import PostgresSettings, get_settings
from brique_01_postgresql.connection import close_pool, create_pool
from brique_01_postgresql.healthcheck_db import run_db_healthcheck
from brique_01_postgresql.tenant_provisioning import (
    InvalidSchemaNameError,
    provision_tenant_schema,
    render_tenant_schema_sql,
    validate_schema_name,
)

# ============================================================
# Tests UNITAIRES — aucune base de données requise
# ============================================================


def test_validate_schema_name_accepts_valid_names() -> None:
    assert validate_schema_name("tenant_ne") == "tenant_ne"
    assert validate_schema_name("tenant_sn") == "tenant_sn"
    assert validate_schema_name("t123") == "t123"


@pytest.mark.parametrize(
    "invalid_name",
    [
        "",
        "Tenant_NE",  # majuscules interdites
        "1tenant",  # doit commencer par une lettre
        "tenant-ne",  # tiret interdit
        "tenant ne",  # espace interdit
        "tenant_ne; DROP SCHEMA shared CASCADE;",  # tentative d'injection SQL
        "ab",  # trop court
    ],
)
def test_validate_schema_name_rejects_invalid_names(invalid_name: str) -> None:
    with pytest.raises(InvalidSchemaNameError):
        validate_schema_name(invalid_name)


def test_render_tenant_schema_sql_injects_schema_name() -> None:
    sql = render_tenant_schema_sql("tenant_ne")
    assert "CREATE SCHEMA IF NOT EXISTS tenant_ne;" in sql
    assert "tenant_ne.transactions" in sql
    assert "{schema_name}" not in sql  # le placeholder doit être entièrement remplacé


def test_render_tenant_schema_sql_rejects_unsafe_name() -> None:
    with pytest.raises(InvalidSchemaNameError):
        render_tenant_schema_sql("tenant_ne; DROP TABLE shared.tenants_registry;")


def test_settings_defaults_are_sane() -> None:
    settings = PostgresSettings(_env_file=None)  # ignore le .env local pour ce test
    assert settings.port == 5432
    assert settings.pool_min_size <= settings.pool_max_size


def test_settings_dsn_format() -> None:
    settings = PostgresSettings(
        _env_file=None,
        host="testhost",
        port=5433,
        db="testdb",
        user="testuser",
        password="testpass",
    )
    assert settings.dsn == "postgresql://testuser:testpass@testhost:5433/testdb"


def test_get_settings_returns_postgres_settings_instance() -> None:
    assert isinstance(get_settings(), PostgresSettings)


# ============================================================
# Tests d'INTÉGRATION — nécessitent une vraie base PostgreSQL
# ============================================================


@pytest.fixture
async def db_settings_or_skip() -> PostgresSettings:
    """
    Fournit la configuration DB, ou SKIP le test si aucune base
    n'est joignable (au lieu de le faire échouer).
    """
    settings = get_settings()
    try:
        await create_pool(settings)
    except ConnectionRefusedError:
        pytest.skip(
            "PostgreSQL non joignable — lancer "
            "'docker compose --profile postgres up -d' pour exécuter ce test."
        )
    else:
        yield settings
        await close_pool()


async def test_db_healthcheck_reports_healthy_when_migrated(
    db_settings_or_skip: PostgresSettings,
) -> None:
    """
    Suppose que la migration 0001 a déjà été appliquée manuellement
    (voir README.md, section 'Appliquer les migrations').
    """
    report = await run_db_healthcheck(db_settings_or_skip)
    assert report.all_ok, [r.detail for r in report.results if not r.ok]


async def test_provision_tenant_schema_is_idempotent(
    db_settings_or_skip: PostgresSettings,
) -> None:
    """Provisionner deux fois le même tenant ne doit jamais lever d'erreur."""
    pool = await create_pool(db_settings_or_skip)
    async with pool.acquire() as conn:
        await provision_tenant_schema(conn, "tenant_test")
        await provision_tenant_schema(conn, "tenant_test")  # rejouable sans erreur

        exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'tenant_test' AND table_name = 'transactions'
            )
            """
        )
        assert exists is True

        # Nettoyage pour ne pas polluer les exécutions suivantes du test.
        await conn.execute("DROP SCHEMA IF EXISTS tenant_test CASCADE")
