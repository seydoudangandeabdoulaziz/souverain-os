"""
Routes de l'extension gouvernance (Brique 2 V2) — gestion des comptes
utilisateurs, réservée au rôle `admin`, strictement limitée au tenant
de l'appelant.

Réutilise require_role() (Brique 2, ce module fait DÉJÀ partie de
Brique 2 — aucune duplication nécessaire ici, contrairement à
session_cookie.py/csrf.py qui dupliquent des mécanismes d'AUTRES
briques). Instance Jinja2Templates propre, comme la Brique 8.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.templating import Jinja2Templates

from brique_02_auth_rbac.gouvernance.connection import create_gouvernance_web_pool
from brique_02_auth_rbac.gouvernance.csrf import (
    obtenir_ou_generer_jeton_csrf,
    poser_cookie_csrf,
    verifier_csrf,
)
from brique_02_auth_rbac.gouvernance.lecture import (
    lire_historique_gouvernance,
    lister_utilisateurs_du_tenant,
)
from brique_02_auth_rbac.gouvernance.persistence import (
    AutoModificationInterditeError,
    UtilisateurHorsTenantError,
    UtilisateurIntrouvableError,
    changer_role_utilisateur,
    creer_utilisateur,
    desactiver_utilisateur,
    reactiver_utilisateur,
)
from brique_02_auth_rbac.gouvernance.session_cookie import get_current_user_from_cookie
from brique_02_auth_rbac.gouvernance.traductions import t
from brique_02_auth_rbac.rbac import Role, require_role
from brique_02_auth_rbac.repository import EmailAlreadyExistsError, RoleInvalideError
from brique_02_auth_rbac.session import AuthenticatedUser

_REPERTOIRE_TEMPLATES = Path(__file__).resolve().parent / "templates"


def construire_routes_gouvernance() -> APIRouter:
    router = APIRouter(tags=["gouvernance"])
    templates = Jinja2Templates(directory=str(_REPERTOIRE_TEMPLATES))
    templates.env.globals["t"] = t

    async def _rendre_page(
        request: Request, utilisateur: AuthenticatedUser, erreur: str | None = None
    ):
        pool = await create_gouvernance_web_pool()
        async with pool.acquire() as connexion:
            utilisateurs = await lister_utilisateurs_du_tenant(connexion, utilisateur.tenant_id)
            historique = await lire_historique_gouvernance(connexion, utilisateur.tenant_id)
        jeton_csrf, doit_poser_cookie = obtenir_ou_generer_jeton_csrf(request)

        reponse = templates.TemplateResponse(
            request,
            "liste_utilisateurs.html",
            {
                "utilisateurs": utilisateurs,
                "historique": historique,
                "utilisateur_courant_id": utilisateur.user_id,
                "jeton_csrf": jeton_csrf,
                "erreur": erreur,
            },
        )
        if doit_poser_cookie:
            poser_cookie_csrf(reponse, jeton_csrf)
        return reponse

    @router.get("/utilisateurs")
    async def liste_utilisateurs(
        request: Request,
        utilisateur: AuthenticatedUser = Depends(  # noqa: B008
            require_role(Role.ADMIN, user_dependency=get_current_user_from_cookie)  # noqa: B008
        ),
    ):
        return await _rendre_page(request, utilisateur)

    @router.post("/utilisateurs")
    async def creer(
        request: Request,
        email: str = Form(...),
        mot_de_passe: str = Form(...),
        role: str = Form(...),
        jeton_csrf: str = Form(...),
        utilisateur: AuthenticatedUser = Depends(  # noqa: B008
            require_role(Role.ADMIN, user_dependency=get_current_user_from_cookie)  # noqa: B008
        ),
    ):
        verifier_csrf(request, jeton_csrf)
        pool = await create_gouvernance_web_pool()
        try:
            async with pool.acquire() as connexion:
                await creer_utilisateur(
                    connexion,
                    tenant_id=utilisateur.tenant_id,
                    email=email,
                    mot_de_passe_clair=mot_de_passe,
                    role=role,
                    acteur_user_id=utilisateur.user_id,
                )
        except EmailAlreadyExistsError:
            return await _rendre_page(
                request, utilisateur, erreur="gouvernance.erreur_email_existe"
            )
        except RoleInvalideError:
            return await _rendre_page(
                request, utilisateur, erreur="gouvernance.erreur_role_invalide"
            )

        return await _rendre_page(request, utilisateur)

    @router.post("/utilisateurs/{cible_id}/role")
    async def changer_role(
        request: Request,
        cible_id: UUID,
        role: str = Form(...),
        jeton_csrf: str = Form(...),
        utilisateur: AuthenticatedUser = Depends(  # noqa: B008
            require_role(Role.ADMIN, user_dependency=get_current_user_from_cookie)  # noqa: B008
        ),
    ):
        verifier_csrf(request, jeton_csrf)
        pool = await create_gouvernance_web_pool()
        try:
            async with pool.acquire() as connexion:
                await changer_role_utilisateur(
                    connexion,
                    cible_user_id=cible_id,
                    nouveau_role=role,
                    tenant_id_appelant=utilisateur.tenant_id,
                    acteur_user_id=utilisateur.user_id,
                )
        except AutoModificationInterditeError as exc:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
        except UtilisateurHorsTenantError as exc:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
        except UtilisateurIntrouvableError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except RoleInvalideError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        return await _rendre_page(request, utilisateur)

    @router.post("/utilisateurs/{cible_id}/desactivation")
    async def desactiver(
        request: Request,
        cible_id: UUID,
        jeton_csrf: str = Form(...),
        utilisateur: AuthenticatedUser = Depends(  # noqa: B008
            require_role(Role.ADMIN, user_dependency=get_current_user_from_cookie)  # noqa: B008
        ),
    ):
        verifier_csrf(request, jeton_csrf)
        pool = await create_gouvernance_web_pool()
        try:
            async with pool.acquire() as connexion:
                await desactiver_utilisateur(
                    connexion,
                    cible_user_id=cible_id,
                    tenant_id_appelant=utilisateur.tenant_id,
                    acteur_user_id=utilisateur.user_id,
                )
        except AutoModificationInterditeError as exc:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
        except UtilisateurHorsTenantError as exc:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
        except UtilisateurIntrouvableError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

        return await _rendre_page(request, utilisateur)

    @router.post("/utilisateurs/{cible_id}/reactivation")
    async def reactiver(
        request: Request,
        cible_id: UUID,
        jeton_csrf: str = Form(...),
        utilisateur: AuthenticatedUser = Depends(  # noqa: B008
            require_role(Role.ADMIN, user_dependency=get_current_user_from_cookie)  # noqa: B008
        ),
    ):
        verifier_csrf(request, jeton_csrf)
        pool = await create_gouvernance_web_pool()
        try:
            async with pool.acquire() as connexion:
                await reactiver_utilisateur(
                    connexion,
                    cible_user_id=cible_id,
                    tenant_id_appelant=utilisateur.tenant_id,
                    acteur_user_id=utilisateur.user_id,
                )
        except UtilisateurHorsTenantError as exc:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
        except UtilisateurIntrouvableError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

        return await _rendre_page(request, utilisateur)

    return router
