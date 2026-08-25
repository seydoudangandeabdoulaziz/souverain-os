"""Point d'entrée CLI de la Brique 5 : uv run souverain-scorer --tenant tenant_ne.

CLI uniquement — pas d'endpoint FastAPI, conformément à la décision
déjà tranchée pour souverain-generer (Brique 3) et souverain-detecter
(Brique 4), même si le document fondateur (Bloc 10) mentionne un
endpoint scoring : contradiction déjà signalée et déjà tranchée
différemment pour ce projet, non réimplémentée ici.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime, timedelta

from brique_01_postgresql.connection import close_pool, create_pool

from brique_05_scoring_alertes.agregation import agreger_par_compte
from brique_05_scoring_alertes.lecture import lire_detections_fenetre
from brique_05_scoring_alertes.persistence import enregistrer_scores
from brique_05_scoring_alertes.seuils import FENETRE_JOURS, SEUIL_ALERTE


async def executer_cycle_scoring(nom_schema_tenant: str) -> None:
    maintenant = datetime.now(UTC)
    fenetre_debut = maintenant - timedelta(days=FENETRE_JOURS)

    pool = await create_pool()
    try:
        detections = await lire_detections_fenetre(pool, nom_schema_tenant, fenetre_debut)

        print(
            f"[souverain-scorer] {len(detections)} détection(s) sur la fenêtre "
            f"trouvée(s) pour {nom_schema_tenant!r} "
            f"(fenêtre : {FENETRE_JOURS} jours, seuil d'alerte : {SEUIL_ALERTE})."
        )

        if not detections:
            print("[souverain-scorer] Rien à scorer.")
            return

        scores = agreger_par_compte(detections, fenetre_debut, maintenant)
        scores_alertants = [s for s in scores if s.score >= SEUIL_ALERTE]

        resultat = await enregistrer_scores(pool, nom_schema_tenant, scores)

        print(
            f"[souverain-scorer] {resultat.nb_comptes_scores} compte(s) scoré(s), "
            f"{len(scores_alertants)} au-dessus du seuil "
            f"({resultat.nb_alertes_creees} alerte(s) créée(s), "
            f"{resultat.nb_alertes_mises_a_jour} mise(s) à jour)."
        )

        for score in sorted(scores_alertants, key=lambda s: s.score, reverse=True):
            print(
                f"  ALERTE compte_pivot={score.compte_pivot!r} score={score.score} "
                f"patterns={score.pattern_types_impliques}"
            )
    finally:
        await close_pool()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Calcule les scores de risque par compte et déclenche les alertes."
    )
    parser.add_argument(
        "--tenant",
        required=True,
        help="Nom du schéma tenant (ex. tenant_ne).",
    )
    args = parser.parse_args()

    asyncio.run(executer_cycle_scoring(args.tenant))


if __name__ == "__main__":
    main()
