"""Construction de l'application FastAPI du dashboard.

t() est enregistrée comme fonction globale Jinja2 : chaque template
appelle {{ t('cle') }}, jamais une chaîne française en dur — voir
traductions/__init__.py pour la règle complète.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from brique_07_dashboard.auth_cookie import SessionInvalide
from brique_07_dashboard.config import get_dashboard_settings
from brique_07_dashboard.lecture import TenantSansDonnees
from brique_07_dashboard.routes.alertes import construire_routes_alertes
from brique_07_dashboard.routes.auth import construire_routes_auth
from brique_07_dashboard.traductions import t

_REPERTOIRE_BASE = Path(__file__).resolve().parent
_logger = logging.getLogger("brique_07_dashboard")


def creer_application() -> FastAPI:
    app = FastAPI(title="SOUVERAIN-OS — Dashboard", docs_url=None, redoc_url=None)

    templates = Jinja2Templates(directory=str(_REPERTOIRE_BASE / "templates"))
    templates.env.globals["t"] = t

    app.mount(
        "/static", StaticFiles(directory=str(_REPERTOIRE_BASE / "static")), name="static"
    )

    @app.exception_handler(SessionInvalide)
    async def gerer_session_invalide(request: Request, exc: SessionInvalide) -> RedirectResponse:
        """Session absente/invalide/révoquée → redirection /login.

        Comportement web attendu, différent d'une 401 JSON brute —
        cette exception ne devrait jamais atteindre un client API pur,
        seulement un navigateur naviguant sur le dashboard.
        """
        dashboard_settings = get_dashboard_settings()
        reponse = RedirectResponse(url="/login", status_code=303)
        reponse.delete_cookie(dashboard_settings.cookie_name)
        return reponse

    @app.exception_handler(TenantSansDonnees)
    async def gerer_tenant_sans_donnees(request: Request, exc: TenantSansDonnees) -> object:
        """{tenant}.alertes/{tenant}.detections n'existe pas encore — état
        légitime (Brique 5 jamais exécutée pour ce tenant), pas une
        erreur 500. Option B validée à l'analyse : l'exception reste
        TRACÉE (logs), l'utilisateur voit une page propre.

        Langue par défaut 'fr' ici — le contexte tenant complet
        (country_code) n'est pas trivialement accessible depuis un
        exception_handler global sans re-résoudre la session ; cas
        suffisamment rare (tenant neuf, avant premier cycle de
        scoring) pour accepter cette simplification documentée.
        """
        _logger.warning("TenantSansDonnees: %s", exc)
        return templates.TemplateResponse(
            request, "tenant_sans_donnees.html", {"langue": "fr"}, status_code=200
        )

    @app.get("/")
    async def racine() -> RedirectResponse:
        return RedirectResponse(url="/alertes", status_code=303)

    app.include_router(construire_routes_auth(templates))
    app.include_router(construire_routes_alertes(templates))

    return app


app = creer_application()
