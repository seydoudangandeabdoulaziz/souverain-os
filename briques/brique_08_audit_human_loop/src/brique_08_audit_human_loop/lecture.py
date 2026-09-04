"""Lecture de l'historique d'audit d'une alerte.

Utilise le pool RESTREINT de cette brique (connection.py) — il a
exactement les privilèges SELECT nécessaires sur {tenant}.audit_log et
shared.users (voir migration 0001), pas besoin du pool admin ici.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from brique_01_postgresql.tenant_provisioning import validate_schema_name

from brique_08_audit_human_loop.modeles import EntreeAudit

_REQUETE_HISTORIQUE_AUDIT = """
    SELECT a.id, a.alerte_id, a.user_id, a.motif, a.commentaire, a.created_at,
           u.email AS email_utilisateur
    FROM {schema}.audit_log a
    LEFT JOIN shared.users u ON u.user_id = a.user_id
    WHERE a.alerte_id = $1
    ORDER BY a.created_at DESC
"""


async def lire_historique_audit(
    pool_audit: asyncpg.Pool, nom_schema_tenant: str, alerte_id: UUID
) -> list[EntreeAudit]:
    """Retourne l'historique, du plus récent au plus ancien.

    Retourne une liste vide si {tenant}.audit_log n'existe pas encore
    (aucune fermeture n'a jamais eu lieu pour ce tenant) — état légitime,
    pas une erreur, même principe que TenantSansDonnees en Brique 7 mais
    sans avoir besoin d'une exception dédiée : "aucun historique" est un
    résultat valide pour cette page, jamais la page entière.
    """
    validate_schema_name(nom_schema_tenant)
    requete = _REQUETE_HISTORIQUE_AUDIT.format(schema=nom_schema_tenant)

    try:
        async with pool_audit.acquire() as connexion:
            lignes = await connexion.fetch(requete, alerte_id)
    except asyncpg.exceptions.UndefinedTableError:
        return []

    return [
        EntreeAudit(
            id=ligne["id"],
            alerte_id=ligne["alerte_id"],
            user_id=ligne["user_id"],
            email_utilisateur=ligne["email_utilisateur"],
            motif=ligne["motif"],
            commentaire=ligne["commentaire"],
            created_at=ligne["created_at"],
        )
        for ligne in lignes
    ]
