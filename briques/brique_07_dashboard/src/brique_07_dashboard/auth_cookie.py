"""Authentification par cookie httpOnly — Option A validée à l'analyse.

brique_02_auth_rbac.session.get_current_user attend un header
`Authorization: Bearer <token>` (HTTPBearer), adapté à une API JSON
mais pas à un dashboard HTMX où le navigateur ne l'attache pas
automatiquement sur une navigation normale.

Ce module réutilise les PRIMITIVES de la Brique 2
(jwt_tokens.decode_token, repository.get_user_by_id) — jamais le
wrapper HTTPBearer — pour construire un équivalent qui lit le jeton
depuis un cookie. Aucune modification de brique_02_auth_rbac (déjà
validée) : c'est un nouvel adaptateur, pas une réécriture.
"""

from __future__ import annotations

from brique_01_postgresql.connection import create_pool
from brique_02_auth_rbac.config import JwtSettings, get_jwt_settings
from brique_02_auth_rbac.jwt_tokens import ExpiredTokenError, InvalidTokenError, decode_token
from brique_02_auth_rbac.repository import get_user_by_id
from brique_02_auth_rbac.session import AuthenticatedUser
from fastapi import Depends, Request

from brique_07_dashboard.config import DashboardSettings, get_dashboard_settings


class SessionInvalide(Exception):
    """Cookie absent, jeton invalide/expiré, ou utilisateur révoqué.

    Levée plutôt qu'une HTTPException directe : app.py y attache un
    exception_handler qui redirige vers /login (comportement web
    attendu), plutôt qu'une réponse 401 JSON brute — inadapté à un
    dashboard consulté dans un navigateur.
    """


async def get_current_user_from_cookie(
    request: Request,
    jwt_settings: JwtSettings = Depends(get_jwt_settings),  # noqa: B008
    dashboard_settings: DashboardSettings = Depends(get_dashboard_settings),  # noqa: B008
) -> AuthenticatedUser:
    """Équivalent de get_current_user (Brique 2), source cookie au lieu d'un header.

    Mêmes étapes de validation que la Brique 2, dans le même ordre :
    1. Cookie présent.
    2. Signature et expiration du jeton.
    3. L'utilisateur existe toujours, est actif, token_version à jour
       (révocation immédiate déjà gérée par la Brique 2 — réutilisée
       telle quelle, pas réimplémentée).
    """
    jeton = request.cookies.get(dashboard_settings.cookie_name)
    if jeton is None:
        raise SessionInvalide("Aucun cookie de session.")

    try:
        payload = decode_token(jeton, jwt_settings)
    except (ExpiredTokenError, InvalidTokenError) as exc:
        raise SessionInvalide("Session invalide, merci de vous reconnecter.") from exc

    pool = await create_pool()
    async with pool.acquire() as connection:
        user = await get_user_by_id(connection, payload.user_id)

    if user is None or not user.is_active or user.token_version != payload.token_version:
        raise SessionInvalide("Session invalide, merci de vous reconnecter.")

    return AuthenticatedUser(
        user_id=user.user_id,
        tenant_id=user.tenant_id,
        role=user.role,
        souverain_id=user.souverain_id,
    )
