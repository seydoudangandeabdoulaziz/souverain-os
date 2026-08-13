"""
Configuration de la Brique 1, chargée depuis les variables d'environnement.

Pourquoi pydantic-settings plutôt que os.environ directement ?
Parce que pydantic-settings valide automatiquement les types (le port
doit être un entier, pas une chaîne quelconque) et centralise la
lecture du fichier .env — un seul endroit à modifier, jamais de valeur
en dur dispersée dans le code (Secure by Design).
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PostgresSettings(BaseSettings):
    """
    Paramètres de connexion à l'instance PostgreSQL/TimescaleDB.

    Ces valeurs sont lues depuis le fichier .env à la racine du dépôt
    (jamais commité — voir .env.example pour le modèle).
    """

    model_config = SettingsConfigDict(
        env_prefix="POSTGRES_",
        env_file=".env",
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
