"""Routes d'authentification du dashboard.

Réutilise directement verify_password/get_user_by_email/
create_access_token de la Brique 2 — la logique de vérification
elle-même n'est jamais dupliquée, seule la source du jeton change
(cookie au lieu d'un header, voir auth_cookie.py).
"""

from __future__ import annotations

from brique_01_postgresql.connection import create_pool
from brique_02_auth_rbac.config import get_jwt_settings
from brique_02_auth_rbac.jwt_tokens import create_access_token
from brique_02_auth_rbac.password_hashing import verify_password
from brique_02_auth_rbac.repository import get_user_by_email, touch_last_login
from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from brique_07_dashboard.config import get_dashboard_settings

router = APIRouter(tags=["auth"])


def construire_routes_auth(templates: Jinja2Templates) -> APIRouter:
    @router.get("/login")
    async def formulaire_login(request: Request) -> object:
        return templates.TemplateResponse(request, "login.html", {"erreur": None})

    @router.post("/login")
    async def soumettre_login(
        request: Request, email: str = Form(...), mot_de_passe: str = Form(...)
    ) -> object:
        pool = await create_pool()
        async with pool.acquire() as connexion:
            utilisateur = await get_user_by_email(connexion, email)

            # Vérification à temps constant même si l'email n'existe
            # pas : verify_password est appelée dans tous les cas
            # (contre un hash factice si l'utilisateur est absent),
            # pour ne jamais laisser un attaquant distinguer "email
            # inconnu" de "mauvais mot de passe" par la durée de
            # réponse — même esprit défensif que _invalid_credentials
            # côté Brique 2.
            hash_a_verifier = (
                utilisateur.password_hash
                if utilisateur is not None
                else "$argon2id$v=19$m=65536,t=3,p=4$ZmFrZXNhbHQAAAAAAAAAAA$ZmFrZWhhc2g"
            )
            mot_de_passe_valide = verify_password(mot_de_passe, hash_a_verifier)

            if utilisateur is None or not utilisateur.is_active or not mot_de_passe_valide:
                return templates.TemplateResponse(
                    request,
                    "login.html",
                    {"erreur": "login.erreur"},
                    status_code=401,
                )

            await touch_last_login(connexion, utilisateur.user_id)

        jwt_settings = get_jwt_settings()
        dashboard_settings = get_dashboard_settings()

        jeton = create_access_token(
            user_id=utilisateur.user_id,
            tenant_id=utilisateur.tenant_id,
            role=utilisateur.role,
            token_version=utilisateur.token_version,
            settings=jwt_settings,
        )

        reponse = RedirectResponse(url="/alertes", status_code=303)
        reponse.set_cookie(
            key=dashboard_settings.cookie_name,
            value=jeton,
            httponly=True,
            secure=dashboard_settings.cookie_secure,
            samesite="lax",
            max_age=jwt_settings.expiration_hours * 3600,
        )
        return reponse

    @router.post("/logout")
    async def logout() -> object:
        dashboard_settings = get_dashboard_settings()
        reponse = RedirectResponse(url="/login", status_code=303)
        reponse.delete_cookie(dashboard_settings.cookie_name)
        return reponse

    return router
