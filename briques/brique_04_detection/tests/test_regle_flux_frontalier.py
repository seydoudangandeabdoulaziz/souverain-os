"""Tests — règle flux frontalier.

Rappel (voir docstring de la règle) : cette règle ne fonctionne que contre
la convention de nommage du générateur synthétique — ce n'est pas une
détection géographique réelle. Ces tests valident donc le comportement du
code, pas une capacité de détection en production.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from brique_04_detection.regles.flux_frontalier import RegleFluxFrontalier
from souverain_generateur.generateur_legitime import generer_lot_legitime
from souverain_generateur.patterns_suspects import generer_flux_frontalier

FUSEAU_NIGER = timezone(timedelta(hours=1))
BASE_TIME = datetime(2026, 3, 1, 10, 0, 0, tzinfo=FUSEAU_NIGER)


def test_detecte_chaque_transaction_frontaliere(vers_observees) -> None:
    rng = random.Random(4)
    lot = generer_flux_frontalier(rng, BASE_TIME, intensite="moyenne")
    transactions = vers_observees(lot)

    regle = RegleFluxFrontalier()
    evenements = [e for t in transactions if (e := regle.traiter(t)) is not None]

    # Sans seuil (décision actée) : une détection par transaction du pattern.
    assert len(evenements) == len(lot)
    assert all(e.pattern_type == "flux_frontalier" for e in evenements)


def test_pas_de_faux_positif_sur_transactions_legitimes(vers_observees) -> None:
    lot = generer_lot_legitime(nb_transactions=300, seed=19, base_time=BASE_TIME)
    transactions = vers_observees(lot)

    regle = RegleFluxFrontalier()
    evenements = [e for t in transactions if (e := regle.traiter(t)) is not None]

    assert len(evenements) == 0
