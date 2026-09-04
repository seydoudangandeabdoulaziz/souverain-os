"""Assemble l'application FastAPI complète : dashboard Brique 7 +
routes d'écriture Brique 8, sur une seule instance.

creer_application() de la Brique 7 reste responsable de TOUT ce qui la
concerne (templates, fichiers statiques, gestion des exceptions,
routes de lecture) — ce module ne fait qu'y ajouter le routeur de la
Brique 8 après coup, via include_router(), sans rouvrir aucun fichier
de la Brique 7.
"""

from __future__ import annotations

from brique_07_dashboard.app import creer_application
from brique_08_audit_human_loop.routes import construire_routes_audit
from fastapi import FastAPI


def creer_application_complete() -> FastAPI:
    app = creer_application()
    app.include_router(construire_routes_audit())
    return app


app = creer_application_complete()
