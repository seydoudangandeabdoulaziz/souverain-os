"""
Routeur FastAPI d'authentification.

Périmètre de cette brique : /auth/login et /auth/me uniquement.

Note de périmètre : la CRÉATION de comptes utilisateurs n'est PAS
exposée via une route publique dans cette brique (pas dans le
périmètre validé). Elle se fait pour l'instant via
repository.create_user() directement (utilisé par les tests et par
un futur script d'administration). Une route d'administration dédiée,
protégée par RBAC, pourra être ajoutée par une brique future sans
remettre en cause ce qui est livré ici.
"""

from __future__ import annotations

from brique_01_postgresql.connection import create_pool
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr

from brique_02_auth_rbac.config import JwtSettings, get_jwt_settings
from brique_02_auth_rbac.jwt_tokens import create_access_token
from brique_02_auth_rbac.password_hashing import verify_password
from brique_02_auth_rbac.repository import get_user_by_email, touch_last_login
from brique_02_auth_rbac.session import AuthenticatedUser, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    user_id: str
    tenant_id: str
    role: str
    souverain_id: str


def _invalid_credentials() -> HTTPException:
    """
    401 générique — ne révèle jamais si c'est l'email ou le mot de
    passe qui est incorrect (protection contre l'énumération de
    comptes existants).
    """
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Email ou mot de passe incorrect.",
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    credentials: LoginRequest,
    jwt_settings: JwtSettings = Depends(get_jwt_settings),  # noqa: B008 — pattern FastAPI standard
) -> LoginResponse:
    pool = await create_pool()
    async with pool.acquire() as connection:
        user = await get_user_by_email(connection, credentials.email)

        # Vérification systématique du hash même si l'utilisateur
        # n'existe pas (avec un hash "factice"), pour que le temps de
        # réponse ne révèle pas l'existence d'un compte. Ici, on garde
        # une version simple : si user est None, on rejette directement
        # (acceptable en MVP, cf. README pour la nuance sur les
        # attaques par mesure de temps).
        if user is None or not verify_password(credentials.password, user.password_hash):
            raise _invalid_credentials()

        if not user.is_active:
            raise _invalid_credentials()

        await touch_last_login(connection, user.user_id)

    token = create_access_token(
        user_id=user.user_id,
        tenant_id=user.tenant_id,
        role=user.role,
        token_version=user.token_version,
        settings=jwt_settings,
    )
    return LoginResponse(access_token=token)


@router.get("/me", response_model=MeResponse)
async def me(
    user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> MeResponse:
    return MeResponse(
        user_id=str(user.user_id),
        tenant_id=str(user.tenant_id),
        role=user.role,
        souverain_id=str(user.souverain_id),
    )
