"""Configuration de la Brique 3.

Réutilise le même principe que les Briques 1 et 2 : le fichier .env est
recherché en remontant l'arborescence depuis ce fichier, pour ne jamais
dépendre du répertoire d'exécution (bug corrigé en Brique 1, cf. avancement.md).

HYPOTHÈSE À VÉRIFIER : si la Brique 1 expose déjà un utilitaire
_find_env_file() partagé (par ex. dans un module `shared`), remplace la
fonction ci-dessous par un import de cet utilitaire pour éviter la
duplication. Je n'ai pas eu accès au code réel de la Brique 1 pour vérifier
son emplacement exact.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file(nom_fichier: str = ".env") -> Path | None:
    """Remonte l'arborescence depuis ce fichier jusqu'à trouver .env.

    Évite le piège classique : un .env non trouvé parce que la commande
    a été lancée depuis un sous-dossier plutôt que depuis la racine du repo.
    """
    courant = Path(__file__).resolve()
    for parent in [courant, *courant.parents]:
        candidat = parent / nom_fichier
        if candidat.is_file():
            return candidat
    return None


class ParametresGenerateur(BaseSettings):
    """Paramètres de connexion et de génération, chargés depuis .env."""

    model_config = SettingsConfigDict(
        env_file=_find_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    """DSN PostgreSQL, ex : postgresql://user:pass@localhost:5432/souverain_os"""

    seed_defaut: int = 42
    """Seed par défaut pour la reproductibilité des générations."""

    nb_transactions_defaut: int = 5_000
    """Volumétrie par défaut d'une génération (configurable en CLI, jusqu'à 50 000)."""

    pourcentage_suspect_defaut: float = 5.0
    """Part de transactions issues des patterns suspects, en pourcentage."""
