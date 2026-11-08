"""Mécanisme d'externalisation des textes de l'explication IA — étape 6b.

Même principe que les Briques 7 et 8 (ADR-001) : aucun texte utilisateur
n'est écrit en dur dans le code ou les templates. Ce dictionnaire est propre
à `souverain_app` et distinct de ceux des briques (voir ADR-007).

Ajouter une langue signifie ajouter un fichier {langue}.py et l'enregistrer
dans _DICTIONNAIRES, sans toucher aux routes.
"""

from __future__ import annotations

from souverain_app.traductions.fr import TEXTES_FR
from souverain_app.traductions.rag_fr import TEXTES_RAG_FR

_DICTIONNAIRES: dict[str, dict[str, str]] = {
    "fr": {**TEXTES_FR, **TEXTES_RAG_FR},
}

_LANGUE_PAR_DEFAUT = "fr"


def t(cle: str, langue: str = _LANGUE_PAR_DEFAUT) -> str:
    """Traduit une clé.

    Repli en cascade : langue absente -> français ; clé absente -> la clé
    elle-même entre crochets (visible en développement, jamais un crash).
    """
    dictionnaire = _DICTIONNAIRES.get(langue, _DICTIONNAIRES[_LANGUE_PAR_DEFAUT])
    return dictionnaire.get(cle, f"[{cle}]")
