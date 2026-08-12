#!/usr/bin/env python3
"""
Script CLI — Healthcheck de l'environnement SOUVERAIN-OS.

Usage :
    uv run python scripts/healthcheck_env.py

Affiche un rapport lisible et retourne un code de sortie non-nul
si un des checks échoue (utile en CI plus tard).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Permet d'exécuter ce script directement sans avoir installé le package,
# tant que la structure src/ layout est respectée.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from brique_00_fondations.healthcheck import run_healthcheck  # noqa: E402


def main() -> int:
    report = run_healthcheck()

    print("=" * 60)
    print("SOUVERAIN-OS — Healthcheck environnement (Brique 0)")
    print("=" * 60)

    for result in report.results:
        status = "OK  " if result.ok else "FAIL"
        print(f"[{status}] {result.label} — {result.detail}")

    print("=" * 60)
    if report.all_ok:
        print("Résultat global : SAIN — l'environnement est prêt.")
        return 0

    print("Résultat global : ÉCHEC — voir les lignes [FAIL] ci-dessus.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
