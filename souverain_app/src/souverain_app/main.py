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
Étape 4a (Observabilité — Prometheus/Grafana, validée à l'analyse
avant tout code) :
- /metrics : instrumentation manuelle via prometheus-client (pas
  d'auto-instrumentator) — 2 métriques seulement (compteur de
  requêtes, histogramme de durée), sur ce même point d'entrée
  transverse. Le label "chemin" utilise le PATRON de route matché
  (ex. "/alertes/{alerte_id}"), jamais le chemin brut résolu — un
  UUID de compte/tenant en label serait une fuite ET un risque de
  cardinalité non bornée, vérifié avant implémentation. Le log JSON
  (Étape 1) garde le chemin brut pour le débogage local ; les deux
  usages sont volontairement différents.
- Neo4j (métriques natives) et postgres-exporter (Étape 4b) sont
  scrutés directement par Prometheus, hors de ce module.
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
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.responses import JSONResponse

_logger = logging.getLogger("souverain_app.requetes")
_logger.setLevel(logging.INFO)
if not _logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(message)s"))  # le message EST déjà le JSON
    _logger.addHandler(_handler)

_requetes_total = Counter(
    "souverain_http_requests_total",
    "Nombre de requêtes HTTP reçues, par méthode/route/statut",
    ["methode", "chemin", "statut"],
)
_requete_duree_secondes = Histogram(
    "souverain_http_request_duration_seconds",
    "Durée des requêtes HTTP, par méthode/route",
    ["methode", "chemin"],
)


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
        duree_s = time.perf_counter() - debut
        duree_ms = round(duree_s * 1000, 2)

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

        # Métriques (Étape 4a) : le patron de route matché (ex.
        # "/alertes/{alerte_id}"), jamais request.url.path — un UUID
        # de compte/tenant en label Prometheus serait une fuite ET un
        # risque de cardinalité non bornée. "non_apparie" pour tout
        # chemin qui n'a matché aucune route (404, sondes, etc.),
        # regroupé sous une seule valeur bornée.
        route = request.scope.get("route")
        chemin_label = getattr(route, "path", "non_apparie")
        _requetes_total.labels(
            methode=request.method, chemin=chemin_label, statut=str(reponse.status_code)
        ).inc()
        _requete_duree_secondes.labels(methode=request.method, chemin=chemin_label).observe(
            duree_s
        )

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

    @app.get("/metrics")
    async def metrics() -> Response:
        """Non authentifié, comme /health — mais jamais destiné à être
        exposé hors du réseau Docker interne (Prometheus uniquement) :
        contrairement à /health, /metrics révèle des volumes de
        requêtes par route qui peuvent indirectement signaler une
        activité d'investigation. Décision actée à la conception :
        aucun port hôte publié par défaut pour Prometheus/Grafana."""
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = creer_application_complete()
