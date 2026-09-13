"""
Orchestration transactionnelle de la gestion des comptes utilisateurs
(Brique 2 V2) — chaque opération + son entrée d'audit dans UNE SEULE
transaction, même principe déjà établi par la Brique 8 pour la
fermeture d'alerte.

Toutes les fonctions de ce module :
1. Vérifient l'isolation stricte (la cible appartient au même tenant
   que l'appelant) AVANT toute écriture.
2. Bloquent l'auto-désactivation et l'auto-rétrogradation.
3. Utilisent le pool dédié (connection.py, rôle souverain_gouvernance_web).
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from brique_01_postgresql.gouvernance_audit import enregistrer_audit_gouvernance_web

from brique_02_auth_rbac.password_hashing import hash_password
from brique_02_auth_rbac.repository import (
    EmailAlreadyExistsError,
    RoleInvalideError,
    UserRecord,
    create_user,
    deactivate_user,
    get_user_by_id,
    reactivate_user,
    update_user_role,
)
from brique_02_auth_rbac.souverain_id import generate_souverain_id


class UtilisateurHorsTenantError(Exception):
    """La cible n'appartient pas au tenant de l'appelant — isolation violée."""


class UtilisateurIntrouvableError(Exception):
    """Aucun utilisateur avec cet identifiant."""


class AutoModificationInterditeError(Exception):
    """Un admin ne peut ni se désactiver, ni se rétrograder lui-même."""


_SELECT_TENANT_CODE = "SELECT tenant_code FROM shared.tenants_registry WHERE tenant_id = $1"


async def _verifier_cible_dans_le_tenant(
    connexion: asyncpg.Connection, *, cible_user_id: UUID, tenant_id_appelant: UUID
) -> UserRecord:
    cible = await get_user_by_id(connexion, cible_user_id)
    if cible is None:
        raise UtilisateurIntrouvableError(f"Aucun utilisateur {cible_user_id}.")
    if cible.tenant_id != tenant_id_appelant:
        raise UtilisateurHorsTenantError(
            "Cet utilisateur n'appartient pas à votre tenant — action refusée."
        )
    return cible


async def creer_utilisateur(
    connexion: asyncpg.Connection,
    *,
    tenant_id: UUID,
    email: str,
    mot_de_passe_clair: str,
    role: str,
    acteur_user_id: UUID,
) -> UserRecord:
    """Crée un utilisateur rattaché AU TENANT DE L'APPELANT — jamais
    un tenant_id fourni librement par le formulaire.

    Raises:
        EmailAlreadyExistsError: propagée telle quelle depuis repository.py.
    """
    async with connexion.transaction():
        tenant_code = await connexion.fetchval(_SELECT_TENANT_CODE, tenant_id)
        souverain_id = generate_souverain_id(tenant_code, email)

        utilisateur = await create_user(
            connexion,
            tenant_id=tenant_id,
            souverain_id=souverain_id,
            email=email,
            password_hash=hash_password(mot_de_passe_clair),
            role=role,
        )

        await enregistrer_audit_gouvernance_web(
            connexion,
            domaine="utilisateur",
            action="utilisateur_creation",
            cible_id=utilisateur.user_id,
            acteur_user_id=acteur_user_id,
            details={"email": email, "role": role},
        )

    return utilisateur


async def changer_role_utilisateur(
    connexion: asyncpg.Connection,
    *,
    cible_user_id: UUID,
    nouveau_role: str,
    tenant_id_appelant: UUID,
    acteur_user_id: UUID,
) -> None:
    """
    Raises:
        AutoModificationInterditeError: cible == appelant.
        UtilisateurHorsTenantError: cible d'un autre tenant.
        UtilisateurIntrouvableError: cible inexistante.
        RoleInvalideError: rôle hors des 3 valeurs autorisées.
    """
    if cible_user_id == acteur_user_id:
        raise AutoModificationInterditeError(
            "Un administrateur ne peut pas changer son propre rôle."
        )

    async with connexion.transaction():
        await _verifier_cible_dans_le_tenant(
            connexion, cible_user_id=cible_user_id, tenant_id_appelant=tenant_id_appelant
        )
        await update_user_role(connexion, cible_user_id, nouveau_role)  # RoleInvalideError possible

        await enregistrer_audit_gouvernance_web(
            connexion,
            domaine="utilisateur",
            action="utilisateur_changement_role",
            cible_id=cible_user_id,
            acteur_user_id=acteur_user_id,
            details={"nouveau_role": nouveau_role},
        )


async def desactiver_utilisateur(
    connexion: asyncpg.Connection,
    *,
    cible_user_id: UUID,
    tenant_id_appelant: UUID,
    acteur_user_id: UUID,
) -> None:
    """
    Raises:
        AutoModificationInterditeError: cible == appelant.
        UtilisateurHorsTenantError: cible d'un autre tenant.
        UtilisateurIntrouvableError: cible inexistante.
    """
    if cible_user_id == acteur_user_id:
        raise AutoModificationInterditeError(
            "Un administrateur ne peut pas se désactiver lui-même."
        )

    async with connexion.transaction():
        await _verifier_cible_dans_le_tenant(
            connexion, cible_user_id=cible_user_id, tenant_id_appelant=tenant_id_appelant
        )
        await deactivate_user(connexion, cible_user_id)

        await enregistrer_audit_gouvernance_web(
            connexion,
            domaine="utilisateur",
            action="utilisateur_desactivation",
            cible_id=cible_user_id,
            acteur_user_id=acteur_user_id,
        )


async def reactiver_utilisateur(
    connexion: asyncpg.Connection,
    *,
    cible_user_id: UUID,
    tenant_id_appelant: UUID,
    acteur_user_id: UUID,
) -> None:
    """Pas de restriction d'auto-modification ici : un compte désactivé
    ne peut de toute façon plus s'authentifier pour appeler cette route
    lui-même — le cas "cible == appelant" est structurellement
    impossible en pratique, pas seulement improbable."""
    async with connexion.transaction():
        await _verifier_cible_dans_le_tenant(
            connexion, cible_user_id=cible_user_id, tenant_id_appelant=tenant_id_appelant
        )
        await reactivate_user(connexion, cible_user_id)

        await enregistrer_audit_gouvernance_web(
            connexion,
            domaine="utilisateur",
            action="utilisateur_reactivation",
            cible_id=cible_user_id,
            acteur_user_id=acteur_user_id,
        )


__all__ = [
    "AutoModificationInterditeError",
    "EmailAlreadyExistsError",
    "RoleInvalideError",
    "UtilisateurHorsTenantError",
    "UtilisateurIntrouvableError",
    "changer_role_utilisateur",
    "creer_utilisateur",
    "desactiver_utilisateur",
    "reactiver_utilisateur",
]
