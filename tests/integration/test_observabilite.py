"""
Test d'intégration de l'instrumentation Prometheus (Étape 4a —
Observabilité, phase transverse).

Placé dans tests/integration/ (racine), même précédent que
test_health_endpoint.py (Étape 1) et test_socle_ux_ui.py (Étape 3) :
transverse, ne dépend d'aucune brique métier unique.

Fonctionne SANS PostgreSQL ni Neo4j (/metrics n'en dépend pas — les
compteurs sont en mémoire, alimentés par le middleware existant).

Ce que ce test NE couvre PAS (nécessite le profile monitoring réel,
à vérifier par le fondateur sur sa machine) :
- Que Prometheus scrute effectivement /metrics avec succès
  (host.docker.internal + extra_hosts).
- Que Neo4j expose bien ses métriques natives sur le port 2004.
- Que Grafana affiche la source de données Prometheus provisionnée.
"""

from __future__ import annotations

from httpx import ASGITransport, AsyncClient
from souverain_app.main import creer_application_complete


async def test_metrics_est_servi_et_bien_forme() -> None:
    """/metrics doit répondre 200 au format d'exposition Prometheus,
    sans dépendre de PostgreSQL/Neo4j."""
    app = creer_application_complete()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        reponse = await client.get("/metrics")

    assert reponse.status_code == 200
    assert "text/plain" in reponse.headers["content-type"]
    corps = reponse.text
    assert "souverain_http_requests_total" in corps
    assert "souverain_http_request_duration_seconds" in corps


async def test_metrics_utilise_le_patron_de_route_jamais_le_chemin_brut() -> None:
    """Le label 'chemin' doit être le patron de route matché
    (/login), jamais un identifiant. Ici /login n'a pas de paramètre
    dynamique — le test de non-fuite porte sur le principe : une
    route sans DB (login GET) doit produire un label texte fixe, pas
    une valeur qui varierait avec la requête."""
    app = creer_application_complete()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.get("/login")
        reponse = await client.get("/metrics")

    corps = reponse.text
    assert 'chemin="/login"' in corps


async def test_metrics_ne_contient_aucun_uuid() -> None:
    """Non-fuite : aucun identifiant de compte/tenant/session ne doit
    apparaître dans l'export de métriques, même après une requête sur
    une route non authentifiée."""
    app = creer_application_complete()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.get("/login")
        reponse = await client.get("/metrics")

    corps = reponse.text
    import re

    motif_uuid = re.compile(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE
    )
    assert motif_uuid.search(corps) is None
