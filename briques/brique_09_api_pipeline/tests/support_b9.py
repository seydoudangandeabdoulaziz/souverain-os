"""Constantes partagées des tests B9 (module à nom unique : pas de collision avec les
`conftest.py` des autres briques, importable avec --import-mode=importlib)."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from uuid import UUID

TENANT_A = UUID("11111111-1111-1111-1111-111111111111")
TENANT_B = UUID("22222222-2222-2222-2222-222222222222")
CONTROLE_MDP = "ctlpw_ctlpw_ctlpw_ctlpw_ctlpw_0123"
MDP_PIPELINE = {TENANT_A: secrets.token_hex(32), TENANT_B: secrets.token_hex(32)}
JWT_SECRET = secrets.token_hex(32)


@dataclass(frozen=True)
class Tenant:
    tenant_id: UUID
    code: str
    schema: str


A = Tenant(TENANT_A, "TA", "tenant_pl_a")
B = Tenant(TENANT_B, "TB", "tenant_pl_b")
