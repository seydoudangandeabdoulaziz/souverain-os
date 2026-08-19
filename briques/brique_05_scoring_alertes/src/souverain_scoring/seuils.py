"""Comparaison du score agrégé au seuil de déclenchement d'alerte.

Fichier volontairement isolé et minimal : le seuil MVP est encore plus
provisoire que les seuils de la Brique 4 (cf. analyse validée, Q4).
L'isoler ici permet de le recalibrer sans toucher à scoring.py.
"""

from __future__ import annotations

from souverain_scoring.modeles import DecisionAlerte, ScoreCompte


def evaluer_seuil(score_compte: ScoreCompte, seuil_alerte: int) -> DecisionAlerte:
    """Décide si le score justifie une alerte."""
    return DecisionAlerte(
        compte_pivot=score_compte.compte_pivot,
        score=score_compte.score,
        doit_alerter=score_compte.score >= seuil_alerte,
        detection_ids=score_compte.detection_ids,
        premiere_detection_at=score_compte.premiere_detection_at,
        derniere_detection_at=score_compte.derniere_detection_at,
    )
