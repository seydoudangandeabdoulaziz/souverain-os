"""Textes français de l'explication IA (étape 6b, ADR-007).

Les textes sont identiques à ceux qui étaient auparavant écrits en dur dans
`explication_routes.py` : aucun changement de wording, seulement un
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
}
