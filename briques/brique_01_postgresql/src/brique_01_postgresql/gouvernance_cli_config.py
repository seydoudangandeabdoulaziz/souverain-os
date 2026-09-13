"""
Configuration du rôle PostgreSQL dédié au CLI de gouvernance de
tenants — même principe que AuditDbSettings (Brique 8) : host/port/db
restent ceux de PostgresSettings (une seule source de vérité "où se
trouve la base"), seuls user/password diffèrent parce que ce pool se
connecte avec un rôle DIFFÉRENT de souverain_admin.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file() -> str | None:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / ".env"
        if candidate.is_file():
            return str(candidate)
    return None


_ENV_FILE = _find_env_file()


class GouvernanceCliDbSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GOUVERNANCE_CLI_DB_",
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    user: str = Field(default="souverain_gouvernance_cli")
    password: str = Field(
        default="change_me_gouvernance_cli",
        description=(
            "Mot de passe du rôle dédié CLI. Défaut de dev uniquement — "
            "DOIT être changé (ALTER ROLE côté base + cette variable) "
            "avant tout déploiement réel."
        ),
    )
    pool_min_size: int = Field(default=1)
    pool_max_size: int = Field(default=3)


def get_gouvernance_cli_db_settings() -> GouvernanceCliDbSettings:
    return GouvernanceCliDbSettings()
