"""Configuration de l'API pipeline (variables SOUVERAIN_API_*)."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file() -> str | None:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / ".env"
        if candidate.is_file():
            return str(candidate)
    return None


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SOUVERAIN_API_",
        env_file=_find_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    # Clé DISTINCTE de celle des jetons humains (B2) : un jeton ne peut pas
    # être valide dans l'autre système, même par erreur de configuration.
    jwt_secret: SecretStr = Field(min_length=32)
    jwt_issuer: str = "souverain-os"
    jwt_audience: str = "souverain-api"
    token_ttl_minutes: int = Field(default=15, ge=1, le=60)
    max_body_bytes: int = Field(default=2_000_000, ge=10_000)
    future_tolerance_minutes: int = Field(default=10, ge=0, le=1440)
    max_amount: int = Field(default=1_000_000_000, ge=1)
    # Plafond (heures) de relecture d'un épisode d'activité. None = exact (relit tout
    # l'épisode). Un plafond borne le coût des comptes à activité continue au prix
    # d'éventuelles lignes de détection supplémentaires (jamais d'épisode perdu).
    episode_max_heures: int | None = Field(default=None, ge=6, le=720)
    # Limitation des échecs d'authentification (par client et par adresse).
    max_auth_failures: int = Field(default=5, ge=1)
    auth_failure_window_seconds: int = Field(default=300, ge=10)
    auth_lockout_seconds: int = Field(default=300, ge=10)


def get_api_settings() -> ApiSettings:
    return ApiSettings()  # type: ignore[call-arg]
