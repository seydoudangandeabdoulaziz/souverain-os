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
) -> Callable[[AuthenticatedUser], Coroutine[Any, Any, AuthenticatedUser]]:
    """
    Fabrique une dépendance FastAPI qui n'autorise l'accès qu'aux
    utilisateurs authentifiés ayant l'un des rôles listés.

    Usage :
        @router.get("/admin-only")
        async def admin_only(user: AuthenticatedUser = Depends(require_role(Role.ADMIN))):
            ...
    """

    async def _dependency(
        user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
    ) -> AuthenticatedUser:
        if user.role not in {role.value for role in allowed_roles}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Vous n'avez pas les droits nécessaires pour cette action.",
            )
        return user

    return _dependency
