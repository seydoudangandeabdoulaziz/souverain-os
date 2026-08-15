"""Tests — règle transactions nocturnes."""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from brique_04_detection.regles.nocturne import RegleNocturne
from souverain_generateur.generateur_legitime import generer_lot_legitime
from souverain_generateur.patterns_suspects import generer_transactions_nocturnes

FUSEAU_NIGER = timezone(timedelta(hours=1))
BASE_TIME = datetime(2026, 3, 1, 10, 0, 0, tzinfo=FUSEAU_NIGER)


def test_detecte_transactions_nocturnes_intensite_moyenne(vers_observees) -> None:
    rng = random.Random(1)
    lot = generer_transactions_nocturnes(rng, BASE_TIME, intensite="moyenne")
    transactions = sorted(vers_observees(lot), key=lambda t: t.occurred_at)

    regle = RegleNocturne()
    evenements = [e for t in transactions if (e := regle.traiter(t)) is not None]

    assert len(evenements) == 1
    assert evenements[0].pattern_type == "transactions_nocturnes"


def test_pas_de_faux_positif_sur_transactions_legitimes_de_jour(vers_observees) -> None:
    """generer_lot_legitime répartit les transactions sur 24h — certaines
    tombent forcément dans la plage 22h-4h, mais avec des émetteurs
    différents à chaque fois (pas de répétition de compte), donc aucune
    ne doit franchir le seuil de 4 transactions nocturnes par compte.
    """
    lot = generer_lot_legitime(nb_transactions=500, seed=17, base_time=BASE_TIME)
    transactions = sorted(vers_observees(lot), key=lambda t: t.occurred_at)

    regle = RegleNocturne()
    evenements = [e for t in transactions if (e := regle.traiter(t)) is not None]

    assert len(evenements) == 0
