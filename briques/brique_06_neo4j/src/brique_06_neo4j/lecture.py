"""Lecture PostgreSQL pour la Brique 6 — double dépendance en amont.

⚠️ Double dépendance de lecture, jamais vers la Brique 4 directement :
- lire_transactions() : source à projeter dans Neo4j (Brique 1).
- lire_comptes_alertes() : comptes déjà alertés, nécessaires aux
  requêtes b) et c) de garde_isolation.py (Brique 5, table alertes).

Dupliquées ici en lecture directe, sans importer brique_05_scoring_alertes
en runtime — même principe déjà appliqué en Brique 5 vis-à-vis de la
Brique 4 (chaque brique duplique sa propre petite requête de lecture
plutôt que de créer une dépendance runtime inter-briques).
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from brique_01_postgresql.tenant_provisioning import validate_schema_name

from brique_06_neo4j.modeles import TransactionAImporter

_REQUETE_TENANT_ID = """
    SELECT tenant_id
    FROM shared.tenants_registry
    WHERE schema_name = $1 AND is_active = true
"""

_REQUETE_TRANSACTIONS = """
    SELECT transaction_id, sender_account, receiver_account,
           amount, currency, channel, occurred_at, is_synthetic
    FROM {schema}.transactions
    ORDER BY occurred_at ASC
"""

# Table alertes (Brique 5) : ne lit que le compte_pivot des alertes
# OUVERTES. Si {tenant}.alertes n'existe pas encore (Brique 5 jamais
# exécutée pour ce tenant) ou est vide (cas réel actuel de tenant_ne,
# aucune alerte encore créée) : liste vide en sortie, jamais une
# erreur — condition couverte par un test dédié.
_REQUETE_COMPTES_ALERTES = """
    SELECT DISTINCT compte_pivot
    FROM {schema}.alertes
    WHERE statut = 'ouverte'
"""


async def lire_transactions(
    pool: asyncpg.Pool, nom_schema_tenant: str
) -> list[TransactionAImporter]:
    """Lit l'intégralité de {tenant}.transactions.

    Portée MVP validée à l'analyse : import complet, pas incrémental.
    À l'échelle UEMOA (volumes bien plus élevés), un import complet à
    chaque exécution deviendra coûteux — limite connue, pas une
    surprise future. Import incrémental = Vision.
    """
    validate_schema_name(nom_schema_tenant)
    requete = _REQUETE_TRANSACTIONS.format(schema=nom_schema_tenant)

    async with pool.acquire() as connexion:
        lignes = await connexion.fetch(requete)

    return [
        TransactionAImporter(
            transaction_id=ligne["transaction_id"],
            sender_account=ligne["sender_account"],
            receiver_account=ligne["receiver_account"],
            amount=ligne["amount"],
            currency=ligne["currency"],
            channel=ligne["channel"],
            occurred_at=ligne["occurred_at"],
            is_synthetic=ligne["is_synthetic"],
        )
        for ligne in lignes
    ]


async def lire_comptes_alertes(pool: asyncpg.Pool, nom_schema_tenant: str) -> list[str]:
    """Lit les compte_pivot des alertes actuellement ouvertes (Brique 5).

    Retourne une liste vide si la table n'a pas encore d'alerte ouverte
    (cas réel actuel de tenant_ne) — jamais une erreur. Si la table
    {tenant}.alertes n'existe pas du tout (Brique 5 jamais exécutée
    pour ce tenant), la requête échoue avec une erreur Postgres claire
    (relation does not exist) plutôt qu'un retour silencieusement vide
    qui masquerait un vrai problème de séquencement des briques.
    """
    validate_schema_name(nom_schema_tenant)
    requete = _REQUETE_COMPTES_ALERTES.format(schema=nom_schema_tenant)

    async with pool.acquire() as connexion:
        lignes = await connexion.fetch(requete)

    return [ligne["compte_pivot"] for ligne in lignes]


async def lire_tenant_id(pool: asyncpg.Pool, nom_schema_tenant: str) -> UUID:
    """Résout le schema_name (ex. 'tenant_ne') vers le vrai tenant_id (UUID).

    Utilisé comme valeur de la propriété tenant_id posée sur chaque
    nœud/relation Neo4j — l'identifiant stable de shared.tenants_registry,
    pas le nom de schéma PostgreSQL (spécifique à cette base, pas un
    identifiant multi-tenant portable en soi). Même principe de
    résolution que recuperer_metadonnees_tenant() en Briques 3/4/5.
    """
    validate_schema_name(nom_schema_tenant)
    async with pool.acquire() as connexion:
        ligne = await connexion.fetchrow(_REQUETE_TENANT_ID, nom_schema_tenant)

    if ligne is None:
        raise ValueError(
            f"Aucun tenant actif trouvé pour le schéma {nom_schema_tenant!r} dans "
            "shared.tenants_registry."
        )

    return ligne["tenant_id"]  # type: ignore[no-any-return]
