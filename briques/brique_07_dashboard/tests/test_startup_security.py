"""Le serveur refuse de démarrer sans configuration JWT et DB runtime sûre."""

from __future__ import annotations

import pytest
from brique_07_dashboard.app import creer_application
from pydantic import ValidationError


@pytest.mark.asyncio
async def test_demarrage_refuse_jwt_par_defaut(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "insecure-dev-secret-change-me-before-any-real-use")
    monkeypatch.setenv("APP_POSTGRES_PASSWORD", "p" * 48)

    app = creer_application()
    with pytest.raises(ValidationError):
        async with app.router.lifespan_context(app):
            pytest.fail("Le lifespan ne doit pas accepter un secret JWT de démonstration")


@pytest.mark.asyncio
async def test_demarrage_accepte_secrets_valides_sans_connecter_la_base(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "j" * 64)
    monkeypatch.setenv("APP_POSTGRES_PASSWORD", "p" * 48)

    app = creer_application()
    async with app.router.lifespan_context(app):
        assert app.title == "SOUVERAIN-OS — Dashboard"


@pytest.mark.asyncio
async def test_demarrage_refuse_mot_de_passe_runtime_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "j" * 64)
    # Une valeur vide force l'override du .env local de développement.
    monkeypatch.setenv("APP_POSTGRES_PASSWORD", "")

    app = creer_application()
    with pytest.raises(ValidationError):
        async with app.router.lifespan_context(app):
            pytest.fail("Le lifespan doit exiger APP_POSTGRES_PASSWORD")
