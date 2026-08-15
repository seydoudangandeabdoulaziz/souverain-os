"""CLI de la Brique 4 — déclenchement manuel, réservé machine de dev.

Même logique que la Brique 3 : pas d'endpoint API en MVP, CLI uniquement.

Usage :
    uv run souverain-detecter --tenant tenant_ne

Prérequis :
1. Brique 3 déjà exécutée pour ce tenant (des transactions existent)
2. Migration 0001_create_detections_table.sql appliquée (ou laissée à
   l'auto-réparation de persistence.py, qui crée la table au premier
   passage si besoin)
"""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter

from brique_01_postgresql.connection import close_pool, create_pool

from brique_04_detection.lecture import lire_transactions_ordonnees
from brique_04_detection.moteur import detecter_sequentiellement
from brique_04_detection.persistence import enregistrer_detections

TENANT_DEFAUT = "tenant_ne"


def _construire_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fait tourner le moteur de détection sur les transactions d'un tenant."
    )
    parser.add_argument(
        "--tenant",
        default=TENANT_DEFAUT,
        help=f"Nom du schéma tenant (défaut : {TENANT_DEFAUT})",
    )
    return parser


async def executer(args: argparse.Namespace) -> None:
    pool = await create_pool()
    try:
        transactions = await lire_transactions_ordonnees(pool, args.tenant)
        print(f"{len(transactions)} transactions lues pour le tenant {args.tenant}")

        evenements = detecter_sequentiellement(transactions)
        print(f"{len(evenements)} événements de détection générés")

        if evenements:
            repartition = Counter(e.pattern_type for e in evenements)
            for pattern_type, nb in sorted(repartition.items()):
                print(f"  - {pattern_type} : {nb}")

        nb_insere = await enregistrer_detections(pool, args.tenant, evenements)
        print(f"✅ {nb_insere} détections enregistrées dans {args.tenant}.detections")
    finally:
        await close_pool()


def main() -> None:
    parser = _construire_parser()
    args = parser.parse_args()
    asyncio.run(executer(args))


if __name__ == "__main__":
    main()
