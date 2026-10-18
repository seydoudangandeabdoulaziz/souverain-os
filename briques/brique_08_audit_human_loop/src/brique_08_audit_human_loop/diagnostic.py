"""Diagnostic en LECTURE SEULE de l'état de l'audit B8 pour un schéma tenant.

Ce module ne contient AUCUN DDL ni GRANT, et n'importe rien qui en
contienne : c'est le seul point d'entrée que le chemin de lecture
(lecture.py, routes.py) a le droit d'utiliser pour interroger le pool
ADMIN. Les garanties (ADR-005, D2) sont cumulatives :

1. séparation du code : ce fichier n'importe pas persistence.py ;
2. transaction `READ ONLY` imposée par le serveur (PostgreSQL rejette
   alors tout CREATE/ALTER/DROP/GRANT/écriture, même pour un
   superutilisateur) ;
3. SQL constant et paramétré, uniquement des lectures de catalogue ;
4. borne de temps (`statement_timeout`).

Limite assumée : le pool admin est superutilisateur, donc ce n'est pas
une frontière de privilèges — c'est de la défense en profondeur.
"""

from __future__ import annotations

from dataclasses import dataclass

import asyncpg
from brique_01_postgresql.connection import create_pool as create_pool_admin
from brique_01_postgresql.tenant_provisioning import validate_schema_name

# Rôle PostgreSQL dédié créé par la migration 0001 — même nom que dans les
# GRANT de persistence.py (une seule source de vérité).
ROLE_AUDIT = "souverain_brique8_audit"

_REQUETE_EXISTENCE = """
    SELECT
        EXISTS (SELECT 1 FROM pg_roles WHERE rolname = $1) AS role_existe,
        EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = $2) AS schema_existe,
        to_regclass($3) IS NOT NULL AS audit_log_existe,
        to_regclass($4) IS NOT NULL AS alertes_existe
"""

_REQUETE_USAGE = "SELECT has_schema_privilege($1::name, $2::text, 'USAGE')"

_REQUETE_PRIVILEGES_AUDIT_LOG = """
    SELECT
        has_table_privilege($1::name, $2::text, 'INSERT') AS insert_,
        has_table_privilege($1::name, $2::text, 'SELECT') AS select_,
        has_table_privilege($1::name, $2::text, 'UPDATE') AS update_,
        has_table_privilege($1::name, $2::text, 'DELETE') AS delete_,
        has_table_privilege($1::name, $2::text, 'TRUNCATE') AS truncate_
"""

_REQUETE_PRIVILEGES_ALERTES = """
    SELECT
        has_table_privilege($1::name, $2::text, 'SELECT') AS select_,
        has_table_privilege($1::name, $2::text, 'UPDATE') AS update_
"""


@dataclass(frozen=True)
class DiagnosticAudit:
    """État constaté (booléens uniquement — aucun texte d'erreur, aucune donnée)."""

    role_existe: bool
    schema_existe: bool
    audit_log_existe: bool
    alertes_existe: bool
    usage_schema: bool
    audit_log_insert: bool
    audit_log_select: bool
    audit_log_update: bool
    audit_log_delete: bool
    audit_log_truncate: bool
    alertes_select: bool
    alertes_update: bool

    @property
    def elements_manquants(self) -> list[str]:
        """Éléments du contrat B8 constatés manquants (liste FERMÉE).

        `alertes` n'est jamais créée par B8 : seul son privilège est
        concerné, et seulement si la table existe.
        """
        manquants: list[str] = []
        if not self.usage_schema:
            manquants.append("usage_schema")
        if not self.audit_log_existe:
            manquants.append("audit_log")
        if not (self.audit_log_existe and self.audit_log_insert and self.audit_log_select):
            manquants.append("audit_log_privileges")
        if self.alertes_existe and not (self.alertes_select and self.alertes_update):
            manquants.append("alertes_privileges")
        return manquants

    @property
    def anomalie_audit_log(self) -> bool:
        """Le rôle B8 ne doit JAMAIS pouvoir modifier ni supprimer audit_log."""
        return self.audit_log_update or self.audit_log_delete or self.audit_log_truncate


async def lire_diagnostic(connexion: asyncpg.Connection, nom_schema_tenant: str) -> DiagnosticAudit:
    """Lectures de catalogue uniquement, sur une connexion fournie par l'appelant.

    Le nom de schéma est validé puis passé comme PARAMÈTRE LIÉ — jamais
    interpolé dans le SQL. Les fonctions has_*_privilege ne sont appelées
    que pour des objets dont l'existence vient d'être constatée.
    """
    validate_schema_name(nom_schema_tenant)
    cible_audit_log = f"{nom_schema_tenant}.audit_log"
    cible_alertes = f"{nom_schema_tenant}.alertes"

    existence = await connexion.fetchrow(
        _REQUETE_EXISTENCE, ROLE_AUDIT, nom_schema_tenant, cible_audit_log, cible_alertes
    )
    assert existence is not None  # un SELECT sans FROM retourne toujours une ligne
    role_et_schema = bool(existence["role_existe"] and existence["schema_existe"])

    usage = False
    if role_et_schema:
        usage = bool(await connexion.fetchval(_REQUETE_USAGE, ROLE_AUDIT, nom_schema_tenant))

    # Les privilèges de TABLE sont indépendants de USAGE sur le schéma :
    # on les lit dès que le rôle et la table existent (sinon une anomalie
    # UPDATE/DELETE passerait inaperçue sur un schéma sans USAGE).
    audit: dict[str, bool] = {
        "insert_": False,
        "select_": False,
        "update_": False,
        "delete_": False,
        "truncate_": False,
    }
    if role_et_schema and existence["audit_log_existe"]:
        ligne = await connexion.fetchrow(_REQUETE_PRIVILEGES_AUDIT_LOG, ROLE_AUDIT, cible_audit_log)
        assert ligne is not None
        audit = dict(ligne)

    alertes: dict[str, bool] = {"select_": False, "update_": False}
    if role_et_schema and existence["alertes_existe"]:
        ligne = await connexion.fetchrow(_REQUETE_PRIVILEGES_ALERTES, ROLE_AUDIT, cible_alertes)
        assert ligne is not None
        alertes = dict(ligne)

    return DiagnosticAudit(
        role_existe=bool(existence["role_existe"]),
        schema_existe=bool(existence["schema_existe"]),
        audit_log_existe=bool(existence["audit_log_existe"]),
        alertes_existe=bool(existence["alertes_existe"]),
        usage_schema=usage,
        audit_log_insert=bool(audit["insert_"]),
        audit_log_select=bool(audit["select_"]),
        audit_log_update=bool(audit["update_"]),
        audit_log_delete=bool(audit["delete_"]),
        audit_log_truncate=bool(audit["truncate_"]),
        alertes_select=bool(alertes["select_"]),
        alertes_update=bool(alertes["update_"]),
    )


async def diagnostiquer_audit(nom_schema_tenant: str) -> DiagnosticAudit:
    """Diagnostic autonome : une connexion admin, transaction READ ONLY, borne de temps.

    Appelé uniquement sur le CHEMIN D'ERREUR (jamais sur le chemin nominal).
    """
    validate_schema_name(nom_schema_tenant)
    pool_admin = await create_pool_admin()
    async with pool_admin.acquire() as connexion, connexion.transaction(readonly=True):
        await connexion.execute("SET LOCAL statement_timeout = '2s'")
        return await lire_diagnostic(connexion, nom_schema_tenant)
