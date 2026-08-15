"""Fixtures partagées pour les tests de la Brique 4.

vers_observee()/vers_observees() convertissent une TransactionSynthetique
(Brique 3, dépendance de TEST uniquement) en TransactionObservee
(Brique 4) — c'est la frontière explicite entre "données labellisées
générées pour le test" et "ce que le moteur de détection voit réellement"
(sans is_synthetic ni pattern_label).

Exposées comme fixtures pytest (pas comme un import direct
`from tests.conftest import ...`) : le dépôt a un dossier tests/ à la
racine du workspace (tests/integration/), qui entre en collision avec
celui de cette brique quand pytest est invoqué depuis la racine — Python
résout alors "tests" vers le mauvais dossier. Les fixtures pytest sont
injectées automatiquement par nom, sans jamais passer par un import
`tests.xxx`, donc immunisées contre ce conflit, quel que soit l'endroit
d'où `pytest`/`uv run pytest` est lancé.
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

import pytest
from brique_04_detection.modeles import TransactionObservee
from souverain_generateur.generateur_legitime import TransactionSynthetique


def _vers_observee(transaction: TransactionSynthetique) -> TransactionObservee:
    return TransactionObservee(
        transaction_id=uuid4(),
        sender_account=transaction.sender_account,
        receiver_account=transaction.receiver_account,
        amount=transaction.amount,
        channel=transaction.channel,
        occurred_at=transaction.occurred_at,
    )


@pytest.fixture
def vers_observees() -> Callable[[list[TransactionSynthetique]], list[TransactionObservee]]:
    def _convertir(
        transactions: list[TransactionSynthetique],
    ) -> list[TransactionObservee]:
        return [_vers_observee(t) for t in transactions]

    return _convertir
