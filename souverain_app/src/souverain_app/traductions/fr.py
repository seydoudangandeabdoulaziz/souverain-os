"""Textes français de l'explication IA (étape 6b, ADR-007).

Les textes sont identiques à ceux qui étaient auparavant écrits en dur dans
`explication_routes.py` et `explication_ia.py` : aucun changement de wording, seulement un
déplacement vers ce dictionnaire.
"""

from __future__ import annotations

TEXTES_FR: dict[str, str] = {
    "explication.bouton": "Expliquer cette alerte",
    "explication.aide": (
        "L’explication est produite localement à partir des faits enregistrés."
    ),
    "explication.titre": "Explication de l’alerte",
    "explication.origine_repli": (
        "Explication de repli déterministe "
        "(modèle indisponible ou réponse rejetée)."
    ),
    "explication.origine_modele": "Explication générée localement par le modèle.",
    "explication.avertissement": (
        "Cette explication est indicative : elle ne constitue ni un verdict "
        "ni une recommandation d’action. "
        "Les seuils et poids actuels sont provisoires."
    ),
    "explication.comparaison.inferieur": "inférieur au seuil",
    "explication.comparaison.egal": "égal au seuil",
    "explication.comparaison.superieur": "supérieur au seuil",
    "explication.phrase.compte": "L'alerte concerne le compte {compte}.",
    "explication.phrase.comparaison_score_seuil": (
        "Le score est de {score}, {comparaison} de {seuil}."
    ),
    "explication.phrase.statut": "Le statut enregistré est : {statut}.",
    "explication.phrase.fenetre": "Fenêtre enregistrée : {debut} au {fin}.",
    "explication.phrase.motifs": "Motifs contributifs enregistrés : {details}.",
    "explication.motif_detail": "{nom} (poids {poids})",
    "explication.phrase.transactions_indisponibles": (
        "Le nombre de transactions n'est pas disponible."
    ),
    "explication.phrase.transactions_disponibles": (
        "Le nombre de transactions fourni est {nombre}."
    ),
    "explication.donnees_insuffisantes": (
        "Les données de cette alerte ne permettent pas de produire "
        "une explication fiable. Une vérification des données est nécessaire."
    ),
    "rag.indisponible": "La recherche documentaire n’est pas disponible.",
    "rag.concurrence": "Une recherche documentaire est déjà en cours.",
    "rag.aucun_resultat": "Aucun passage documentaire sourcé n’a été trouvé.",
    "rag.reference": "Référence documentaire",
    "rag.page": "page",
    "rag.source": "Ouvrir la source",
    "rag.synthetique": "Source synthétique",
}
