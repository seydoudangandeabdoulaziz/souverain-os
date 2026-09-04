"""Mécanisme d'externalisation des textes de la Brique 8 — même règle
non négociable que la Brique 7 (ADR-001) : aucun texte français en dur
dans un template. Instance ISOLÉE de celle de la Brique 7 (fichier
distinct, fonction distincte) pour ne modifier aucun fichier déjà
validé de la Brique 7 — voir routes.py, qui construit sa propre
Jinja2Templates plutôt que de réutiliser celle de creer_application().
"""

from __future__ import annotations

from brique_08_audit_human_loop.traductions.fr import TEXTES_FR

_DICTIONNAIRES: dict[str, dict[str, str]] = {
    "fr": TEXTES_FR,
}

_LANGUE_PAR_DEFAUT = "fr"


def t(cle: str, langue: str = _LANGUE_PAR_DEFAUT) -> str:
    """Repli en cascade identique à brique_07_dashboard.traductions.t —
    langue absente -> français, clé absente -> la clé entre crochets.
    """
    dictionnaire = _DICTIONNAIRES.get(langue, _DICTIONNAIRES[_LANGUE_PAR_DEFAUT])
    return dictionnaire.get(cle, f"[{cle}]")
