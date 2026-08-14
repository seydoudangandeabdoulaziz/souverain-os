"""Tests unitaires — souverain_id.py (aucune DB requise)."""

from __future__ import annotations

from brique_02_auth_rbac.souverain_id import generate_souverain_id


def test_generate_souverain_id_is_deterministic() -> None:
    """Même tenant + même email doit toujours produire le même identifiant."""
    id_1 = generate_souverain_id("NE", "user@example.ne")
    id_2 = generate_souverain_id("NE", "user@example.ne")
    assert id_1 == id_2


def test_generate_souverain_id_differs_by_email() -> None:
    id_a = generate_souverain_id("NE", "a@example.ne")
    id_b = generate_souverain_id("NE", "b@example.ne")
    assert id_a != id_b


def test_generate_souverain_id_differs_by_tenant() -> None:
    id_ne = generate_souverain_id("NE", "user@example.com")
    id_sn = generate_souverain_id("SN", "user@example.com")
    assert id_ne != id_sn


def test_generate_souverain_id_is_case_insensitive() -> None:
    """Un email/tenant_code en majuscules doit produire le même id qu'en minuscules."""
    id_lower = generate_souverain_id("ne", "user@example.ne")
    id_upper = generate_souverain_id("NE", "USER@EXAMPLE.NE")
    assert id_lower == id_upper
