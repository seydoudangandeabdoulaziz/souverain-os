"""Autorisations des routes d'explication IA (étape 6B, ADR-007).

Règles :
- `analyst` et `admin` peuvent afficher le bouton et déclencher une génération ;
- `auditor` (et tout rôle inconnu) ne voit pas le bouton : le fragment répond
  200 avec un contenu vide ;
- une tentative directe de `/expliquer` par un rôle non autorisé reçoit 403,
  sans lecture en base ni appel à Ollama.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from brique_02_auth_rbac.rbac import Role
from brique_02_auth_rbac.session import AuthenticatedUser
from brique_07_dashboard.lecture import AlerteDetail
from brique_07_dashboard.tenant_garde import MetadonneesTenant
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from souverain_app.traductions.fr import TEXTES_FR

from souverain_app import explication_ia as ia
from souverain_app import explication_routes as routes

_MESSAGE_403 = "Vous n'avez pas les droits nécessaires pour cette action."
_AUTORISES = ["admin", "analyst"]
_REFUSES = ["auditor", "visiteur", ""]


class _Contexte:
    """Espions partagés : combien de fois chaque ressource coûteuse est touchée."""

    def __init__(self) -> None:
        self.appels_tenant = 0
        self.appels_pool = 0
        self.appels_ollama = 0


def _alerte() -> AlerteDetail:
    maintenant = datetime.now(UTC)
    return AlerteDetail(
        alerte_id=uuid4(),
        compte_pivot="compte-test",
        score=50,
        statut="ouverte",
        pattern_types_impliques=["compte_pivot"],
        fenetre_debut=maintenant,
        fenetre_fin=maintenant,
        details={"compte_pivot": 30},
    )


def _construire(role: str, monkeypatch: pytest.MonkeyPatch) -> tuple[FastAPI, _Contexte]:
    contexte = _Contexte()
    tenant = MetadonneesTenant(
        tenant_id=uuid4(),
        schema_name="tenant_test_roles",
        country_code="NE",
        data_classification="confidential",
    )
    utilisateur = AuthenticatedUser(
        user_id=uuid4(), tenant_id=tenant.tenant_id, role=role, souverain_id=uuid4()
    )

    def tenant_espion() -> MetadonneesTenant:
        contexte.appels_tenant += 1
        return tenant

    async def pool_espion() -> object:
        contexte.appels_pool += 1
        return object()

    def ollama_espion(_url: str, _modele: str, faits: ia.FaitsAlerte, _timeout: float) -> str:
        contexte.appels_ollama += 1
        return json.dumps({"claims": list(ia._identifiants_autorises(faits))})

    monkeypatch.setattr(routes, "create_pool", pool_espion)
    monkeypatch.setattr(routes.lecture, "lire_alerte", AsyncMock(return_value=_alerte()))
    monkeypatch.setattr(ia, "_requete_ollama_sync", ollama_espion)

    app = FastAPI()
    app.include_router(routes.construire_routes_explication())
    app.dependency_overrides[routes.tenant_valide] = tenant_espion
    app.dependency_overrides[routes.get_current_user_from_cookie] = lambda: utilisateur
    return app, contexte


async def _get(app: FastAPI, chemin: str) -> Any:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.get(chemin)


def test_les_roles_autorises_sont_analyst_et_admin_uniquement() -> None:
    assert set(routes._ROLES_AUTORISES_EXPLICATION) == {Role.ANALYST, Role.ADMIN}
    assert Role.AUDITOR not in routes._ROLES_AUTORISES_EXPLICATION


@pytest.mark.parametrize("role", _AUTORISES)
def test_le_helper_accepte_les_roles_autorises(role: str) -> None:
    assert routes._role_peut_expliquer(role) is True


@pytest.mark.parametrize("role", _REFUSES)
def test_le_helper_refuse_par_defaut(role: str) -> None:
    assert routes._role_peut_expliquer(role) is False


# --- Fragment : le bouton -------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("role", _AUTORISES)
async def test_fragment_affiche_le_bouton_pour_analyst_et_admin(
    role: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, contexte = _construire(role, monkeypatch)
    alerte_id = uuid4()

    reponse = await _get(app, f"/alertes/{alerte_id}/explication")

    assert reponse.status_code == 200
    assert TEXTES_FR["explication.bouton"] in reponse.text
    assert f"/alertes/{alerte_id}/expliquer" in reponse.text
    assert (contexte.appels_pool, contexte.appels_ollama) == (0, 0)


@pytest.mark.asyncio
@pytest.mark.parametrize("role", _REFUSES)
async def test_fragment_est_vide_pour_un_role_non_autorise(
    role: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, contexte = _construire(role, monkeypatch)

    reponse = await _get(app, f"/alertes/{uuid4()}/explication")

    assert reponse.status_code == 200, "Un 4xx laisserait le chargement bloqué."
    assert reponse.text == ""
    assert "button" not in reponse.text
    assert (contexte.appels_pool, contexte.appels_ollama) == (0, 0)


# --- Déclenchement : /expliquer -------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("role", _AUTORISES)
async def test_expliquer_fonctionne_pour_analyst_et_admin(
    role: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, contexte = _construire(role, monkeypatch)

    reponse = await _get(app, f"/alertes/{uuid4()}/expliquer")

    assert reponse.status_code == 200
    assert TEXTES_FR["explication.origine_modele"] in reponse.text
    assert contexte.appels_ollama == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("role", _REFUSES)
async def test_expliquer_est_refuse_en_403_sans_aucune_ressource_touchee(
    role: str, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    app, contexte = _construire(role, monkeypatch)
    caplog.set_level(logging.DEBUG)

    reponse = await _get(app, f"/alertes/{uuid4()}/expliquer")

    assert reponse.status_code == 403
    assert reponse.json()["detail"] == _MESSAGE_403
    assert contexte.appels_ollama == 0, "Ollama ne doit jamais être appelé."
    assert contexte.appels_pool == 0, "Aucune lecture en base pour un refus."
    assert contexte.appels_tenant == 0, "Le rôle est vérifié avant le tenant."
    assert routes.lecture.lire_alerte.await_count == 0
    assert [r for r in caplog.records if r.name == "souverain_app.explication"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("role", _AUTORISES + _REFUSES)
async def test_une_alerte_inconnue_reste_un_404_pour_les_roles_autorises(
    role: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, _contexte = _construire(role, monkeypatch)
    monkeypatch.setattr(routes.lecture, "lire_alerte", AsyncMock(return_value=None))

    reponse = await _get(app, f"/alertes/{uuid4()}/expliquer")

    assert reponse.status_code == (404 if role in _AUTORISES else 403)


# --- Session : inchangé ----------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("chemin", ["explication", "expliquer"])
async def test_sans_session_les_deux_routes_redirigent_vers_login(chemin: str) -> None:
    from souverain_app.main import creer_application_complete

    app = creer_application_complete()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        reponse = await client.get(f"/alertes/{uuid4()}/{chemin}")

    assert reponse.status_code == 303
    assert reponse.headers["location"] == "/login"
