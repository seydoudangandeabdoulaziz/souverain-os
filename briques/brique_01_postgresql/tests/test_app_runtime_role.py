"""Vérifie en base les privilèges effectifs du rôle web, sans écrire de données."""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import asyncpg
import pytest
import pytest_asyncio
from brique_01_postgresql import connection
from brique_01_postgresql.config import RuntimePostgresSettings
from brique_01_postgresql.connection import close_runtime_pool, create_runtime_pool
from pydantic import SecretStr, ValidationError


def test_runtime_settings_ne_peuvent_pas_reprendre_le_compte_admin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = RuntimePostgresSettings(  # type: ignore[call-arg]
        _env_file=None, password=SecretStr("x" * 48)
    )
    assert settings.user == "souverain_app"

    monkeypatch.delenv("APP_POSTGRES_PASSWORD", raising=False)
    with pytest.raises(ValidationError):
        RuntimePostgresSettings(  # type: ignore[call-arg]
            _env_file=None,
            user="souverain_admin",
            password=SecretStr("x" * 48),
        )


@pytest.mark.asyncio
async def test_pool_runtime_utilise_uniquement_le_role_dedie(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pool = AsyncMock()
    create_mock = AsyncMock(return_value=pool)
    monkeypatch.setattr(connection.asyncpg, "create_pool", create_mock)
    await close_runtime_pool()

    settings = RuntimePostgresSettings(  # type: ignore[call-arg]
        _env_file=None,
        user="souverain_app",
        password=SecretStr("x" * 48),
    )
    await create_runtime_pool(settings)

    assert create_mock.await_args is not None
    assert create_mock.await_args.kwargs["dsn"].startswith("postgresql://souverain_app:")
    await close_runtime_pool()


@pytest_asyncio.fixture
async def runtime_pool() -> AsyncIterator[asyncpg.Pool]:
    try:
        pool = await create_runtime_pool()
    except (ConnectionRefusedError, ValidationError):
        pytest.skip(
            "Rôle souverain_app inactif ou non configuré : appliquer la migration 0006, "
            "activer le rôle et renseigner APP_POSTGRES_PASSWORD."
        )
    try:
        yield pool
    finally:
        await close_runtime_pool()


async def test_runtime_role_is_not_privileged_and_has_only_required_access(
    runtime_pool: asyncpg.Pool,
) -> None:
    async with runtime_pool.acquire() as connection:
        role = await connection.fetchrow(
            """
            SELECT r.rolname, r.rolsuper, r.rolbypassrls, r.rolcreaterole,
                   r.rolcreatedb, r.rolcanlogin, current_user = r.rolname AS is_current
            FROM pg_roles AS r
            WHERE r.rolname = current_user
            """
        )
        assert role is not None
        assert role["rolname"] == "souverain_app"
        assert role["is_current"] is True
        assert role["rolcanlogin"] is True
        assert role["rolsuper"] is False
        assert role["rolbypassrls"] is False
        assert role["rolcreaterole"] is False
        assert role["rolcreatedb"] is False

        assert await connection.fetchval(
            "SELECT has_table_privilege(current_user, 'shared.tenants_registry', 'SELECT')"
        )
        assert not await connection.fetchval(
            "SELECT has_table_privilege(current_user, 'shared.users', 'SELECT')"
        )
