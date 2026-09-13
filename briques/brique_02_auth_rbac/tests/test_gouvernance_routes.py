"""
Tests HTTP de bout en bout de l'extension gouvernance (Brique 2 V2).

App minimale ne contenant QUE le routeur de gouvernance (pattern
identique à test_api.py, qui n'inclut que auth_router) — Brique 2 doit
rester testable seule, sans dépendre de l'assemblage souverain_app
(Brique 7/8).

httpx.AsyncClient + ASGITransport, jamais TestClient (même précaution
que partout ailleurs dans ce dépôt : TestClient exécute dans un thread
avec sa propre boucle asyncio, incompatible avec un pool asyncpg créé
dans la boucle du test).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID

import asyncpg
import pytest
from brique_01_postgresql.config import PostgresSettings, get_settings
from brique_01_postgresql.connection import close_pool, create_pool
from brique_02_auth_rbac.config import get_jwt_settings
from brique_02_auth_rbac.gouvernance.config import get_gouvernance_cookie_settings
from brique_02_auth_rbac.gouvernance.connection import (
    close_gouvernance_web_pool,
    create_gouvernance_web_pool,
)
from brique_02_auth_rbac.gouvernance.csrf import NOM_COOKIE_CSRF
from brique_02_auth_rbac.gouvernance.routes import construire_routes_gouvernance
from brique_02_auth_rbac.jwt_tokens import create_access_token
from brique_02_auth_rbac.password_hashing import hash_password
from brique_02_auth_rbac.repository import UserRecord, create_user
from brique_02_auth_rbac.souverain_id import generate_souverain_id
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

TENANT_CODE_A = "YC"
TENANT_CODE_B = "YD"
SCHEMA_A = "tenant_test_gouv_routes_a"
SCHEMA_B = "tenant_test_gouv_routes_b"
MOT_DE_PASSE_TEST = "mot-de-passe-de-test-suffisamment-long"


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(construire_routes_gouvernance())
    return app


@pytest.fixture
async def pool_admin_ou_skip() -> AsyncIterator[PostgresSettings]:
    settings = get_settings()
    try:
        await create_pool(settings)
    except ConnectionRefusedError:
        pytest.skip("PostgreSQL non joignable.")
    else:
        yield settings
        await close_pool()


@pytest.fixture
async def pool_web_ou_skip(pool_admin_ou_skip: PostgresSettings) -> AsyncIterator[asyncpg.Pool]:
    try:
        yield await create_gouvernance_web_pool()
    except ConnectionRefusedError:
        pytest.skip(
            "Rôle souverain_gouvernance_web non joignable — "
            "appliquer la migration 0002 de la Brique 2."
        )
    finally:
        await close_gouvernance_web_pool()


async def _nettoyer(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as connexion:
        for schema in (SCHEMA_A, SCHEMA_B):
            await connexion.execute(
                "DELETE FROM shared.users WHERE tenant_id IN "
                "(SELECT tenant_id FROM shared.tenants_registry WHERE schema_name = $1)",
                schema,
            )
            await connexion.execute(
                "DELETE FROM shared.tenants_registry WHERE schema_name = $1", schema
            )


@pytest.fixture
async def deux_tenants_avec_admin(
    pool_admin_ou_skip: PostgresSettings,
) -> AsyncIterator[dict[str, UUID | UserRecord]]:
    pool = await create_pool()
    await _nettoyer(pool)

    async with pool.acquire() as connexion:
        tenant_a_id = await connexion.fetchval(
            "INSERT INTO shared.tenants_registry (tenant_code, country_code, schema_name) "
            "VALUES ($1, 'YC', $2) RETURNING tenant_id",
            TENANT_CODE_A,
            SCHEMA_A,
        )
        tenant_b_id = await connexion.fetchval(
            "INSERT INTO shared.tenants_registry (tenant_code, country_code, schema_name) "
            "VALUES ($1, 'YD', $2) RETURNING tenant_id",
            TENANT_CODE_B,
            SCHEMA_B,
        )
        admin_a = await create_user(
            connexion,
            tenant_id=tenant_a_id,
            souverain_id=generate_souverain_id(TENANT_CODE_A, "admin-routes-a@example.com"),
            email="admin-routes-a@example.com",
            password_hash=hash_password(MOT_DE_PASSE_TEST),
            role="admin",
        )
        analyst_a = await create_user(
            connexion,
            tenant_id=tenant_a_id,
            souverain_id=generate_souverain_id(TENANT_CODE_A, "analyst-routes-a@example.com"),
            email="analyst-routes-a@example.com",
            password_hash=hash_password(MOT_DE_PASSE_TEST),
            role="analyst",
        )
        admin_b = await create_user(
            connexion,
            tenant_id=tenant_b_id,
            souverain_id=generate_souverain_id(TENANT_CODE_B, "admin-routes-b@example.com"),
            email="admin-routes-b@example.com",
            password_hash=hash_password(MOT_DE_PASSE_TEST),
            role="admin",
        )

    try:
        yield {
            "tenant_a_id": tenant_a_id,
            "tenant_b_id": tenant_b_id,
            "admin_a": admin_a,
            "analyst_a": analyst_a,
            "admin_b": admin_b,
        }
    finally:
        await _nettoyer(pool)


async def _client_pour(utilisateur: UserRecord) -> AsyncClient:
    jwt_settings = get_jwt_settings()
    cookie_settings = get_gouvernance_cookie_settings()
    jeton = create_access_token(
        user_id=utilisateur.user_id,
        tenant_id=utilisateur.tenant_id,
        role=utilisateur.role,
        token_version=utilisateur.token_version,
        settings=jwt_settings,
    )
    return AsyncClient(
        transport=ASGITransport(app=_build_app()),
        base_url="http://test",
        cookies={cookie_settings.cookie_name: jeton},
    )


async def test_liste_utilisateurs_accessible_a_l_admin(
    pool_web_ou_skip: asyncpg.Pool,
    deux_tenants_avec_admin: dict,
) -> None:
    admin_a: UserRecord = deux_tenants_avec_admin["admin_a"]
    async with await _client_pour(admin_a) as client:
        reponse = await client.get("/utilisateurs")
    assert reponse.status_code == 200
    assert "admin-routes-a@example.com" in reponse.text
    assert "admin-routes-b@example.com" not in reponse.text  # isolation stricte


async def test_liste_utilisateurs_refusee_a_l_analyst(
    pool_web_ou_skip: asyncpg.Pool,
    deux_tenants_avec_admin: dict,
) -> None:
    analyst_a: UserRecord = deux_tenants_avec_admin["analyst_a"]
    async with await _client_pour(analyst_a) as client:
        reponse = await client.get("/utilisateurs")
    assert reponse.status_code == 403


async def test_creation_utilisateur_avec_csrf_valide(
    pool_web_ou_skip: asyncpg.Pool,
    deux_tenants_avec_admin: dict,
) -> None:
    admin_a: UserRecord = deux_tenants_avec_admin["admin_a"]
    async with await _client_pour(admin_a) as client:
        await client.get("/utilisateurs")
        jeton_csrf = client.cookies.get(NOM_COOKIE_CSRF)
        assert jeton_csrf is not None

        reponse = await client.post(
            "/utilisateurs",
            data={
                "email": "nouveau@example.com",
                "mot_de_passe": MOT_DE_PASSE_TEST,
                "role": "analyst",
                "jeton_csrf": jeton_csrf,
            },
        )
    assert reponse.status_code == 200
    assert "nouveau@example.com" in reponse.text


async def test_creation_utilisateur_refusee_sans_csrf_valide(
    pool_web_ou_skip: asyncpg.Pool,
    deux_tenants_avec_admin: dict,
) -> None:
    admin_a: UserRecord = deux_tenants_avec_admin["admin_a"]
    async with await _client_pour(admin_a) as client:
        await client.get("/utilisateurs")  # pose le cookie CSRF
        reponse = await client.post(
            "/utilisateurs",
            data={
                "email": "intrus@example.com",
                "mot_de_passe": MOT_DE_PASSE_TEST,
                "role": "analyst",
                "jeton_csrf": "jeton-invente",
            },
        )
    assert reponse.status_code == 403


async def test_admin_ne_peut_pas_se_desactiver_lui_meme(
    pool_web_ou_skip: asyncpg.Pool,
    deux_tenants_avec_admin: dict,
) -> None:
    admin_a: UserRecord = deux_tenants_avec_admin["admin_a"]
    async with await _client_pour(admin_a) as client:
        await client.get("/utilisateurs")
        jeton_csrf = client.cookies.get(NOM_COOKIE_CSRF)

        reponse = await client.post(
            f"/utilisateurs/{admin_a.user_id}/desactivation",
            data={"jeton_csrf": jeton_csrf},
        )
    assert reponse.status_code == 403


async def test_admin_ne_peut_pas_agir_hors_de_son_tenant(
    pool_web_ou_skip: asyncpg.Pool,
    deux_tenants_avec_admin: dict,
) -> None:
    """admin_a tente de désactiver admin_b (autre tenant) — refusé."""
    admin_a: UserRecord = deux_tenants_avec_admin["admin_a"]
    admin_b: UserRecord = deux_tenants_avec_admin["admin_b"]

    async with await _client_pour(admin_a) as client:
        await client.get("/utilisateurs")
        jeton_csrf = client.cookies.get(NOM_COOKIE_CSRF)

        reponse = await client.post(
            f"/utilisateurs/{admin_b.user_id}/desactivation",
            data={"jeton_csrf": jeton_csrf},
        )
    assert reponse.status_code == 403
