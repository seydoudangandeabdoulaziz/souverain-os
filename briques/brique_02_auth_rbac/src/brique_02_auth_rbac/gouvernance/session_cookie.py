"""
Authentification par cookie httpOnly — DUPLIQUÉE depuis
brique_07_dashboard.auth_cookie, pas importée.

Pourquoi une duplication et pas un import : Brique 2 est censée être
EN AMONT de Brique 7 dans le graphe de dépendances (Brique 7 dépend de
Brique 2 pour l'auth/RBAC, jamais l'inverse). Importer
get_current_user_from_cookie depuis brique_07_dashboard ici inverserait
ce graphe. Duplication minimale et explicite, décision validée à
l'analyse — même principe que Brique 7 avait déjà appliqué en
dupliquant (plutôt qu'en réutilisant à l'identique) la logique de
session de cette même Brique 2 pour son propre besoin cookie.

Ne réutilise PAS non plus tenant_valide (Brique 7) pour la même
raison — cette extension n'en a de toute façon pas besoin : un `admin`
gérant les comptes de SON tenant utilise directement
utilisateur.tenant_id (déjà présent dans AuthenticatedUser), pas une
revalidation séparée de l'état actif du tenant lui-même (hors périmètre
de cette extension, qui ne gère jamais l'état d'un tenant — c'est le
rôle de la Brique 1).
"""

from __future__ import annotations

from brique_01_postgresql.connection import create_pool
from fastapi import Depends, Request

from brique_02_auth_rbac.config import JwtSettings, get_jwt_settings
from brique_02_auth_rbac.gouvernance.config import (
    GouvernanceCookieSettings,
    get_gouvernance_cookie_settings,
)
from brique_02_auth_rbac.jwt_tokens import ExpiredTokenError, InvalidTokenError, decode_token
from brique_02_auth_rbac.repository import get_user_by_id
from brique_02_auth_rbac.session import AuthenticatedUser


class SessionInvalideError(Exception):
    """Cookie absent, jeton invalide/expiré, ou utilisateur révoqué."""


async def get_current_user_from_cookie(
    request: Request,
    jwt_settings: JwtSettings = Depends(get_jwt_settings),  # noqa: B008
    cookie_settings: GouvernanceCookieSettings = Depends(get_gouvernance_cookie_settings),  # noqa: B008
) -> AuthenticatedUser:
    """Équivalent de get_current_user (Brique 2), source cookie au lieu d'un header.

    Mêmes étapes de validation que brique_07_dashboard.auth_cookie,
    dupliquées ici intentionnellement (voir docstring du module).
    """
    jeton = request.cookies.get(cookie_settings.cookie_name)
    if jeton is None:
        raise SessionInvalideError("Aucun cookie de session.")

    try:
        payload = decode_token(jeton, jwt_settings)
    except (ExpiredTokenError, InvalidTokenError) as exc:
        raise SessionInvalideError("Session invalide, merci de vous reconnecter.") from exc

    pool = await create_pool()
    async with pool.acquire() as connection:
        user = await get_user_by_id(connection, payload.user_id)

    if user is None or not user.is_active or user.token_version != payload.token_version:
        raise SessionInvalideError("Session invalide, merci de vous reconnecter.")

    return AuthenticatedUser(
        user_id=user.user_id,
        tenant_id=user.tenant_id,
        role=user.role,
        souverain_id=user.souverain_id,
    )
