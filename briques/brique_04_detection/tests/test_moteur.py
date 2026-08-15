"""Test du moteur complet — mélange légitime + tous les patterns suspects,
comme le fera réellement le CLI sur les données de la Brique 3.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from brique_04_detection.moteur import detecter_sequentiellement
from souverain_generateur.generateur_legitime import generer_lot_legitime
from souverain_generateur.patterns_suspects import (
    generer_compte_pivot,
    generer_flux_frontalier,
    generer_micro_fractionnement,
    generer_structure_etoile,
    generer_transactions_nocturnes,
)

FUSEAU_NIGER = timezone(timedelta(hours=1))
BASE_TIME = datetime(2026, 3, 1, 10, 0, 0, tzinfo=FUSEAU_NIGER)


def test_moteur_detecte_tous_les_patterns_injectes_sur_jeu_mixte(vers_observees) -> None:
    rng = random.Random(42)

    legitimes = generer_lot_legitime(nb_transactions=1000, seed=42, base_time=BASE_TIME)
    suspects = (
        generer_structure_etoile(rng, BASE_TIME, intensite="moyenne")
        + generer_compte_pivot(rng, BASE_TIME, intensite="moyenne")
        + generer_micro_fractionnement(rng, BASE_TIME, intensite="moyenne")
        + generer_transactions_nocturnes(rng, BASE_TIME, intensite="moyenne")
        + generer_flux_frontalier(rng, BASE_TIME, intensite="moyenne")
    )

    tous = sorted(vers_observees(legitimes + suspects), key=lambda t: t.occurred_at)

    evenements = detecter_sequentiellement(tous)
    types_detectes = {e.pattern_type for e in evenements}

    assert "structure_etoile" in types_detectes
    assert "compte_pivot" in types_detectes
    assert "micro_fractionnement" in types_detectes
    assert "transactions_nocturnes" in types_detectes
    assert "flux_frontalier" in types_detectes


def test_moteur_peu_de_faux_positifs_sur_jeu_purement_legitime(vers_observees) -> None:
    """Objectif indicatif aligné sur le <12% du document fondateur — pas un
    gate strict en MVP, mais un signal si le taux dérape fortement.
    """
    legitimes = generer_lot_legitime(nb_transactions=2000, seed=99, base_time=BASE_TIME)
    tous = sorted(vers_observees(legitimes), key=lambda t: t.occurred_at)

    evenements = detecter_sequentiellement(tous)

    taux_faux_positifs = len(evenements) / len(tous)
    assert taux_faux_positifs < 0.12
