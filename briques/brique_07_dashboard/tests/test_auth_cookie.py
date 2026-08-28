"""Tests de l'adaptateur cookie — lit le JWT depuis un cookie, réutilise
les primitives de la Brique 2 (jamais HTTPBearer).

⚠️ NON VÉRIFIÉ dans l'environnement de génération (pas de PostgreSQL
disponible) — à exécuter sur ta machine réelle.
"""

from __future__ import annotations

import asyncpg
import pytest
from brique_02_auth_rbac.config import get_jwt_settings
from brique_02_auth_rbac.jwt_tokens import create_access_token
from brique_02_auth_rbac.repository import UserRecord
from brique_07_dashboard.auth_cookie import SessionInvalide, get_current_user_from_cookie
from brique_07_dashboard.config import get_dashboard_settings
from starlette.requests import Request


def _fausse_requete(cookies: dict[str, str]) -> Request:
    """Construit une Request Starlette minimale portant les cookies donnés."""
    en_tete_cookie = "; ".join(f"{k}={v}" for k, v in cookies.items())
    scope = {
        "type": "http",
        "headers": [(b"cookie", en_tete_cookie.encode())] if cookies else [],
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_aucun_cookie_leve_session_invalide() -> None:
    requete = _fausse_requete({})
    with pytest.raises(SessionInvalide):
        await get_current_user_from_cookie(
            requete, get_jwt_settings(), get_dashboard_settings()
        )


@pytest.mark.asyncio
async def test_cookie_avec_jeton_invalide_leve_session_invalide() -> None:
    dashboard_settings = get_dashboard_settings()
    requete = _fausse_requete({dashboard_settings.cookie_name: "ceci-nest-pas-un-jwt-valide"})
    with pytest.raises(SessionInvalide):
        await get_current_user_from_cookie(requete, get_jwt_settings(), dashboard_settings)


@pytest.mark.asyncio
async def test_cookie_avec_jeton_valide_resout_utilisateur(
    pool: asyncpg.Pool, utilisateur_test: UserRecord
) -> None:
    jwt_settings = get_jwt_settings()
    dashboard_settings = get_dashboard_settings()

    jeton = create_access_token(
        user_id=utilisateur_test.user_id,
        tenant_id=utilisateur_test.tenant_id,
        role=utilisateur_test.role,
        token_version=utilisateur_test.token_version,
        settings=jwt_settings,
    )
    requete = _fausse_requete({dashboard_settings.cookie_name: jeton})

    resultat = await get_current_user_from_cookie(requete, jwt_settings, dashboard_settings)

    assert resultat.user_id == utilisateur_test.user_id
    assert resultat.tenant_id == utilisateur_test.tenant_id
