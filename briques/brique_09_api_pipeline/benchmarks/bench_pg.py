"""Banc d'essai du cycle incrémental sur PostgreSQL RÉEL (base jetable).

Mesure, pour un tenant déjà chargé de N transactions : durée d'ingestion d'un
lot de 1 000 (p50/p95), durée d'un cycle (p50/p95/max), transactions relues,
repli d'épisode et pic mémoire Python d'un cycle. Compare aux seuils
d'acceptation du document de périmètre.

DESTRUCTIF sur le schéma du tenant de test (TRUNCATE) : refuse toute base autre
que `souverain_pipeline_test`.

Prérequis : base préparée comme pour les tests (migrations B1 0001-0009, B2,
B3-B5, B8, B9 0001), SOUVERAIN_PIPELINE_TEST_DSN, variables d'environnement des
tests B9 (voir tests/conftest.py).

Usage (depuis briques/brique_09_api_pipeline) :
    uv run python benchmarks/bench_pg.py --volume 50000 --comptes 5000
    uv run python benchmarks/bench_pg.py --volume 50000 --comptes 300   # comptes très actifs
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
import statistics
import sys
import time
import tracemalloc
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))

import asyncpg  # noqa: E402
from brique_01_postgresql.connection import close_tenant_pools, create_tenant_pipeline_pool  # noqa: E402
from brique_01_postgresql.tenant_credentials import role_name_for_tenant  # noqa: E402
from brique_09_api_pipeline import cycle as module_cycle  # noqa: E402
from brique_09_api_pipeline.cycle import executer_cycle  # noqa: E402
from brique_09_api_pipeline.ingestion import ingerer_lot  # noqa: E402
from brique_09_api_pipeline.provisionnement import provisionner_tenant  # noqa: E402
from helpers_b9 import generer  # noqa: E402

DSN_PAR_DEFAUT = (
    "postgresql://postgres:devpw_local_uniquement@127.0.0.1:55432/souverain_pipeline_test"
)
SEUILS = {"cycle_p95_s": 2.0, "ingestion_p95_s": 1.0, "memoire_cycle_mo": 300.0}
LOT = 1000
ITERATIONS = 20


def _p(valeurs: list[float], q: float) -> float:
    ordonnees = sorted(valeurs)
    return ordonnees[min(len(ordonnees) - 1, int(q * (len(ordonnees) - 1) + 0.5))]


async def main(
    volume: int,
    comptes: int,
    preparer_env: bool,
    episode_max_heures: int | None = None,
    chauds: int = 0,
    part_chaude: float = 0.0,
) -> dict[str, object]:
    # Par défaut : le conteneur jetable créé par scripts/preparer_base_test.sh.
    dsn = os.environ.get("SOUVERAIN_PIPELINE_TEST_DSN", DSN_PAR_DEFAUT)
    if urlsplit(dsn).path.lstrip("/") != "souverain_pipeline_test":
        raise SystemExit("Refus : base différente de souverain_pipeline_test")
    from support_b9 import A  # noqa: PLC0415

    admin = await asyncpg.connect(dsn)
    await provisionner_tenant(admin, A.tenant_id, A.schema)
    await admin.execute(
        f"TRUNCATE {A.schema}.transactions, {A.schema}.ingestion_keys, "
        f"{A.schema}.pipeline_cursor, {A.schema}.detections, {A.schema}.alertes"
    )
    # Identité base de données du rôle pipeline : mot de passe jetable local.
    mot_de_passe = secrets.token_hex(32)
    role = role_name_for_tenant(A.tenant_id, "pipeline")
    ordre = await admin.fetchval(
        "SELECT format('ALTER ROLE %I LOGIN PASSWORD %L', $1::text, $2::text)", role, mot_de_passe
    )
    await admin.execute(ordre)
    os.environ["TENANT_DB_CREDENTIALS_JSON"] = json.dumps(
        {str(A.tenant_id): {"pipeline_password": mot_de_passe}}
    )
    host = urlsplit(dsn)
    os.environ.setdefault("POSTGRES_HOST", host.hostname or "127.0.0.1")
    os.environ.setdefault("POSTGRES_PORT", str(host.port or 5432))
    os.environ.setdefault("POSTGRES_DB", "souverain_pipeline_test")
    os.environ.setdefault("APP_POSTGRES_HOST", host.hostname or "127.0.0.1")
    os.environ.setdefault("APP_POSTGRES_PORT", str(host.port or 5432))
    os.environ.setdefault("APP_POSTGRES_DB", "souverain_pipeline_test")
    pool = await create_tenant_pipeline_pool(A.tenant_id)

    plafond = None if episode_max_heures is None else timedelta(hours=episode_max_heures)
    jours = max(2, volume // 20_000)
    items = generer(
        n=volume + ITERATIONS * LOT,
        pool=comptes,
        jours=jours,
        seed=11,
        comptes_chauds=chauds,
        part_chaude=part_chaude,
    )
    # Les ITERATIONS derniers lots servent à la mesure en régime établi.
    prechargement, mesures = items[: -ITERATIONS * LOT], items[-ITERATIONS * LOT :]

    t0 = time.perf_counter()
    for i in range(0, len(prechargement), LOT):
        await ingerer_lot(pool, A.schema, A.tenant_id, "bench", prechargement[i : i + LOT])
        if (i // LOT) % 25 == 24:
            await executer_cycle(pool, A.schema, A.tenant_id, plafond)
    await executer_cycle(pool, A.schema, A.tenant_id, plafond)
    prechargement_s = time.perf_counter() - t0

    t_ing, t_cyc, relues, replis, nouvelles, tronques = [], [], [], [], [], []
    phases: dict[str, float] = {}

    def _chronometrer(nom: str) -> None:
        """Cumule le temps passé dans une phase du cycle (async ou sync)."""
        original = getattr(module_cycle, nom)
        if asyncio.iscoroutinefunction(original):

            async def enveloppe_async(*a, **k):  # type: ignore[no-untyped-def]
                debut = time.perf_counter()
                try:
                    return await original(*a, **k)
                finally:
                    phases[nom] = phases.get(nom, 0.0) + time.perf_counter() - debut

            setattr(module_cycle, nom, enveloppe_async)
        else:

            def enveloppe(*a, **k):  # type: ignore[no-untyped-def]
                debut = time.perf_counter()
                try:
                    return original(*a, **k)
                finally:
                    phases[nom] = phases.get(nom, 0.0) + time.perf_counter() - debut

            setattr(module_cycle, nom, enveloppe)

    for nom in (
        "_charger_episodes",
        "detecter_sequentiellement",
        "_filtrer_deja_connus",
        "lire_detections_fenetre",
        "enregistrer_scores",
    ):
        _chronometrer(nom)
    phases.clear()
    for i in range(0, len(mesures), LOT):
        lot = mesures[i : i + LOT]
        a = time.perf_counter()
        await ingerer_lot(pool, A.schema, A.tenant_id, "bench", lot)
        t_ing.append(time.perf_counter() - a)
        if i == len(mesures) - LOT:  # dernière itération : mesure mémoire
            tracemalloc.start()
        a = time.perf_counter()
        res = await executer_cycle(pool, A.schema, A.tenant_id, plafond)
        t_cyc.append(time.perf_counter() - a)
        relues.append(res.transactions_relues)
        replis.append(res.replis_episode)
        tronques.append(res.episodes_tronques)
        nouvelles.append(res.nouvelles_transactions)
    _, pic = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    stockees = await admin.fetchval(f"SELECT count(*) FROM {A.schema}.transactions")
    detections = await admin.fetchval(f"SELECT count(*) FROM {A.schema}.detections")
    resultat = {
        "volume_stocke": stockees,
        "comptes": comptes,
        "comptes_chauds": chauds,
        "part_chaude": part_chaude,
        "detections": detections,
        "prechargement_s": round(prechargement_s, 1),
        "ingestion_lot1000_p50_s": round(statistics.median(t_ing), 3),
        "ingestion_lot1000_p95_s": round(_p(t_ing, 0.95), 3),
        "cycle_p50_s": round(statistics.median(t_cyc), 3),
        "cycle_p95_s": round(_p(t_cyc, 0.95), 3),
        "cycle_max_s": round(max(t_cyc), 3),
        "transactions_relues_moy": round(statistics.mean(relues)),
        "transactions_relues_max": max(relues),
        "episode_max_heures": episode_max_heures,
        "replis_episode_total": sum(replis),
        "episodes_tronques_total": sum(tronques),
        "memoire_cycle_pic_mo": round(pic / 1_048_576, 1),
        "phases_cycle_moy_s": {
            nom: round(total / len(t_cyc), 3) for nom, total in sorted(phases.items())
        },
    }
    resultat["verdict"] = {
        "cycle_p95": resultat["cycle_p95_s"] <= SEUILS["cycle_p95_s"],
        "ingestion_p95": resultat["ingestion_lot1000_p95_s"] <= SEUILS["ingestion_p95_s"],
        "memoire_cycle": resultat["memoire_cycle_pic_mo"] <= SEUILS["memoire_cycle_mo"],
    }
    await close_tenant_pools()
    await admin.close()
    return resultat


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--volume", type=int, required=True)
    parser.add_argument("--comptes", type=int, required=True)
    parser.add_argument("--episode-max-heures", type=int, default=None)
    parser.add_argument("--comptes-chauds", type=int, default=0, help="agents très actifs")
    parser.add_argument(
        "--part-chaude", type=float, default=0.0, help="part des transactions des agents"
    )
    parser.add_argument("--preparer-env", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    print(
        json.dumps(
            asyncio.run(
                main(
                    args.volume,
                    args.comptes,
                    args.preparer_env,
                    args.episode_max_heures,
                    args.comptes_chauds,
                    args.part_chaude,
                )
            ),
            ensure_ascii=False,
        )
    )
