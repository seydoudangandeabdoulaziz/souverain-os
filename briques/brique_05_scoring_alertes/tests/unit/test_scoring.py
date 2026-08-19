"""Tests unitaires de scoring.py — aucune dépendance base de données."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from souverain_scoring.modeles import DetectionAgregee
from souverain_scoring.scoring import calculer_score

TABLE_POIDS = {
    "compte_pivot": 30,
    "structure_etoile": 25,
    "micro_fractionnement": 20,
    "flux_frontalier": 15,
    "transactions_nocturnes": 10,
}


def _detection(pattern_type: str, compte_pivot: str = "cp_001") -> DetectionAgregee:
    return DetectionAgregee(
        detection_id=uuid4(),
        pattern_type=pattern_type,
        compte_pivot=compte_pivot,
        transaction_ids=[uuid4()],
        detected_at=datetime.now(UTC),
    )


def test_un_seul_type_donne_le_poids_de_ce_type() -> None:
    detections = [_detection("transactions_nocturnes")]
    score = calculer_score(detections, TABLE_POIDS)
    assert score.score == 10
    assert score.types_presents == {"transactions_nocturnes"}


def test_types_distincts_sont_additionnes() -> None:
    detections = [_detection("compte_pivot"), _detection("transactions_nocturnes")]
    score = calculer_score(detections, TABLE_POIDS)
    assert score.score == 40  # 30 + 10


def test_meme_type_repete_ne_compte_qu_une_fois() -> None:
    # Correction validée : dédup par type, pas par occurrence.
    detections = [
        _detection("transactions_nocturnes"),
        _detection("transactions_nocturnes"),
        _detection("transactions_nocturnes"),
    ]
    score = calculer_score(detections, TABLE_POIDS)
    assert score.score == 10  # pas 30


def test_score_plafonne_a_100() -> None:
    detections = [
        _detection("compte_pivot"),
        _detection("structure_etoile"),
        _detection("micro_fractionnement"),
        _detection("flux_frontalier"),
        _detection("transactions_nocturnes"),
    ]
    # 30+25+20+15+10 = 100, exactement au plafond — cas limite volontaire
    score = calculer_score(detections, TABLE_POIDS, score_maximum=100)
    assert score.score == 100


def test_liste_vide_leve_une_erreur() -> None:
    with pytest.raises(ValueError):
        calculer_score([], TABLE_POIDS)


def test_comptes_pivot_differents_leve_une_erreur() -> None:
    detections = [
        _detection("compte_pivot", compte_pivot="cp_001"),
        _detection("transactions_nocturnes", compte_pivot="cp_002"),
    ]
    with pytest.raises(ValueError):
        calculer_score(detections, TABLE_POIDS)


def test_dates_premiere_et_derniere_detection() -> None:
    maintenant = datetime.now(UTC)
    ancienne = maintenant - timedelta(days=3)

    d1 = _detection("compte_pivot")
    d1 = d1.model_copy(update={"detected_at": ancienne})
    d2 = _detection("transactions_nocturnes")
    d2 = d2.model_copy(update={"detected_at": maintenant})

    score = calculer_score([d1, d2], TABLE_POIDS)
    assert score.premiere_detection_at == ancienne
    assert score.derniere_detection_at == maintenant


def test_type_inconnu_ne_leve_pas_mais_pese_zero() -> None:
    # Défensif : un pattern_type non répertorié dans la table de poids
    # (ex. future règle Brique 6+) ne doit pas faire planter le scoring.
    detections = [_detection("pattern_futur_inconnu")]
    score = calculer_score(detections, TABLE_POIDS)
    assert score.score == 0
