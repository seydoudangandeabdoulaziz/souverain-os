"""Textes français de l'extension gouvernance (Brique 2 V2) — dictionnaire
distinct de celui de la Brique 7 ET de celui de la Brique 8, même
principe déjà établi : un mécanisme t() par brique, jamais un ajout
aux clés d'une autre brique déjà validée."""

from __future__ import annotations

TEXTES_FR: dict[str, str] = {
    "gouvernance.confirmation_changement_role": (
        "Confirmer le changement de rôle de cet utilisateur ?"
    ),
    "gouvernance.historique_acteur_web": "par l'utilisateur",
    "gouvernance.historique_acteur_cli": "par un opérateur CLI (non authentifié)",
    "gouvernance.nav_alertes": "Alertes",
    "gouvernance.nav_utilisateurs": "Utilisateurs",
    "gouvernance.nav_deconnexion": "Déconnexion",
    "gouvernance.titre": "Gestion des utilisateurs",
    "gouvernance.creer_titre": "Créer un utilisateur",
    "gouvernance.email": "Email",
    "gouvernance.mot_de_passe": "Mot de passe",
    "gouvernance.role": "Rôle",
    "gouvernance.role_admin": "Administrateur",
    "gouvernance.role_analyst": "Analyste",
    "gouvernance.role_auditor": "Auditeur",
    "gouvernance.bouton_creer": "Créer",
    "gouvernance.liste_titre": "Comptes du tenant",
    "gouvernance.colonne_email": "Email",
    "gouvernance.colonne_role": "Rôle",
    "gouvernance.colonne_statut": "Statut",
    "gouvernance.statut_actif": "Actif",
    "gouvernance.statut_desactive": "Désactivé",
    "gouvernance.action_desactiver": "Désactiver",
    "gouvernance.action_reactiver": "Réactiver",
    "gouvernance.action_soi_meme": "(vous)",
    "gouvernance.historique_titre": "Historique de gouvernance",
    "gouvernance.historique_vide": "Aucune opération de gouvernance enregistrée.",
    "gouvernance.erreur_email_existe": "Un compte existe déjà avec cet email.",
    "gouvernance.erreur_auto_modification": "Action impossible sur votre propre compte.",
    "gouvernance.erreur_hors_tenant": "Cet utilisateur n'appartient pas à votre tenant.",
    "gouvernance.erreur_role_invalide": "Rôle invalide.",
}
