"""
Configuration de la Brique 1, chargée depuis les variables d'environnement.

Pourquoi pydantic-settings plutôt que os.environ directement ?
Parce que pydantic-settings valide automatiquement les types (le port
doit être un entier, pas une chaîne quelconque) et centralise la
lecture du fichier .env — un seul endroit à modifier, jamais de valeur
en dur dispersée dans le code (Secure by Design).
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file() -> str | None:
    """
    Cherche le fichier .env en remontant depuis ce fichier, pas depuis
    le répertoire de travail courant.

    Pourquoi c'est nécessaire : si on utilisait simplement env_file=".env",
    ce chemin serait interprété relativement à l'endroit d'où la commande
    est lancée (ex. "uv run python scripts/db_healthcheck.py" depuis
    briques/brique_01_postgresql/). Le fichier .env réel est toujours à
    la racine du dépôt, quel que soit le dossier courant — on le
    retrouve donc en remontant l'arborescence.
    """
    for parent in Path(__file__).resolve().parents:
        candidate = parent / ".env"
        if candidate.is_file():
            return str(candidate)
    return None


_ENV_FILE = _find_env_file()


class PostgresSettings(BaseSettings):
    """
    Paramètres de connexion à l'instance PostgreSQL/TimescaleDB.

    Ces valeurs sont lues depuis le fichier .env à la racine du dépôt
    (jamais commité — voir .env.example pour le modèle), quel que soit
    le répertoire depuis lequel le code est exécuté.
    """

    model_config = SettingsConfigDict(
        env_prefix="POSTGRES_",
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = Field(default="localhost", description="Hôte PostgreSQL")
    port: int = Field(default=5432, description="Port PostgreSQL")
    db: str = Field(default="souverain_os", description="Nom de la base")
    user: str = Field(default="souverain_admin", description="Utilisateur PostgreSQL")
    password: str = Field(default="", description="Mot de passe (jamais en dur, via .env)")

    # Paramètres du pool de connexions asyncpg.
    pool_min_size: int = Field(default=2, description="Taille minimale du pool")
    pool_max_size: int = Field(default=10, description="Taille maximale du pool")

    @property
    def dsn(self) -> str:
        """Construit le DSN (Data Source Name) attendu par asyncpg."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"


def get_settings() -> PostgresSettings:
    """
    Point d'entrée unique pour récupérer la configuration.

    Centraliser cet accès permet, plus tard, d'y ajouter du cache
    ou de la validation supplémentaire sans changer les appelants.
    """
    return PostgresSettings()
