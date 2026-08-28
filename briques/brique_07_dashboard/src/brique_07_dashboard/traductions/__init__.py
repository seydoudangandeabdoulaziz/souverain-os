"""Mécanisme d'externalisation des textes — posé dès cette brique, pas
un ajout futur (ADR-001, point 6 de 00_DECISIONS_VERROUILLEES.md).

RÈGLE NON NÉGOCIABLE, même niveau de rigueur que "aucun Cypher hors
garde_isolation.py" : aucun texte utilisateur écrit en dur dans un
template Jinja2 ou dans le code Python générant du HTML. Tout texte
passe par t(cle, langue) — enregistrée comme global Jinja2 dans app.py
({{ t('cle') }} dans les templates).

Seul le français est livré maintenant (fr.py) ; ajouter une langue
future (haoussa, zarma) signifie ajouter un fichier {langue}.py et
l'enregistrer dans _DICTIONNAIRES, jamais toucher aux templates.
"""

from __future__ import annotations

from brique_07_dashboard.traductions.fr import TEXTES_FR

_DICTIONNAIRES: dict[str, dict[str, str]] = {
    "fr": TEXTES_FR,
}

_LANGUE_PAR_DEFAUT = "fr"

# Mapping country_code -> langue par défaut (point 6 verrouillé : la
# langue se dérive de country_code, déjà présent dans le schéma tenant
# depuis la Brique 1 — aucune modification de schéma nécessaire).
# Extensible sans toucher au reste du mécanisme.
_LANGUE_PAR_PAYS: dict[str, str] = {
    "NE": "fr",
}


def langue_pour_pays(country_code: str) -> str:
    """Résout la langue par défaut pour un country_code, avec repli sur le français."""
    return _LANGUE_PAR_PAYS.get(country_code, _LANGUE_PAR_DEFAUT)


def t(cle: str, langue: str = _LANGUE_PAR_DEFAUT) -> str:
    """Traduit une clé.

    Repli en cascade : langue demandée absente -> français ; clé
    absente même en français -> la clé elle-même entre crochets
    (visible immédiatement en développement, jamais un crash côté
    utilisateur).
    """
    dictionnaire = _DICTIONNAIRES.get(langue, _DICTIONNAIRES[_LANGUE_PAR_DEFAUT])
    return dictionnaire.get(cle, f"[{cle}]")
