"""
Configuration de l'extension gouvernance (Brique 2 V2).

Deux groupes de settings, séparés intentionnellement :

1. GouvernanceCookieSettings — lit DASHBOARD_COOKIE_NAME, le MÊME nom
   de variable d'environnement que DashboardSettings (Brique 7). Ce
   n'est PAS un import de Brique 7 (qui créerait une dépendance
   remontante, Brique 2 est censée être en AMONT de Brique 7) — c'est
   une classe de settings dupliquée, qui lit intentionnellement la
   même variable d'environnement pour que le MÊME cookie de session
   fonctionne indifféremment sur le dashboard (Brique 7) et sur cette
   extension (Brique 2), sans coupler le code des deux briques.

2. GouvernanceWebDbSettings — identifiants du rôle PostgreSQL dédié
   souverain_gouvernance_web (voir migrations/0002).
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


class GouvernanceCookieSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DASHBOARD_",
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    cookie_name: str = Field(default="souverain_session")


class GouvernanceWebDbSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GOUVERNANCE_WEB_DB_",
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    user: str = Field(default="souverain_gouvernance_web")
    password: str = Field(default="change_me_gouvernance_web")
    pool_min_size: int = Field(default=1)
    pool_max_size: int = Field(default=5)


def get_gouvernance_cookie_settings() -> GouvernanceCookieSettings:
    return GouvernanceCookieSettings()


def get_gouvernance_web_db_settings() -> GouvernanceWebDbSettings:
    return GouvernanceWebDbSettings()
