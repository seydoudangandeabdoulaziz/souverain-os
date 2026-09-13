"""Assemble l'application FastAPI complète : dashboard Brique 7 +
routes d'écriture Brique 8 + gouvernance des utilisateurs (Brique 2 V2),
sur une seule instance.

creer_application() de la Brique 7 reste responsable de TOUT ce qui la
concerne (templates, fichiers statiques, gestion des exceptions,
routes de lecture) — ce module ne fait qu'y ajouter les routeurs
après coup, via include_router(), sans rouvrir aucun fichier de la
Brique 7.

Étape 1 (Hygiène de socle, validée à l'analyse avant tout code) :
- /health : réutilise run_db_healthcheck() (Brique 1, INCHANGÉE) —
  PostgreSQL uniquement pour cette étape, Neo4j explicitement hors
  périmètre (décision actée, pas un oubli). Détail minimal exposé
  publiquement (ok/label seulement) — jamais host/port/db ni le
  message d'erreur brut, réservés aux logs serveur.
- Middleware de logs structurés (JSON) sur CE point d'entrée
  uniquement — aucune brique existante modifiée, aucune nouvelle
  dépendance (module logging standard, pas structlog).
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from brique_01_postgresql.healthcheck_db import run_db_healthcheck
from brique_02_auth_rbac.gouvernance.routes import construire_routes_gouvernance
from brique_07_dashboard.app import creer_application
from brique_08_audit_human_loop.routes import construire_routes_audit
from fastapi import FastAPI, Request, Response
from starlette.responses import JSONResponse

_logger = logging.getLogger("souverain_app.requetes")
_logger.setLevel(logging.INFO)
if not _logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(message)s"))  # le message EST déjà le JSON
    _logger.addHandler(_handler)


def creer_application_complete() -> FastAPI:
    app = creer_application()
    app.include_router(construire_routes_audit())
    app.include_router(construire_routes_gouvernance())

    @app.middleware("http")
    async def journaliser_requete(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Log JSON structuré par requête — un seul point d'entrée
        instrumenté (Étape 1), pas une modification des briques
        existantes. request_id permet de corréler une entrée de log à
        une requête précise, absent partout ailleurs dans le projet
        avant cette étape."""
        request_id = str(uuid.uuid4())
        debut = time.perf_counter()
        reponse = await call_next(request)
        duree_ms = round((time.perf_counter() - debut) * 1000, 2)

        _logger.info(
            json.dumps(
                {
                    "request_id": request_id,
                    "methode": request.method,
                    "chemin": request.url.path,
                    "statut": reponse.status_code,
                    "duree_ms": duree_ms,
                },
                ensure_ascii=False,
            )
        )
        reponse.headers["X-Request-ID"] = request_id
        return reponse

    @app.get("/health")
    async def health() -> JSONResponse:
        """Point d'entrée non authentifié — un orchestrateur doit
        pouvoir l'interroger avant toute session. Détail minimal
        volontaire (ok/label), jamais le detail complet du rapport
        (host/port/db, messages d'erreur bruts) — décision actée à la
        conception, pas un oubli de sécurité."""
        rapport = await run_db_healthcheck()
        corps = {
            "ok": rapport.all_ok,
            "verifications": [
                {"label": resultat.label, "ok": resultat.ok} for resultat in rapport.results
            ],
        }
        return JSONResponse(content=corps, status_code=200 if rapport.all_ok else 503)

    return app


app = creer_application_complete()
