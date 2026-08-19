"""Logique métier : anti-doublon (Q5) et calcul de is_synthetic (Correction 1).

Ne touche pas encore la base en écriture — produit un objet Alerte prêt
à persister. La lecture (alerte existante, flags is_synthetic) est
nécessaire ici pour construire cet objet.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg

from souverain_scoring.modeles import Alerte, DecisionAlerte


def calculer_is_synthetic(flags_transactions: list[bool]) -> bool:
    """Calcule is_synthetic pour une alerte à partir des flags transactions.

    Règle validée : True seulement si TOUTES les transactions liées à
    TOUTES les détections contributrices sont synthétiques. En cas de
    doute (liste vide, mélange), on retourne False — une alerte est
    traitée comme réelle plutôt que comme test.
    """
    if not flags_transactions:
        return False
    return all(flags_transactions)


async def _recuperer_flags_synthetic(
    connexion: asyncpg.Connection,
    schema: str,
    transaction_ids: list[str],
) -> list[bool]:
    if not transaction_ids:
        return []
    lignes = await connexion.fetch(
        f"""
        SELECT is_synthetic
        FROM {schema}.transactions
        WHERE transaction_id = ANY($1::uuid[])
        """,
        transaction_ids,
    )
    return [ligne["is_synthetic"] for ligne in lignes]


async def _recuperer_transaction_ids_des_detections(
    connexion: asyncpg.Connection,
    schema: str,
    detection_ids: list[str],
) -> list[str]:
    lignes = await connexion.fetch(
        f"""
        SELECT unnest(transaction_ids) AS transaction_id
        FROM {schema}.detections
        WHERE detection_id = ANY($1::uuid[])
        """,
        detection_ids,
    )
    return [ligne["transaction_id"] for ligne in lignes]


async def preparer_alerte(
    connexion: asyncpg.Connection,
    schema: str,
    tenant_id: UUID,
    country_code: str,
    data_classification: str,
    decision: DecisionAlerte,
) -> Alerte:
    """Construit l'objet Alerte final (upsert géré ensuite par persistence.py).

    Le upsert lui-même (recherche d'une alerte 'ouverte' existante pour
    ce compte_pivot) est délégué à persistence.py au moment de
    l'écriture, pour éviter une double requête (lecture ici, puis
    re-lecture dans une transaction d'écriture). Ce module se concentre
    sur le calcul métier de is_synthetic.
    """
    transaction_ids = await _recuperer_transaction_ids_des_detections(
        connexion, schema, [str(detection_id) for detection_id in decision.detection_ids]
    )
    flags = await _recuperer_flags_synthetic(connexion, schema, transaction_ids)
    is_synthetic = calculer_is_synthetic(flags)

    return Alerte(
        tenant_id=tenant_id,
        country_code=country_code,
        data_classification=data_classification,
        compte_pivot=decision.compte_pivot,
        score=decision.score,
        statut="ouverte",
        premiere_detection_at=decision.premiere_detection_at,
        derniere_detection_at=decision.derniere_detection_at,
        is_synthetic=is_synthetic,
        detection_ids=decision.detection_ids,
    )
