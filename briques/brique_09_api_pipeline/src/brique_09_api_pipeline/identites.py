"""Gestion des identités techniques (opérateur, rôle admin) et lecture (API)."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import asyncpg
from brique_02_auth_rbac.password_hashing import hash_password

SCOPES_VALIDES = ("ingest", "cycle")

_CHARGER_POUR_AUTH = """
    SELECT c.client_id, c.tenant_id, c.source_code, c.secret_hash, c.scopes, c.is_active,
           c.expires_at, c.secret_version, r.is_active AS tenant_actif, r.schema_name
    FROM shared.api_clients c
    JOIN shared.tenants_registry r ON r.tenant_id = c.tenant_id
    WHERE c.client_id = $1
"""


@dataclass(frozen=True)
class ClientAuth:
    client_id: UUID
    tenant_id: UUID
    source_code: str
    secret_hash: str
    scopes: tuple[str, ...]
    is_active: bool
    expires_at: datetime | None
    secret_version: int
    tenant_actif: bool
    schema_name: str

    def utilisable(self, maintenant: datetime) -> bool:
        return (
            self.is_active
            and self.tenant_actif
            and (self.expires_at is None or self.expires_at > maintenant)
        )


async def charger_client_pour_auth(pool: asyncpg.Pool, client_id: UUID) -> ClientAuth | None:
    """Lecture sous le rôle `pipeline` : la RLS ne montre que le tenant du rôle."""
    ligne = await pool.fetchrow(_CHARGER_POUR_AUTH, client_id)
    if ligne is None:
        return None
    return ClientAuth(
        client_id=ligne["client_id"],
        tenant_id=ligne["tenant_id"],
        source_code=ligne["source_code"],
        secret_hash=ligne["secret_hash"],
        scopes=tuple(ligne["scopes"]),
        is_active=ligne["is_active"],
        expires_at=ligne["expires_at"],
        secret_version=ligne["secret_version"],
        tenant_actif=ligne["tenant_actif"],
        schema_name=ligne["schema_name"],
    )


def _nouveau_secret() -> str:
    return secrets.token_urlsafe(32)


async def _evenement(
    connexion: asyncpg.Connection, client_id: UUID, tenant_id: UUID, type_: str, acteur: str
) -> None:
    await connexion.execute(
        "INSERT INTO shared.api_client_events (client_id, tenant_id, event_type, actor) "
        "VALUES ($1, $2, $3, $4)",
        client_id,
        tenant_id,
        type_,
        acteur,
    )


async def creer_client(
    connexion: asyncpg.Connection,
    tenant_code: str,
    source_code: str,
    scopes: list[str],
    acteur: str,
    expire_dans_jours: int | None = None,
) -> tuple[UUID, str]:
    """Crée l'identité ; retourne (client_id, secret en clair, affiché une seule fois)."""
    if not scopes or any(s not in SCOPES_VALIDES for s in scopes):
        raise ValueError(f"scopes valides : {', '.join(SCOPES_VALIDES)}")
    secret = _nouveau_secret()
    expiration = (
        None if expire_dans_jours is None else datetime.now(UTC) + timedelta(days=expire_dans_jours)
    )
    async with connexion.transaction():
        tenant_id = await connexion.fetchval(
            "SELECT tenant_id FROM shared.tenants_registry "
            "WHERE tenant_code = $1 AND is_active = true",
            tenant_code.strip().upper(),
        )
        if tenant_id is None:
            raise ValueError("tenant actif introuvable")
        client_id = await connexion.fetchval(
            "INSERT INTO shared.api_clients "
            "(tenant_id, source_code, secret_hash, scopes, expires_at) "
            "VALUES ($1, $2, $3, $4, $5) RETURNING client_id",
            tenant_id,
            source_code,
            hash_password(secret),
            sorted(set(scopes)),
            expiration,
        )
        await _evenement(connexion, client_id, tenant_id, "created", acteur)
    return client_id, secret


async def renouveler_secret(connexion: asyncpg.Connection, client_id: UUID, acteur: str) -> str:
    """Nouveau secret ; l'ancien et tous les jetons émis deviennent invalides."""
    secret = _nouveau_secret()
    async with connexion.transaction():
        ligne = await connexion.fetchrow(
            "UPDATE shared.api_clients SET secret_hash = $2, secret_version = secret_version + 1, "
            "rotated_at = now() WHERE client_id = $1 RETURNING tenant_id",
            client_id,
            hash_password(secret),
        )
        if ligne is None:
            raise ValueError("identité introuvable")
        await _evenement(connexion, client_id, ligne["tenant_id"], "rotated", acteur)
    return secret


async def revoquer_client(connexion: asyncpg.Connection, client_id: UUID, acteur: str) -> None:
    """Révocation immédiate : désactivation + version incrémentée."""
    async with connexion.transaction():
        ligne = await connexion.fetchrow(
            "UPDATE shared.api_clients SET is_active = false, revoked_at = now(), "
            "secret_version = secret_version + 1 WHERE client_id = $1 RETURNING tenant_id",
            client_id,
        )
        if ligne is None:
            raise ValueError("identité introuvable")
        await _evenement(connexion, client_id, ligne["tenant_id"], "revoked", acteur)


async def lister_clients(connexion: asyncpg.Connection) -> list[asyncpg.Record]:
    return await connexion.fetch(
        "SELECT c.client_id, r.tenant_code, c.source_code, c.scopes, c.is_active, c.expires_at, "
        "c.secret_version FROM shared.api_clients c "
        "JOIN shared.tenants_registry r USING (tenant_id) ORDER BY r.tenant_code, c.source_code"
    )
