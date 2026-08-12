"""
Tests de base (sanity) pour la Brique 0 — Fondations.

Ces tests ne vérifient aucune logique métier (il n'y en a pas encore).
Ils garantissent uniquement que le socle de développement est sain :
version Python correcte, structure de dossiers présente, module
healthcheck fonctionnel.
"""

from __future__ import annotations

import sys

from brique_00_fondations.healthcheck import (
    PYTHON_MIN_VERSION,
    check_brique_00_layout,
    check_python_version,
    check_repo_structure,
    find_repo_root,
    run_healthcheck,
)


def test_python_version_is_at_least_3_12() -> None:
    """Le projet impose Python 3.12+ (document fondateur, Bloc 6)."""
    assert sys.version_info[:2] >= PYTHON_MIN_VERSION


def test_check_python_version_reports_ok() -> None:
    result = check_python_version()
    assert result.ok is True
    assert "détectée" in result.detail


def test_find_repo_root_locates_expected_markers() -> None:
    """
    La racine du dépôt doit être détectable depuis ce fichier de test,
    et doit contenir les dossiers structurants attendus.
    """
    root = find_repo_root()
    assert root is not None
    assert (root / "briques").is_dir()
    assert (root / "docs").is_dir()


def test_check_repo_structure_is_ok() -> None:
    result = check_repo_structure()
    assert result.ok is True, result.detail


def test_check_brique_00_layout_is_ok() -> None:
    result = check_brique_00_layout()
    assert result.ok is True, result.detail


def test_run_healthcheck_aggregates_all_checks() -> None:
    """Le rapport global doit contenir exactement 3 vérifications, toutes OK."""
    report = run_healthcheck()
    assert len(report.results) == 3
    assert report.all_ok is True
