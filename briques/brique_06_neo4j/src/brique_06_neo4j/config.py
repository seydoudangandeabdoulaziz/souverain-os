"""
Configuration de la Brique 6, chargée depuis les variables d'environnement.

Même pattern que brique_01_postgresql/config.py — pydantic-settings,
fichier .env retrouvé en remontant depuis ce fichier plutôt que depuis
le répertoire de travail courant.
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


class Neo4jSettings(BaseSettings):
    """
    Paramètres de connexion à l'instance Neo4j Community.

    RAM (validée à l'analyse, Bloc 5 du document fondateur) : configuration
    JVM explicite posée côté docker-compose.yml (heap 512m-1G, page cache
    512m), pas les valeurs par défaut de l'image — empreinte totale
    attendue ~1,5-2 Go sur 16 Go disponibles, à confirmer par `docker
    stats` au premier démarrage réel.
    """

    model_config = SettingsConfigDict(
        env_prefix="NEO4J_",
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    uri: str = Field(default="bolt://localhost:7687", description="URI Bolt Neo4j")
    user: str = Field(default="neo4j", description="Utilisateur Neo4j")
    password: str = Field(
        default="change_me",
        description=(
            "Mot de passe (jamais en dur en prod, via .env). Défaut aligné "
            "sur celui de docker-compose.yml (NEO4J_AUTH) — un défaut "
            "différent entre l'app et le conteneur provoque un échec "
            "d'authentification silencieux si .env ne le surcharge pas."
        ),
    )
    database: str = Field(
        default="neo4j",
        description=(
            "Nom de la base Neo4j. Community Edition ne supporte qu'UNE SEULE "
            "base — ce paramètre existe pour la clarté du driver, pas comme "
            "levier multi-tenant. L'isolation multi-tenant réelle passe par "
            "tenant_id sur chaque nœud/relation, voir garde_isolation.py."
        ),
    )


def get_settings() -> Neo4jSettings:
    """Point d'entrée unique pour récupérer la configuration Neo4j."""
    return Neo4jSettings()
