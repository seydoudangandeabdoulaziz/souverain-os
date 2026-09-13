"""Mécanisme d'externalisation des textes de l'extension gouvernance
— instance ISOLÉE de celles de Brique 7 et Brique 8 (ADR-001)."""

from __future__ import annotations

from brique_02_auth_rbac.gouvernance.traductions.fr import TEXTES_FR

_DICTIONNAIRES: dict[str, dict[str, str]] = {"fr": TEXTES_FR}
_LANGUE_PAR_DEFAUT = "fr"


def t(cle: str, langue: str = _LANGUE_PAR_DEFAUT) -> str:
    dictionnaire = _DICTIONNAIRES.get(langue, _DICTIONNAIRES[_LANGUE_PAR_DEFAUT])
    return dictionnaire.get(cle, f"[{cle}]")
