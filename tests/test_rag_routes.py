from __future__ import annotations

from uuid import uuid4

import pytest
from brique_02_auth_rbac.session import AuthenticatedUser
from brique_07_dashboard.tenant_garde import MetadonneesTenant
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from souverain_app.rag_routes import construire_routes_rag
from souverain_rag.engine import SearchResponse
from souverain_rag.index import SearchResult
from souverain_rag.patterns import PatternType

from souverain_app import rag_routes


def _app(role: str) -> FastAPI:
    app = FastAPI()
    app.include_router(construire_routes_rag())
    user = AuthenticatedUser(uuid4(), uuid4(), role, uuid4())

    async def role_guard():
        return await rag_routes._DEPENDANCE_ROLE(user=user)

    app.dependency_overrides[rag_routes._DEPENDANCE_ROLE] = role_guard
    return app


def _inline_worker(monkeypatch) -> None:
    async def inline(function, *args):
        return function(*args)

    monkeypatch.setattr(rag_routes.asyncio, "to_thread", inline)


@pytest.mark.asyncio
async def test_role_auditor_est_refuse_avant_chargement_du_rag(monkeypatch) -> None:
    _inline_worker(monkeypatch)
    called = False

    def forbidden_loader():
        nonlocal called
        called = True
        raise AssertionError("Le moteur ne doit pas être chargé avant le contrôle du rôle.")

    monkeypatch.setattr(rag_routes, "_charger_moteur", forbidden_loader)
    app = _app("auditor")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/references/compte_pivot")

    assert response.status_code == 403
    assert called is False


@pytest.mark.asyncio
async def test_analyst_ne_transmet_que_le_pattern_et_reçoit_html_échappé(monkeypatch) -> None:
    _inline_worker(monkeypatch)
    class FakeEngine:
        def search(self, pattern_type: PatternType, *, k: int) -> SearchResponse:
            assert pattern_type is PatternType.COMPTE_PIVOT
            assert k == 5
            return SearchResponse(
                "fixture-v1",
                pattern_type,
                (
                    SearchResult(
                        "p1",
                        "doc1",
                        "Référence test",
                        "Éditeur",
                        "https://example.invalid/doc",
                        2,
                        "<script>alert('x')</script>",
                        False,
                        0.9,
                    ),
                ),
            )

    monkeypatch.setattr(rag_routes, "_charger_moteur", lambda: FakeEngine())

    async def tenant_local(_user):
        return MetadonneesTenant(uuid4(), "tenant_ne", "NE", "public")

    monkeypatch.setattr(rag_routes, "tenant_valide", tenant_local)
    app = _app("analyst")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/references/compte_pivot")

    assert response.status_code == 200
    assert "&lt;script&gt;" in response.text
    assert "<script>" not in response.text
    assert "https://example.invalid/doc" in response.text
