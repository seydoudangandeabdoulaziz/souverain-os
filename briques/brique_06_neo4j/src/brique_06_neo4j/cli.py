"""Point d'entrée CLI de la Brique 6 : uv run souverain-grapher --tenant tenant_ne.

CLI uniquement, cohérent avec toutes les briques précédentes. Synchronise
le graphe puis exécute les 3 requêtes métier, affiche un résumé.
"""

from __future__ import annotations

import argparse
import asyncio

from brique_01_postgresql.connection import close_pool, create_pool

from brique_06_neo4j import requetes
from brique_06_neo4j.connexion import close_driver, create_driver
from brique_06_neo4j.lecture import lire_comptes_alertes
from brique_06_neo4j.synchronisation import synchroniser


async def executer_cycle_graphe(nom_schema_tenant: str) -> None:
    pool = await create_pool()
    driver = await create_driver()
    try:
        resultat_sync = await synchroniser(pool, driver, nom_schema_tenant)
        print(
            f"[souverain-grapher] {resultat_sync.nb_transactions_lues} transaction(s) lue(s), "
            f"{resultat_sync.nb_transactions_envoyees} envoyée(s) au graphe "
            f"(tenant_id={resultat_sync.tenant_id})."
        )

        comptes_alertes = await lire_comptes_alertes(pool, nom_schema_tenant)
        print(f"[souverain-grapher] {len(comptes_alertes)} compte(s) alerté(s) ouvert(s).")

        tenant_id = resultat_sync.tenant_id

        chaines = await requetes.chaines_redistribution(driver, tenant_id)
        print(f"[souverain-grapher] {len(chaines)} chaîne(s) de redistribution (3-6 sauts).")
        for chemin in chaines[:10]:
            print(f"  CHAÎNE {' -> '.join(chemin.comptes)}")

        ponts = await requetes.comptes_pont(driver, tenant_id, comptes_alertes)
        print(f"[souverain-grapher] {len(ponts)} compte(s) pont détecté(s).")
        for pont in ponts[:10]:
            print(
                f"  PONT {pont.compte_alerte_source} -> {pont.compte_pont} "
                f"-> {pont.compte_alerte_cible}"
            )

        chemins_alertes = await requetes.plus_courts_chemins_entre_alertes(
            driver, tenant_id, comptes_alertes
        )
        print(
            f"[souverain-grapher] {len(chemins_alertes)} chemin(s) trouvé(s) "
            f"entre comptes alertés distincts."
        )
        for chemin in chemins_alertes[:10]:
            print(f"  CHEMIN {' -> '.join(chemin.comptes)} ({chemin.nb_sauts} saut(s))")
    finally:
        await close_driver()
        await close_pool()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Synchronise le graphe Neo4j et exécute les requêtes d'investigation."
    )
    parser.add_argument(
        "--tenant",
        required=True,
        help="Nom du schéma tenant (ex. tenant_ne).",
    )
    args = parser.parse_args()

    asyncio.run(executer_cycle_graphe(args.tenant))


if __name__ == "__main__":
    main()
