"""Indicateur d'attente du bouton d'explication (amélioration d'interface).

L'indicateur est une animation CSS sans aucun texte : aucune nouvelle traduction,
donc aucun effet sur le gel du lot v2. Le bouton est désactivé pendant l'attente.
"""

from __future__ import annotations

import html
import re
from uuid import uuid4

import pytest
from brique_02_auth_rbac.session import AuthenticatedUser
from brique_07_dashboard.tenant_garde import MetadonneesTenant
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from souverain_app.traductions.fr import TEXTES_FR

from souverain_app import explication_routes as routes


def _app(role: str) -> FastAPI:
    tenant = MetadonneesTenant(
        tenant_id=uuid4(),
        schema_name="tenant_test_indicateur",
        country_code="NE",
        data_classification="confidential",
    )
    utilisateur = AuthenticatedUser(
        user_id=uuid4(), tenant_id=tenant.tenant_id, role=role, souverain_id=uuid4()
    )
    app = FastAPI()
    app.include_router(routes.construire_routes_explication())
    app.dependency_overrides[routes.tenant_valide] = lambda: tenant
    app.dependency_overrides[routes.get_current_user_from_cookie] = lambda: utilisateur
    return app


async def _fragment(role: str) -> str:
    async with AsyncClient(
        transport=ASGITransport(app=_app(role)), base_url="http://test"
    ) as client:
        reponse = await client.get(f"/alertes/{uuid4()}/explication")
    assert reponse.status_code == 200
    return reponse.text


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["analyst", "admin"])
async def test_le_bouton_reference_un_indicateur_unique_et_se_desactive(role: str) -> None:
    texte = await _fragment(role)

    assert 'hx-indicator="#explication-attente"' in texte
    assert 'hx-disabled-elt="this"' in texte
    assert texte.count('id="explication-attente"') == 1
    assert re.search(
        r'<span id="explication-attente" class="htmx-indicator explication-spinner" '
        r'aria-hidden="true"></span>',
        texte,
    ), "L'indicateur doit être un élément vide, masqué aux lecteurs d'écran."


@pytest.mark.asyncio
async def test_le_fragment_ne_contient_aucun_nouveau_texte() -> None:
    texte = await _fragment("analyst")

    sans_style = re.sub(r"<style>.*?</style>", "", texte, flags=re.DOTALL)
    visible = html.unescape(re.sub(r"<[^>]+>", "", sans_style)).strip()

    assert visible == TEXTES_FR["explication.bouton"] + TEXTES_FR["explication.aide"]


@pytest.mark.asyncio
async def test_le_style_prevoit_la_reduction_des_animations() -> None:
    texte = await _fragment("analyst")

    assert "@keyframes explication-rotation" in texte
    assert "prefers-reduced-motion" in texte


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["auditor", "visiteur", ""])
async def test_un_role_non_autorise_ne_recoit_ni_bouton_ni_indicateur(role: str) -> None:
    assert await _fragment(role) == ""
