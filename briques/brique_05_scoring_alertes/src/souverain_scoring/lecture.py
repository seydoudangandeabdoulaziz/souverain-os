"""Identification des compte_pivot à recalculer.

Ce module ne calcule AUCUN score. Il répond uniquement à la question :
"quels compte_pivot ont une activité nouvelle depuis le dernier cycle
de scoring ?" — via une jointure vers detections_traitees (table de
suivi séparée, cf. Correction 1 : aucun flag n'existe sur detections).

Le calcul du score lui-même relit ensuite TOUTES les détections du
compte dans la fenêtre (agregation.py), traitées ou non — le flag
"traité" n'est qu'un déclencheur, jamais un filtre de calcul
(résolution de la tension flag/fenêtre, cf. analyse validée).
"""

from __future__ import annotations

import logging

import asyncpg

logger = logging.getLogger(__name__)


async def lister_comptes_a_recalculer(
    connexion: asyncpg.Connection,
    schema: str,
) -> list[str]:
    """Retourne la liste des compte_pivot ayant une détection non traitée.

    Exclut explicitement les détections avec compte_pivot NULL
    (Correction 2) : elles sont journalisées en warning et jamais
    incluses dans le scoring MVP.
    """
    lignes_null = await connexion.fetch(
        f"""
        SELECT d.detection_id
        FROM {schema}.detections d
        LEFT JOIN {schema}.detections_traitees dt
            ON dt.detection_id = d.detection_id
        WHERE d.compte_pivot IS NULL
          AND dt.detection_id IS NULL
        """
    )
    for ligne in lignes_null:
        logger.warning(
            "Détection sans compte_pivot exclue du scoring : detection_id=%s",
            ligne["detection_id"],
        )
        # Marquée traitée quand même pour ne pas la re-signaler à chaque
        # cycle : c'est un problème de qualité de données déjà journalisé,
        # pas une erreur à re-signaler indéfiniment.
        await connexion.execute(
            f"""
            INSERT INTO {schema}.detections_traitees (detection_id)
            VALUES ($1)
            ON CONFLICT (detection_id) DO NOTHING
            """,
            ligne["detection_id"],
        )

    lignes = await connexion.fetch(
        f"""
        SELECT DISTINCT d.compte_pivot
        FROM {schema}.detections d
        LEFT JOIN {schema}.detections_traitees dt
            ON dt.detection_id = d.detection_id
        WHERE d.compte_pivot IS NOT NULL
          AND dt.detection_id IS NULL
        """
    )
    return [ligne["compte_pivot"] for ligne in lignes]
