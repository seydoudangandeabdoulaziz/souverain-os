"""Écriture transactionnelle : fermeture d'alerte + entrée d'audit.

Les DEUX opérations (UPDATE {tenant}.alertes, INSERT {tenant}.audit_log)
se déroulent dans UNE SEULE transaction, sur UNE SEULE connexion — celle
du pool RESTREINT de cette brique (connection.py), jamais le pool admin
de la Brique 1. C'est cette connexion, avec ce rôle précis, qui porte la
garantie d'immuabilité : le rôle n'a tout simplement pas le droit
UPDATE/DELETE sur audit_log, quoi que fasse le code applicatif.

L'auto-réparation de la table (CREATE TABLE IF NOT EXISTS + GRANT) est
une exception explicite : elle nécessite des privilèges DDL que le rôle
restreint n'a volontairement pas, donc elle utilise le pool ADMIN de la
Brique 1 (create_pool()) — jamais le pool restreint pour cette seule
étape préparatoire.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

import asyncpg
from brique_01_postgresql.connection import create_pool as create_pool_admin
from brique_01_postgresql.tenant_provisioning import validate_schema_name

from brique_08_audit_human_loop.modeles import AlerteNonFermable, MotifFermeture

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

_REQUETE_ASSURER_GRANTS = (
    "GRANT USAGE ON SCHEMA {schema} TO souverain_brique8_audit",
    "GRANT SELECT, UPDATE ON {schema}.alertes TO souverain_brique8_audit",
    "GRANT INSERT, SELECT ON {schema}.audit_log TO souverain_brique8_audit",
)


@dataclass(frozen=True)
class ResultatFermeture:
    """Résumé d'une fermeture réussie, pour la route/le template."""

    alerte_id: UUID
    audit_id: UUID


async def _table_alertes_existe(nom_schema_tenant: str) -> bool:
    """Vérifie l'existence de {tenant}.alertes via le catalogue système
    (to_regclass), sans dépendre d'un privilège particulier sur la table
    elle-même — juste besoin de lire pg_class, via le pool ADMIN pour
    éviter toute ambiguïté de privilège.

    Distingue les DEUX causes possibles d'un UndefinedTableError dans
    fermer_alerte_avec_audit() : {tenant}.alertes absente (pas notre
    table — la Brique 5 n'a jamais tourné pour ce tenant, l'alerte est
    par définition introuvable, rien à réparer) contre {tenant}.audit_log
    absente (NOTRE table, à auto-réparer). Sans cette distinction, une
    alerte simplement inexistante déclenchait à tort une tentative de
    réparation de audit_log, puis un second échec brut et non traduit
    en AlerteNonFermable — bug réel trouvé en testant sur une vraie
    base (le mock ne l'aurait jamais révélé).
    """
    pool_admin = await create_pool_admin()
    async with pool_admin.acquire() as connexion:
        resultat = await connexion.fetchval(
            "SELECT to_regclass($1) IS NOT NULL", f"{nom_schema_tenant}.alertes"
        )
    return bool(resultat)


async def _assurer_table_audit_log(nom_schema_tenant: str) -> None:
    """Crée la table + accorde les privilèges via le pool ADMIN (Brique 1).

    Étape DDL, hors du chemin transactionnel principal — le rôle
    restreint (pool de cette brique) ne pourrait pas l'exécuter lui-même.
    """
    validate_schema_name(nom_schema_tenant)
    pool_admin = await create_pool_admin()

    async with pool_admin.acquire() as connexion:
        await connexion.execute(_REQUETE_ASSURER_TABLE_AUDIT_LOG.format(schema=nom_schema_tenant))
        await connexion.execute(
            _REQUETE_ASSURER_INDEX_AUDIT_LOG.format(schema=nom_schema_tenant)
        )
        for requete_grant in _REQUETE_ASSURER_GRANTS:
            await connexion.execute(requete_grant.format(schema=nom_schema_tenant))


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
    except asyncpg.exceptions.UndefinedTableError as exc:
        if not await _table_alertes_existe(nom_schema_tenant):
            # Pas notre table, rien à réparer — l'alerte est par
            # construction introuvable sur ce tenant.
            raise AlerteNonFermable(alerte_id) from exc

        # alertes existe : l'absente est forcément audit_log — NOTRE
        # table, auto-réparation via le pool admin puis un seul retry
        # (même principe que persistence.py des Briques 4/5).
        await _assurer_table_audit_log(nom_schema_tenant)
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
