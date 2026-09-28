"""Textes français du dashboard — SEUL dictionnaire livré maintenant.

Aucun texte de ce fichier n'est écrit ailleurs dans le code ou les
templates : tout passage par t() dans __init__.py. Ajouter une langue
future (haoussa, zarma — ADR-001) signifie ajouter un fichier
{langue}.py similaire, jamais modifier les templates.
"""

from __future__ import annotations

TEXTES_FR: dict[str, str] = {
    "app.titre": "SOUVERAIN-OS — Investigation",
    "nav.alertes": "Alertes",
    "nav.deconnexion": "Déconnexion",
    "login.titre": "Connexion",
    "login.email": "Email",
    "login.mot_de_passe": "Mot de passe",
    "login.bouton": "Se connecter",
    "login.erreur": "Email ou mot de passe incorrect.",
    "alertes.titre": "Alertes ouvertes",
    "alertes.colonne_compte": "Compte",
    "alertes.colonne_score": "Score",
    "alertes.colonne_statut": "Statut",
    "alertes.colonne_patterns": "Motifs impliqués",
    "alertes.colonne_maj": "Dernière mise à jour",
    "alertes.aucune": "Aucune alerte ouverte pour ce tenant.",
    "alerte_detail.titre": "Détail de l'alerte",
    "alerte_detail.retour": "Retour à la liste",
    "alerte_detail.score": "Score",
    "alerte_detail.statut": "Statut",
    "alerte_detail.patterns": "Motifs impliqués",
    "alerte_detail.fenetre": "Fenêtre d'observation",
    "alerte_detail.avertissement_score": (
        "Ce score et ces motifs sont des indices d'investigation, "
        "pas une preuve de culpabilité."
    ),
    "alerte_detail.detections_liees": "Détections liées",
    "alerte_detail.chaines_redistribution": "Chaînes de redistribution",
    "alerte_detail.comptes_pont": "Comptes pont",
    "alerte_detail.chemins_alertes": "Chemins vers d'autres comptes alertés",
    "alerte_detail.aucun_resultat_graphe": "Aucun résultat pour ce compte sur cette requête.",
    "alerte_detail.chargement_graphe": "Chargement des résultats du graphe…",
    "erreur.non_trouve": "Alerte introuvable.",
    "erreur.session_invalide": "Session invalide, merci de vous reconnecter.",
    "erreur.tenant_sans_donnees": "Aucun cycle de scoring n'a encore été exécuté pour ce tenant.",
}
