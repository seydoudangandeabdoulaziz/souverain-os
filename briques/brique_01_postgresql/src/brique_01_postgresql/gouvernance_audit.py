"""
Écriture dans shared.gouvernance_audit_log — table transverse validée
à l'analyse de la Brique 1 V2, couvrant à la fois la gouvernance des
tenants (Brique 1) et celle des utilisateurs (Brique 2, extension).

Ce module vit dans la Brique 1 parce qu'elle est déjà propriétaire
historique de shared.* (shared.tenants_registry, migration 0001) — et
parce que la Brique 2 dépend DÉJÀ légitimement de la Brique 1
(dependencies = ["brique-01-postgresql", ...] dans son pyproject.toml)
: aucune inversion de dépendance à ajouter ici, contrairement à
auth_cookie.py/csrf.py (Brique 7/8), que l'extension de la Brique 2
duplique plutôt que d'importer pour cette raison précise.

Deux fonctions distinctes, jamais interchangeables, pour rendre visible
dans le code lui-même la distinction que la contrainte SQL
`acteur_coherent` impose déjà en base : un acteur CLI n'est JAMAIS une
identité authentifiée, un acteur web l'est toujours.
"""

from __future__ import annotations

import json
from typing import Any, Literal
from uuid import UUID

import asyncpg

Domaine = Literal["tenant", "utilisateur"]
Action = Literal[
    "tenant_creation",
    "tenant_activation",
    "tenant_desactivation",
    "utilisateur_creation",
    "utilisateur_changement_role",
    "utilisateur_desactivation",
    "utilisateur_reactivation",
]

_INSERT_AUDIT = """
    INSERT INTO shared.gouvernance_audit_log
        (domaine, action, cible_id, acteur_type, acteur_declare, acteur_user_id, details)
    VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
"""


async def enregistrer_audit_gouvernance_cli(
    connexion: asyncpg.Connection,
    *,
    domaine: Domaine,
    action: Action,
    cible_id: UUID,
    acteur_declare: str,
    details: dict[str, Any] | None = None,
) -> None:
    """
    Enregistre une action de gouvernance déclenchée par le CLI.

    `acteur_declare` est une DÉCLARATION LIBRE, non authentifiée — un
    texte saisi en paramètre par l'opérateur, jamais vérifié. Ne JAMAIS
    la présenter comme une identité fiable dans un affichage ou un
    rapport : l'attribution forte de l'auteur CLI reste un chantier
    futur (aucun mécanisme d'authentification n'existe aujourd'hui pour
    aucun CLI du projet — vérifié, pas supposé).
    """
    await connexion.execute(
        _INSERT_AUDIT,
        domaine,
        action,
        cible_id,
        "cli_non_authentifie",
        acteur_declare,
        None,
        json.dumps(details) if details is not None else None,
    )


async def enregistrer_audit_gouvernance_web(
    connexion: asyncpg.Connection,
    *,
    domaine: Domaine,
    action: Action,
    cible_id: UUID,
    acteur_user_id: UUID,
    details: dict[str, Any] | None = None,
) -> None:
    """
    Enregistre une action de gouvernance déclenchée via une route web.

    `acteur_user_id` référence un utilisateur RÉELLEMENT authentifié
    par JWT (shared.users) — même garantie d'attribution que
    {tenant}.audit_log (Brique 8).
    """
    await connexion.execute(
        _INSERT_AUDIT,
        domaine,
        action,
        cible_id,
        "utilisateur_authentifie",
        None,
        acteur_user_id,
        json.dumps(details) if details is not None else None,
    )
