"""
RBAC minimal — 3 rôles fixes (MVP).

Ce module ne fait QUE la vérification de rôle. Il s'appuie sur
session.get_current_user pour savoir QUI fait la demande, et se
contente de vérifier QUEL rôle cette personne a le droit d'avoir
pour accéder à une route donnée.

Hors périmètre (voir README.md) : permissions granulaires par
ressource/action — réservé à la Brique 8.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from enum import StrEnum
from typing import Any

from fastapi import Depends, HTTPException, status

from brique_02_auth_rbac.session import AuthenticatedUser, get_current_user


class Role(StrEnum):
    """Les 3 rôles MVP de SOUVERAIN-OS."""

    ADMIN = "admin"
    ANALYST = "analyst"
    AUDITOR = "auditor"


def require_role(
    *allowed_roles: Role,
    user_dependency: Callable[..., Coroutine[Any, Any, AuthenticatedUser]] = get_current_user,
) -> Callable[[AuthenticatedUser], Coroutine[Any, Any, AuthenticatedUser]]:
    """
    Fabrique une dépendance FastAPI qui n'autorise l'accès qu'aux
    utilisateurs authentifiés ayant l'un des rôles listés.

    Usage (API pure, header Authorization: Bearer) :
        @router.get("/admin-only")
        async def admin_only(user: AuthenticatedUser = Depends(require_role(Role.ADMIN))):
            ...

    Usage (dashboard cookie, Brique 7/8) :
        require_role(Role.ANALYST, Role.ADMIN, user_dependency=get_current_user_from_cookie)

    Retouche validée à l'analyse de la Brique 8 (28-29 août 2026) :
    get_current_user (défaut, HTTPBearer) ne convient qu'à une API JSON
    pure. Le dashboard (Brique 7) résout déjà la session via un cookie
    httpOnly (get_current_user_from_cookie, brique_07_dashboard) — sans
    ce paramètre, require_role() était inutilisable pour toute route
    nécessitant à la fois une vérification de rôle ET une session
    cookie (Brique 8 : fermeture d'alerte). user_dependency est
    rétrocompatible : sa valeur par défaut est get_current_user,
    exactement le comportement d'avant cette retouche — aucune
    régression pour les appelants existants (voir test_rbac.py,
    inchangé par cette modification).
    """

    async def _dependency(
        user: AuthenticatedUser = Depends(user_dependency),  # noqa: B008
    ) -> AuthenticatedUser:
        if user.role not in {role.value for role in allowed_roles}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Vous n'avez pas les droits nécessaires pour cette action.",
            )
        return user

    return _dependency
