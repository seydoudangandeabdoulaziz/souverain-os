"""Orchestration du traitement séquentiel — cœur du principe "Hybrid".

Reçoit une liste de transactions déjà triées chronologiquement (peu
importe qu'elles viennent d'un SELECT batch aujourd'hui ou d'un vrai
flux Kafka/Redis demain) et les fait passer, une par une, dans chaque
règle active. Chaque règle maintient son propre état interne — le
moteur lui-même est sans état, il ne fait qu'orchestrer.
"""

from __future__ import annotations

from collections.abc import Iterable

from brique_04_detection.modeles import DetectionEvent, TransactionObservee
from brique_04_detection.regles.base import RegleDetection
from brique_04_detection.regles.compte_pivot import ReglePivot
from brique_04_detection.regles.flux_frontalier import RegleFluxFrontalier
from brique_04_detection.regles.micro_fractionnement import RegleMicroFractionnement
from brique_04_detection.regles.nocturne import RegleNocturne
from brique_04_detection.regles.structure_etoile import RegleStructureEtoile


def regles_par_defaut() -> list[RegleDetection]:
    """Instancie les 5 règles MVP avec leurs seuils par défaut validés.

    La saisonnalité n'est volontairement PAS incluse (décision actée :
    facteur de contexte réservé à la Vision, pas une règle de détection).
    """
    return [
        RegleStructureEtoile(),
        ReglePivot(),
        RegleMicroFractionnement(),
        RegleNocturne(),
        RegleFluxFrontalier(),
    ]


def detecter_sequentiellement(
    transactions: Iterable[TransactionObservee],
    regles: list[RegleDetection] | None = None,
) -> list[DetectionEvent]:
    """Fait passer les transactions dans chaque règle, dans l'ordre reçu.

    ⚠️ L'appelant est responsable de fournir les transactions déjà triées
    par occurred_at croissant (lecture.py le garantit pour la source DB).
    """
    regles_actives = regles if regles is not None else regles_par_defaut()
    evenements: list[DetectionEvent] = []

    for transaction in transactions:
        for regle in regles_actives:
            evenement = regle.traiter(transaction)
            if evenement is not None:
                evenements.append(evenement)

    return evenements
