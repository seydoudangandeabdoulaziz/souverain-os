"""Ingestion des transactions synthétiques dans le schéma tenant réel.

HYPOTHÈSE À VÉRIFIER : les noms de colonnes ci-dessous (sender_id,
receiver_id, amount, currency, channel, occurred_at, is_synthetic) sont une
supposition raisonnable basée sur le document fondateur et les échanges
précédents, mais je n'ai pas eu accès au fichier réel de migration de la
Brique 1 (0001_init_shared_schema.sql) pour confirmer les noms exacts.
Avant le premier `uv run pytest`, compare cette liste à ta table
{tenant}.transactions réelle et adapte la requête INSERT si nécessaire.

Ce module accepte un pool asyncpg déjà créé plutôt que de recréer sa propre
logique de connexion, pour rester compatible avec le pool de la Brique 1 —
adapte l'import dans cli.py si la Brique 1 expose un module de pool partagé
(ex. `from souverain_db.pool import creer_pool`) à réutiliser tel quel.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from souverain_generateur.generateur_legitime import (
    TransactionSynthetique,
    nouvel_id_transaction,
)

if TYPE_CHECKING:
    import asyncpg

TAILLE_LOT_DEFAUT = 500

_REQUETE_INSERT = """
    INSERT INTO {schema}.transactions
        (id, sender_id, receiver_id, amount, currency, channel, occurred_at, is_synthetic)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
"""


def _valider_nom_schema(nom_schema: str) -> None:
    """Protection basique contre l'injection SQL sur le nom de schéma.

    Même logique de prudence que provision_tenant_schema() en Brique 1 :
    on ne fait jamais confiance à une chaîne injectée directement dans
    un identifiant SQL, même en interne.
    """
    if not nom_schema.replace("_", "").isalnum():
        raise ValueError(
            f"Nom de schéma tenant invalide : {nom_schema!r}. "
            "Attendu : lettres, chiffres et underscores uniquement."
        )


async def inserer_transactions(
    pool: asyncpg.Pool,
    nom_schema_tenant: str,
    transactions: list[TransactionSynthetique],
    taille_lot: int = TAILLE_LOT_DEFAUT,
) -> int:
    """Insère les transactions par lots, dans une transaction SQL par lot.

    Retourne le nombre total de transactions insérées.
    Lève ValueError si nom_schema_tenant est suspect (protection injection).
    """
    _valider_nom_schema(nom_schema_tenant)
    requete = _REQUETE_INSERT.format(schema=nom_schema_tenant)

    total_insere = 0
    async with pool.acquire() as connexion:
        for debut in range(0, len(transactions), taille_lot):
            lot = transactions[debut : debut + taille_lot]
            valeurs = [
                (
                    nouvel_id_transaction(),
                    t.sender_id,
                    t.receiver_id,
                    t.amount,
                    t.currency,
                    t.channel,
                    t.occurred_at,
                    t.is_synthetic,
                )
                for t in lot
            ]
            async with connexion.transaction():
                await connexion.executemany(requete, valeurs)
            total_insere += len(lot)

    return total_insere
