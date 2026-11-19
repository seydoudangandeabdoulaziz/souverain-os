"""Identifiants PostgreSQL tenant stockés dans le .env local protégé.

Le nom de rôle est dérivé du tenant_id signé côté serveur. Les secrets
ne sont jamais inclus dans les logs ou les représentations des objets.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file() -> str | None:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / ".env"
        if candidate.is_file():
            return str(candidate)
    return None


class TenantCredentialSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TENANT_DB_",
        env_file=_find_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    credentials_json: SecretStr = Field(
        min_length=2,
        description=(
            "JSON privé indexé par tenant UUID : chaque entrée contient "
            "data_password et audit_password (et pipeline_password si le "
            "rôle pipeline est provisionné)."
        ),
    )


@dataclass(frozen=True, repr=False)
class TenantRoleCredentials:
    username: str
    password: SecretStr

    def __repr__(self) -> str:
        return (
            "TenantRoleCredentials("
            f"username={self.username!r}, password=SecretStr('**********'))"
        )


# Buts de rôle tenant : préfixe du nom PostgreSQL et clé du secret dans
# TENANT_DB_CREDENTIALS_JSON. `data` et `audit` sont inchangés (P0) ;
# `pipeline` (étape API d'ingestion/scoring) est un ajout strictement additif.
_ROLE_PURPOSES: dict[str, tuple[str, str]] = {
    "data": ("sov_t_", "data_password"),
    "audit": ("sov_a_", "audit_password"),
    "pipeline": ("sov_p_", "pipeline_password"),
}


def role_name_for_tenant(tenant_id: UUID, purpose: str) -> str:
    if purpose not in _ROLE_PURPOSES:
        raise ValueError("purpose doit valoir 'data', 'audit' ou 'pipeline'")
    return _ROLE_PURPOSES[purpose][0] + tenant_id.hex


def get_tenant_role_credentials(
    tenant_id: UUID,
    purpose: str,
    *,
    settings: TenantCredentialSettings | None = None,
) -> TenantRoleCredentials:
    resolved = settings or TenantCredentialSettings()  # type: ignore[call-arg]
    try:
        raw = json.loads(resolved.credentials_json.get_secret_value())
    except json.JSONDecodeError as exc:
        raise ValueError("TENANT_DB_CREDENTIALS_JSON doit contenir un objet JSON valide") from exc
    if not isinstance(raw, dict):
        raise ValueError("TENANT_DB_CREDENTIALS_JSON doit être indexé par tenant UUID")

    entry = raw.get(str(tenant_id)) or raw.get(str(tenant_id).lower())
    if purpose not in _ROLE_PURPOSES:
        raise ValueError("purpose doit valoir 'data', 'audit' ou 'pipeline'")
    password_key = _ROLE_PURPOSES[purpose][1]
    if not isinstance(entry, dict) or not isinstance(entry.get(password_key), str):
        raise ValueError(f"Identifiants PostgreSQL {purpose} absents pour le tenant demandé")
    password = entry[password_key]
    if len(password) < 32:
        raise ValueError("Les secrets des rôles tenant doivent contenir au moins 32 caractères")
    return TenantRoleCredentials(
        username=role_name_for_tenant(tenant_id, purpose),
        password=SecretStr(password),
    )
