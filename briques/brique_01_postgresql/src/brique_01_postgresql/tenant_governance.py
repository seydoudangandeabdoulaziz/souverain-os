"""
Brique 1 V2 — Gouvernance des tenants.

create_tenant() : transaction UNIQUE couvrant l'enregistrement dans
shared.tenants_registry, le provisioning physique du schéma
(provision_tenant_schema(), RÉUTILISÉE TELLE QUELLE, aucune
modification) et l'entrée d'audit — si une étape échoue, tout est
annulé, jamais de schéma orphelin ni de ligne de registre sans schéma
physique.

Vérifié avant d'écrire ce module, pas supposé : provision_tenant_schema()
accepte déjà une connexion en paramètre (pas son propre pool), et son
template SQL (schema_tenant_template.sql) ne contient aucun contrôle de
transaction interne (BEGIN/COMMIT absents) — PostgreSQL exécute le DDL
(CREATE SCHEMA/CREATE TABLE) de façon transactionnelle comme n'importe
quel DML. Elle participe donc telle quelle à la transaction de
create_tenant(), sans aucune adaptation.

CLI-only (décision verrouillée, docs/MODELISATION_OPERATIONNELLE.md
section 7bis) : aucune route HTTP n'expose ces fonctions. Le "Platform
Operator" n'existe pas — reconception différée jusqu'à un besoin
cross-tenant réel.

Toutes les opérations sont exécutées avec le pool dédié
(gouvernance_cli_connection.py, rôle souverain_gouvernance_cli), jamais
avec le pool admin.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg

from brique_01_postgresql.gouvernance_audit import enregistrer_audit_gouvernance_cli
from brique_01_postgresql.tenant_provisioning import provision_tenant_schema, validate_schema_name


class TenantDejaExistant(Exception):
    """Un tenant avec ce tenant_code ou ce schema_name existe déjà."""


class TenantIntrouvable(Exception):
    """Aucun tenant ne correspond au schema_name fourni."""


_INSERT_TENANT = """
    INSERT INTO shared.tenants_registry
        (tenant_code, country_code, schema_name, data_classification, is_active)
    VALUES ($1, $2, $3, $4, true)
    RETURNING tenant_id
"""

_SELECT_TENANT_ID = "SELECT tenant_id FROM shared.tenants_registry WHERE schema_name = $1"

_SET_ACTIVE = """
    UPDATE shared.tenants_registry
    SET is_active = $2, updated_at = now()
    WHERE tenant_id = $1
"""


async def create_tenant(
    connexion: asyncpg.Connection,
    *,
    tenant_code: str,
    country_code: str,
    schema_name: str,
    data_classification: str,
    acteur_declare: str,
) -> UUID:
    """
    Crée un tenant : enregistrement + provisioning physique + audit,
    dans UNE SEULE transaction atomique.

    Raises:
        TenantDejaExistant: tenant_code ou schema_name déjà pris
            (contraintes UNIQUE réelles sur shared.tenants_registry).
        InvalidSchemaNameError: schema_name invalide (propagée par
            validate_schema_name(), réutilisée sans modification).
    """
    validate_schema_name(schema_name)

    async with connexion.transaction():
        try:
            tenant_id: UUID = await connexion.fetchval(
                _INSERT_TENANT, tenant_code, country_code, schema_name, data_classification
            )
        except asyncpg.exceptions.UniqueViolationError as exc:
            raise TenantDejaExistant(
                f"Un tenant existe déjà avec tenant_code={tenant_code!r} "
                f"ou schema_name={schema_name!r}."
            ) from exc

        await provision_tenant_schema(connexion, schema_name)

        await enregistrer_audit_gouvernance_cli(
            connexion,
            domaine="tenant",
            action="tenant_creation",
            cible_id=tenant_id,
            acteur_declare=acteur_declare,
            details={
                "tenant_code": tenant_code,
                "country_code": country_code,
                "schema_name": schema_name,
            },
        )

    return tenant_id


async def _resoudre_tenant_id(connexion: asyncpg.Connection, schema_name: str) -> UUID:
    tenant_id = await connexion.fetchval(_SELECT_TENANT_ID, schema_name)
    if tenant_id is None:
        raise TenantIntrouvable(f"Aucun tenant avec schema_name={schema_name!r}.")
    return tenant_id


async def activate_tenant(
    connexion: asyncpg.Connection,
    *,
    schema_name: str,
    acteur_declare: str,
) -> None:
    """Réactive un tenant désactivé — bascule is_active à true, dans
    une transaction incluant l'écriture d'audit."""
    async with connexion.transaction():
        tenant_id = await _resoudre_tenant_id(connexion, schema_name)
        await connexion.execute(_SET_ACTIVE, tenant_id, True)
        await enregistrer_audit_gouvernance_cli(
            connexion,
            domaine="tenant",
            action="tenant_activation",
            cible_id=tenant_id,
            acteur_declare=acteur_declare,
        )


async def deactivate_tenant(
    connexion: asyncpg.Connection,
    *,
    schema_name: str,
    acteur_declare: str,
) -> None:
    """
    Désactive un tenant — bascule is_active à false UNIQUEMENT.

    Ne supprime JAMAIS le schéma physique : aucun DROP SCHEMA ici, ni
    maintenant ni plus tard sans une décision explicite séparée du
    fondateur. Une désactivation reste réversible via activate_tenant().
    """
    async with connexion.transaction():
        tenant_id = await _resoudre_tenant_id(connexion, schema_name)
        await connexion.execute(_SET_ACTIVE, tenant_id, False)
        await enregistrer_audit_gouvernance_cli(
            connexion,
            domaine="tenant",
            action="tenant_desactivation",
            cible_id=tenant_id,
            acteur_declare=acteur_declare,
        )
