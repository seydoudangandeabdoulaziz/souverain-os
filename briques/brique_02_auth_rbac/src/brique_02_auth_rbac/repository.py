"""
Accès aux données utilisateurs (shared.users).

Toutes les requêtes utilisent des valeurs paramétrées (jamais de
construction dynamique de SQL) — contrairement à la Brique 1 où les
noms de SCHÉMA devaient être insérés dans le texte SQL (impossible à
paramétrer autrement), ici on ne manipule que des valeurs classiques,
donc le risque d'injection SQL est intrinsèquement plus faible.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import asyncpg


class EmailAlreadyExistsError(Exception):
    """Un compte existe déjà avec cet email."""


@dataclass(frozen=True)
class UserRecord:
    """Représentation d'une ligne de shared.users."""

    user_id: uuid.UUID
    souverain_id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    password_hash: str
    role: str
    token_version: int
    is_active: bool


_SELECT_FIELDS = (
    "user_id, souverain_id, tenant_id, email, password_hash, role, token_version, is_active"
)


def _row_to_user_record(row: asyncpg.Record) -> UserRecord:
    return UserRecord(
        user_id=row["user_id"],
        souverain_id=row["souverain_id"],
        tenant_id=row["tenant_id"],
        email=row["email"],
        password_hash=row["password_hash"],
        role=row["role"],
        token_version=row["token_version"],
        is_active=row["is_active"],
    )


async def create_user(
    connection: asyncpg.Connection,
    *,
    tenant_id: uuid.UUID,
    souverain_id: uuid.UUID,
    email: str,
    password_hash: str,
    role: str,
) -> UserRecord:
    """
    Crée un nouvel utilisateur.

    Raises:
        EmailAlreadyExistsError: un compte existe déjà avec cet email.
    """
    try:
        row = await connection.fetchrow(
            f"""
            INSERT INTO shared.users
                (tenant_id, souverain_id, email, password_hash, role)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING {_SELECT_FIELDS}
            """,
            tenant_id,
            souverain_id,
            email,
            password_hash,
            role,
        )
    except asyncpg.UniqueViolationError as exc:
        raise EmailAlreadyExistsError(f"Un compte existe déjà pour {email!r}.") from exc

    assert row is not None  # noqa: S101 — RETURNING garantit une ligne si pas d'exception
    return _row_to_user_record(row)


async def get_user_by_email(connection: asyncpg.Connection, email: str) -> UserRecord | None:
    """Retourne l'utilisateur correspondant à cet email, ou None si inexistant."""
    row = await connection.fetchrow(
        f"SELECT {_SELECT_FIELDS} FROM shared.users WHERE email = $1", email
    )
    return _row_to_user_record(row) if row else None


async def get_user_by_id(connection: asyncpg.Connection, user_id: uuid.UUID) -> UserRecord | None:
    """Retourne l'utilisateur correspondant à cet identifiant, ou None si inexistant."""
    row = await connection.fetchrow(
        f"SELECT {_SELECT_FIELDS} FROM shared.users WHERE user_id = $1", user_id
    )
    return _row_to_user_record(row) if row else None


async def touch_last_login(connection: asyncpg.Connection, user_id: uuid.UUID) -> None:
    """Met à jour l'horodatage de dernière connexion réussie."""
    await connection.execute(
        "UPDATE shared.users SET last_login_at = now() WHERE user_id = $1", user_id
    )


async def increment_token_version(connection: asyncpg.Connection, user_id: uuid.UUID) -> None:
    """
    Incrémente token_version, invalidant immédiatement tous les jetons
    JWT déjà émis pour cet utilisateur (voir jwt_tokens.py).
    """
    await connection.execute(
        "UPDATE shared.users SET token_version = token_version + 1, updated_at = now() "
        "WHERE user_id = $1",
        user_id,
    )


async def deactivate_user(connection: asyncpg.Connection, user_id: uuid.UUID) -> None:
    """
    Désactive un compte (jamais de suppression physique) et invalide
    immédiatement ses jetons en cours via token_version.
    """
    await connection.execute(
        "UPDATE shared.users "
        "SET is_active = false, token_version = token_version + 1, updated_at = now() "
        "WHERE user_id = $1",
        user_id,
    )


async def reactivate_user(connection: asyncpg.Connection, user_id: uuid.UUID) -> None:
    """
    Réactive un compte désactivé — bascule is_active à true UNIQUEMENT.

    Ne touche JAMAIS token_version, et c'est volontaire, pas un oubli :
    deactivate_user() l'a déjà incrémenté de façon irréversible au
    moment de la désactivation. C'est cette incrémentation passée,
    jamais décrémentée, qui garantit à elle seule qu'un ancien jeton
    émis avant la désactivation reste invalide pour toujours — vérifié
    en traçant get_current_user() (session.py) et login() (api.py) :
    login() n'incrémente jamais token_version lui-même, il émet un
    nouveau jeton avec la valeur COURANTE en base, qui sera donc déjà
    correcte après une simple réactivation. Toucher token_version ici
    serait inoffensif mais redondant.
    """
    await connection.execute(
        "UPDATE shared.users SET is_active = true, updated_at = now() WHERE user_id = $1",
        user_id,
    )


class RoleInvalideError(Exception):
    """Le rôle demandé n'est pas l'une des 3 valeurs autorisées."""


async def update_user_role(connection: asyncpg.Connection, user_id: uuid.UUID, role: str) -> None:
    """
    Change le rôle d'un utilisateur.

    Raises:
        RoleInvalideError: rôle hors de {'admin', 'analyst', 'auditor'}
            (la contrainte CHECK de shared.users le garantit déjà côté
            base ; cette exception traduit la CheckViolationError brute
            d'asyncpg en quelque chose d'explicite pour l'appelant).

    Ne contient AUCUNE protection contre l'auto-rétrogradation — c'est
    la responsabilité de l'appelant (routes.py, Brique 2 V2), qui doit
    vérifier que user_id != l'utilisateur actuellement authentifié
    avant même d'appeler cette fonction.
    """
    try:
        await connection.execute(
            "UPDATE shared.users SET role = $2, updated_at = now() WHERE user_id = $1",
            user_id,
            role,
        )
    except asyncpg.exceptions.CheckViolationError as exc:
        raise RoleInvalideError(
            f"Rôle invalide : {role!r} — attendu 'admin', 'analyst' ou 'auditor'."
        ) from exc
