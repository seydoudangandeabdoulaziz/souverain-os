"""Tests de régularisation ADR-001 / ADR-007 — textes de l'explication IA.

Garde-fou contre le retour de textes français écrits en dur dans la route
d'explication et dans le bloc d'explication du template de la Brique 7.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path
from uuid import uuid4

import brique_07_dashboard
import pytest
from brique_02_auth_rbac.session import AuthenticatedUser
from brique_07_dashboard.tenant_garde import MetadonneesTenant
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from souverain_app.traductions import t
from souverain_app.traductions.fr import TEXTES_FR

from souverain_app import explication_routes as routes

_FICHIER_ROUTES = Path(routes.__file__)
_TEMPLATE_B7 = (
    Path(brique_07_dashboard.__file__).parent / "templates" / "alerte_detail.html"
)

# Heuristique volontairement simple : un texte français contient soit une
# lettre accentuée, soit un mot-outil courant entouré d'espaces.
_MOTS_OUTILS = (" le ", " la ", " de ", " des ", " ne ", " est ", " pas ", " à ")
_ACCENTS = re.compile(r"[àâäéèêëîïôöùûüçœ’]", re.IGNORECASE)


def _constantes_texte(source: str) -> list[str]:
    """Retourne les chaînes littérales hors docstrings."""
    arbre = ast.parse(source)
    docstrings: set[int] = set()
    for noeud in ast.walk(arbre):
        if isinstance(
            noeud, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
        ):
            corps = noeud.body
            if (
                corps
                and isinstance(corps[0], ast.Expr)
                and isinstance(corps[0].value, ast.Constant)
                and isinstance(corps[0].value.value, str)
            ):
                docstrings.add(id(corps[0].value))
    return [
        n.value
        for n in ast.walk(arbre)
        if isinstance(n, ast.Constant)
        and isinstance(n.value, str)
        and id(n) not in docstrings
    ]


def test_aucun_texte_francais_en_dur_dans_les_routes() -> None:
    suspects = [
        c
        for c in _constantes_texte(_FICHIER_ROUTES.read_text(encoding="utf-8"))
        if _ACCENTS.search(c) or any(m in f" {c} " for m in _MOTS_OUTILS)
    ]
    assert suspects == [], f"Textes en dur détectés : {suspects}"


def test_toutes_les_cles_utilisees_existent_dans_le_dictionnaire() -> None:
    source = _FICHIER_ROUTES.read_text(encoding="utf-8")
    cles = set(re.findall(r"""t\(\s*['"]([a-z_.]+)['"]""", source))
    cles |= {c for c in re.findall(r'"(explication\.[a-z_]+)"', source)}
    assert cles, "Aucune clé de traduction trouvée : test sans objet."
    manquantes = sorted(c for c in cles if c not in TEXTES_FR)
    assert manquantes == []


def test_cle_inconnue_ne_plante_pas() -> None:
    assert t("cle.inexistante") == "[cle.inexistante]"
    assert t("explication.bouton", "langue_inconnue") == TEXTES_FR["explication.bouton"]


def test_bloc_explication_du_template_b7_ne_contient_aucun_texte() -> None:
    template = _TEMPLATE_B7.read_text(encoding="utf-8")
    template = re.sub(r"\{#.*?#\}", "", template, flags=re.DOTALL)
    bloc = re.search(
        r'<div id="explication-ia".*?</div>', template, flags=re.DOTALL
    )
    assert bloc is not None
    sans_balises = re.sub(r"<[^>]+>", "", bloc.group(0)).strip()
    assert sans_balises == "…"
    assert 'hx-trigger="load"' in bloc.group(0)
    assert "/explication" in bloc.group(0)


@pytest.fixture
def app_fragment() -> FastAPI:
    app = FastAPI()
    app.include_router(routes.construire_routes_explication())
    tenant = MetadonneesTenant(
        tenant_id=uuid4(),
        schema_name="tenant_test_fragment",
        country_code="NE",
        data_classification="confidential",
    )
    utilisateur = AuthenticatedUser(
        user_id=uuid4(),
        tenant_id=tenant.tenant_id,
        role="auditor",
        souverain_id=uuid4(),
    )
    app.dependency_overrides[routes.tenant_valide] = lambda: tenant
    app.dependency_overrides[routes.get_current_user_from_cookie] = (
        lambda: utilisateur
    )
    return app


@pytest.mark.asyncio
async def test_fragment_affiche_le_bouton_sans_acces_base_ni_modele(
    app_fragment: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def interdit(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Le fragment ne doit accéder ni à la base ni au modèle.")

    monkeypatch.setattr(routes, "create_pool", interdit)
    monkeypatch.setattr(routes, "expliquer_alerte", interdit)
    alerte_id = uuid4()

    async with AsyncClient(
        transport=ASGITransport(app=app_fragment), base_url="http://test"
    ) as client:
        reponse = await client.get(f"/alertes/{alerte_id}/explication")

    assert reponse.status_code == 200
    assert TEXTES_FR["explication.bouton"] in reponse.text
    assert f"/alertes/{alerte_id}/expliquer" in reponse.text
    assert 'hx-target="#explication-ia"' in reponse.text


@pytest.mark.asyncio
async def test_fragment_exige_une_session() -> None:
    from souverain_app.main import creer_application_complete

    app = creer_application_complete()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        reponse = await client.get(f"/alertes/{uuid4()}/explication")

    assert reponse.status_code == 303
    assert reponse.headers["location"] == "/login"
