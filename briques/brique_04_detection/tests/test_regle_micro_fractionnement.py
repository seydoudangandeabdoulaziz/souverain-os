"""Tests — règle micro-fractionnement."""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from brique_04_detection.regles.micro_fractionnement import RegleMicroFractionnement
from souverain_generateur.generateur_legitime import generer_lot_legitime
from souverain_generateur.patterns_suspects import generer_micro_fractionnement

FUSEAU_NIGER = timezone(timedelta(hours=1))
BASE_TIME = datetime(2026, 3, 1, 10, 0, 0, tzinfo=FUSEAU_NIGER)


def test_detecte_micro_fractionnement_intensite_moyenne(vers_observees) -> None:
    rng = random.Random(3)
    lot = generer_micro_fractionnement(rng, BASE_TIME, intensite="moyenne")
    transactions = sorted(vers_observees(lot), key=lambda t: t.occurred_at)

    regle = RegleMicroFractionnement()
    evenements = [e for t in transactions if (e := regle.traiter(t)) is not None]

    assert len(evenements) == 1
    assert evenements[0].pattern_type == "micro_fractionnement"


def test_pas_de_faux_positif_sur_transactions_legitimes(vers_observees) -> None:
    lot = generer_lot_legitime(nb_transactions=300, seed=13, base_time=BASE_TIME)
    transactions = sorted(vers_observees(lot), key=lambda t: t.occurred_at)

    regle = RegleMicroFractionnement()
    evenements = [e for t in transactions if (e := regle.traiter(t)) is not None]

    assert len(evenements) == 0
