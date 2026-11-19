"""Ingestion idempotente : l'unicité (source, external_id) vient de la base."""

from __future__ import annotations

import asyncio
from decimal import Decimal

import asyncpg
import pytest
from brique_01_postgresql.connection import create_tenant_pipeline_pool
from brique_09_api_pipeline.ingestion import ConflitIngestion, ingerer_lot
from brique_09_api_pipeline.schemas import TransactionIn
from support_b9 import A, B


def _tx(
    i: int, montant: str = "1000.00", quand: str = "2026-03-01T10:00:00+00:00"
) -> TransactionIn:
    return TransactionIn.model_validate(
        {
            "external_id": f"ext-{i}",
            "sender_account": f"cpt_{i}",
            "receiver_account": f"cpt_{i + 1000}",
            "amount": montant,
            "currency": "XOF",
            "channel": "orange_money",
            "occurred_at": quand,
        }
    )


async def _compter(admin: asyncpg.Connection, schema: str, table: str) -> int:
    return int(await admin.fetchval(f"SELECT count(*) FROM {schema}.{table}"))


async def test_ingestion_puis_rejeu_identique_sans_doublon(admin: asyncpg.Connection) -> None:
    pool = await create_tenant_pipeline_pool(A.tenant_id)
    lot = [_tx(i) for i in range(50)]
    premier = await ingerer_lot(pool, A.schema, A.tenant_id, "feed", lot)
    assert (premier.recues, premier.inserees, premier.doublons_ignores) == (50, 50, 0)
    rejeu = await ingerer_lot(pool, A.schema, A.tenant_id, "feed", lot)
    assert (rejeu.inserees, rejeu.doublons_ignores) == (0, 50)
    assert await _compter(admin, A.schema, "transactions") == 50
    assert await _compter(admin, A.schema, "ingestion_keys") == 50
    ligne = await admin.fetchrow(
        f"SELECT tenant_id, country_code, is_synthetic, raw_payload "
        f"FROM {A.schema}.transactions LIMIT 1"
    )
    assert ligne is not None
    assert ligne["tenant_id"] == A.tenant_id and ligne["is_synthetic"] is False
    assert "ext-" in ligne["raw_payload"]


async def test_meme_identifiant_contenu_different_est_un_conflit_explicite(
    admin: asyncpg.Connection,
) -> None:
    pool = await create_tenant_pipeline_pool(A.tenant_id)
    await ingerer_lot(pool, A.schema, A.tenant_id, "feed", [_tx(1), _tx(2)])
    with pytest.raises(ConflitIngestion) as exc:
        await ingerer_lot(pool, A.schema, A.tenant_id, "feed", [_tx(1, montant="999.00")])
    assert exc.value.external_ids == ["ext-1"]
    # Le conflit n'écrase rien et ne laisse aucune écriture partielle.
    assert await _compter(admin, A.schema, "transactions") == 2
    montant = await admin.fetchval(
        f"SELECT amount FROM {A.schema}.transactions t JOIN {A.schema}.ingestion_keys k "
        f"USING (transaction_id, occurred_at) WHERE k.external_id = 'ext-1'"
    )
    assert montant == Decimal("1000.00")


async def test_lot_avec_un_conflit_est_annule_en_entier(admin: asyncpg.Connection) -> None:
    pool = await create_tenant_pipeline_pool(A.tenant_id)
    await ingerer_lot(pool, A.schema, A.tenant_id, "feed", [_tx(1)])
    with pytest.raises(ConflitIngestion):
        await ingerer_lot(
            pool, A.schema, A.tenant_id, "feed", [_tx(10), _tx(11), _tx(1, montant="5.00")]
        )
    assert await _compter(admin, A.schema, "transactions") == 1
    assert await _compter(admin, A.schema, "ingestion_keys") == 1


async def test_doublons_et_conflits_dans_le_meme_lot(admin: asyncpg.Connection) -> None:
    pool = await create_tenant_pipeline_pool(A.tenant_id)
    res = await ingerer_lot(pool, A.schema, A.tenant_id, "feed", [_tx(1), _tx(1), _tx(2)])
    assert (res.recues, res.inserees, res.doublons_ignores) == (3, 2, 1)
    with pytest.raises(ConflitIngestion):
        await ingerer_lot(pool, A.schema, A.tenant_id, "feed", [_tx(5), _tx(5, montant="2.00")])


async def test_deux_sources_peuvent_reutiliser_un_external_id(admin: asyncpg.Connection) -> None:
    pool = await create_tenant_pipeline_pool(A.tenant_id)
    await ingerer_lot(pool, A.schema, A.tenant_id, "source_a", [_tx(1)])
    res = await ingerer_lot(pool, A.schema, A.tenant_id, "source_b", [_tx(1, montant="7.00")])
    assert res.inserees == 1
    assert await _compter(admin, A.schema, "transactions") == 2


async def test_unicite_garantie_par_la_base_meme_hors_application(
    admin: asyncpg.Connection,
) -> None:
    pool = await create_tenant_pipeline_pool(A.tenant_id)
    await ingerer_lot(pool, A.schema, A.tenant_id, "feed", [_tx(1)])
    with pytest.raises(asyncpg.UniqueViolationError):
        await pool.execute(
            f"INSERT INTO {A.schema}.ingestion_keys "
            f"(source, external_id, transaction_id, occurred_at, content_hash) "
            f"VALUES ('feed', 'ext-1', gen_random_uuid(), now(), '\\x00')"
        )


async def test_rejeux_concurrents_n_inserent_qu_une_fois(admin: asyncpg.Connection) -> None:
    pool = await create_tenant_pipeline_pool(A.tenant_id)
    lot = [_tx(i) for i in range(40)]
    resultats = await asyncio.gather(
        *[ingerer_lot(pool, A.schema, A.tenant_id, "feed", lot) for _ in range(4)]
    )
    assert sum(r.inserees for r in resultats) == 40
    assert await _compter(admin, A.schema, "transactions") == 40


async def test_isolation_entre_tenants(admin: asyncpg.Connection) -> None:
    pool_a = await create_tenant_pipeline_pool(A.tenant_id)
    await ingerer_lot(pool_a, A.schema, A.tenant_id, "feed", [_tx(1)])
    assert await _compter(admin, B.schema, "transactions") == 0
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await pool_a.execute(f"SELECT * FROM {B.schema}.transactions")
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await pool_a.execute(f"SELECT * FROM {B.schema}.ingestion_keys")
    # Le schéma du tenant B reçu avec l'identité de A : refusé par PostgreSQL.
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await ingerer_lot(pool_a, B.schema, A.tenant_id, "feed", [_tx(2)])
    assert await _compter(admin, B.schema, "transactions") == 0


async def test_le_role_pipeline_ne_peut_ni_supprimer_ni_creer(admin: asyncpg.Connection) -> None:
    pool = await create_tenant_pipeline_pool(A.tenant_id)
    await ingerer_lot(pool, A.schema, A.tenant_id, "feed", [_tx(1)])
    for ordre in (
        f"DELETE FROM {A.schema}.transactions",
        f"DELETE FROM {A.schema}.ingestion_keys",
        f"UPDATE {A.schema}.transactions SET amount = 1",
        f"TRUNCATE {A.schema}.detections",
        f"CREATE TABLE {A.schema}.intrus (x int)",
        "UPDATE shared.users SET role = 'admin'",
    ):
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await pool.execute(ordre)
