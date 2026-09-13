"""
Test d'intégration de /health (Étape 1 — Hygiène de socle).

Placé dans tests/integration/ (racine) et non dans une brique
spécifique : /health est une préoccupation transverse portée par
souverain_app (la couche d'assemblage), pas par une brique métier.

Fonctionne SANS PostgreSQL disponible (vérifie le cas dégradé, 503) —
et vérifie le cas sain (200) si PostgreSQL est joignable, sans
jamais faire échouer le test faute de base (cohérent avec le reste
du projet : SKIP, jamais d'erreur, quand une dépendance externe
manque — ici, le test lui-même s'adapte plutôt que de skip, car les
DEUX cas (200 et 503) sont des comportements valides à vérifier).
"""

from __future__ import annotations

import pytest_asyncio
from brique_01_postgresql.connection import close_pool
from httpx import ASGITransport, AsyncClient
from souverain_app.main import creer_application_complete


@pytest_asyncio.fixture(autouse=True)
async def _fermer_pool_admin_apres_chaque_test():
    """Ferme le pool admin (singleton, brique_01_postgresql.connection)
    après chaque test — sinon un pool créé dans la boucle asyncio d'un
    test fuit vers le suivant (boucle différente, pytest-asyncio étant
    scope function par défaut). Même bug déjà rencontré et corrigé
    pour le driver Neo4j (Brique 7) et les pools dédiés (Brique 8,
    gouvernance V2) — reproduit ici par oubli, corrigé de la même
    façon."""
    yield
    await close_pool()


async def test_health_repond_toujours_avec_un_corps_json_coherent() -> None:
    """Que PostgreSQL soit joignable ou non, /health doit répondre
    (jamais une exception non gérée) avec un corps JSON structuré."""
    app = creer_application_complete()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        reponse = await client.get("/health")

    assert reponse.status_code in (200, 503)
    corps = reponse.json()
    assert "ok" in corps
    assert "verifications" in corps
    assert isinstance(corps["verifications"], list)
    assert len(corps["verifications"]) >= 1

    # Cohérence : le statut HTTP doit refléter exactement corps["ok"].
    if corps["ok"]:
        assert reponse.status_code == 200
    else:
        assert reponse.status_code == 503


async def test_health_ne_fuit_aucun_detail_sensible() -> None:
    """Décision actée à la conception : jamais host/port/db, jamais un
    message d'erreur brut exposé publiquement — seulement ok/label."""
    app = creer_application_complete()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        reponse = await client.get("/health")

    corps = reponse.json()
    for verification in corps["verifications"]:
        assert set(verification.keys()) == {"label", "ok"}
        # "detail" ne doit JAMAIS apparaître dans la réponse publique.
        assert "detail" not in verification


async def test_health_pose_un_request_id_correlable() -> None:
    """X-Request-ID doit être présent — corrélation log <-> requête,
    absente partout ailleurs dans le projet avant cette étape."""
    app = creer_application_complete()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        reponse = await client.get("/health")

    assert "X-Request-ID" in reponse.headers
    # Format UUID4 minimal — 36 caractères avec tirets.
    assert len(reponse.headers["X-Request-ID"]) == 36
