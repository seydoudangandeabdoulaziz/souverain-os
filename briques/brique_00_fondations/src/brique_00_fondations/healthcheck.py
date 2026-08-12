"""
Healthcheck de l'environnement de développement SOUVERAIN-OS.

Rôle pédagogique : avant de construire quoi que ce soit, on vérifie
que le socle sur lequel on va construire est sain — un peu comme
un maçon qui teste la solidité du sol avant de couler des fondations.

Ce module ne contacte aucun service externe (pas de réseau, pas de
base de données) : il vérifie uniquement l'état local de la machine
de développement.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

# Version minimale requise par le projet (cf. pyproject.toml racine).
PYTHON_MIN_VERSION: tuple[int, int] = (3, 12)

# Dossiers structurants qui doivent exister à la racine du dépôt.
# Racine du dépôt = 4 niveaux au-dessus de ce fichier :
# src/brique_00_fondations/healthcheck.py -> brique_00_fondations -> briques -> racine
REPO_ROOT_MARKERS: tuple[str, ...] = (
    "briques",
    "docs",
    "shared",
    "scripts",
    "tests",
    "data",
)


@dataclass
class HealthcheckResult:
    """
    Résultat structuré d'une vérification unique.

    ok : le check est-il passé ?
    label : description humaine du check.
    detail : information complémentaire (ex. version détectée).
    """

    ok: bool
    label: str
    detail: str = ""


@dataclass
class HealthcheckReport:
    """Agrège l'ensemble des résultats d'un healthcheck complet."""

    results: list[HealthcheckResult] = field(default_factory=list)

    @property
    def all_ok(self) -> bool:
        """Vrai seulement si TOUS les checks sont passés."""
        return all(result.ok for result in self.results)

    def add(self, result: HealthcheckResult) -> None:
        self.results.append(result)


def check_python_version(
    min_version: tuple[int, int] = PYTHON_MIN_VERSION,
) -> HealthcheckResult:
    """
    Vérifie que la version de Python utilisée respecte le minimum requis.

    Le projet impose Python 3.12+ (cf. document fondateur, Bloc 6).
    """
    current = sys.version_info[:2]
    ok = current >= min_version
    detail = f"détectée: {current[0]}.{current[1]} — requise: >= {min_version[0]}.{min_version[1]}"
    return HealthcheckResult(ok=ok, label="Version de Python", detail=detail)


def find_repo_root(start: Path | None = None) -> Path | None:
    """
    Remonte l'arborescence depuis `start` pour trouver la racine du dépôt.

    On considère qu'on a trouvé la racine quand le dossier contient
    TOUS les marqueurs structurants attendus (briques/, docs/, etc.).
    Retourne None si aucune racine valide n'est trouvée.
    """
    current = start or Path(__file__).resolve()

    for candidate in [current, *current.parents]:
        if all((candidate / marker).is_dir() for marker in REPO_ROOT_MARKERS):
            return candidate

    return None


def check_repo_structure() -> HealthcheckResult:
    """
    Vérifie que la structure de dossiers cible du dépôt est présente.

    Ne vérifie PAS le contenu des briques futures (elles ne doivent
    contenir qu'un README, conformément à la règle
    STRUCTURE != IMPLÉMENTATION) — seulement leur existence.
    """
    root = find_repo_root()
    if root is None:
        return HealthcheckResult(
            ok=False,
            label="Structure du dépôt",
            detail=f"racine introuvable (marqueurs attendus: {', '.join(REPO_ROOT_MARKERS)})",
        )

    missing = [marker for marker in REPO_ROOT_MARKERS if not (root / marker).is_dir()]
    ok = len(missing) == 0
    detail = "structure complète" if ok else f"dossiers manquants: {', '.join(missing)}"
    return HealthcheckResult(ok=ok, label="Structure du dépôt", detail=detail)


def check_brique_00_layout() -> HealthcheckResult:
    """
    Vérifie que la Brique 0 elle-même respecte son propre périmètre attendu
    (README, pyproject.toml, src/, tests/, scripts/).
    """
    brique_root = Path(__file__).resolve().parents[2]
    expected = ("README.md", "pyproject.toml", "src", "tests", "scripts")
    missing = [name for name in expected if not (brique_root / name).exists()]
    ok = len(missing) == 0
    detail = "layout Brique 0 complet" if ok else f"éléments manquants: {', '.join(missing)}"
    return HealthcheckResult(ok=ok, label="Structure de la Brique 0", detail=detail)


def run_healthcheck() -> HealthcheckReport:
    """
    Exécute l'ensemble des vérifications et retourne un rapport agrégé.

    C'est le point d'entrée principal utilisé par le script CLI
    et par les tests automatisés.
    """
    report = HealthcheckReport()
    report.add(check_python_version())
    report.add(check_repo_structure())
    report.add(check_brique_00_layout())
    return report
