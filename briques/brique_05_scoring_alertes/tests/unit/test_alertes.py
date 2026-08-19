"""Tests unitaires de la règle is_synthetic (Correction 1)."""

from __future__ import annotations

from souverain_scoring.alertes import calculer_is_synthetic


def test_toutes_synthetiques_donne_true() -> None:
    assert calculer_is_synthetic([True, True, True]) is True


def test_toutes_reelles_donne_false() -> None:
    assert calculer_is_synthetic([False, False]) is False


def test_mixte_donne_false() -> None:
    # Règle validée : en cas de doute, traité comme réel.
    assert calculer_is_synthetic([True, False]) is False


def test_liste_vide_donne_false() -> None:
    assert calculer_is_synthetic([]) is False


def test_une_seule_transaction_synthetique() -> None:
    assert calculer_is_synthetic([True]) is True


def test_une_seule_transaction_reelle() -> None:
    assert calculer_is_synthetic([False]) is False
