"""Calcul du score agrégé pour un compte_pivot.

Fonction pure, sans dépendance base de données — testable unitairement
sans DB, même approche que les règles de la Brique 4.

Formule figée par l'analyse validée le 15/08/2026 :
  - somme des poids des pattern_type DISTINCTS présents dans la fenêtre
    (une détection répétée du même type ne compte qu'une fois) ;
  - pas de bonus de combinaison (Vision) ;
  - pas de décroissance temporelle (Vision) ;
  - plafonné à score_maximum (100 par défaut).
"""

from __future__ import annotations

from souverain_scoring.modeles import DetectionAgregee, ScoreCompte


def calculer_score(
    detections: list[DetectionAgregee],
    table_poids: dict[str, int],
    score_maximum: int = 100,
) -> ScoreCompte:
    """Calcule le score agrégé d'un compte_pivot à partir de ses détections.

    Lève ValueError si `detections` est vide ou si les compte_pivot ne
    sont pas tous identiques — ce sont des erreurs d'appel, pas des cas
    métier à gérer silencieusement.
    """
    if not detections:
        raise ValueError("calculer_score() appelé avec une liste de détections vide")

    comptes = {detection.compte_pivot for detection in detections}
    if len(comptes) != 1:
        raise ValueError(
            f"Toutes les détections doivent partager le même compte_pivot, reçu : {comptes}"
        )

    types_presents = {detection.pattern_type for detection in detections}
    score_brut = sum(table_poids.get(pattern_type, 0) for pattern_type in types_presents)
    score = min(score_brut, score_maximum)

    dates = [detection.detected_at for detection in detections]

    return ScoreCompte(
        compte_pivot=detections[0].compte_pivot,
        score=score,
        types_presents=types_presents,
        premiere_detection_at=min(dates),
        derniere_detection_at=max(dates),
        detection_ids=[detection.detection_id for detection in detections],
    )
