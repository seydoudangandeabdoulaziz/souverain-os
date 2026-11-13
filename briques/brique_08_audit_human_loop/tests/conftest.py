"""Fixtures B8 utilisant une identité d'audit propre au tenant de test."""

from __future__ import annotations

import json
import os
import secrets
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import asyncpg
import pytest_asyncio
from brique_01_postgresql.connection import close_pool, create_pool
from brique_01_postgresql.tenant_credentials import role_name_for_tenant
from brique_01_postgresql.tenant_provisioning import provision_tenant_schema
from brique_01_postgresql.tenant_roles import provision_tenant_role
from brique_02_auth_rbac.password_hashing import hash_password
from brique_02_auth_rbac.repository import UserRecord, create_user
from brique_02_auth_rbac.souverain_id import generate_souverain_id
from brique_04_detection.modeles import DetectionEvent
from brique_04_detection.persistence import enregistrer_detections
from brique_05_scoring_alertes.modeles import ScoreCompte
from brique_05_scoring_alertes.persistence import enregistrer_scores
from brique_08_audit_human_loop.connection import close_audit_pool, create_audit_pool

TENANT_TEST = "tenant_test_audit"
TENANT_CODE_TEST = "YY"
EMAIL_ANALYST_TEST = "audit-analyst-test@example.com"
EMAIL_AUDITOR_TEST = "audit-auditor-test@example.com"
MOT_DE_PASSE_TEST = "mot-de-passe-de-test-suffisamment-long"
COMPTE_ALERTE_TEST = "compte_test_audit_01"


async def _preparer_alertes_test(
    connexion: asyncpg.Connection, schema_name: str
) -> None:
    """Simule le DDL opérateur de la migration B5 pour les fixtures B8."""
    await connexion.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {schema_name}.alertes (
            alerte_id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL,
            country_code TEXT NOT NULL,
            data_classification TEXT NOT NULL,
            compte_pivot TEXT NOT NULL,
            score INTEGER NOT NULL,
            statut TEXT NOT NULL DEFAULT 'ouverte'
                CHECK (statut IN ('ouverte', 'fermee')),
            pattern_types_impliques TEXT[] NOT NULL,
            detection_ids UUID[] NOT NULL,
            fenetre_debut TIMESTAMPTZ NOT NULL,
            fenetre_fin TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            details JSONB
        )
        """
    )
    await connexion.execute(
        f"CREATE UNIQUE INDEX IF NOT EXISTS idx_{schema_name}_alertes_ouverte_compte "
        f"ON {schema_name}.alertes (compte_pivot) WHERE statut = 'ouverte'"
    )


async def _preparer_role_test(
    connexion: asyncpg.Connection, tenant_id: UUID, schema: str, purpose: str
) -> str:
    """Active le rôle tenant-scoped dans la base de test uniquement."""
    role = await provision_tenant_role(connexion, tenant_id, schema, purpose)
    secret = secrets.token_hex(32)
    alter = await connexion.fetchval(
        "SELECT format('ALTER ROLE %I LOGIN PASSWORD %L', $1::text, $2::text)",
        role,
        secret,
    )
    await connexion.execute(alter)
    raw = os.environ.get("TENANT_DB_CREDENTIALS_JSON", "{}")
    credentials = json.loads(raw)
    credentials.setdefault(str(tenant_id), {})[f"{purpose}_password"] = secret
    os.environ["TENANT_DB_CREDENTIALS_JSON"] = json.dumps(credentials)
    return role


@pytest_asyncio.fixture
async def pool() -> AsyncIterator[asyncpg.Pool]:
    p = await create_pool()
    try:
        yield p
    finally:
        await close_pool()


@pytest_asyncio.fixture
async def pool_audit(
    tenant_provisionne: tuple[UUID, str],
) -> AsyncIterator[asyncpg.Pool]:
    """Pool avec le rôle RESTREINT souverain_brique8_audit — dépend de
    tenant_provisionne pour garantir que les GRANT du tenant de test
    (voir cette fixture) ont déjà eu lieu avant toute connexion.
    """
    p = await create_audit_pool(tenant_provisionne[0])
    try:
        yield p
    finally:
        await close_audit_pool()


@pytest_asyncio.fixture
async def tenant_provisionne(pool: asyncpg.Pool) -> AsyncIterator[tuple[UUID, str]]:
    """(tenant_id, schema_name) éphémères, nettoyés après le test.

    Crée un rôle d'audit tenant-scoped sans accès aux tables métier.
    """
    previous_credentials = os.environ.get("TENANT_DB_CREDENTIALS_JSON")
    async with pool.acquire() as connexion:
        tenant_id: UUID = await connexion.fetchval(
            """
            INSERT INTO shared.tenants_registry
                (tenant_code, country_code, schema_name, data_classification, is_active)
            VALUES ($1, 'NE', $2, 'confidential', true)
            ON CONFLICT (schema_name) DO UPDATE SET is_active = true
            RETURNING tenant_id
            """,
            TENANT_CODE_TEST,
            TENANT_TEST,
        )
        await provision_tenant_schema(connexion, TENANT_TEST)
        data_role = await _preparer_role_test(connexion, tenant_id, TENANT_TEST, "data")
        audit_role = await _preparer_role_test(connexion, tenant_id, TENANT_TEST, "audit")

    try:
        yield tenant_id, TENANT_TEST
    finally:
        async with pool.acquire() as connexion:
            roles = (data_role, audit_role)
            await connexion.execute("DELETE FROM shared.users WHERE tenant_id = $1", tenant_id)
            await connexion.execute(f"DROP SCHEMA IF EXISTS {TENANT_TEST} CASCADE")
            await connexion.execute(
                "DELETE FROM shared.tenants_registry WHERE schema_name = $1", TENANT_TEST
            )
            for role in roles:
                await connexion.execute("DROP OWNED BY " + role)
                await connexion.execute(f"DROP ROLE IF EXISTS {role}")
            if previous_credentials is None:
                os.environ.pop("TENANT_DB_CREDENTIALS_JSON", None)
            else:
                os.environ["TENANT_DB_CREDENTIALS_JSON"] = previous_credentials


@pytest_asyncio.fixture
async def utilisateur_analyst_test(
    pool: asyncpg.Pool, tenant_provisionne: tuple[UUID, str]
) -> UserRecord:
    tenant_id, _ = tenant_provisionne
    async with pool.acquire() as connexion:
        return await create_user(
            connexion,
            tenant_id=tenant_id,
            souverain_id=generate_souverain_id(TENANT_CODE_TEST, EMAIL_ANALYST_TEST),
            email=EMAIL_ANALYST_TEST,
            password_hash=hash_password(MOT_DE_PASSE_TEST),
            role="analyst",
        )


@pytest_asyncio.fixture
async def utilisateur_auditor_test(
    pool: asyncpg.Pool, tenant_provisionne: tuple[UUID, str]
) -> UserRecord:
    tenant_id, _ = tenant_provisionne
    async with pool.acquire() as connexion:
        return await create_user(
            connexion,
            tenant_id=tenant_id,
            souverain_id=generate_souverain_id(TENANT_CODE_TEST, EMAIL_AUDITOR_TEST),
            email=EMAIL_AUDITOR_TEST,
            password_hash=hash_password(MOT_DE_PASSE_TEST),
            role="auditor",
        )


@pytest_asyncio.fixture
async def alerte_test(
    pool: asyncpg.Pool, tenant_provisionne: tuple[UUID, str]
) -> UUID:
    """Une vraie alerte 'ouverte', via le pipeline Brique 4 -> Brique 5.

    compte_pivot (30) + micro_fractionnement (20) = 50 = SEUIL_ALERTE.
    Retourne alerte_id (nécessaire pour cibler la fermeture).
    """
    _, schema_name = tenant_provisionne
    maintenant = datetime.now(UTC)

    async with pool.acquire() as connexion:
        await _preparer_alertes_test(connexion, schema_name)

    evenements = [
        DetectionEvent(
            pattern_type="compte_pivot",
            transaction_ids=[uuid4(), uuid4()],
            fenetre_debut=maintenant - timedelta(minutes=30),
            fenetre_fin=maintenant,
            compte_pivot=COMPTE_ALERTE_TEST,
        ),
        DetectionEvent(
            pattern_type="micro_fractionnement",
            transaction_ids=[uuid4(), uuid4()],
            fenetre_debut=maintenant - timedelta(minutes=30),
            fenetre_fin=maintenant,
            compte_pivot=COMPTE_ALERTE_TEST,
        ),
    ]
    await enregistrer_detections(pool, schema_name, evenements)

    async with pool.acquire() as connexion:
        lignes = await connexion.fetch(
            f"SELECT detection_id FROM {schema_name}.detections WHERE compte_pivot = $1",
            COMPTE_ALERTE_TEST,
        )
    detection_ids_reels = [ligne["detection_id"] for ligne in lignes]
    assert len(detection_ids_reels) == 2

    score = ScoreCompte(
        compte_pivot=COMPTE_ALERTE_TEST,
        score=50,
        pattern_types_impliques=["compte_pivot", "micro_fractionnement"],
        detection_ids=detection_ids_reels,
        fenetre_debut=maintenant - timedelta(days=7),
        fenetre_fin=maintenant,
        details={"compte_pivot": 30, "micro_fractionnement": 20},
    )
    await enregistrer_scores(pool, schema_name, [score])

    # {tenant}.alertes existe désormais réellement. Le privilège est
    # accordé uniquement au rôle d'audit de ce tenant.
    async with pool.acquire() as connexion:
        role = role_name_for_tenant((await connexion.fetchval(
            "SELECT tenant_id FROM shared.tenants_registry WHERE schema_name = $1", schema_name
        )), "audit")
        grant = await connexion.fetchval(
            "SELECT format('GRANT SELECT, UPDATE ON %I.alertes TO %I', $1::text, $2::text)",
            schema_name,
            role,
        )
        await connexion.execute(
            grant
        )

    async with pool.acquire() as connexion:
        alerte_id: UUID = await connexion.fetchval(
            f"SELECT alerte_id FROM {schema_name}.alertes WHERE compte_pivot = $1",
            COMPTE_ALERTE_TEST,
        )
    return alerte_id
