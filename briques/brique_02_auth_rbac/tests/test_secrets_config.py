"""Contrôles fail-closed des secrets, sans accès à PostgreSQL."""

from __future__ import annotations

import pytest
from brique_01_postgresql.gouvernance_cli_config import GouvernanceCliDbSettings
from brique_02_auth_rbac.config import JwtSettings
from brique_02_auth_rbac.gouvernance.config import GouvernanceWebDbSettings
from brique_06_neo4j.config import Neo4jSettings
from brique_08_audit_human_loop.config import AuditDbSettings
from pydantic import ValidationError


@pytest.mark.parametrize(
    "secret",
    [
        "",
        "short",
        "insecure-dev-secret-change-me-before-any-real-use",
        "change_me_dev_secret_at_least_32_characters_long",
        "change_me",
    ],
)
def test_jwt_settings_rejette_secret_vide_court_ou_de_demonstration(secret: str) -> None:
    with pytest.raises(ValidationError):
        JwtSettings(_env_file=None, secret_key=secret)


def test_jwt_settings_exige_un_secret_si_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    with pytest.raises(ValidationError):
        JwtSettings(_env_file=None)


def test_jwt_settings_accepte_secret_long_et_ne_le_reprend_pas_en_clair() -> None:
    secret = "x" * 64
    settings = JwtSettings(_env_file=None, secret_key=secret)

    assert settings.secret_key.get_secret_value() == secret
    assert secret not in repr(settings)


def test_erreur_validation_ne_revele_pas_le_secret_fourni() -> None:
    sentinelle = "secret-test-ne-pas-afficher"
    with pytest.raises(ValidationError) as erreur:
        JwtSettings(_env_file=None, secret_key=sentinelle)

    assert sentinelle not in str(erreur.value)


@pytest.mark.parametrize(
    "settings_type",
    [
        GouvernanceCliDbSettings,
        GouvernanceWebDbSettings,
        AuditDbSettings,
        Neo4jSettings,
    ],
)
def test_identifiants_de_roles_dedies_exigent_un_secret_long_et_le_masquent(
    settings_type, monkeypatch: pytest.MonkeyPatch,
) -> None:
    for variable in (
        "GOUVERNANCE_CLI_DB_PASSWORD",
        "GOUVERNANCE_WEB_DB_PASSWORD",
        "AUDIT_DB_PASSWORD",
        "NEO4J_PASSWORD",
    ):
        monkeypatch.delenv(variable, raising=False)
    secret = "secret-synthetique-dedie-de-plus-de-32-caracteres"
    with pytest.raises(ValidationError):
        settings_type(_env_file=None)
    settings = settings_type(_env_file=None, password=secret)
    assert secret not in repr(settings)
