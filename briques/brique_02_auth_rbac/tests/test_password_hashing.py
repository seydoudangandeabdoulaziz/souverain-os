"""Tests unitaires — password_hashing.py (aucune DB requise)."""

from __future__ import annotations

from brique_02_auth_rbac.password_hashing import hash_password, verify_password


def test_hash_password_does_not_return_plain_text() -> None:
    plain = "un-mot-de-passe-solide-2026"
    hashed = hash_password(plain)
    assert hashed != plain


def test_verify_password_accepts_correct_password() -> None:
    plain = "un-mot-de-passe-solide-2026"
    hashed = hash_password(plain)
    assert verify_password(plain, hashed) is True


def test_verify_password_rejects_incorrect_password() -> None:
    hashed = hash_password("le-bon-mot-de-passe")
    assert verify_password("un-mauvais-mot-de-passe", hashed) is False


def test_two_hashes_of_same_password_differ() -> None:
    """Le salage doit produire des hash différents pour un même mot de passe."""
    plain = "meme-mot-de-passe"
    assert hash_password(plain) != hash_password(plain)


def test_verify_password_rejects_malformed_hash() -> None:
    assert verify_password("peu-importe", "pas-un-vrai-hash-argon2") is False
