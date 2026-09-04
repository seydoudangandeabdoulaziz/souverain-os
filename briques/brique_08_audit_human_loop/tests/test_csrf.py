"""Tests unitaires de la protection CSRF — aucune dépendance DB."""

from __future__ import annotations

import pytest
from brique_08_audit_human_loop.csrf import NOM_COOKIE_CSRF, generer_jeton_csrf, verifier_csrf
from fastapi import HTTPException
from starlette.requests import Request


def _requete_avec_cookie(jeton: str | None) -> Request:
    """Construit une Request Starlette minimale portant (ou non) le cookie CSRF."""
    cookies_header = f"{NOM_COOKIE_CSRF}={jeton}".encode() if jeton is not None else b""
    scope = {
        "type": "http",
        "headers": [(b"cookie", cookies_header)] if jeton is not None else [],
        "method": "POST",
        "path": "/",
    }
    return Request(scope)


def test_generer_jeton_csrf_produit_des_jetons_uniques() -> None:
    jeton_a = generer_jeton_csrf()
    jeton_b = generer_jeton_csrf()
    assert jeton_a != jeton_b
    assert len(jeton_a) > 20  # secrets.token_urlsafe(32) — largement suffisant


def test_verifier_csrf_accepte_jetons_identiques() -> None:
    requete = _requete_avec_cookie("jeton-valide-123")
    # Ne doit lever aucune exception.
    verifier_csrf(requete, "jeton-valide-123")


def test_verifier_csrf_rejette_jetons_differents() -> None:
    requete = _requete_avec_cookie("jeton-cookie")
    with pytest.raises(HTTPException) as exc_info:
        verifier_csrf(requete, "jeton-formulaire-different")
    assert exc_info.value.status_code == 403


def test_verifier_csrf_rejette_cookie_absent() -> None:
    requete = _requete_avec_cookie(None)
    with pytest.raises(HTTPException) as exc_info:
        verifier_csrf(requete, "peu-importe")
    assert exc_info.value.status_code == 403
