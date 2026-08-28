"""Revalidation défensive du tenant_id extrait du JWT.

Un JWT signé prouve qu'il n'a pas été modifié depuis son émission —
pas que le tenant qu'il désigne est toujours actif MAINTENANT. Un
tenant désactivé après l'émission du jeton (is_active = false) doit
être rejeté immédiatement, pas seulement au prochain login. Même
discipline défensive que validate_schema_name() (Brique 1) : ne jamais
faire confiance à une valeur entrante sans la revérifier contre la
source de vérité, même si sa provenance est signée.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import asyncpg
from brique_01_postgresql.connection import create_pool
from brique_02_auth_rbac.session import AuthenticatedUser
from fastapi import Depends

from brique_07_dashboard.auth_cookie import SessionInvalide, get_current_user_from_cookie

_REQUETE_TENANT = """
    SELECT schema_name, country_code, data_classification
    FROM shared.tenants_registry
    WHERE tenant_id = $1 AND is_active = true
"""


@dataclass(frozen=True)
class MetadonneesTenant:
    tenant_id: UUID
    schema_name: str
    country_code: str
    data_classification: str


async def tenant_valide(
    utilisateur: AuthenticatedUser = Depends(get_current_user_from_cookie),  # noqa: B008
) -> MetadonneesTenant:
    """Revérifie le tenant_id du JWT contre shared.tenants_registry.

    Raises:
        SessionInvalide: le tenant n'existe plus ou a été désactivé
            depuis l'émission du jeton — même exception que pour un
            utilisateur invalide, pour ne pas donner d'indice
            distinctif à un attaquant sur la cause exacte du rejet.
    """
    pool: asyncpg.Pool = await create_pool()
    async with pool.acquire() as connection:
        ligne = await connection.fetchrow(_REQUETE_TENANT, utilisateur.tenant_id)

    if ligne is None:
        raise SessionInvalide(
            f"Tenant {utilisateur.tenant_id} introuvable ou désactivé."
        )

    return MetadonneesTenant(
        tenant_id=utilisateur.tenant_id,
        schema_name=ligne["schema_name"],
        country_code=ligne["country_code"],
        data_classification=ligne["data_classification"],
    )
