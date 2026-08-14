"""CLI de la Brique 3 — déclenchement manuel, réservé machine de dev (décision
actée : pas d'endpoint API en MVP, cf. docs/brique-03/ARCHITECTURE.md).

Usage :
    uv run souverain-generer --tenant tenant_001 --nb-transactions 5000

HYPOTHÈSE À VÉRIFIER : la création du pool asyncpg ci-dessous est
autonome (asyncpg.create_pool direct) pour ne pas supposer un module
partagé précis. Si la Brique 1 expose déjà une fonction de création de
pool réutilisable (probable, vu le pattern déjà en place), remplace
_creer_pool() par un import de cette fonction pour éviter la duplication.
"""

from __future__ import annotations

import argparse
import asyncio
import random
from datetime import datetime

import asyncpg

from souverain_generateur.config import ParametresGenerateur
from souverain_generateur.generateur_legitime import (
    FUSEAU_NIGER,
    TransactionSynthetique,
    generer_lot_legitime,
)
from souverain_generateur.ingestion import inserer_transactions
from souverain_generateur.patterns_suspects import (
    generer_compte_pivot,
    generer_flux_frontalier,
    generer_micro_fractionnement,
    generer_structure_etoile,
    generer_transactions_nocturnes,
)

VOLUMETRIE_MAX_RECOMMANDEE = 50_000


def _construire_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Génère et insère des transactions synthétiques SOUVERAIN-OS."
    )
    parser.add_argument("--tenant", required=True, help="Nom du schéma tenant (ex: tenant_001)")
    parser.add_argument(
        "--nb-transactions",
        type=int,
        default=None,
        help="Volumétrie totale visée (défaut : valeur de .env, recommandé ≤ 50 000)",
    )
    parser.add_argument(
        "--pourcentage-suspect",
        type=float,
        default=None,
        help="Part de transactions issues de patterns suspects, en %% (défaut : .env)",
    )
    parser.add_argument("--seed", type=int, default=None, help="Seed de reproductibilité")
    parser.add_argument(
        "--intensite",
        choices=["legere", "moyenne", "forte"],
        default="moyenne",
        help="Intensité des patterns suspects injectés",
    )
    return parser


def _generer_transactions_suspectes(
    rng: random.Random, base_time: datetime, intensite: str, nb_cible: int
) -> list[TransactionSynthetique]:
    """Alterne entre les 5 patterns "structurels" jusqu'à approcher nb_cible.

    La saisonnalité est exclue par défaut du tirage (elle nécessite un
    événement calendaire explicite) — utilisable séparément si besoin.
    """
    generateurs = [
        generer_transactions_nocturnes,
        generer_structure_etoile,
        generer_micro_fractionnement,
        generer_flux_frontalier,
        generer_compte_pivot,
    ]
    resultat: list[TransactionSynthetique] = []
    while len(resultat) < nb_cible:
        fonction = rng.choice(generateurs)
        resultat.extend(fonction(rng, base_time, intensite=intensite))  # type: ignore[arg-type]
    return resultat[:nb_cible] if len(resultat) > nb_cible else resultat


async def _creer_pool(dsn: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=5)


async def executer(args: argparse.Namespace) -> None:
    # Ignore mypy ci-dessous nécessaire : pydantic-settings remplit database_url
    # depuis .env à l'exécution, mais mypy ne le sait pas sans le plugin
    # pydantic.mypy. Si le mypy.ini / pyproject.toml racine active déjà ce
    # plugin (probable, vu que les Briques 1 et 2 sont "mypy clean" avec le
    # même pattern), l'ignore ci-dessous devient inutile et peut être retiré.
    parametres = ParametresGenerateur()  # type: ignore[call-arg]

    nb_total = args.nb_transactions or parametres.nb_transactions_defaut
    if nb_total > VOLUMETRIE_MAX_RECOMMANDEE:
        print(
            f"⚠️  {nb_total} transactions demandées, au-delà de la recommandation "
            f"MVP de {VOLUMETRIE_MAX_RECOMMANDEE}. Poursuite quand même."
        )

    pct_suspect = args.pourcentage_suspect or parametres.pourcentage_suspect_defaut
    seed = args.seed if args.seed is not None else parametres.seed_defaut

    rng = random.Random(seed)
    base_time = datetime.now(FUSEAU_NIGER).replace(microsecond=0)

    nb_suspect = round(nb_total * pct_suspect / 100)
    nb_legitime = nb_total - nb_suspect

    transactions_legitimes = generer_lot_legitime(nb_legitime, seed=seed, base_time=base_time)
    transactions_suspectes = _generer_transactions_suspectes(
        rng, base_time, args.intensite, nb_suspect
    )

    toutes_transactions = transactions_legitimes + transactions_suspectes
    rng.shuffle(toutes_transactions)

    print(
        f"Génération : {len(transactions_legitimes)} légitimes + "
        f"{len(transactions_suspectes)} suspectes (seed={seed}, intensité={args.intensite})"
    )

    pool = await _creer_pool(parametres.database_url)
    try:
        total_insere = await inserer_transactions(pool, args.tenant, toutes_transactions)
    finally:
        await pool.close()

    print(f"✅ {total_insere} transactions insérées dans le schéma {args.tenant} (is_synthetic=true)")


def main() -> None:
    parser = _construire_parser()
    args = parser.parse_args()
    asyncio.run(executer(args))


if __name__ == "__main__":
    main()
