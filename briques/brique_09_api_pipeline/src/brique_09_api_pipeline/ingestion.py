"""Ingestion idempotente d'un lot de transactions.

Garantie portée par la BASE DE DONNÉES : clé primaire (source, external_id)
de `{tenant}.ingestion_keys`. Un rejeu identique n'insère rien ; un même
external_id avec un contenu différent est un CONFLIT explicite (le lot entier
est annulé), jamais ignoré silencieusement.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import UUID, uuid4

import asyncpg
from brique_01_postgresql.tenant_provisioning import validate_schema_name

from brique_09_api_pipeline.schemas import TransactionIn
from brique_09_api_pipeline.verrous import CLASSE_INGESTION, cle_tenant

_INSERT_CLES = """
    INSERT INTO {schema}.ingestion_keys
        (source, external_id, transaction_id, occurred_at, content_hash)
    SELECT $1, u.e, u.t, u.o, u.h
    FROM unnest($2::text[], $3::uuid[], $4::timestamptz[], $5::bytea[]) AS u(e, t, o, h)
    ON CONFLICT (source, external_id) DO NOTHING
    RETURNING external_id
"""
_LIRE_EXISTANTS = """
    SELECT external_id, content_hash FROM {schema}.ingestion_keys
    WHERE source = $1 AND external_id = ANY($2::text[])
"""
_INSERT_TX = """
    INSERT INTO {schema}.transactions
        (transaction_id, tenant_id, country_code, data_classification, amount, currency,
         sender_account, receiver_account, channel, occurred_at, raw_payload, is_synthetic)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::jsonb, false)
"""
_METADONNEES = """
    SELECT tenant_id, country_code, data_classification
    FROM shared.tenants_registry WHERE tenant_id = $1 AND is_active = true
"""


class ConflitIngestion(Exception):
    """Un external_id déjà connu l'a été avec un contenu différent."""

    def __init__(self, external_ids: list[str]) -> None:
        super().__init__("conflit d'ingestion")
        self.external_ids = external_ids


class TenantInactif(Exception):
    """Le tenant de l'identité n'existe plus ou est désactivé."""


@dataclass(frozen=True)
class ResultatIngestion:
    recues: int
    inserees: int
    doublons_ignores: int


async def ingerer_lot(
    pool: asyncpg.Pool,
    schema: str,
    tenant_id: UUID,
    source: str,
    items: list[TransactionIn],
) -> ResultatIngestion:
    validate_schema_name(schema)

    # Dédoublonnage interne au lot : même id + même contenu = doublon ;
    # même id + contenu différent = conflit.
    uniques: dict[str, tuple[TransactionIn, bytes, UUID]] = {}
    for item in items:
        empreinte = item.content_hash()
        connu = uniques.get(item.external_id)
        if connu is None:
            uniques[item.external_id] = (item, empreinte, uuid4())
        elif connu[1] != empreinte:
            raise ConflitIngestion([item.external_id])

    ids = list(uniques)
    async with pool.acquire() as connexion, connexion.transaction():
        # Verrou partagé : le cycle prend le verrou exclusif pour attendre les
        # lots en cours avant de figer sa borne de lecture (voir cycle.py).
        await connexion.execute(
            "SELECT pg_advisory_xact_lock_shared($1, $2)", CLASSE_INGESTION, cle_tenant(tenant_id)
        )
        meta = await connexion.fetchrow(_METADONNEES, tenant_id)
        if meta is None:
            raise TenantInactif
        inserees = await connexion.fetch(
            _INSERT_CLES.format(schema=schema),
            source,
            ids,
            [uniques[i][2] for i in ids],
            [uniques[i][0].occurred_at for i in ids],
            [uniques[i][1] for i in ids],
        )
        nouveaux = {row["external_id"] for row in inserees}
        reste = [i for i in ids if i not in nouveaux]
        if reste:
            existants = await connexion.fetch(_LIRE_EXISTANTS.format(schema=schema), source, reste)
            conflits = [
                row["external_id"]
                for row in existants
                if bytes(row["content_hash"]) != uniques[row["external_id"]][1]
            ]
            if conflits:
                raise ConflitIngestion(sorted(conflits))
        await connexion.executemany(
            _INSERT_TX.format(schema=schema),
            [
                (
                    uniques[i][2],
                    meta["tenant_id"],
                    meta["country_code"],
                    meta["data_classification"],
                    uniques[i][0].amount,
                    uniques[i][0].currency,
                    uniques[i][0].sender_account,
                    uniques[i][0].receiver_account,
                    uniques[i][0].channel,
                    uniques[i][0].occurred_at,
                    json.dumps({"source": source, "external_id": i}),
                )
                for i in ids
                if i in nouveaux
            ],
        )
    return ResultatIngestion(
        recues=len(items), inserees=len(nouveaux), doublons_ignores=len(items) - len(nouveaux)
    )
