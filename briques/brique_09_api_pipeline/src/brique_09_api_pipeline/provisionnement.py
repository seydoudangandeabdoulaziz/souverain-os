"""Provisionnement par tenant des objets propres à la Brique 9 (opérateur).

Exécuté avec le rôle admin (propriétaire des tables), jamais par l'API : le
rôle `pipeline` n'a aucun droit de création. Idempotent. Aucune table des
Briques 1 à 8 n'est modifiée ; seuls des INDEX sont ajoutés sur
`transactions` et `detections` (index composites absents du template B1).
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from brique_01_postgresql.tenant_provisioning import validate_schema_name
from brique_01_postgresql.tenant_roles import provision_tenant_role

_DDL = """
CREATE TABLE IF NOT EXISTS {schema}.ingestion_keys (
    source        TEXT        NOT NULL,
    external_id   TEXT        NOT NULL,
    transaction_id UUID       NOT NULL,
    occurred_at   TIMESTAMPTZ NOT NULL,
    content_hash  BYTEA       NOT NULL,
    seq           BIGINT GENERATED ALWAYS AS IDENTITY,
    ingested_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (source, external_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_{schema}_ingestion_keys_seq
    ON {schema}.ingestion_keys (seq);

CREATE TABLE IF NOT EXISTS {schema}.pipeline_cursor (
    singleton BOOLEAN PRIMARY KEY DEFAULT true CHECK (singleton),
    last_seq  BIGINT  NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_{schema}_tx_sender_time
    ON {schema}.transactions (sender_account, occurred_at);
CREATE INDEX IF NOT EXISTS idx_{schema}_tx_receiver_time
    ON {schema}.transactions (receiver_account, occurred_at);
"""

_DDL_DETECTIONS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_{schema}_detections_compte_fenetre
    ON {schema}.detections (compte_pivot, fenetre_debut);
"""


async def provisionner_tenant(connection: asyncpg.Connection, tenant_id: UUID, schema: str) -> None:
    """Crée les objets B9 du tenant puis rafraîchit les droits du rôle `pipeline`.

    Le rôle reste NOLOGIN tant que `provision_tenant_roles.py --with-pipeline`
    ne l'a pas activé : ce module ne manipule aucun secret.
    """
    validate_schema_name(schema)
    async with connection.transaction():
        await connection.execute(_DDL.format(schema=schema))
        if await connection.fetchval("SELECT to_regclass($1) IS NOT NULL", f"{schema}.detections"):
            await connection.execute(_DDL_DETECTIONS_INDEX.format(schema=schema))
        # Rafraîchit les droits (liste blanche B1) maintenant que les tables existent.
        await provision_tenant_role(connection, tenant_id, schema, "pipeline")
