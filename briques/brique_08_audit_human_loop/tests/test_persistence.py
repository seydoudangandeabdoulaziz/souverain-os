"""Tests d'intégration de persistence.py — contre une vraie instance
PostgreSQL/TimescaleDB (tenant éphémère), pas de mock.

Non exécutés dans l'environnement de génération (pas de PostgreSQL
disponible) — à exécuter sur la machine réelle avant validation, même
mention que les briques précédentes.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import asyncpg
import pytest
from brique_08_audit_human_loop.lecture import lire_historique_audit
from brique_08_audit_human_loop.modeles import AlerteNonFermable, MotifFermeture
from brique_08_audit_human_loop.persistence import fermer_alerte_avec_audit


@pytest.mark.asyncio
async def test_fermer_alerte_change_le_statut_et_ecrit_l_audit(
    pool: asyncpg.Pool,
    pool_audit: asyncpg.Pool,
    tenant_provisionne: tuple[UUID, str],
    alerte_test: UUID,
) -> None:
    tenant_id, schema_name = tenant_provisionne
    user_id = uuid4()

    resultat = await fermer_alerte_avec_audit(
        pool_audit,
        schema_name,
        alerte_id=alerte_test,
        tenant_id=tenant_id,
        user_id=user_id,
        motif=MotifFermeture.CONFIRME,
        commentaire="Vérifié manuellement, réseau hawala confirmé.",
    )
    assert resultat.alerte_id == alerte_test

    async with pool.acquire() as connexion:
        statut = await connexion.fetchval(
            f"SELECT statut FROM {schema_name}.alertes WHERE alerte_id = $1", alerte_test
        )
    assert statut == "fermee"

    historique = await lire_historique_audit(pool_audit, schema_name, alerte_test)
    assert len(historique) == 1
    assert historique[0].motif == "confirme"
    assert historique[0].commentaire == "Vérifié manuellement, réseau hawala confirmé."
    assert historique[0].user_id == user_id


@pytest.mark.asyncio
async def test_fermer_alerte_deja_fermee_leve_alerte_non_fermable(
    pool_audit: asyncpg.Pool,
    tenant_provisionne: tuple[UUID, str],
    alerte_test: UUID,
) -> None:
    """Rejeu du même cycle : la deuxième fermeture doit échouer proprement
    (anti-course), pas dupliquer l'entrée d'audit ni écraser silencieusement.
    """
    _, schema_name = tenant_provisionne
    tenant_id, _ = tenant_provisionne

    await fermer_alerte_avec_audit(
        pool_audit,
        schema_name,
        alerte_id=alerte_test,
        tenant_id=tenant_id,
        user_id=uuid4(),
        motif=MotifFermeture.FAUX_POSITIF,
        commentaire=None,
    )

    with pytest.raises(AlerteNonFermable):
        await fermer_alerte_avec_audit(
            pool_audit,
            schema_name,
            alerte_id=alerte_test,
            tenant_id=tenant_id,
            user_id=uuid4(),
            motif=MotifFermeture.CONFIRME,
            commentaire="Tentative de double fermeture.",
        )

    historique = await lire_historique_audit(pool_audit, schema_name, alerte_test)
    assert len(historique) == 1  # toujours une seule entrée, pas deux


@pytest.mark.asyncio
async def test_fermer_alerte_inexistante_leve_alerte_non_fermable(
    pool_audit: asyncpg.Pool,
    tenant_provisionne: tuple[UUID, str],
) -> None:
    _, schema_name = tenant_provisionne
    tenant_id, _ = tenant_provisionne

    with pytest.raises(AlerteNonFermable):
        await fermer_alerte_avec_audit(
            pool_audit,
            schema_name,
            alerte_id=uuid4(),  # n'existe pas
            tenant_id=tenant_id,
            user_id=uuid4(),
            motif=MotifFermeture.CONFIRME,
            commentaire=None,
        )


@pytest.mark.asyncio
async def test_role_restreint_ne_peut_pas_modifier_l_audit_log(
    pool_audit: asyncpg.Pool,
    tenant_provisionne: tuple[UUID, str],
    alerte_test: UUID,
) -> None:
    """LE test de la protection par privilège réel (pas seulement la
    discipline applicative) : même en contournant persistence.py et en
    exécutant du SQL directement avec le pool restreint, un UPDATE ou
    un DELETE sur audit_log doit être refusé par PostgreSQL lui-même.
    """
    tenant_id, schema_name = tenant_provisionne

    # Fait exister la table + une ligne, via le chemin normal.
    await fermer_alerte_avec_audit(
        pool_audit,
        schema_name,
        alerte_id=alerte_test,
        tenant_id=tenant_id,
        user_id=uuid4(),
        motif=MotifFermeture.EN_COURS_INVESTIGATION,
        commentaire=None,
    )

    async with pool_audit.acquire() as connexion:
        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
            await connexion.execute(
                f"UPDATE {schema_name}.audit_log SET commentaire = 'falsifié'"
            )

        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
            await connexion.execute(f"DELETE FROM {schema_name}.audit_log")


@pytest.mark.asyncio
async def test_lire_historique_audit_sans_table_retourne_liste_vide(
    pool_audit: asyncpg.Pool,
    tenant_provisionne: tuple[UUID, str],
) -> None:
    """Tenant neuf, aucune fermeture n'a jamais eu lieu — audit_log
    n'existe pas encore. Doit retourner [], pas lever d'exception.
    """
    _, schema_name = tenant_provisionne
    historique = await lire_historique_audit(pool_audit, schema_name, uuid4())
    assert historique == []
