"""Textes français de la recherche documentaire (étape 8, ADR-008).

Fichier distinct de `fr.py` : celui-ci est couvert par le gel du lot v2
(étape 6b) et ne doit pas changer sans lot v3.
"""

from __future__ import annotations

TEXTES_RAG_FR: dict[str, str] = {
    "rag.indisponible": "La recherche documentaire n’est pas disponible.",
    "rag.concurrence": "Une recherche documentaire est déjà en cours.",
    "rag.aucun_resultat": "Aucun passage documentaire sourcé n’a été trouvé.",
    "rag.reference": "Référence documentaire",
    "rag.page": "page",
    "rag.source": "Ouvrir la source",
    "rag.synthetique": "Source synthétique",
}
