"""
Configuration de la Brique 2 : paramètres liés aux jetons JWT.

Séparée volontairement de PostgresSettings (Brique 1) : deux
responsabilités différentes ne doivent pas partager une même classe
de configuration, même si les deux sont lues depuis le même .env.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file() -> str | None:
    """
    Identique au pattern de la Brique 1 (config.py) : remonte
    l'arborescence depuis ce fichier pour trouver le .env à la racine
    du dépôt, indépendamment du répertoire d'exécution courant.
    """
    for parent in Path(__file__).resolve().parents:
        candidate = parent / ".env"
        if candidate.is_file():
            return str(candidate)
    return None


_ENV_FILE = _find_env_file()


class JwtSettings(BaseSettings):
    """Paramètres de signature et d'expiration des jetons JWT."""

    model_config = SettingsConfigDict(
        env_prefix="JWT_",
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    secret_key: str = Field(
        default="insecure-dev-secret-change-me-before-any-real-use",
        description="Secret de signature HMAC — DOIT être changé hors développement local",
    )
    algorithm: str = Field(default="HS256", description="Algorithme de signature JWT")
    expiration_hours: int = Field(
        default=8,
        description="Durée de validité d'un jeton, en heures (MVP : pas de refresh token)",
    )


def get_jwt_settings() -> JwtSettings:
    """Point d'entrée unique pour récupérer la configuration JWT."""
    return JwtSettings()
