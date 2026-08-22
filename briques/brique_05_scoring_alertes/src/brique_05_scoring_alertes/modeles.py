"""Modèles de données de la Brique 5.

DetectionNonTraitee est volontairement indépendant de DetectionEvent
(Brique 4) : le moteur de scoring ne doit rien savoir de la façon dont
une détection a été produite (règle à état, futur flux temps réel,
etc.) — il ne reçoit que les champs dont il a besoin pour agréger, lus
depuis la base via lecture.py. Même découplage que TransactionObservee
en Brique 4 vis-à-vis de la Brique 3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class DetectionNonTraitee:
    """Une détection telle que vue par le moteur de scoring.

    Reflet minimal d'une ligne {tenant}.detections non encore présente
    dans {tenant}.detections_traitees. Ne porte aucune logique de poids
    ni de seuil — ces règles vivent dans seuils.py/agregation.py.
    """

    detection_id: UUID
    compte_pivot: str
    pattern_type: str
    detected_at: datetime


@dataclass
class ScoreCompte:
    """Résultat de l'agrégation pour un compte_pivot, sur la fenêtre glissante.

    pattern_types_impliques est déjà dédupliqué au moment du calcul
    (agregation.py) — persistence.py doit le réutiliser tel quel, sans
    recalcul redondant.
    """

    compte_pivot: str
    score: int
    pattern_types_impliques: list[str]
    detection_ids: list[UUID]
    fenetre_debut: datetime
    fenetre_fin: datetime
    details: dict[str, int] = field(default_factory=dict)
