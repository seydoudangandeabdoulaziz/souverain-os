"""Garanties statiques de l'ADR-005 (D2), sans base de données.

Elles protègent la SÉPARATION du code : le chemin de lecture ne doit jamais
pouvoir atteindre le provisionnement (DDL/GRANT), et le diagnostic ne doit
contenir que des lectures de catalogue.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from brique_08_audit_human_loop import diagnostic

_SRC = Path(__file__).resolve().parents[1] / "src" / "brique_08_audit_human_loop"
_MOTS_INTERDITS = re.compile(
    r"\b(CREATE|ALTER|DROP|GRANT|REVOKE|INSERT|UPDATE|DELETE|TRUNCATE)\b", re.IGNORECASE
)


def _modules_importes(fichier: str) -> set[str]:
    arbre = ast.parse((_SRC / fichier).read_text(encoding="utf-8"))
    modules: set[str] = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.ImportFrom) and noeud.module:
            modules.add(noeud.module)
            modules.update(f"{noeud.module}.{alias.name}" for alias in noeud.names)
        elif isinstance(noeud, ast.Import):
            modules.update(alias.name for alias in noeud.names)
    return modules


def test_lecture_n_importe_ni_persistence_ni_pool_admin() -> None:
    importes = _modules_importes("lecture.py")
    assert not any("persistence" in m for m in importes)
    assert "brique_01_postgresql.connection" not in importes
    assert "provisionner_audit" not in (_SRC / "lecture.py").read_text(encoding="utf-8")


def test_diagnostic_n_importe_pas_persistence() -> None:
    assert not any("persistence" in m for m in _modules_importes("diagnostic.py"))


def test_requetes_du_diagnostic_sont_des_lectures_de_catalogue() -> None:
    requetes = {
        nom: valeur
        for nom, valeur in vars(diagnostic).items()
        if nom.startswith("_REQUETE") and isinstance(valeur, str)
    }
    assert requetes, "aucune requête de diagnostic trouvée : le test ne vérifie plus rien"
    for nom, sql in requetes.items():
        sans_litteraux = re.sub(r"'[^']*'", "''", sql)  # 'INSERT' en littéral est une valeur
        assert not _MOTS_INTERDITS.search(sans_litteraux), f"{nom} contient du DDL/DML"
