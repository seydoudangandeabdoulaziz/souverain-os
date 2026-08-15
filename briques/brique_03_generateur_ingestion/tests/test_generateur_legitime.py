"""Tests unitaires — génération de transactions légitimes."""

from datetime import datetime, timedelta, timezone

from souverain_generateur.generateur_legitime import (
    CANAUX,
    generer_lot_legitime,
)


def test_generer_lot_legitime_produit_le_bon_nombre() -> None:
    lot = generer_lot_legitime(nb_transactions=100, seed=42)
    assert len(lot) == 100


def test_generer_lot_legitime_est_reproductible_avec_meme_seed() -> None:
    base_time = datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=1)))
    lot_a = generer_lot_legitime(nb_transactions=50, seed=123, base_time=base_time)
    lot_b = generer_lot_legitime(nb_transactions=50, seed=123, base_time=base_time)

    for transaction_a, transaction_b in zip(lot_a, lot_b, strict=True):
        assert transaction_a.sender_account == transaction_b.sender_account
        assert transaction_a.receiver_account == transaction_b.receiver_account
        assert transaction_a.amount == transaction_b.amount
        assert transaction_a.occurred_at == transaction_b.occurred_at


def test_generer_lot_legitime_seeds_differentes_donnent_resultats_differents() -> None:
    lot_a = generer_lot_legitime(nb_transactions=50, seed=1)
    lot_b = generer_lot_legitime(nb_transactions=50, seed=2)
    assert [t.sender_account for t in lot_a] != [t.sender_account for t in lot_b]


def test_montants_toujours_positifs_et_bornes() -> None:
    lot = generer_lot_legitime(nb_transactions=200, seed=7)
    for transaction in lot:
        assert transaction.amount > 0
        assert transaction.amount <= 500_000


def test_canaux_generes_sont_valides() -> None:
    lot = generer_lot_legitime(nb_transactions=200, seed=7)
    for transaction in lot:
        assert transaction.channel in CANAUX


def test_transactions_legitimes_ont_pattern_label_none() -> None:
    lot = generer_lot_legitime(nb_transactions=10, seed=7)
    assert all(t.pattern_label is None for t in lot)
    assert all(t.is_synthetic is True for t in lot)
