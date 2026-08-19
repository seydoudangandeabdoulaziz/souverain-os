"""Tests unitaires de seuils.py."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from souverain_scoring.modeles import ScoreCompte
from souverain_scoring.seuils import evaluer_seuil


def _score_compte(score: int) -> ScoreCompte:
    maintenant = datetime.now(UTC)
    return ScoreCompte(
        compte_pivot="cp_001",
        score=score,
        types_presents={"transactions_nocturnes"},
        premiere_detection_at=maintenant,
        derniere_detection_at=maintenant,
        detection_ids=[uuid4()],
    )


def test_score_sous_le_seuil_ne_declenche_pas() -> None:
    decision = evaluer_seuil(_score_compte(40), seuil_alerte=50)
    assert decision.doit_alerter is False


def test_score_egal_au_seuil_declenche() -> None:
    decision = evaluer_seuil(_score_compte(50), seuil_alerte=50)
    assert decision.doit_alerter is True


def test_score_au_dessus_du_seuil_declenche() -> None:
    decision = evaluer_seuil(_score_compte(80), seuil_alerte=50)
    assert decision.doit_alerter is True
