"""Agrégation des détections d'un compte_pivot sur la fenêtre glissante.

Réutilise le même principe binaire in/out que les fenêtres glissantes
de la Brique 4 : une détection compte pleinement tant qu'elle est dans
la fenêtre, puis en sort complètement. Pas de décroissance temporelle.
"""

from __future__ import annotations

from datetime import timedelta

import asyncpg

from souverain_scoring.modeles import DetectionAgregee


async def recuperer_detections_fenetre(
    connexion: asyncpg.Connection,
    schema: str,
    compte_pivot: str,
    fenetre_jours: int,
) -> list[DetectionAgregee]:
    """Retourne TOUTES les détections d'un compte dans la fenêtre.

    Traitées ou non : le calcul du score est indépendant du flag de
    detections_traitees (cf. lecture.py).
    """
    lignes = await connexion.fetch(
        f"""
        SELECT detection_id, pattern_type, compte_pivot,
               transaction_ids, detected_at
        FROM {schema}.detections
        WHERE compte_pivot = $1
          AND detected_at >= now() - $2::interval
        ORDER BY detected_at
        """,
        compte_pivot,
        timedelta(days=fenetre_jours),
    )
    return [
        DetectionAgregee(
            detection_id=ligne["detection_id"],
            pattern_type=ligne["pattern_type"],
            compte_pivot=ligne["compte_pivot"],
            transaction_ids=list(ligne["transaction_ids"]),
            detected_at=ligne["detected_at"],
        )
        for ligne in lignes
    ]
