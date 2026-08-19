"""Configuration de la Brique 5.

Réutilise le pattern pydantic-settings déjà validé dans les briques
précédentes (chargement depuis .env, résolution jusqu'à la racine du
dépôt indépendamment du répertoire d'exécution — cf. bug corrigé en
Brique 1).

Tous les paramètres métier "provisoires" (poids, fenêtre, seuil) sont
ici plutôt qu'en dur dans le code, pour permettre un recalibrage futur
sans toucher à la logique de scoring.py.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class ParametresScoring(BaseSettings):
    """Paramètres métier du scoring, explicitement provisoires (MVP).

    Ces valeurs sont des points de départ validés le 15/08/2026 — elles
    seront très probablement recalibrées une fois de vraies données
    disponibles. Ne jamais les traiter comme définitives dans le code.
    """

    model_config = SettingsConfigDict(
        env_prefix="SOUVERAIN_SCORING_",
        env_file=".env",
        extra="ignore",
    )

    # Poids par type de règle (pattern_type de detections). Comptés une
    # seule fois par type présent dans la fenêtre, jamais par occurrence.
    poids_compte_pivot: int = 30
    poids_structure_etoile: int = 25
    poids_micro_fractionnement: int = 20
    poids_flux_frontalier: int = 15
    poids_transactions_nocturnes: int = 10

    # Fenêtre glissante d'agrégation par compte_pivot.
    fenetre_jours: int = 7

    # Seuil de déclenchement d'une alerte. Encore plus provisoire que
    # les seuils de la Brique 4 (cf. analyse validée, Q4).
    # Recalibré le 16/08/2026 après première exécution réelle sur
    # tenant_ne (5000 transactions synthétiques, 51 compte_pivot) :
    # le score max observé était 40 (comptes "pivot_*", cumul de
    # compte_pivot + transactions_nocturnes), 0 alerte avec seuil=50.
    # Seuil abaissé à 35 pour capter les comptes cumulant au moins
    # 2 types de règles distincts (hub_* à 35, pivot_* à 40), tout en
    # excluant les comptes à pattern unique (niamey_* à 15, cpt_*/hub_*
    # à 10, cpt_* à 30) — coupure lue sur la distribution réelle, pas
    # une valeur arbitraire, mais toujours provisoire.
    seuil_alerte: int = 35

    # Plafond du score agrégé.
    score_maximum: int = 100

    def table_poids(self) -> dict[str, int]:
        """Retourne la table pattern_type -> poids.

        Les clés doivent correspondre exactement aux valeurs de
        detections.pattern_type telles qu'écrites par la Brique 4.
        """
        return {
            "compte_pivot": self.poids_compte_pivot,
            "structure_etoile": self.poids_structure_etoile,
            "micro_fractionnement": self.poids_micro_fractionnement,
            "flux_frontalier": self.poids_flux_frontalier,
            "transactions_nocturnes": self.poids_transactions_nocturnes,
        }
