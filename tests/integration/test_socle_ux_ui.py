"""
Test d'intégration du socle UX/UI (Étape 3 — Phase transverse).

Placé dans tests/integration/ (racine), même précédent que
test_health_endpoint.py (Étape 1) : cette étape est transverse (elle
touche la Brique 7 ET l'extension V2 de la Brique 2), pas une brique
métier unique.

Fonctionne SANS PostgreSQL ni Neo4j disponibles : les pages vérifiées
ici (fichier CSS statique, page de connexion) ne déclenchent aucun
accès base de données — cohérent avec le principe déjà établi (aucun
test transverse ne doit échouer faute de Docker en environnement de
génération).

Ce que ce test NE couvre PAS (nécessite une vraie base + un vrai
utilisateur authentifié, à vérifier manuellement par le fondateur sur
sa machine réelle, comme pour chaque étape précédente) :
- Le rendu authentifié de /utilisateurs (Brique 2 V2) avec sa nouvelle
  nav — la page redirige vers /login sans session valide, donc son
  contenu HTML n'est pas observable ici.
"""

from __future__ import annotations

from brique_07_dashboard.app import creer_application
from httpx import ASGITransport, AsyncClient


async def test_le_css_partage_est_servi() -> None:
    """/static/souverain.css doit être joignable et contenir les
    tokens de base — c'est le fichier que base.html, login.html et
    liste_utilisateurs.html référencent tous désormais."""
    app = creer_application()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        reponse = await client.get("/static/souverain.css")

    assert reponse.status_code == 200
    assert "text/css" in reponse.headers["content-type"]
    corps = reponse.text
    assert "--couleur-primaire" in corps
    # Les classes qui manquaient réellement avant cette étape (Brique 8).
    assert ".audit-historique" in corps
    assert ".audit-commentaire" in corps
    assert ".succes" in corps
    # Nouvelles classes de ce cycle (bandeau rôle, badges, boutons,
    # tags, message de contexte réel).
    assert ".badge-role" in corps
    assert ".bouton-primaire" in corps
    assert ".bouton-danger" in corps
    assert ".tag" in corps
    assert ".avertissement" in corps


async def test_la_page_de_connexion_charge_le_css_partage() -> None:
    """login.html (Brique 7) ne doit plus avoir de <style> inline —
    seulement le <link> vers le socle partagé."""
    app = creer_application()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        reponse = await client.get("/login")

    assert reponse.status_code == 200
    corps = reponse.text
    assert '<link rel="stylesheet" href="/static/souverain.css">' in corps
    assert "<style>" not in corps
