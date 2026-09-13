"""
Tests d'intégration de l'extension gouvernance (Brique 2 V2).

Pattern identique à test_api.py : auto-SKIP (pas d'échec) si
PostgreSQL ou le rôle dédié souverain_gouvernance_web ne sont pas
joignables.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID

import asyncpg
import pytest
from brique_01_postgresql.config import PostgresSettings, get_settings
from brique_01_postgresql.connection import close_pool, create_pool
from brique_02_auth_rbac.config import JwtSettings, get_jwt_settings
from brique_02_auth_rbac.gouvernance.connection import (
    close_gouvernance_web_pool,
    create_gouvernance_web_pool,
)
from brique_02_auth_rbac.gouvernance.persistence import (
    AutoModificationInterditeError,
    UtilisateurHorsTenantError,
    changer_role_utilisateur,
    creer_utilisateur,
    desactiver_utilisateur,
    reactiver_utilisateur,
)
from brique_02_auth_rbac.jwt_tokens import create_access_token, decode_token
from brique_02_auth_rbac.password_hashing import hash_password
from brique_02_auth_rbac.repository import UserRecord, create_user, get_user_by_id
from brique_02_auth_rbac.souverain_id import generate_souverain_id

TENANT_CODE_A = "YA"
TENANT_CODE_B = "YB"
SCHEMA_A = "tenant_test_gouv_a"
SCHEMA_B = "tenant_test_gouv_b"
MOT_DE_PASSE_TEST = "mot-de-passe-de-test-suffisamment-long"


@pytest.fixture
async def pool_admin_ou_skip() -> AsyncIterator[PostgresSettings]:
    settings = get_settings()
    try:
        await create_pool(settings)
    except ConnectionRefusedError:
        pytest.skip("PostgreSQL non joignable.")
    else:
        yield settings
        await close_pool()


@pytest.fixture
async def pool_web_ou_skip(pool_admin_ou_skip: PostgresSettings) -> AsyncIterator[asyncpg.Pool]:
    try:
        pool = await create_gouvernance_web_pool()
    except ConnectionRefusedError:
        pytest.skip(
            "Rôle souverain_gouvernance_web non joignable — "
            "appliquer la migration 0002 de la Brique 2."
        )
    else:
        yield pool
        await close_gouvernance_web_pool()


async def _nettoyer(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as connexion:
        for schema in (SCHEMA_A, SCHEMA_B):
            await connexion.execute(
                "DELETE FROM shared.users WHERE tenant_id IN "
                "(SELECT tenant_id FROM shared.tenants_registry WHERE schema_name = $1)",
                schema,
            )
            await connexion.execute(
                "DELETE FROM shared.tenants_registry WHERE schema_name = $1", schema
            )


@pytest.fixture
async def deux_tenants_avec_admin(
    pool_admin_ou_skip: PostgresSettings,
) -> AsyncIterator[dict[str, UUID | UserRecord]]:
    """Deux tenants distincts, un admin chacun — nécessaire pour tester
    l'isolation stricte (un admin ne peut jamais agir sur l'autre tenant)."""
    pool = await create_pool()
    await _nettoyer(pool)

    async with pool.acquire() as connexion:
        tenant_a_id = await connexion.fetchval(
            "INSERT INTO shared.tenants_registry (tenant_code, country_code, schema_name) "
            "VALUES ($1, 'YA', $2) RETURNING tenant_id",
            TENANT_CODE_A,
            SCHEMA_A,
        )
        tenant_b_id = await connexion.fetchval(
            "INSERT INTO shared.tenants_registry (tenant_code, country_code, schema_name) "
            "VALUES ($1, 'YB', $2) RETURNING tenant_id",
            TENANT_CODE_B,
            SCHEMA_B,
        )

        admin_a = await create_user(
            connexion,
            tenant_id=tenant_a_id,
            souverain_id=generate_souverain_id(TENANT_CODE_A, "admin-a@example.com"),
            email="admin-a@example.com",
            password_hash=hash_password(MOT_DE_PASSE_TEST),
            role="admin",
        )
        admin_b = await create_user(
            connexion,
            tenant_id=tenant_b_id,
            souverain_id=generate_souverain_id(TENANT_CODE_B, "admin-b@example.com"),
            email="admin-b@example.com",
            password_hash=hash_password(MOT_DE_PASSE_TEST),
            role="admin",
        )

    try:
        yield {
            "tenant_a_id": tenant_a_id,
            "tenant_b_id": tenant_b_id,
            "admin_a": admin_a,
            "admin_b": admin_b,
        }
    finally:
        await _nettoyer(pool)


async def test_creer_utilisateur_rattache_au_tenant_de_l_appelant(
    pool_web_ou_skip: asyncpg.Pool,
    deux_tenants_avec_admin: dict,
) -> None:
    tenant_a_id = deux_tenants_avec_admin["tenant_a_id"]
    admin_a: UserRecord = deux_tenants_avec_admin["admin_a"]

    async with pool_web_ou_skip.acquire() as connexion:
        nouvel_utilisateur = await creer_utilisateur(
            connexion,
            tenant_id=tenant_a_id,
            email="analyst-a@example.com",
            mot_de_passe_clair=MOT_DE_PASSE_TEST,
            role="analyst",
            acteur_user_id=admin_a.user_id,
        )

    assert nouvel_utilisateur.tenant_id == tenant_a_id
    assert nouvel_utilisateur.role == "analyst"

    async with pool_web_ou_skip.acquire() as connexion:
        entree = await connexion.fetchrow(
            "SELECT acteur_user_id FROM shared.gouvernance_audit_log "
            "WHERE cible_id = $1 AND action = 'utilisateur_creation'",
            nouvel_utilisateur.user_id,
        )
    assert entree is not None
    assert entree["acteur_user_id"] == admin_a.user_id


async def test_changer_role_bloque_auto_modification(
    pool_web_ou_skip: asyncpg.Pool,
    deux_tenants_avec_admin: dict,
) -> None:
    admin_a: UserRecord = deux_tenants_avec_admin["admin_a"]

    async with pool_web_ou_skip.acquire() as connexion:
        with pytest.raises(AutoModificationInterditeError):
            await changer_role_utilisateur(
                connexion,
                cible_user_id=admin_a.user_id,
                nouveau_role="analyst",
                tenant_id_appelant=admin_a.tenant_id,
                acteur_user_id=admin_a.user_id,
            )


async def test_changer_role_bloque_hors_tenant(
    pool_web_ou_skip: asyncpg.Pool,
    deux_tenants_avec_admin: dict,
) -> None:
    """admin_a ne doit JAMAIS pouvoir changer le rôle de admin_b (autre tenant)."""
    admin_a: UserRecord = deux_tenants_avec_admin["admin_a"]
    admin_b: UserRecord = deux_tenants_avec_admin["admin_b"]

    async with pool_web_ou_skip.acquire() as connexion:
        with pytest.raises(UtilisateurHorsTenantError):
            await changer_role_utilisateur(
                connexion,
                cible_user_id=admin_b.user_id,
                nouveau_role="analyst",
                tenant_id_appelant=admin_a.tenant_id,
                acteur_user_id=admin_a.user_id,
            )


async def test_desactiver_bloque_auto_modification(
    pool_web_ou_skip: asyncpg.Pool,
    deux_tenants_avec_admin: dict,
) -> None:
    admin_a: UserRecord = deux_tenants_avec_admin["admin_a"]

    async with pool_web_ou_skip.acquire() as connexion:
        with pytest.raises(AutoModificationInterditeError):
            await desactiver_utilisateur(
                connexion,
                cible_user_id=admin_a.user_id,
                tenant_id_appelant=admin_a.tenant_id,
                acteur_user_id=admin_a.user_id,
            )


async def test_chaine_complete_desactivation_reactivation_jwt(
    pool_web_ou_skip: asyncpg.Pool,
    deux_tenants_avec_admin: dict,
    pool_admin_ou_skip: PostgresSettings,
) -> None:
    """LE test de sécurité explicitement demandé : création -> connexion
    -> JWT(version N) -> désactivation -> révocation -> réactivation ->
    ancien JWT toujours invalide -> nouvelle connexion -> nouveau JWT valide.

    Vérifie le comportement réel, pas une supposition : reactivate_user()
    ne touche jamais token_version (voir repository.py) — c'est
    l'incrémentation IRRÉVERSIBLE faite par deactivate_user() qui
    garantit à elle seule l'invalidation permanente de l'ancien jeton.
    """
    admin_a: UserRecord = deux_tenants_avec_admin["admin_a"]
    tenant_a_id = deux_tenants_avec_admin["tenant_a_id"]
    jwt_settings: JwtSettings = get_jwt_settings()

    pool_admin = await create_pool()

    async with pool_web_ou_skip.acquire() as connexion:
        cible = await creer_utilisateur(
            connexion,
            tenant_id=tenant_a_id,
            email="cycle-complet@example.com",
            mot_de_passe_clair=MOT_DE_PASSE_TEST,
            role="analyst",
            acteur_user_id=admin_a.user_id,
        )

    # "Connexion" : émission d'un jeton avec le token_version courant (1).
    jeton_avant = create_access_token(
        user_id=cible.user_id,
        tenant_id=cible.tenant_id,
        role=cible.role,
        token_version=cible.token_version,
        settings=jwt_settings,
    )
    payload_avant = decode_token(jeton_avant, jwt_settings)
    assert payload_avant.token_version == cible.token_version

    # Désactivation (via l'orchestration de l'extension).
    async with pool_web_ou_skip.acquire() as connexion:
        await desactiver_utilisateur(
            connexion,
            cible_user_id=cible.user_id,
            tenant_id_appelant=tenant_a_id,
            acteur_user_id=admin_a.user_id,
        )

    async with pool_admin.acquire() as connexion:
        apres_desactivation = await get_user_by_id(connexion, cible.user_id)
    assert apres_desactivation is not None
    assert apres_desactivation.is_active is False
    assert apres_desactivation.token_version == cible.token_version + 1

    # L'ancien jeton est désormais invalide (version différente).
    assert payload_avant.token_version != apres_desactivation.token_version

    # Réactivation.
    async with pool_web_ou_skip.acquire() as connexion:
        await reactiver_utilisateur(
            connexion,
            cible_user_id=cible.user_id,
            tenant_id_appelant=tenant_a_id,
            acteur_user_id=admin_a.user_id,
        )

    async with pool_admin.acquire() as connexion:
        apres_reactivation = await get_user_by_id(connexion, cible.user_id)
    assert apres_reactivation is not None
    assert apres_reactivation.is_active is True
    # token_version INCHANGÉ par la réactivation — c'est le point vérifié.
    assert apres_reactivation.token_version == apres_desactivation.token_version

    # L'ancien jeton (version N) reste invalide POUR TOUJOURS : la
    # version courante (N+1) ne redescend jamais.
    assert payload_avant.token_version != apres_reactivation.token_version

    # Nouvelle connexion après réactivation : émet un jeton avec la
    # version COURANTE (N+1) — valide.
    jeton_apres = create_access_token(
        user_id=apres_reactivation.user_id,
        tenant_id=apres_reactivation.tenant_id,
        role=apres_reactivation.role,
        token_version=apres_reactivation.token_version,
        settings=jwt_settings,
    )
    payload_apres = decode_token(jeton_apres, jwt_settings)
    assert payload_apres.token_version == apres_reactivation.token_version


async def test_role_gouvernance_web_ne_peut_pas_modifier_l_audit(
    pool_web_ou_skip: asyncpg.Pool,
    deux_tenants_avec_admin: dict,
) -> None:
    """LE test de la protection par privilège réel — même principe que
    la Brique 8 et la Brique 1 : souverain_gouvernance_web ne doit
    jamais pouvoir UPDATE/DELETE shared.gouvernance_audit_log."""
    async with pool_web_ou_skip.acquire() as connexion:
        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
            await connexion.execute("UPDATE shared.gouvernance_audit_log SET details = NULL")

        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
            await connexion.execute("DELETE FROM shared.gouvernance_audit_log")
