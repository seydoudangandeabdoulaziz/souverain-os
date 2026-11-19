"""Fixtures B9 : base PostgreSQL jetable `souverain_pipeline_test` uniquement.

Préparer la base (migrations B1 0001-0009, B2, B3, B4, B5, B8, puis
B9 0001) et exporter SOUVERAIN_PIPELINE_TEST_DSN (rôle propriétaire). Chaque
test reprovisionne les objets B9 et vide les données : aucun état partagé.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from urllib.parse import urlsplit

# Rend les modules de support importables quel que soit le mode d'import de pytest
# (la racine du dépôt impose --import-mode=importlib, qui n'ajoute pas ce dossier).
sys.path.insert(0, str(Path(__file__).resolve().parent))

import asyncpg  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from brique_01_postgresql.connection import close_runtime_pool, close_tenant_pools  # noqa: E402
from brique_01_postgresql.tenant_credentials import role_name_for_tenant  # noqa: E402
from brique_09_api_pipeline.auth import reinitialiser_etat  # noqa: E402
from brique_09_api_pipeline.provisionnement import provisionner_tenant  # noqa: E402
from support_b9 import (  # noqa: E402
    CONTROLE_MDP,
    JWT_SECRET,
    MDP_PIPELINE,
    TENANT_A,
    TENANT_B,
    A,
    B,
)


def _dsn() -> str:
    dsn = os.environ.get("SOUVERAIN_PIPELINE_TEST_DSN")
    if not dsn:
        pytest.skip("SOUVERAIN_PIPELINE_TEST_DSN absent; tests B9 réservés à une base jetable")
    if urlsplit(dsn).path.lstrip("/") != "souverain_pipeline_test":
        pytest.fail("Refus d'exécuter les tests B9 hors de souverain_pipeline_test")
    return dsn


@pytest.fixture
def environnement(monkeypatch: pytest.MonkeyPatch) -> None:
    dsn = urlsplit(_dsn())
    monkeypatch.setenv("APP_POSTGRES_HOST", dsn.hostname or "127.0.0.1")
    monkeypatch.setenv("APP_POSTGRES_PORT", str(dsn.port or 5432))
    monkeypatch.setenv("APP_POSTGRES_DB", "souverain_pipeline_test")
    monkeypatch.setenv("APP_POSTGRES_USER", "souverain_app")
    monkeypatch.setenv("APP_POSTGRES_PASSWORD", CONTROLE_MDP)
    monkeypatch.setenv(
        "TENANT_DB_CREDENTIALS_JSON",
        json.dumps({str(t): {"pipeline_password": p} for t, p in MDP_PIPELINE.items()}),
    )
    monkeypatch.setenv("SOUVERAIN_API_JWT_SECRET", JWT_SECRET)
    monkeypatch.setenv("SOUVERAIN_API_MAX_BODY_BYTES", "60000")
    reinitialiser_etat()


@pytest_asyncio.fixture
async def admin(environnement: None) -> AsyncIterator[asyncpg.Connection]:
    connexion = await asyncpg.connect(_dsn())
    try:
        for tenant in (A, B):
            await provisionner_tenant(connexion, tenant.tenant_id, tenant.schema)
            role = role_name_for_tenant(tenant.tenant_id, "pipeline")
            ordre = await connexion.fetchval(
                "SELECT format('ALTER ROLE %I LOGIN PASSWORD %L', $1::text, $2::text)",
                role,
                MDP_PIPELINE[tenant.tenant_id],
            )
            await connexion.execute(ordre)
            await connexion.execute(
                f"TRUNCATE {tenant.schema}.transactions, {tenant.schema}.ingestion_keys, "
                f"{tenant.schema}.pipeline_cursor, {tenant.schema}.detections, "
                f"{tenant.schema}.alertes"
            )
        await connexion.execute("DELETE FROM shared.api_clients")
        await connexion.execute("DELETE FROM shared.api_client_events")
        await connexion.execute(
            "UPDATE shared.tenants_registry SET is_active = true WHERE tenant_id = ANY($1::uuid[])",
            [TENANT_A, TENANT_B],
        )
        yield connexion
    finally:
        await close_tenant_pools()
        await close_runtime_pool()
        await connexion.close()
