"""CLI de la Brique 5 : `uv run souverain-scorer --tenant tenant_ne`.

Orchestration séquentielle : lecture -> agregation -> scoring -> seuils
-> alertes -> persistence, pour chaque compte_pivot identifié.

Réutilise create_pool() de la Brique 1 (pool asyncpg partagé,
brique_01_postgresql.connection.create_pool — confirmé sur la machine
du fondateur le 15/08/2026).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from uuid import UUID

import asyncpg

from souverain_scoring.agregation import recuperer_detections_fenetre
from souverain_scoring.alertes import preparer_alerte
from souverain_scoring.config import ParametresScoring
from souverain_scoring.lecture import lister_comptes_a_recalculer
from souverain_scoring.persistence import upsert_alerte, verifier_schema
from souverain_scoring.scoring import calculer_score
from souverain_scoring.seuils import evaluer_seuil

logger = logging.getLogger(__name__)


async def executer_cycle_scoring(
    pool: asyncpg.Pool,
    schema: str,
    tenant_id: UUID,
    country_code: str,
    data_classification: str,
    parametres: ParametresScoring,
) -> int:
    """Exécute un cycle complet de scoring pour un tenant.

    Retourne le nombre d'alertes créées ou mises à jour.
    """
    async with pool.acquire() as connexion:
        await verifier_schema(connexion, schema)
        comptes = await lister_comptes_a_recalculer(connexion, schema)

    if not comptes:
        logger.info("Aucun compte_pivot à recalculer pour le schéma %s", schema)
        return 0

    logger.info("%d compte_pivot à recalculer pour le schéma %s", len(comptes), schema)

    nombre_alertes = 0
    table_poids = parametres.table_poids()

    for compte_pivot in comptes:
        async with pool.acquire() as connexion:
            detections = await recuperer_detections_fenetre(
                connexion, schema, compte_pivot, parametres.fenetre_jours
            )
            if not detections:
                # Ne devrait pas arriver (le compte vient d'être signalé
                # par lecture.py), mais défensif en cas de course entre
                # cycles concurrents.
                logger.warning(
                    "Aucune détection trouvée dans la fenêtre pour compte_pivot=%s "
                    "alors que signalé par lecture.py — ignoré ce cycle",
                    compte_pivot,
                )
                continue

            score_compte = calculer_score(
                detections, table_poids, parametres.score_maximum
            )
            decision = evaluer_seuil(score_compte, parametres.seuil_alerte)

            if not decision.doit_alerter:
                logger.info(
                    "compte_pivot=%s score=%d sous le seuil (%d) — pas d'alerte",
                    compte_pivot,
                    decision.score,
                    parametres.seuil_alerte,
                )
                # Les détections sont quand même marquées "vues" pour ne
                # pas re-déclencher un recalcul inutile au prochain cycle
                # tant qu'aucune nouvelle détection n'arrive.
                for detection in detections:
                    await connexion.execute(
                        f"""
                        INSERT INTO {schema}.detections_traitees (detection_id)
                        VALUES ($1)
                        ON CONFLICT (detection_id) DO NOTHING
                        """,
                        detection.detection_id,
                    )
                continue

            alerte = await preparer_alerte(
                connexion, schema, tenant_id, country_code, data_classification, decision
            )
            await upsert_alerte(connexion, schema, alerte)
            nombre_alertes += 1
            logger.info(
                "Alerte créée/mise à jour : compte_pivot=%s score=%d is_synthetic=%s",
                compte_pivot,
                alerte.score,
                alerte.is_synthetic,
            )

    return nombre_alertes


def construire_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="SOUVERAIN-OS — Brique 5 : cycle de scoring et alertes"
    )
    parser.add_argument("--tenant", required=True, help="Nom du schéma tenant (ex. tenant_ne)")
    parser.add_argument(
        "--tenant-id",
        required=True,
        type=UUID,
        help="tenant_id UUID (référence shared.tenants_registry — "
        "vérifié le 17/08/2026 : tenant_id est UUID, pas texte, "
        "dans transactions/detections/alertes)",
    )
    parser.add_argument("--country-code", required=True, help="country_code (ex. NE)")
    parser.add_argument(
        "--data-classification",
        default="restricted",
        help="Classification de données par défaut pour les alertes",
    )
    return parser


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = construire_parser().parse_args()
    asyncio.run(_main_async(args))


async def _main_async(args: argparse.Namespace) -> None:
    # Nom de module confirmé sur la machine du fondateur (15/08/2026) :
    # brique_01_postgresql.connection.create_pool.
    from brique_01_postgresql.connection import create_pool

    parametres = ParametresScoring()
    pool = await create_pool()
    try:
        nombre = await executer_cycle_scoring(
            pool,
            schema=args.tenant,
            tenant_id=args.tenant_id,
            country_code=args.country_code,
            data_classification=args.data_classification,
            parametres=parametres,
        )
        logger.info("Cycle de scoring terminé : %d alerte(s) créée(s) ou mise(s) à jour", nombre)
    finally:
        await pool.close()


if __name__ == "__main__":
    main()
