"""
Configuration de la Brique 8 — identifiants du rôle PostgreSQL dédié.

Ne redéclare JAMAIS host/port/db : ces valeurs restent celles de
PostgresSettings (Brique 1, préfixe POSTGRES_) — une seule source de
vérité pour "où se trouve la base", même principe déjà appliqué par
DashboardSettings (Brique 7) pour le secret JWT. Seuls user/password
diffèrent, parce que ce pool se connecte avec un rôle PostgreSQL
DIFFÉRENT de souverain_admin (voir connection.py : c'est précisément
ce qui rend la protection par privilège réelle).
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


class AuditDbSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AUDIT_DB_",
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    user: str = Field(
        default="souverain_brique8_audit",
        description="Rôle PostgreSQL dédié — doit correspondre au rôle créé par la migration 0001.",
    )
    password: str = Field(
        default="change_me_audit",
        description=(
            "Mot de passe du rôle dédié. Défaut de dev uniquement — DOIT être changé "
            "(ALTER ROLE côté base + cette variable) avant tout déploiement réel."
        ),
    )
    pool_min_size: int = Field(default=1, description="Taille minimale du pool dédié")
    pool_max_size: int = Field(default=5, description="Taille maximale du pool dédié")


def get_audit_db_settings() -> AuditDbSettings:
    return AuditDbSettings()
