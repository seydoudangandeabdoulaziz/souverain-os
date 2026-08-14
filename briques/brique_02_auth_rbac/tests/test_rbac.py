"""
Tests unitaires — rbac.py (aucune DB requise).

require_role() retourne une dépendance FastAPI. On peut l'appeler
directement en lui passant un AuthenticatedUser construit à la main
(le paramètre `Depends(get_current_user)` n'est qu'une valeur par
défaut, ignorée dès qu'on fournit explicitement `user=...`).
"""

from __future__ import annotations

import uuid

import pytest
from brique_02_auth_rbac.rbac import Role, require_role
from brique_02_auth_rbac.session import AuthenticatedUser
from fastapi import HTTPException


def _fake_user(role: str) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=uuid.uuid4(), tenant_id=uuid.uuid4(), role=role, souverain_id=uuid.uuid4()
    )


async def test_require_role_accepts_matching_role() -> None:
    dependency = require_role(Role.ADMIN)
    admin_user = _fake_user("admin")

    result = await dependency(user=admin_user)

    assert result is admin_user


async def test_require_role_rejects_non_matching_role() -> None:
    dependency = require_role(Role.ADMIN)
    analyst_user = _fake_user("analyst")

    with pytest.raises(HTTPException) as exc_info:
        await dependency(user=analyst_user)

    assert exc_info.value.status_code == 403


async def test_require_role_accepts_any_of_multiple_roles() -> None:
    dependency = require_role(Role.ADMIN, Role.AUDITOR)

    assert await dependency(user=_fake_user("auditor")) is not None
    assert await dependency(user=_fake_user("admin")) is not None

    with pytest.raises(HTTPException):
        await dependency(user=_fake_user("analyst"))
