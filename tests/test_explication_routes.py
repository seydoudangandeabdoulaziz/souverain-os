from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from brique_02_auth_rbac.session import AuthenticatedUser
from brique_07_dashboard.modeles import AlerteDetail
from brique_07_dashboard.tenant_garde import MetadonneesTenant
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from souverain_app import explication_routes as routes


@pytest.fixture
def contexte():
    app = FastAPI()
    app.include_router(routes.construire_routes_explication())

    tenant = MetadonneesTenant(
        tenant_id=uuid4(),
        schema_name="tenant_test_securite",
        country_code="NE",
        data_classification="confidential",
    )
    utilisateur = AuthenticatedUser(
        user_id=uuid4(),
        tenant_id=tenant.tenant_id,
        role="analyst",
        souverain_id=uuid4(),
    )

    app.dependency_overrides[routes.tenant_valide] = lambda: tenant
    app.dependency_overrides[routes.get_current_user_from_cookie] = (
        lambda: utilisateur
    )

    routes.create_pool = AsyncMock(return_value=object())
    routes.lecture.lire_alerte = AsyncMock(return_value=None)

    return app, tenant


@pytest.mark.asyncio
async def test_alerte_absente_retourne_404(contexte):
    app, tenant = contexte

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(f"/alertes/{uuid4()}/expliquer")

    assert response.status_code == 404
    routes.lecture.lire_alerte.assert_awaited_once()
    assert routes.lecture.lire_alerte.await_args.args[1] == tenant.schema_name


@pytest.mark.asyncio
async def test_alerte_valide_affiche_explication_echappee(
    contexte, monkeypatch
):
    app, tenant = contexte
    alerte_id = uuid4()
    maintenant = datetime.now(UTC)

    alerte = AlerteDetail(
        alerte_id=alerte_id,
        compte_pivot="compte-test",
        score=50,
        statut="ouverte",
        pattern_types_impliques=["compte_pivot"],
        fenetre_debut=maintenant,
        fenetre_fin=maintenant,
        details={"compte_pivot": 30},
    )
    routes.lecture.lire_alerte.return_value = alerte

    explication = AsyncMock(return_value=("<script>alert(1)</script>", True))
    monkeypatch.setattr(routes, "expliquer_alerte", explication)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(f"/alertes/{alerte_id}/expliquer")

    assert response.status_code == 200
    assert "&lt;script&gt;" in response.text
    assert "<script>" not in response.text
    assert "repli déterministe" in response.text
    routes.lecture.lire_alerte.assert_awaited_once_with(
        routes.create_pool.return_value,
        tenant.schema_name,
        alerte_id,
    )
    explication.assert_awaited_once()


@pytest.mark.asyncio
async def test_route_exige_session_sans_acces_a_postgresql(monkeypatch):
    from souverain_app.main import creer_application_complete

    creer_pool = AsyncMock()
    lire_alerte = AsyncMock()

    monkeypatch.setattr(routes, "create_pool", creer_pool)
    monkeypatch.setattr(routes.lecture, "lire_alerte", lire_alerte)

    app = creer_application_complete()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        reponse = await client.get(f"/alertes/{uuid4()}/expliquer")

    assert reponse.status_code == 303
    assert reponse.headers["location"] == "/login"
    creer_pool.assert_not_awaited()
    lire_alerte.assert_not_awaited()
