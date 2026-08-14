"""Tests unitaires — jwt_tokens.py (aucune DB requise)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from brique_02_auth_rbac.config import JwtSettings
from brique_02_auth_rbac.jwt_tokens import (
    ExpiredTokenError,
    InvalidTokenError,
    create_access_token,
    decode_token,
)

_SETTINGS = JwtSettings(
    _env_file=None, secret_key="test-secret-key-suffisamment-longue-32b", expiration_hours=1
)


def test_create_and_decode_token_roundtrip() -> None:
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    token = create_access_token(
        user_id=user_id, tenant_id=tenant_id, role="analyst", token_version=1, settings=_SETTINGS
    )
    payload = decode_token(token, _SETTINGS)

    assert payload.user_id == user_id
    assert payload.tenant_id == tenant_id
    assert payload.role == "analyst"
    assert payload.token_version == 1


def test_decode_token_rejects_tampered_signature() -> None:
    token = create_access_token(
        user_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        role="admin",
        token_version=1,
        settings=_SETTINGS,
    )
    wrong_settings = JwtSettings(_env_file=None, secret_key="autre-secret-egalement-assez-long-32")

    with pytest.raises(InvalidTokenError):
        decode_token(token, wrong_settings)


def test_decode_token_rejects_expired_token() -> None:
    now = datetime.now(UTC)
    expired_payload = {
        "sub": str(uuid.uuid4()),
        "tenant_id": str(uuid.uuid4()),
        "role": "auditor",
        "token_version": 1,
        "iat": now - timedelta(hours=2),
        "exp": now - timedelta(hours=1),
    }
    expired_token = jwt.encode(expired_payload, _SETTINGS.secret_key, algorithm=_SETTINGS.algorithm)

    with pytest.raises(ExpiredTokenError):
        decode_token(expired_token, _SETTINGS)


def test_decode_token_rejects_missing_claims() -> None:
    incomplete_payload = {"sub": str(uuid.uuid4())}  # tenant_id/role/token_version manquants
    token = jwt.encode(incomplete_payload, _SETTINGS.secret_key, algorithm=_SETTINGS.algorithm)

    with pytest.raises(InvalidTokenError):
        decode_token(token, _SETTINGS)
