"""Lecture — liste des utilisateurs du tenant de l'appelant, et
historique de gouvernance (domaine='utilisateur' pour son tenant +
domaine='tenant' pour son propre tenant, décision validée à l'analyse).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import asyncpg

_SELECT_UTILISATEURS_DU_TENANT = """
    SELECT user_id, email, role, is_active, created_at
    FROM shared.users
    WHERE tenant_id = $1
    ORDER BY created_at ASC
"""

_SELECT_HISTORIQUE_GOUVERNANCE = """
    SELECT id, domaine, action, cible_id, acteur_type, acteur_declare, acteur_user_id,
           details, created_at
    FROM shared.gouvernance_audit_log
    WHERE
        (domaine = 'utilisateur'
            AND cible_id IN (SELECT user_id FROM shared.users WHERE tenant_id = $1))
        OR (domaine = 'tenant' AND cible_id = $1)
    ORDER BY created_at DESC
"""


@dataclass(frozen=True)
class UtilisateurAffichage:
    user_id: UUID
    email: str
    role: str
    is_active: bool
    created_at: datetime


@dataclass(frozen=True)
class EntreeHistoriqueGouvernance:
    id: UUID
    domaine: str
    action: str
    cible_id: UUID
    acteur_type: str
    acteur_declare: str | None
    acteur_user_id: UUID | None
    details: dict[str, object] | None
    created_at: datetime


async def lister_utilisateurs_du_tenant(
    connexion: asyncpg.Connection, tenant_id: UUID
) -> list[UtilisateurAffichage]:
    lignes = await connexion.fetch(_SELECT_UTILISATEURS_DU_TENANT, tenant_id)
    return [
        UtilisateurAffichage(
            user_id=ligne["user_id"],
            email=ligne["email"],
            role=ligne["role"],
            is_active=ligne["is_active"],
            created_at=ligne["created_at"],
        )
        for ligne in lignes
    ]


async def lire_historique_gouvernance(
    connexion: asyncpg.Connection, tenant_id: UUID
) -> list[EntreeHistoriqueGouvernance]:
    """tenant_id sert deux rôles dans la requête : filtre les
    utilisateurs cibles (domaine='utilisateur') ET est lui-même la
    cible pour domaine='tenant' — un admin ne voit que SON tenant dans
    les deux cas, jamais un autre."""
    lignes = await connexion.fetch(_SELECT_HISTORIQUE_GOUVERNANCE, tenant_id)
    return [
        EntreeHistoriqueGouvernance(
            id=ligne["id"],
            domaine=ligne["domaine"],
            action=ligne["action"],
            cible_id=ligne["cible_id"],
            acteur_type=ligne["acteur_type"],
            acteur_declare=ligne["acteur_declare"],
            acteur_user_id=ligne["acteur_user_id"],
            # JSONB non décodé automatiquement par asyncpg (aucun codec
            # enregistré sur ce pool) — même piège déjà documenté et
            # corrigé dans brique_07_dashboard.lecture.
            details=json.loads(ligne["details"]) if ligne["details"] else None,
            created_at=ligne["created_at"],
        )
        for ligne in lignes
    ]
