"""Calcul pur du score de risque par compte_pivot.

Fonction pure (aucun I/O) : prend une liste de détections non traitées
et les bornes de la fenêtre glissante utilisée pour les lire, retourne
un ScoreCompte par compte_pivot distinct.

Sépare volontairement le CALCUL (ici) de la DÉCISION (quels comptes
dépassent le seuil) — ce fichier ne connaît pas SEUIL_ALERTE. Le filtre
par seuil est appliqué par l'appelant (cli.py), sur le résultat de
agreger_par_compte(). Ça permet de tester la formule d'agrégation
indépendamment de la notion de seuil.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from brique_05_scoring_alertes.modeles import DetectionNonTraitee, ScoreCompte
from brique_05_scoring_alertes.seuils import POIDS_PAR_PATTERN


def agreger_par_compte(
    detections: list[DetectionNonTraitee],
    fenetre_debut: datetime,
    fenetre_fin: datetime,
) -> list[ScoreCompte]:
    """Agrège les détections non traitées par compte_pivot.

    Déduplication : un même pattern_type détecté plusieurs fois pour un
    même compte_pivot sur la fenêtre ne compte qu'une seule fois dans
    le score (peu importe le nombre d'occurrences).

    ScoreCompte.detection_ids contient TOUTES les détections du compte
    sur cette fenêtre (pas seulement une par pattern déduplié) : c'est
    la liste que persistence.py doit marquer comme traitées dans
    {tenant}.detections_traitees, que le compte franchisse le seuil ou
    non — la déduplication n'affecte que le score, jamais le suivi de
    consommation.
    """
    par_compte: dict[str, list[DetectionNonTraitee]] = defaultdict(list)
    for detection in detections:
        par_compte[detection.compte_pivot].append(detection)

    resultats: list[ScoreCompte] = []
    for compte_pivot, detections_du_compte in par_compte.items():
        patterns_distincts = sorted({d.pattern_type for d in detections_du_compte})

        details = {pattern: POIDS_PAR_PATTERN.get(pattern, 0) for pattern in patterns_distincts}
        score = sum(details.values())

        resultats.append(
            ScoreCompte(
                compte_pivot=compte_pivot,
                score=score,
                pattern_types_impliques=patterns_distincts,
                detection_ids=[d.detection_id for d in detections_du_compte],
                fenetre_debut=fenetre_debut,
                fenetre_fin=fenetre_fin,
                details=details,
            )
        )

    return resultats
