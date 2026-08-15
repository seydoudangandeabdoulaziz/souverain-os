"""Lecture des transactions d'un tenant, triées chronologiquement.

Isole la seule requête SQL qui alimente le moteur. C'est le point qui
sera remplacé en phase transverse par un vrai consommateur de flux
(Kafka/Redis) — le reste du pipeline (moteur.py, regles/) n'a besoin
d'aucune modification pour ce changement, puisqu'il ne connaît que
TransactionObservee (voir modeles.py).

⚠️ Ne sélectionne volontairement PAS is_synthetic : le moteur de détection
ne doit jamais pouvoir s'appuyer sur cette colonne pour "tricher" (même
principe que pour pattern_label en Brique 3).
"""

from __future__ import annotations

import asyncpg
from brique_01_postgresql.tenant_provisioning import validate_schema_name

from brique_04_detection.modeles import TransactionObservee

_REQUETE_TRANSACTIONS_ORDONNEES = """
    SELECT transaction_id, sender_account, receiver_account, amount, channel, occurred_at
    FROM {schema}.transactions
    ORDER BY occurred_at ASC
"""


async def lire_transactions_ordonnees(
    pool: asyncpg.Pool, nom_schema_tenant: str
) -> list[TransactionObservee]:
    """Lit toutes les transactions d'un tenant, triées par occurred_at croissant."""
    validate_schema_name(nom_schema_tenant)
    requete = _REQUETE_TRANSACTIONS_ORDONNEES.format(schema=nom_schema_tenant)

    async with pool.acquire() as connexion:
        lignes = await connexion.fetch(requete)

    return [
        TransactionObservee(
            transaction_id=ligne["transaction_id"],
            sender_account=ligne["sender_account"],
            receiver_account=ligne["receiver_account"],
            amount=float(ligne["amount"]),
            channel=ligne["channel"],
            occurred_at=ligne["occurred_at"],
        )
        for ligne in lignes
    ]
