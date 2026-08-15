"""Configuration de la Brique 3 — paramètres de GÉNÉRATION uniquement.

CORRECTIF : la version précédente redéfinissait sa propre connexion DB
(DATABASE_URL). C'était une supposition erronée — la Brique 1 fournit déjà
PostgresSettings/get_settings() (préfixe POSTGRES_) et create_pool(), qu'il
faut réutiliser tel quel (voir cli.py). Ce fichier ne gère donc plus QUE
les paramètres propres à la génération de données synthétiques.

Pattern identique aux Briques 1 et 2 (config.py) : classe BaseSettings
dédiée avec son propre préfixe, _find_env_file() dupliqué localement —
c'est la convention déjà en place dans ce dépôt, pas une improvisation.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file() -> str | None:
    """Identique au pattern des Briques 1 et 2 : remonte l'arborescence
    depuis ce fichier pour trouver le .env à la racine du dépôt.
    """
    for parent in Path(__file__).resolve().parents:
        candidate = parent / ".env"
        if candidate.is_file():
            return str(candidate)
    return None


_ENV_FILE = _find_env_file()


class GenerateurSettings(BaseSettings):
    """Paramètres par défaut de génération (surchargeables en CLI)."""

    model_config = SettingsConfigDict(
        env_prefix="GENERATEUR_",
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    seed_defaut: int = Field(default=42, description="Seed par défaut pour la reproductibilité")
    nb_transactions_defaut: int = Field(
        default=5_000, description="Volumétrie par défaut (jusqu'à 50 000 recommandé)"
    )
    pourcentage_suspect_defaut: float = Field(
        default=5.0, description="Part de transactions issues des patterns suspects, en %"
    )


def get_generateur_settings() -> GenerateurSettings:
    """Point d'entrée unique pour récupérer la configuration de génération."""
    return GenerateurSettings()
