"""Tests — règle compte pivot."""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from brique_04_detection.regles.compte_pivot import ReglePivot
from souverain_generateur.generateur_legitime import generer_lot_legitime
from souverain_generateur.patterns_suspects import generer_compte_pivot

FUSEAU_NIGER = timezone(timedelta(hours=1))
BASE_TIME = datetime(2026, 3, 1, 10, 0, 0, tzinfo=FUSEAU_NIGER)


def test_detecte_compte_pivot_intensite_moyenne(vers_observees) -> None:
    rng = random.Random(5)
    lot = generer_compte_pivot(rng, BASE_TIME, intensite="moyenne")
    transactions = sorted(vers_observees(lot), key=lambda t: t.occurred_at)

    regle = ReglePivot()
    evenements = [e for t in transactions if (e := regle.traiter(t)) is not None]

    assert len(evenements) >= 1
    assert evenements[0].pattern_type == "compte_pivot"
    # Le compte pivot détecté doit être le compte qui reçoit ET redistribue,
    # c-à-d le receiver_account des transactions de réception du lot généré.
    comptes_reception = {
        t.receiver_account for t in lot if t.pattern_label == "compte_pivot_reception"
    }
    assert evenements[0].compte_pivot in comptes_reception


def test_pas_de_faux_positif_sur_transactions_legitimes(vers_observees) -> None:
    lot = generer_lot_legitime(nb_transactions=300, seed=11, base_time=BASE_TIME)
    transactions = sorted(vers_observees(lot), key=lambda t: t.occurred_at)

    regle = ReglePivot()
    evenements = [e for t in transactions if (e := regle.traiter(t)) is not None]

    assert len(evenements) == 0
