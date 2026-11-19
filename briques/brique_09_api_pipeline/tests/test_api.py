"""Tests HTTP de l'API pipeline : identité technique, portées, isolation, journaux."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator, AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import asyncpg
import httpx
import jwt
import pytest
import pytest_asyncio
from brique_01_postgresql.connection import create_tenant_pipeline_pool
from brique_09_api_pipeline.identites import creer_client, renouveler_secret, revoquer_client
from brique_09_api_pipeline.routes import construire_routes_pipeline
from fastapi import FastAPI
from support_b9 import JWT_SECRET, A, B


@pytest_asyncio.fixture
async def http(admin: asyncpg.Connection) -> AsyncIterator[httpx.AsyncClient]:
    app = FastAPI()
    app.include_router(construire_routes_pipeline())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


def _tx(i: int, **surcharges: object) -> dict[str, object]:
    base: dict[str, object] = {
        "external_id": f"ext-{i}",
        "sender_account": f"cpt_{i}",
        "receiver_account": f"cpt_{i + 5000}",
        "amount": "2500.00",
        "currency": "XOF",
        "channel": "orange_money",
        "occurred_at": "2026-03-01T10:00:00+00:00",
    }
    base.update(surcharges)
    return base


async def _jeton(
    http: httpx.AsyncClient, tenant_code: str, client_id: UUID | str, secret: str
) -> httpx.Response:
    return await http.post(
        "/api/v1/auth/token",
        json={"tenant_code": tenant_code, "client_id": str(client_id), "client_secret": secret},
    )


async def _client(
    admin: asyncpg.Connection,
    tenant: object = A,
    scopes: list[str] | None = None,
    source: str = "feed_a",
) -> tuple[UUID, str]:
    return await creer_client(
        admin,
        tenant.code,
        source,
        scopes or ["ingest", "cycle"],
        "test",  # type: ignore[attr-defined]
    )


async def _entetes(
    http: httpx.AsyncClient, tenant_code: str, cid: UUID, secret: str
) -> dict[str, str]:
    reponse = await _jeton(http, tenant_code, cid, secret)
    assert reponse.status_code == 200, reponse.text
    return {"Authorization": f"Bearer {reponse.json()['access_token']}"}


# ------------------------------------------------------------- flux nominal
async def test_flux_complet_jeton_ingestion_cycle(
    http: httpx.AsyncClient, admin: asyncpg.Connection
) -> None:
    cid, secret = await _client(admin)
    entetes = await _entetes(http, A.code, cid, secret)
    lot = {"transactions": [_tx(i) for i in range(30)]}
    r = await http.post("/api/v1/transactions", json=lot, headers=entetes)
    assert r.status_code == 200 and r.json() == {
        "recues": 30,
        "inserees": 30,
        "doublons_ignores": 0,
    }
    rejeu = await http.post("/api/v1/transactions", json=lot, headers=entetes)
    assert rejeu.json()["inserees"] == 0 and rejeu.json()["doublons_ignores"] == 30
    c = await http.post("/api/v1/pipeline/cycle", headers=entetes)
    assert c.status_code == 200 and c.json()["nouvelles_transactions"] == 30
    source = await admin.fetchval(f"SELECT DISTINCT source FROM {A.schema}.ingestion_keys")
    assert source == "feed_a"  # la source vient de l'identité, jamais du corps
    assert await admin.fetchval(f"SELECT count(*) FROM {B.schema}.transactions") == 0


async def test_conflit_renvoie_409_explicite(
    http: httpx.AsyncClient, admin: asyncpg.Connection
) -> None:
    cid, secret = await _client(admin)
    entetes = await _entetes(http, A.code, cid, secret)
    await http.post("/api/v1/transactions", json={"transactions": [_tx(1)]}, headers=entetes)
    r = await http.post(
        "/api/v1/transactions",
        json={"transactions": [_tx(1, amount="1.00"), _tx(2)]},
        headers=entetes,
    )
    assert r.status_code == 409
    assert r.json()["detail"] == {"code": "conflit_external_id", "external_ids": ["ext-1"]}
    assert await admin.fetchval(f"SELECT count(*) FROM {A.schema}.transactions") == 1


# ---------------------------------------------------------- authentification
async def test_echecs_indistinguables_et_limitation(
    http: httpx.AsyncClient, admin: asyncpg.Connection
) -> None:
    cid, secret = await _client(admin)
    mauvais = await _jeton(http, A.code, cid, "faux" * 10)
    inconnu = await _jeton(http, A.code, uuid4(), secret)
    tenant_inconnu = await _jeton(http, "ZZ", cid, secret)
    pas_uuid = await _jeton(http, A.code, "pas-un-uuid", secret)
    autre_tenant = await _jeton(http, B.code, cid, secret)
    for r in (mauvais, inconnu, tenant_inconnu, pas_uuid, autre_tenant):
        assert r.status_code == 401
        assert r.json() == {"detail": {"code": "identifiants_invalides"}}
    # 5 échecs du même couple (client, adresse) : verrouillage, même avec le bon secret.
    for _ in range(5):
        await _jeton(http, A.code, cid, "faux" * 10)
    assert (await _jeton(http, A.code, cid, secret)).status_code == 429


async def test_sans_jeton_ou_jeton_invalide(http: httpx.AsyncClient) -> None:
    assert (await http.post("/api/v1/pipeline/cycle")).status_code == 401
    r = await http.post("/api/v1/pipeline/cycle", headers={"Authorization": "Bearer nimporte.quoi"})
    assert r.status_code == 401 and r.headers["www-authenticate"] == "Bearer"
    # Un cookie (session du dashboard) ne fournit aucune authentification ici.
    r = await http.post("/api/v1/pipeline/cycle", cookies={"access_token": "x", "session": "y"})
    assert r.status_code == 401


async def test_portees_minimales(http: httpx.AsyncClient, admin: asyncpg.Connection) -> None:
    c_ing, s_ing = await _client(admin, scopes=["ingest"], source="seulement_ingest")
    c_cyc, s_cyc = await _client(admin, scopes=["cycle"], source="seulement_cycle")
    h_ing = await _entetes(http, A.code, c_ing, s_ing)
    h_cyc = await _entetes(http, A.code, c_cyc, s_cyc)
    assert (await http.post("/api/v1/pipeline/cycle", headers=h_ing)).status_code == 403
    r = await http.post("/api/v1/transactions", json={"transactions": [_tx(1)]}, headers=h_cyc)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "portee_insuffisante"
    assert (
        await http.post("/api/v1/transactions", json={"transactions": [_tx(1)]}, headers=h_ing)
    ).status_code == 200
    assert (await http.post("/api/v1/pipeline/cycle", headers=h_cyc)).status_code == 200


async def test_revocation_et_rotation_immediates(
    http: httpx.AsyncClient, admin: asyncpg.Connection
) -> None:
    cid, secret = await _client(admin)
    ancien = await _entetes(http, A.code, cid, secret)
    assert (await http.post("/api/v1/pipeline/cycle", headers=ancien)).status_code == 200

    nouveau_secret = await renouveler_secret(admin, cid, "test")
    assert (await http.post("/api/v1/pipeline/cycle", headers=ancien)).status_code == 401
    assert (await _jeton(http, A.code, cid, secret)).status_code == 401
    apres = await _entetes(http, A.code, cid, nouveau_secret)
    assert (await http.post("/api/v1/pipeline/cycle", headers=apres)).status_code == 200

    await revoquer_client(admin, cid, "test")
    assert (await http.post("/api/v1/pipeline/cycle", headers=apres)).status_code == 401
    assert (await _jeton(http, A.code, cid, nouveau_secret)).status_code == 401
    types = [
        r["event_type"]
        for r in await admin.fetch(
            "SELECT event_type FROM shared.api_client_events "
            "WHERE client_id = $1 ORDER BY event_id",
            cid,
        )
    ]
    assert types == ["created", "rotated", "revoked"]


async def test_identite_expiree_ou_tenant_desactive(
    http: httpx.AsyncClient, admin: asyncpg.Connection
) -> None:
    cid, secret = await _client(admin)
    entetes = await _entetes(http, A.code, cid, secret)
    await admin.execute(
        "UPDATE shared.tenants_registry SET is_active = false WHERE tenant_id = $1", A.tenant_id
    )
    assert (await http.post("/api/v1/pipeline/cycle", headers=entetes)).status_code == 401
    await admin.execute(
        "UPDATE shared.tenants_registry SET is_active = true WHERE tenant_id = $1", A.tenant_id
    )
    assert (await http.post("/api/v1/pipeline/cycle", headers=entetes)).status_code == 200
    await admin.execute(
        "UPDATE shared.api_clients SET expires_at = now() - interval '1 minute' "
        "WHERE client_id = $1",
        cid,
    )
    assert (await http.post("/api/v1/pipeline/cycle", headers=entetes)).status_code == 401
    assert (await _jeton(http, A.code, cid, secret)).status_code == 401


async def test_secret_jamais_stocke_en_clair(admin: asyncpg.Connection) -> None:
    cid, secret = await _client(admin)
    empreinte = await admin.fetchval(
        "SELECT secret_hash FROM shared.api_clients WHERE client_id = $1", cid
    )
    assert empreinte.startswith("$argon2id$") and secret not in empreinte


async def test_jetons_falsifies_ou_etrangers_refuses(
    http: httpx.AsyncClient, admin: asyncpg.Connection
) -> None:
    cid, secret = await _client(admin)
    maintenant = datetime.now(UTC)
    base = {
        "iss": "souverain-os",
        "aud": "souverain-api",
        "sub": str(cid),
        "tenant_id": str(A.tenant_id),
        "typ": "service",
        "sv": 1,
        "iat": maintenant,
        "exp": maintenant + timedelta(minutes=5),
    }
    valide = jwt.encode(base, JWT_SECRET, algorithm="HS256")
    assert (
        await http.post("/api/v1/pipeline/cycle", headers={"Authorization": f"Bearer {valide}"})
    ).status_code == 200
    cas = {
        "autre clé": jwt.encode(base, "k" * 40, algorithm="HS256"),
        "jeton humain": jwt.encode(
            {**base, "typ": "user", "aud": "autre"}, JWT_SECRET, algorithm="HS256"
        ),
        # Même client mais tenant B forgé : la RLS du pool de B ne voit pas ce client.
        "tenant forgé": jwt.encode(
            {**base, "tenant_id": str(B.tenant_id)}, JWT_SECRET, algorithm="HS256"
        ),
        "mauvaise version": jwt.encode({**base, "sv": 99}, JWT_SECRET, algorithm="HS256"),
    }
    for nom, jeton in cas.items():
        r = await http.post("/api/v1/pipeline/cycle", headers={"Authorization": f"Bearer {jeton}"})
        assert r.status_code == 401, nom


async def test_rls_et_privileges_de_la_table_des_identites(admin: asyncpg.Connection) -> None:
    ca, _ = await _client(admin, A, source="a_feed")
    cb, _ = await _client(admin, B, source="b_feed")
    pool_a = await create_tenant_pipeline_pool(A.tenant_id)
    visibles = {
        r["client_id"] for r in await pool_a.fetch("SELECT client_id FROM shared.api_clients")
    }
    assert visibles == {ca}
    for ordre in (
        "SELECT * FROM shared.api_client_events",
        "UPDATE shared.api_clients SET is_active = true",
        "DELETE FROM shared.api_clients",
        "INSERT INTO shared.api_clients (tenant_id, source_code, secret_hash, scopes) "
        f"VALUES ('{A.tenant_id}', 'intrus', 'x', ARRAY['cycle'])",
    ):
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await pool_a.execute(ordre)
    assert cb


# ------------------------------------------------------------ validation corps
async def test_corps_invalides(http: httpx.AsyncClient, admin: asyncpg.Connection) -> None:
    cid, secret = await _client(admin)
    h = await _entetes(http, A.code, cid, secret)
    futur = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    cas = {
        "tenant_id forgé": {"transactions": [_tx(1, tenant_id=str(B.tenant_id))]},
        "source dans le corps": {"transactions": [_tx(1, source="autre")]},
        "date future": {"transactions": [_tx(1, occurred_at=futur)]},
        "montant hors plafond": {"transactions": [_tx(1, amount="99999999999.00")]},
        "lot vide": {"transactions": []},
        "lot trop gros": {"transactions": [_tx(i) for i in range(1001)]},
        "champ racine inconnu": {"transactions": [_tx(1)], "tenant_id": str(B.tenant_id)},
    }
    for nom, corps in cas.items():
        r = await http.post("/api/v1/transactions", json=corps, headers=h)
        assert r.status_code in (413, 422), (nom, r.status_code)
    assert await admin.fetchval(f"SELECT count(*) FROM {A.schema}.transactions") == 0


async def test_taille_du_corps_bornee_avant_lecture(
    http: httpx.AsyncClient, admin: asyncpg.Connection
) -> None:
    cid, secret = await _client(admin)
    h = await _entetes(http, A.code, cid, secret)
    gros = json.dumps({"transactions": [_tx(1)], "remplissage": "x" * 70_000})
    r = await http.post(
        "/api/v1/transactions", content=gros, headers={**h, "Content-Type": "application/json"}
    )
    assert r.status_code == 413

    async def morceaux() -> AsyncGenerator[bytes, None]:
        yield b"{}"

    r = await http.post(
        "/api/v1/transactions",
        content=morceaux(),
        headers={**h, "Content-Type": "application/json"},
    )
    assert r.status_code == 411


# ------------------------------------------------------------------- journaux
async def test_journaux_sans_donnee_sensible(
    http: httpx.AsyncClient, admin: asyncpg.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="souverain.api.pipeline")
    cid, secret = await _client(admin)
    await _jeton(http, A.code, cid, "mauvais" * 6)
    h = await _entetes(http, A.code, cid, secret)
    jeton = h["Authorization"].split()[1]
    await http.post("/api/v1/transactions", json={"transactions": [_tx(7), _tx(8)]}, headers=h)
    await http.post(
        "/api/v1/transactions", json={"transactions": [_tx(7, amount="3.00")]}, headers=h
    )
    await http.post("/api/v1/pipeline/cycle", headers=h)
    texte = "\n".join(r.getMessage() for r in caplog.records if r.name == "souverain.api.pipeline")
    assert "ingestion" in texte and "cycle" in texte and "auth_echec" in texte
    for interdit in (secret, "mauvais", jeton, "cpt_", "2500", "ext-7", "ext-8"):
        assert interdit not in texte, interdit


async def test_post_sans_corps_ni_content_length_est_accepte(
    http: httpx.AsyncClient, admin: asyncpg.Connection
) -> None:
    """`curl -X POST` sans données n'envoie pas de Content-Length : corps vide, pas un 411."""
    cid, secret = await _client(admin)
    entetes = await _entetes(http, A.code, cid, secret)
    requete = http.build_request("POST", "/api/v1/pipeline/cycle", headers=entetes)
    requete.headers.pop("content-length", None)
    assert "content-length" not in requete.headers
    assert (await http.send(requete)).status_code == 200
