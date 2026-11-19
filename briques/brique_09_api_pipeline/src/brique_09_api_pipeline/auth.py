"""Authentification des identités techniques (jeton court, portée, tenant actif)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from uuid import UUID

import asyncpg
from brique_01_postgresql.connection import create_runtime_pool, create_tenant_pipeline_pool
from brique_02_auth_rbac.password_hashing import hash_password, verify_password
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import ValidationError

from brique_09_api_pipeline.config import ApiSettings, get_api_settings
from brique_09_api_pipeline.identites import charger_client_pour_auth
from brique_09_api_pipeline.jetons import JetonInvalide, decoder_jeton, emettre_jeton
from brique_09_api_pipeline.journal import journaliser
from brique_09_api_pipeline.limiteur import LimiteurEchecs
from brique_09_api_pipeline.schemas import DemandeJeton, ReponseJeton

_bearer = HTTPBearer(auto_error=False)
_FAUX_HASH = hash_password("x" * 40)  # égalise le temps de réponse (client inconnu)
_limiteur: LimiteurEchecs | None = None


@lru_cache
def _charger_parametres() -> ApiSettings:
    return get_api_settings()


def parametres_api() -> ApiSettings:
    """Réglages de l'API ; non configurée => 503 générique (échec fermé)."""
    try:
        return _charger_parametres()
    except ValidationError as exc:
        raise HTTPException(503, detail={"code": "api_non_configuree"}) from exc


def reinitialiser_etat() -> None:
    """Remet à zéro le limiteur et le cache des réglages (tests)."""
    global _limiteur
    _limiteur = None
    _charger_parametres.cache_clear()


def _limiteur_pour(settings: ApiSettings) -> LimiteurEchecs:
    global _limiteur
    if _limiteur is None:
        _limiteur = LimiteurEchecs(
            settings.max_auth_failures,
            settings.auth_failure_window_seconds,
            settings.auth_lockout_seconds,
        )
    return _limiteur


def _refus(statut: int, code: str) -> HTTPException:
    entetes = {"WWW-Authenticate": "Bearer"} if statut == 401 else None
    return HTTPException(statut, detail={"code": code}, headers=entetes)


@dataclass(frozen=True)
class IdentiteService:
    client_id: UUID
    tenant_id: UUID
    source_code: str
    scopes: tuple[str, ...]
    schema_name: str
    pool: asyncpg.Pool


async def authentifier_client(
    demande: DemandeJeton, adresse: str, settings: ApiSettings
) -> ReponseJeton:
    limiteur = _limiteur_pour(settings)
    cle = f"{demande.client_id}|{adresse}"
    if limiteur.verrouille(cle):
        raise _refus(429, "trop_d_echecs")

    client = None
    try:
        identifiant = UUID(demande.client_id)
        runtime = await create_runtime_pool()
        tenant_id = await runtime.fetchval(
            "SELECT tenant_id FROM shared.tenants_registry "
            "WHERE tenant_code = $1 AND is_active = true",
            demande.tenant_code.strip().upper(),
        )
        if tenant_id is not None:
            try:
                pool = await create_tenant_pipeline_pool(tenant_id)
            except ConnectionRefusedError as exc:
                raise _refus(503, "service_indisponible") from exc
            client = await charger_client_pour_auth(pool, identifiant)
            if client is not None and client.tenant_id != tenant_id:
                client = None
    except ValueError:
        client = None

    empreinte = client.secret_hash if client is not None else _FAUX_HASH
    secret_ok = await asyncio.to_thread(verify_password, demande.client_secret, empreinte)
    if client is None or not secret_ok or not client.utilisable(datetime.now(UTC)):
        limiteur.enregistrer_echec(cle)
        journaliser("auth_echec", code="identifiants_invalides")
        raise _refus(401, "identifiants_invalides")

    limiteur.reinitialiser(cle)
    jeton = emettre_jeton(
        client.client_id, client.tenant_id, list(client.scopes), client.secret_version, settings
    )
    journaliser("auth_ok", client_id=client.client_id, tenant_id=client.tenant_id)
    return ReponseJeton(
        access_token=jeton,
        expires_in=settings.token_ttl_minutes * 60,
        scope=" ".join(client.scopes),
    )


async def identite_service(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),  # noqa: B008
    settings: ApiSettings = Depends(parametres_api),  # noqa: B008
) -> IdentiteService:
    if credentials is None:
        raise _refus(401, "non_authentifie")
    try:
        jeton = decoder_jeton(credentials.credentials, settings)
    except JetonInvalide as exc:
        raise _refus(401, "non_authentifie") from exc
    try:
        pool = await create_tenant_pipeline_pool(jeton.tenant_id)
    except ConnectionRefusedError as exc:
        raise _refus(503, "service_indisponible") from exc
    client = await charger_client_pour_auth(pool, jeton.client_id)
    if (
        client is None
        or client.tenant_id != jeton.tenant_id
        or client.secret_version != jeton.secret_version
        or not client.utilisable(datetime.now(UTC))
    ):
        raise _refus(401, "non_authentifie")
    return IdentiteService(
        client_id=client.client_id,
        tenant_id=client.tenant_id,
        source_code=client.source_code,
        scopes=client.scopes,
        schema_name=client.schema_name,
        pool=pool,
    )


def exiger_scope(scope: str):  # type: ignore[no-untyped-def]
    async def _verifier(
        identite: IdentiteService = Depends(identite_service),  # noqa: B008
    ) -> IdentiteService:
        if scope not in identite.scopes:
            raise _refus(403, "portee_insuffisante")
        return identite

    return _verifier
