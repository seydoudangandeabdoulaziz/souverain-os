"""Ingestion des transactions synthétiques dans le schéma tenant réel.

CORRECTIF majeur par rapport à la version précédente :
- Colonnes alignées sur le vrai schéma {tenant}.transactions (Brique 1,
  schema_tenant_template.sql) : transaction_id, tenant_id, country_code,
  data_classification, amount, currency, sender_account, receiver_account,
  channel, occurred_at, is_synthetic. ingested_at et raw_payload sont
  laissés à leurs valeurs par défaut (now() / NULL).
- tenant_id, country_code et data_classification ne sont PAS des valeurs
  libres : ils sont récupérés depuis shared.tenants_registry (récupérer_
  metadonnees_tenant), car ce sont des colonnes NOT NULL du vrai schéma.
- Réutilise validate_schema_name() de la Brique 1 au lieu d'une
  validation dupliquée.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import asyncpg
from brique_01_postgresql.tenant_provisioning import (
    InvalidSchemaNameError,
    validate_schema_name,
)

from souverain_generateur.generateur_legitime import (
    TransactionSynthetique,
    nouvel_id_transaction,
)

TAILLE_LOT_DEFAUT = 500

# Exposé pour compatibilité — les appelants qui veulent capturer une erreur
# de nom de schéma peuvent utiliser InvalidSchemaNameError directement.
__all__ = [
    "InvalidSchemaNameError",
    "MetadonneesTenant",
    "inserer_transactions",
    "recuperer_metadonnees_tenant",
    "validate_schema_name",
]

_REQUETE_INSERT = """
    INSERT INTO {schema}.transactions
        (transaction_id, tenant_id, country_code, data_classification,
         amount, currency, sender_account, receiver_account, channel,
         occurred_at, is_synthetic)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
"""

_REQUETE_ASSURER_COLONNE_IS_SYNTHETIC = """
    ALTER TABLE {schema}.transactions
    ADD COLUMN IF NOT EXISTS is_synthetic BOOLEAN NOT NULL DEFAULT false;
"""

_REQUETE_METADONNEES_TENANT = """
    SELECT tenant_id, country_code, data_classification
    FROM shared.tenants_registry
    WHERE schema_name = $1 AND is_active = true
"""


@dataclass(frozen=True)
class MetadonneesTenant:
    """Métadonnées d'un tenant, telles qu'enregistrées dans shared.tenants_registry."""

    tenant_id: UUID
    country_code: str
    data_classification: str


async def recuperer_metadonnees_tenant(
    pool: asyncpg.Pool, nom_schema_tenant: str
) -> MetadonneesTenant:
    """Récupère tenant_id/country_code/data_classification depuis le registre.

    Lève ValueError si le tenant n'est pas enregistré ou est désactivé —
    cas attendu tant que la Brique 8 (create_tenant complet) n'existe pas
    et que seul le bootstrap MVP (scripts/bootstrap_tenant_ne.sql) a été
    joué manuellement.
    """
    validate_schema_name(nom_schema_tenant)
    async with pool.acquire() as connexion:
        ligne = await connexion.fetchrow(_REQUETE_METADONNEES_TENANT, nom_schema_tenant)

    if ligne is None:
        raise ValueError(
            f"Aucun tenant actif trouvé pour le schéma {nom_schema_tenant!r} dans "
            "shared.tenants_registry. As-tu joué le bootstrap MVP "
            "(scripts/bootstrap_tenant_ne.sql) ? Voir README.md de cette brique."
        )

    return MetadonneesTenant(
        tenant_id=ligne["tenant_id"],
        country_code=ligne["country_code"],
        data_classification=ligne["data_classification"],
    )


async def inserer_transactions(
    pool: asyncpg.Pool,
    nom_schema_tenant: str,
    transactions: list[TransactionSynthetique],
    taille_lot: int = TAILLE_LOT_DEFAUT,
) -> int:
    """Insère les transactions par lots, dans une transaction SQL par lot.

    Récupère automatiquement tenant_id/country_code/data_classification
    depuis shared.tenants_registry (une seule fois, avant la boucle).

    S'assure aussi que la colonne is_synthetic existe sur ce tenant avant
    d'insérer (ADD COLUMN IF NOT EXISTS, idempotent) — indépendant de
    l'ordre d'exécution de migrations/0001_add_is_synthetic.sql, qui ne
    couvre que les tenants déjà enregistrés au moment où elle tourne.
    Un tenant provisionné après coup (ex. en test) est donc toujours
    correctement supporté, sans dépendre de rejouer la migration.

    Retourne le nombre total de transactions insérées.
    """
    validate_schema_name(nom_schema_tenant)
    metadonnees = await recuperer_metadonnees_tenant(pool, nom_schema_tenant)
    requete = _REQUETE_INSERT.format(schema=nom_schema_tenant)

    async with pool.acquire() as connexion:
        await connexion.execute(
            _REQUETE_ASSURER_COLONNE_IS_SYNTHETIC.format(schema=nom_schema_tenant)
        )

    total_insere = 0
    async with pool.acquire() as connexion:
        for debut in range(0, len(transactions), taille_lot):
            lot = transactions[debut : debut + taille_lot]
            valeurs = [
                (
                    nouvel_id_transaction(),
                    metadonnees.tenant_id,
                    metadonnees.country_code,
                    metadonnees.data_classification,
                    t.amount,
                    t.currency,
                    t.sender_account,
                    t.receiver_account,
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
