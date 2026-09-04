"""Tests HTTP de bout en bout des routes de la Brique 8, via l'app
ASSEMBLÉE (souverain_app), pas la Brique 7 seule — c'est le point
d'entrée réel dont dispose un utilisateur du dashboard complet.

httpx.AsyncClient + ASGITransport, jamais TestClient (même précaution
que la Brique 7 : TestClient exécute dans un thread avec sa propre
boucle asyncio, incompatible avec le pool asyncpg créé dans la boucle
du test).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID

import pytest
import pytest_asyncio
from brique_02_auth_rbac.config import get_jwt_settings
from brique_02_auth_rbac.jwt_tokens import create_access_token
from brique_02_auth_rbac.repository import UserRecord
from brique_07_dashboard.config import get_dashboard_settings
from brique_08_audit_human_loop.connection import close_audit_pool
from brique_08_audit_human_loop.csrf import NOM_COOKIE_CSRF
from httpx import ASGITransport, AsyncClient
from souverain_app.main import creer_application_complete


async def _client_pour(utilisateur: UserRecord) -> AsyncIterator[AsyncClient]:
    app = creer_application_complete()
    jwt_settings = get_jwt_settings()
    dashboard_settings = get_dashboard_settings()

    jeton = create_access_token(
        user_id=utilisateur.user_id,
        tenant_id=utilisateur.tenant_id,
        role=utilisateur.role,
        token_version=utilisateur.token_version,
        settings=jwt_settings,
    )

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            cookies={dashboard_settings.cookie_name: jeton},
        ) as ac:
            yield ac
    finally:
        # Le pool dédié de la Brique 8 est un singleton créé paresseusement
        # par la ROUTE elle-même (create_audit_pool()), jamais fermé par
        # une fixture pool_audit ici — ces tests HTTP ne la demandent
        # jamais dans leur signature. pytest-asyncio isole chaque test
        # dans sa PROPRE boucle asyncio (scope function, défaut) : un pool
        # créé dans la boucle du test 1 et laissé ouvert devient inutili-
        # sable au test 2 (boucle déjà fermée) — RuntimeError "Event loop
        # is closed" / "attached to a different loop". Même bug de fond
        # déjà rencontré et corrigé pour le driver Neo4j en Brique 7
        # (close_driver() en teardown de la fixture client) — je ne
        # l'avais pas transposé à mon propre pool. Fermer ici, à chaque
        # fin de test, garantit un pool toujours frais pour le suivant.
        await close_audit_pool()


@pytest_asyncio.fixture
async def client_analyst(utilisateur_analyst_test: UserRecord) -> AsyncIterator[AsyncClient]:
    async for ac in _client_pour(utilisateur_analyst_test):
        yield ac


@pytest_asyncio.fixture
async def client_auditor(utilisateur_auditor_test: UserRecord) -> AsyncIterator[AsyncClient]:
    async for ac in _client_pour(utilisateur_auditor_test):
        yield ac


@pytest.mark.asyncio
async def test_fragment_affiche_le_formulaire_pour_un_analyst(
    client_analyst: AsyncClient, alerte_test: UUID
) -> None:
    reponse = await client_analyst.get(f"/alertes/{alerte_test}/fermeture")
    assert reponse.status_code == 200
    assert "fermeture.bouton" not in reponse.text  # clé traduite, pas la clé brute
    assert "<form" in reponse.text
    assert NOM_COOKIE_CSRF in reponse.cookies


@pytest.mark.asyncio
async def test_fragment_masque_le_formulaire_pour_un_auditor(
    client_auditor: AsyncClient, alerte_test: UUID
) -> None:
    reponse = await client_auditor.get(f"/alertes/{alerte_test}/fermeture")
    assert reponse.status_code == 200
    assert "<form" not in reponse.text  # auditor : historique seul, pas de formulaire


@pytest.mark.asyncio
async def test_fermeture_refusee_pour_un_auditor(
    client_auditor: AsyncClient, alerte_test: UUID
) -> None:
    # RBAC appliqué même si le formulaire n'est pas affiché — un POST
    # direct (URL forgée) doit être refusé indépendamment de l'UI.
    await client_auditor.get(f"/alertes/{alerte_test}/fermeture")
    jeton_csrf = client_auditor.cookies.get(NOM_COOKIE_CSRF)

    reponse = await client_auditor.post(
        f"/alertes/{alerte_test}/fermeture",
        data={"motif": "confirme", "jeton_csrf": jeton_csrf},
    )
    assert reponse.status_code == 403


@pytest.mark.asyncio
async def test_fermeture_refusee_sans_jeton_csrf_valide(
    client_analyst: AsyncClient, alerte_test: UUID
) -> None:
    await client_analyst.get(f"/alertes/{alerte_test}/fermeture")  # pose le cookie CSRF

    reponse = await client_analyst.post(
        f"/alertes/{alerte_test}/fermeture",
        data={"motif": "confirme", "jeton_csrf": "jeton-invente-par-un-attaquant"},
    )
    assert reponse.status_code == 403


@pytest.mark.asyncio
async def test_fermeture_reussie_pour_un_analyst_avec_csrf_valide(
    client_analyst: AsyncClient, alerte_test: UUID
) -> None:
    await client_analyst.get(f"/alertes/{alerte_test}/fermeture")
    jeton_csrf = client_analyst.cookies.get(NOM_COOKIE_CSRF)
    assert jeton_csrf is not None

    reponse = await client_analyst.post(
        f"/alertes/{alerte_test}/fermeture",
        data={
            "motif": "confirme",
            "commentaire": "Confirmé après vérification manuelle.",
            "jeton_csrf": jeton_csrf,
        },
    )
    assert reponse.status_code == 200
    assert "<form" not in reponse.text  # plus rien à fermer, formulaire disparu


@pytest.mark.asyncio
async def test_fermeture_deja_fermee_retourne_409(
    client_analyst: AsyncClient, alerte_test: UUID
) -> None:
    await client_analyst.get(f"/alertes/{alerte_test}/fermeture")
    jeton_csrf = client_analyst.cookies.get(NOM_COOKIE_CSRF)

    premiere = await client_analyst.post(
        f"/alertes/{alerte_test}/fermeture",
        data={"motif": "confirme", "jeton_csrf": jeton_csrf},
    )
    assert premiere.status_code == 200

    deuxieme = await client_analyst.post(
        f"/alertes/{alerte_test}/fermeture",
        data={"motif": "faux_positif", "jeton_csrf": jeton_csrf},
    )
    assert deuxieme.status_code == 409
