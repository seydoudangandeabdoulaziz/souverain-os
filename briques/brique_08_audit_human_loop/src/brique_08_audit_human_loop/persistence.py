"""Écriture transactionnelle : fermeture d'alerte + entrée d'audit.

Les DEUX opérations (UPDATE {tenant}.alertes, INSERT {tenant}.audit_log)
se déroulent dans UNE SEULE transaction, sur UNE SEULE connexion — celle
du pool RESTREINT de cette brique (connection.py), jamais le pool admin
de la Brique 1. C'est cette connexion, avec ce rôle précis, qui porte la
garantie d'immuabilité : le rôle n'a tout simplement pas le droit
UPDATE/DELETE sur audit_log, quoi que fasse le code applicatif.

Le provisionnement (CREATE TABLE + GRANT, du DDL) est une exception
explicite : il nécessite des privilèges que le rôle restreint n'a
volontairement pas, donc `provisionner_audit()` utilise le pool ADMIN de
la Brique 1 — jamais le pool restreint. Il est appelé par la commande
`souverain-audit-provisionner` (cli.py) et, en réparation défensive, par
`fermer_alerte_avec_audit()` (ADR-005). Le chemin de LECTURE ne l'appelle
jamais.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from time import monotonic
from uuid import UUID, uuid4

import asyncpg
from brique_01_postgresql.connection import create_pool as create_pool_admin
from brique_01_postgresql.tenant_provisioning import validate_schema_name

from brique_08_audit_human_loop.diagnostic import (
    ROLE_AUDIT,
    DiagnosticAudit,
    diagnostiquer_audit,
    lire_diagnostic,
)
from brique_08_audit_human_loop.modeles import (
    AlerteNonFermable,
    AuditNonProvisionne,
    MotifFermeture,
    RaisonAudit,
)

journal = logging.getLogger(__name__)

_REQUETE_FERMER_ALERTE = """
    UPDATE {schema}.alertes
    SET statut = 'fermee', updated_at = now()
    WHERE alerte_id = $1 AND statut = 'ouverte'
    RETURNING alerte_id, tenant_id
"""

_REQUETE_INSERER_AUDIT = """
    INSERT INTO {schema}.audit_log
        (id, alerte_id, tenant_id, user_id, motif, commentaire)
    VALUES ($1, $2, $3, $4, $5, $6)
"""

_REQUETE_ASSURER_TABLE_AUDIT_LOG = """
    CREATE TABLE IF NOT EXISTS {schema}.audit_log (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        alerte_id UUID NOT NULL,
        tenant_id UUID NOT NULL,
        user_id UUID NOT NULL,
        motif TEXT NOT NULL
            CHECK (motif IN ('faux_positif', 'confirme', 'en_cours_investigation')),
        commentaire TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
"""

_REQUETE_ASSURER_INDEX_AUDIT_LOG = """
    CREATE INDEX IF NOT EXISTS idx_{schema}_audit_log_alerte
    ON {schema}.audit_log (alerte_id, created_at DESC)
"""

_GRANT_USAGE = "GRANT USAGE ON SCHEMA {schema} TO {role}"
_GRANT_AUDIT_LOG = "GRANT INSERT, SELECT ON {schema}.audit_log TO {role}"
_GRANT_ALERTES = "GRANT SELECT, UPDATE ON {schema}.alertes TO {role}"


@dataclass(frozen=True)
class ResultatFermeture:
    """Résumé d'une fermeture réussie, pour la route/le template."""

    alerte_id: UUID
    audit_id: UUID


async def _appliquer_contrat(
    connexion: asyncpg.Connection, schema: str, avant: DiagnosticAudit
) -> list[str]:
    """Crée/accorde UNIQUEMENT les éléments constatés manquants (liste fermée).

    Jamais : UPDATE/DELETE sur audit_log, création de `alertes`, création du
    rôle, privilège sur `shared`.
    """
    repares: list[str] = []
    if not avant.audit_log_existe:
        await connexion.execute(_REQUETE_ASSURER_TABLE_AUDIT_LOG.format(schema=schema))
        await connexion.execute(_REQUETE_ASSURER_INDEX_AUDIT_LOG.format(schema=schema))
        repares.append("audit_log")
    if not avant.usage_schema:
        await connexion.execute(_GRANT_USAGE.format(schema=schema, role=ROLE_AUDIT))
        repares.append("usage_schema")
    if not (avant.audit_log_existe and avant.audit_log_insert and avant.audit_log_select):
        await connexion.execute(_GRANT_AUDIT_LOG.format(schema=schema, role=ROLE_AUDIT))
        repares.append("audit_log_privileges")
    if avant.alertes_existe and not (avant.alertes_select and avant.alertes_update):
        await connexion.execute(_GRANT_ALERTES.format(schema=schema, role=ROLE_AUDIT))
        repares.append("alertes_privileges")
    return repares


def _refuser_si_inprovisionnable(schema: str, diagnostic: DiagnosticAudit) -> None:
    if not diagnostic.role_existe:
        raise AuditNonProvisionne(RaisonAudit.ROLE_ABSENT)
    if not diagnostic.schema_existe:
        raise AuditNonProvisionne(RaisonAudit.SCHEMA_ABSENT)
    if diagnostic.anomalie_audit_log:
        # Anomalie de sécurité PRÉEXISTANTE : signalée, jamais corrigée automatiquement.
        journal.critical("b8.anomalie_audit_log_privilege schema=%s", schema)
        raise AuditNonProvisionne(RaisonAudit.ANOMALIE_PRIVILEGE)


async def provisionner_audit(nom_schema_tenant: str) -> list[str]:
    """Provisionne l'audit B8 d'UN schéma tenant. Idempotent, sous le pool ADMIN.

    Une seule connexion admin, une seule transaction : verrou advisory de
    transaction (propre au schéma, libéré au COMMIT/ROLLBACK), diagnostic
    sous verrou, réparation ciblée, puis contrôle final (le rôle B8 ne doit
    avoir ni UPDATE ni DELETE sur audit_log — sinon tout est annulé).

    Returns:
        Éléments réparés (liste vide = déjà conforme).

    Raises:
        AuditNonProvisionne: rôle ou schéma absent, anomalie de privilège,
            timeout du verrou, ou réparation impossible. Les causes SQL
            sont chaînées (`from`), jamais recopiées dans le message.
    """
    validate_schema_name(nom_schema_tenant)
    debut = monotonic()
    pool_admin = await create_pool_admin()

    try:
        async with pool_admin.acquire() as connexion, connexion.transaction():
            await connexion.execute("SET LOCAL lock_timeout = '5s'")
            await connexion.execute("SET LOCAL statement_timeout = '15s'")
            await connexion.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended($1::text, 0))",
                f"souverain:b8_audit:{nom_schema_tenant}",
            )
            avant = await lire_diagnostic(connexion, nom_schema_tenant)
            _refuser_si_inprovisionnable(nom_schema_tenant, avant)

            repares = await _appliquer_contrat(connexion, nom_schema_tenant, avant)

            apres = await lire_diagnostic(connexion, nom_schema_tenant)
            if apres.anomalie_audit_log:
                journal.critical("b8.anomalie_audit_log_privilege schema=%s", nom_schema_tenant)
                raise AuditNonProvisionne(RaisonAudit.ANOMALIE_PRIVILEGE)
    except asyncpg.exceptions.LockNotAvailableError as exc:
        journal.error("b8.verrou_timeout schema=%s", nom_schema_tenant)
        raise AuditNonProvisionne(RaisonAudit.VERROU_TIMEOUT) from exc
    except (
        asyncpg.exceptions.QueryCanceledError,
        asyncpg.exceptions.DeadlockDetectedError,
        asyncpg.exceptions.PostgresConnectionError,
        OSError,
    ) as exc:
        journal.error(
            "b8.reparation_echec schema=%s classe=%s sqlstate=%s",
            nom_schema_tenant,
            type(exc).__name__,
            getattr(exc, "sqlstate", None),
        )
        raise AuditNonProvisionne(RaisonAudit.REPARATION_ECHOUEE) from exc

    journal.info(
        "b8.reparation schema=%s elements=%s duree_ms=%d",
        nom_schema_tenant,
        ",".join(repares) or "aucun",
        int((monotonic() - debut) * 1000),
    )
    return repares


async def _tenter_fermeture(
    pool_audit: asyncpg.Pool,
    nom_schema_tenant: str,
    *,
    alerte_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
    motif: MotifFermeture,
    commentaire: str | None,
    audit_id: UUID,
) -> None:
    """Une seule tentative, une seule transaction. Lève UndefinedTableError
    brute si {tenant}.alertes OU {tenant}.audit_log est absente — à
    l'appelant de distinguer laquelle (voir fermer_alerte_avec_audit).
    """
    requete_fermer = _REQUETE_FERMER_ALERTE.format(schema=nom_schema_tenant)
    requete_audit = _REQUETE_INSERER_AUDIT.format(schema=nom_schema_tenant)

    async with pool_audit.acquire() as connexion, connexion.transaction():
        ligne = await connexion.fetchrow(requete_fermer, alerte_id)
        if ligne is None:
            raise AlerteNonFermable(alerte_id)

        await connexion.execute(
            requete_audit,
            audit_id,
            alerte_id,
            tenant_id,
            user_id,
            motif.value,
            commentaire,
        )


async def fermer_alerte_avec_audit(
    pool_audit: asyncpg.Pool,
    nom_schema_tenant: str,
    *,
    alerte_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
    motif: MotifFermeture,
    commentaire: str | None,
) -> ResultatFermeture:
    """Ferme une alerte et enregistre l'entrée d'audit, atomiquement.

    Raises:
        AlerteNonFermable: l'alerte n'existe pas (y compris quand
            {tenant}.alertes elle-même n'existe pas encore — la
            Brique 5 n'a jamais tourné pour ce tenant, ce n'est pas
            une raison de créer quoi que ce soit ici, seulement de
            rapporter "introuvable"), ou n'était déjà plus 'ouverte'
            au moment du UPDATE (garantie anti-course réelle, portée
            par la clause WHERE + RETURNING — pas une simple
            vérification préalable qui laisserait une fenêtre de
            course entre lecture et écriture).
        AuditNonProvisionne: l'audit B8 est inutilisable pour ce tenant et
            n'a pas pu être réparé (rôle absent, verrou expiré, anomalie).
    """
    validate_schema_name(nom_schema_tenant)
    audit_id = uuid4()

    try:
        await _tenter_fermeture(
            pool_audit,
            nom_schema_tenant,
            alerte_id=alerte_id,
            tenant_id=tenant_id,
            user_id=user_id,
            motif=motif,
            commentaire=commentaire,
            audit_id=audit_id,
        )
    except (
        asyncpg.exceptions.UndefinedTableError,
        asyncpg.exceptions.InsufficientPrivilegeError,
    ) as exc:
        # Jamais de GRANT sur la seule classe d'exception : on diagnostique
        # d'abord (lecture seule) et on ne répare que ce qui manque réellement.
        diagnostic = await diagnostiquer_audit(nom_schema_tenant)

        if isinstance(exc, asyncpg.exceptions.UndefinedTableError):
            if not diagnostic.alertes_existe:
                # Pas notre table : la Brique 5 n'a jamais tourné pour ce
                # tenant, l'alerte est par construction introuvable.
                raise AlerteNonFermable(alerte_id) from exc
            if diagnostic.audit_log_existe:
                raise  # anormal : les deux tables existent, rien à réparer
        else:
            if not diagnostic.role_existe:
                raise AuditNonProvisionne(RaisonAudit.ROLE_ABSENT) from exc
            if not diagnostic.elements_manquants:
                raise  # contrat complet : la cause est autre, on ne devine pas

        journal.info(
            "b8.diagnostic schema=%s manquants=%s sqlstate=%s",
            nom_schema_tenant,
            ",".join(diagnostic.elements_manquants) or "aucun",
            exc.sqlstate,
        )
        # provisionner_audit() re-diagnostique SOUS VERROU : un appelant
        # concurrent qui a déjà réparé n'entraîne aucune seconde réparation.
        await provisionner_audit(nom_schema_tenant)

        # UN SEUL nouvel essai (autre rôle, autre connexion, hors verrou — la
        # réparation est déjà validée et idempotente). Un second échec remonte.
        await _tenter_fermeture(
            pool_audit,
            nom_schema_tenant,
            alerte_id=alerte_id,
            tenant_id=tenant_id,
            user_id=user_id,
            motif=motif,
            commentaire=commentaire,
            audit_id=audit_id,
        )

    return ResultatFermeture(alerte_id=alerte_id, audit_id=audit_id)
