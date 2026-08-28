"""
Configuration de la Brique 7 — settings propres au dashboard uniquement.

Ne redéclare JAMAIS de secret de signature JWT : JwtSettings de la
Brique 2 (get_jwt_settings()) reste l'unique source de vérité pour
tout ce qui touche le jeton (secret_key, algorithm, expiration_hours).
Dupliquer un secret de signature créerait exactement le risque à deux
sources de vérité qu'on a explicitement écarté à l'analyse.
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


class DashboardSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DASHBOARD_",
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    port: int = Field(default=8080, description="Port HTTP du dashboard")
    cookie_name: str = Field(
        default="souverain_session",
        description="Nom du cookie httpOnly portant le JWT (Option A validée à l'analyse)",
    )
    cookie_secure: bool = Field(
        default=False,
        description=(
            "Cookie Secure (HTTPS uniquement) — False en dev local HTTP, "
            "DOIT être True en tout déploiement réel."
        ),
    )


def get_dashboard_settings() -> DashboardSettings:
    return DashboardSettings()
