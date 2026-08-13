#!/usr/bin/env python3
"""
Script CLI — Healthcheck de la base PostgreSQL/TimescaleDB.

Usage :
    uv run python scripts/db_healthcheck.py

Prérequis : le conteneur PostgreSQL doit être démarré :
    docker compose --profile postgres up -d
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from brique_01_postgresql.connection import close_pool  # noqa: E402
from brique_01_postgresql.healthcheck_db import run_db_healthcheck  # noqa: E402


async def main() -> int:
    print("=" * 60)
    print("SOUVERAIN-OS — Healthcheck base de données (Brique 1)")
    print("=" * 60)

    report = await run_db_healthcheck()

    for result in report.results:
        status = "OK  " if result.ok else "FAIL"
        print(f"[{status}] {result.label} — {result.detail}")

    await close_pool()

    print("=" * 60)
    if report.all_ok:
        print("Résultat global : SAIN — la base est prête.")
        return 0

    print("Résultat global : ÉCHEC — voir les lignes [FAIL] ci-dessus.")
    print("Astuce : vérifier que 'docker compose --profile postgres up -d' a été lancé,")
    print("et que les migrations ont été appliquées (voir README.md de la Brique 1).")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
