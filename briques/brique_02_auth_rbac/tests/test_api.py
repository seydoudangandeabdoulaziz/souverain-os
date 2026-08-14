"""
Tests d'intégration de la Brique 2 — nécessitent une vraie base
PostgreSQL avec les migrations des Briques 1 ET 2 appliquées.

Pattern identique à la Brique 1 : auto-SKIP (pas d'échec) si la base
n'est pas joignable, pour ne pas casser l'exécution des tests
unitaires dans un environnement sans Docker.
"""

from __future__ import annotations

import uuid

import pytest
from brique_01_postgresql.config import PostgresSettings, get_settings
from brique_01_postgresql.connection import close_pool, create_pool
from brique_02_auth_rbac.api import router as auth_router
from brique_02_auth_rbac.password_hashing import hash_password
from brique_02_auth_rbac.repository import (
    EmailAlreadyExistsError,
    create_user,
    deactivate_user,
    increment_token_version,
)
from brique_02_auth_rbac.souverain_id import generate_souverain_id
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

_TEST_TENANT_CODE = "ZZ"
_TEST_EMAIL = "auth-test@example.com"
_TEST_PASSWORD = "mot-de-passe-de-test-suffisamment-long"


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(auth_router)
    return app


def _build_client() -> AsyncClient:
    """
    Construit un client de test qui exécute l'application ASGI
    directement dans la boucle asyncio courante (celle du test),
    plutôt que dans un thread séparé.

    Pourquoi pas fastapi.testclient.TestClient ? TestClient exécute
    l'app dans un thread dédié avec SA PROPRE boucle asyncio (mécanisme
    "portal"). Le pool asyncpg, lui, est créé et lié à la boucle du
    test. Résultat : dès que l'API tente d'utiliser le pool depuis le
    thread du TestClient, asyncio refuse ("attached to a different
    loop") — pas un bug de l'API elle-même, un problème d'outillage de
    test. httpx.AsyncClient + ASGITransport exécute tout dans la même
    boucle, ce qui élimine le problème à la racine. C'est le pattern
    actuellement recommandé pour tester une application ASGI de
    manière asynchrone.
    """
    transport = ASGITransport(app=_build_app())
    return AsyncClient(transport=transport, base_url="http://testserver")


@pytest.fixture
async def db_settings_or_skip() -> PostgresSettings:
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


@pytest.fixture
async def test_user(db_settings_or_skip: PostgresSettings) -> dict:
    """
    Crée un tenant de test + un utilisateur de test, et nettoie tout
    après le test (idempotent, rejouable sans intervention manuelle).
    """
    pool = await create_pool(db_settings_or_skip)
    async with pool.acquire() as conn:
        # Nettoyage préalable si une exécution précédente a échoué en cours de route.
        await conn.execute("DELETE FROM shared.users WHERE email = $1", _TEST_EMAIL)
        await conn.execute(
            "DELETE FROM shared.tenants_registry WHERE tenant_code = $1", _TEST_TENANT_CODE
        )

        tenant_row = await conn.fetchrow(
            """
            INSERT INTO shared.tenants_registry (tenant_code, country_code, schema_name)
            VALUES ($1, 'ZZ', 'tenant_zz_test')
            RETURNING tenant_id
            """,
            _TEST_TENANT_CODE,
        )
        tenant_id = tenant_row["tenant_id"]

        souverain_id = generate_souverain_id(_TEST_TENANT_CODE, _TEST_EMAIL)
        user = await create_user(
            conn,
            tenant_id=tenant_id,
            souverain_id=souverain_id,
            email=_TEST_EMAIL,
            password_hash=hash_password(_TEST_PASSWORD),
            role="analyst",
        )

        yield {"tenant_id": tenant_id, "user": user}

        await conn.execute("DELETE FROM shared.users WHERE email = $1", _TEST_EMAIL)
        await conn.execute(
            "DELETE FROM shared.tenants_registry WHERE tenant_code = $1", _TEST_TENANT_CODE
        )


async def test_login_with_correct_credentials_returns_token(test_user: dict) -> None:
    async with _build_client() as client:
        response = await client.post(
            "/auth/login", json={"email": _TEST_EMAIL, "password": _TEST_PASSWORD}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str) and len(body["access_token"]) > 0


async def test_login_with_wrong_password_returns_401(test_user: dict) -> None:
    async with _build_client() as client:
        response = await client.post(
            "/auth/login", json={"email": _TEST_EMAIL, "password": "mauvais-mot-de-passe"}
        )

    assert response.status_code == 401


async def test_login_with_unknown_email_returns_401(
    db_settings_or_skip: PostgresSettings,
) -> None:
    async with _build_client() as client:
        response = await client.post(
            "/auth/login",
            json={"email": "inconnu@example.com", "password": "peu-importe"},
        )

    assert response.status_code == 401


async def test_me_endpoint_returns_current_user(test_user: dict) -> None:
    async with _build_client() as client:
        login_response = await client.post(
            "/auth/login", json={"email": _TEST_EMAIL, "password": _TEST_PASSWORD}
        )
        token = login_response.json()["access_token"]

        me_response = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert me_response.status_code == 200
    body = me_response.json()
    assert body["role"] == "analyst"
    assert body["tenant_id"] == str(test_user["tenant_id"])


async def test_me_endpoint_rejects_missing_token() -> None:
    async with _build_client() as client:
        response = await client.get("/auth/me")

    assert response.status_code in (401, 403)  # HTTPBearer renvoie 403 si header absent


async def test_token_revoked_after_password_change_via_token_version(
    test_user: dict, db_settings_or_skip: PostgresSettings
) -> None:
    """
    Vérifie le mécanisme de révocation : un jeton émis avant un
    incrément de token_version doit être rejeté, même signé
    correctement et non expiré.
    """
    async with _build_client() as client:
        login_response = await client.post(
            "/auth/login", json={"email": _TEST_EMAIL, "password": _TEST_PASSWORD}
        )
        token = login_response.json()["access_token"]

        pool = await create_pool(db_settings_or_skip)
        async with pool.acquire() as conn:
            await increment_token_version(conn, test_user["user"].user_id)

        me_response = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert me_response.status_code == 401


async def test_token_rejected_after_deactivation(
    test_user: dict, db_settings_or_skip: PostgresSettings
) -> None:
    async with _build_client() as client:
        login_response = await client.post(
            "/auth/login", json={"email": _TEST_EMAIL, "password": _TEST_PASSWORD}
        )
        token = login_response.json()["access_token"]

        pool = await create_pool(db_settings_or_skip)
        async with pool.acquire() as conn:
            await deactivate_user(conn, test_user["user"].user_id)

        me_response = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert me_response.status_code == 401


async def test_create_user_rejects_duplicate_email(test_user: dict) -> None:
    pool = await create_pool()
    async with pool.acquire() as conn:
        with pytest.raises(EmailAlreadyExistsError):
            await create_user(
                conn,
                tenant_id=test_user["tenant_id"],
                souverain_id=uuid.uuid4(),
                email=_TEST_EMAIL,  # déjà utilisé par test_user
                password_hash=hash_password("autre-mot-de-passe"),
                role="auditor",
            )
