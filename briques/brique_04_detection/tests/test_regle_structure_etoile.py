"""Tests — règle structure en étoile.

Réutilise patterns_suspects.py (Brique 3) pour générer des transactions
labellisées en mémoire, jamais persistées avec leur label — exactement
la stratégie de validation actée en analyse.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from brique_04_detection.regles.structure_etoile import RegleStructureEtoile
from souverain_generateur.generateur_legitime import generer_lot_legitime
from souverain_generateur.patterns_suspects import generer_structure_etoile

FUSEAU_NIGER = timezone(timedelta(hours=1))
BASE_TIME = datetime(2026, 3, 1, 10, 0, 0, tzinfo=FUSEAU_NIGER)


def test_detecte_structure_etoile_intensite_moyenne(vers_observees) -> None:
    rng = random.Random(42)
    lot = generer_structure_etoile(rng, BASE_TIME, intensite="moyenne")
    transactions = sorted(vers_observees(lot), key=lambda t: t.occurred_at)

    regle = RegleStructureEtoile()
    evenements = [e for t in transactions if (e := regle.traiter(t)) is not None]

    assert len(evenements) == 1
    assert evenements[0].pattern_type == "structure_etoile"
    assert evenements[0].compte_pivot == lot[0].sender_account


def test_ne_declenche_pas_un_second_evenement_pour_la_meme_episode(vers_observees) -> None:
    """Une fois signalé, le même épisode ne doit pas se re-déclencher à
    chaque transaction supplémentaire tant que la fenêtre reste active.
    """
    rng = random.Random(42)
    lot = generer_structure_etoile(rng, BASE_TIME, intensite="forte")
    transactions = sorted(vers_observees(lot), key=lambda t: t.occurred_at)

    regle = RegleStructureEtoile()
    evenements = [e for t in transactions if (e := regle.traiter(t)) is not None]

    assert len(evenements) == 1


def test_pas_de_faux_positif_sur_transactions_legitimes(vers_observees) -> None:
    lot = generer_lot_legitime(nb_transactions=300, seed=7, base_time=BASE_TIME)
    transactions = sorted(vers_observees(lot), key=lambda t: t.occurred_at)

    regle = RegleStructureEtoile()
    evenements = [e for t in transactions if (e := regle.traiter(t)) is not None]

    assert len(evenements) == 0
