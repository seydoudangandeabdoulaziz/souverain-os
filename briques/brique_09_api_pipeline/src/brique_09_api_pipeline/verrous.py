"""Verrous consultatifs PostgreSQL par tenant (sans Redis, cf. étape 9)."""

from __future__ import annotations

from uuid import UUID

# Deux « classes » de verrou, combinées à un entier dérivé du tenant.
CLASSE_INGESTION = 0x50495045  # 'PIPE' : verrou partagé pris par chaque lot
CLASSE_CYCLE = 0x50495046  # 'PIPF' : un seul cycle à la fois par tenant


def cle_tenant(tenant_id: UUID) -> int:
    """Entier signé 32 bits stable dérivé du tenant (pour pg_advisory_*)."""
    return int.from_bytes(tenant_id.bytes[:4], "big", signed=True)
