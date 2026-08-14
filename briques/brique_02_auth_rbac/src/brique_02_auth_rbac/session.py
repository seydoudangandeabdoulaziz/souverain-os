"""
Résolution de la session utilisateur courante à partir d'un jeton JWT.

C'est le point de jonction entre jwt_tokens.py (décodage du jeton) et
repository.py (vérification que l'utilisateur existe toujours, est
actif, et que le jeton n'a pas été révoqué via token_version).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from brique_01_postgresql.connection import create_pool
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from brique_02_auth_rbac.config import JwtSettings, get_jwt_settings
from brique_02_auth_rbac.jwt_tokens import ExpiredTokenError, InvalidTokenError, decode_token
from brique_02_auth_rbac.repository import get_user_by_id

_bearer_scheme = HTTPBearer(auto_error=True)


@dataclass(frozen=True)
class AuthenticatedUser:
    """Session résolue et validée d'un utilisateur authentifié."""

    user_id: uuid.UUID
    tenant_id: uuid.UUID
    role: str
    souverain_id: uuid.UUID


def _unauthorized(detail: str) -> HTTPException:
    """
    Construit une 401 générique.

    Le détail exposé à l'appelant reste volontairement vague — ne
    jamais révéler si c'est le jeton, l'utilisateur ou le
    token_version qui a échoué, pour ne pas donner d'information
    exploitable à un attaquant.
    """
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),  # noqa: B008
    jwt_settings: JwtSettings = Depends(get_jwt_settings),  # noqa: B008
) -> AuthenticatedUser:
    """
    Dépendance FastAPI : résout et valide l'utilisateur courant.

    Étapes de validation, dans l'ordre :
    1. Signature et expiration du jeton (jwt_tokens.decode_token).
    2. L'utilisateur existe toujours en base.
    3. Le compte est toujours actif.
    4. Le token_version du jeton correspond à celui en base (sinon
       le jeton a été révoqué — changement de mot de passe ou
       désactivation survenue après son émission).
    """
    try:
        payload = decode_token(credentials.credentials, jwt_settings)
    except (ExpiredTokenError, InvalidTokenError) as exc:
        raise _unauthorized("Session invalide, merci de vous reconnecter.") from exc

    pool = await create_pool()
    async with pool.acquire() as connection:
        user = await get_user_by_id(connection, payload.user_id)

    if user is None or not user.is_active or user.token_version != payload.token_version:
        raise _unauthorized("Session invalide, merci de vous reconnecter.")

    return AuthenticatedUser(
        user_id=user.user_id,
        tenant_id=user.tenant_id,
        role=user.role,
        souverain_id=user.souverain_id,
    )
