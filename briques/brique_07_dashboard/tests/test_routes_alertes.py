"""Tests HTTP de bout en bout — via httpx.AsyncClient + ASGITransport
(jamais TestClient, même précaution documentée en Brique 2 : TestClient
exécute l'app dans un thread séparé avec sa propre boucle asyncio,
incompatible avec le pool asyncpg créé dans la boucle du test).

⚠️ NON VÉRIFIÉ dans l'environnement de génération (pas de PostgreSQL ni
Neo4j disponibles) — à exécuter sur ta machine réelle.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import asyncpg
import pytest
from brique_07_dashboard import lecture
from brique_07_dashboard.app import creer_application
from httpx import ASGITransport, AsyncClient

COMPTE_ALERTE_TEST = "compte_test_dashboard_01"


@pytest.mark.asyncio
async def test_acces_sans_cookie_redirige_vers_login() -> None:
    app = creer_application()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", follow_redirects=False
    ) as ac:
        reponse = await ac.get("/alertes")

    assert reponse.status_code == 303
    assert reponse.headers["location"] == "/login"


@pytest.mark.asyncio
async def test_login_avec_mauvais_mot_de_passe_retourne_401(
    pool: asyncpg.Pool, tenant_provisionne: tuple[UUID, str], utilisateur_test: object
) -> None:
    app = creer_application()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        reponse = await ac.post(
            "/login",
            data={"email": "dashboard-test@example.com", "mot_de_passe": "mauvais-mot-de-passe"},
        )

    assert reponse.status_code == 401


@pytest.mark.asyncio
async def test_login_avec_email_inconnu_retourne_401(pool: asyncpg.Pool) -> None:
    """Vérifie seulement le code retour ici — pas de test de timing réel,
    hors périmètre de ce test unitaire. La protection anti-énumération
    (hash factice systématiquement vérifié) est documentée dans
    routes/auth.py."""
    app = creer_application()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        reponse = await ac.post(
            "/login", data={"email": "personne@example.com", "mot_de_passe": "peu-importe"}
        )

    assert reponse.status_code == 401


@pytest.mark.asyncio
async def test_liste_alertes_contient_le_compte_de_test(
    client: AsyncClient, alerte_test: None
) -> None:
    reponse = await client.get("/alertes")

    assert reponse.status_code == 200
    assert COMPTE_ALERTE_TEST in reponse.text


@pytest.mark.asyncio
async def test_liste_alertes_tenant_sans_table_affiche_page_dediee(client: AsyncClient) -> None:
    """Aucune fixture de données — {tenant}.alertes n'existe pas du tout
    (Brique 5 jamais exécutée pour ce tenant). 200, pas un 500 brut —
    Option B validée après le bug trouvé en validation locale."""
    reponse = await client.get("/alertes")

    assert reponse.status_code == 200
    assert "Aucune alerte" in reponse.text


@pytest.mark.asyncio
async def test_liste_alertes_vide_affiche_le_message_dedie(
    client: AsyncClient, alertes_table_creee_sans_alerte: None
) -> None:
    """Distinct du test ci-dessus : ici la table {tenant}.alertes existe
    réellement (score sous le seuil), simplement aucune ligne."""
    reponse = await client.get("/alertes")

    assert reponse.status_code == 200
    assert "Aucune alerte" in reponse.text


@pytest.mark.asyncio
async def test_detail_alerte_inexistante_retourne_404(
    client: AsyncClient, alertes_table_creee_sans_alerte: None
) -> None:
    """Table PRÉSENTE (fixture dédiée) — sans elle, ce test tombait par
    erreur dans le cas table absente (200, pas 404). Corrigé."""
    reponse = await client.get(f"/alertes/{uuid4()}")

    assert reponse.status_code == 404


@pytest.mark.asyncio
async def test_fragment_graphe_sur_tenant_sans_table_alertes_ne_leve_pas_500(
    client: AsyncClient,
) -> None:
    """Accès direct au fragment graphe (URL en favori/tapée à la main),
    sur un tenant où {tenant}.alertes n'existe pas du tout (Brique 5
    jamais exécutée). Risque connexe identifié après le bug
    TenantSansDonnees — corrigé dans routes/alertes.py, sans toucher à
    la Brique 6. Doit rendre un fragment vide, jamais un 500."""
    reponse = await client.get(
        f"/alertes/{uuid4()}/graphe", params={"compte_pivot": "peu-importe"}
    )

    assert reponse.status_code == 200


@pytest.mark.asyncio
async def test_detail_alerte_et_fragment_graphe(
    client: AsyncClient,
    pool: asyncpg.Pool,
    tenant_provisionne: tuple[UUID, str],
    alerte_test: None,
) -> None:
    _, schema_name = tenant_provisionne
    alertes = await lecture.lister_alertes_ouvertes(pool, schema_name)
    alerte_id = alertes[0].alerte_id

    reponse_detail = await client.get(f"/alertes/{alerte_id}")
    assert reponse_detail.status_code == 200
    assert COMPTE_ALERTE_TEST in reponse_detail.text
    # Le fragment graphe est chargé via hx-trigger="load" côté
    # navigateur, pas au chargement de la page — l'URL apparaît dans le
    # HTML, mais n'est pas encore appelée à ce stade.
    assert f"/alertes/{alerte_id}/graphe" in reponse_detail.text

    reponse_fragment = await client.get(
        f"/alertes/{alerte_id}/graphe", params={"compte_pivot": COMPTE_ALERTE_TEST}
    )
    assert reponse_fragment.status_code == 200
    # Aucune transaction synchronisée dans Neo4j pour ce tenant de
    # test -> résultats vides, mais rendu sans erreur (même
    # comportement que le cas vide déjà testé côté Brique 6, vérifié
    # ici côté HTTP).
