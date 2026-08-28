"""Test de la revalidation défensive du tenant_id — exigence explicite
de l'analyse : un tenant désactivé APRÈS l'émission du jeton doit être
rejeté immédiatement, pas seulement au prochain login.

⚠️ NON VÉRIFIÉ dans l'environnement de génération (pas de PostgreSQL
disponible) — à exécuter sur ta machine réelle.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import asyncpg
import pytest
from brique_02_auth_rbac.session import AuthenticatedUser
from brique_07_dashboard.auth_cookie import SessionInvalide
from brique_07_dashboard.tenant_garde import tenant_valide


@pytest.mark.asyncio
async def test_tenant_actif_est_accepte(
    pool: asyncpg.Pool, tenant_provisionne: tuple[UUID, str]
) -> None:
    tenant_id, schema_name = tenant_provisionne
    utilisateur = AuthenticatedUser(
        user_id=uuid4(), tenant_id=tenant_id, role="analyst", souverain_id=uuid4()
    )

    metadonnees = await tenant_valide(utilisateur)

    assert metadonnees.tenant_id == tenant_id
    assert metadonnees.schema_name == schema_name


@pytest.mark.asyncio
async def test_tenant_desactive_apres_emission_du_jwt_est_rejete(
    pool: asyncpg.Pool, tenant_provisionne: tuple[UUID, str]
) -> None:
    """Le scénario exact exigé à l'analyse : le JWT reste valide (signature
    intacte), mais le tenant qu'il désigne a été désactivé depuis — doit
    être rejeté malgré la signature valide."""
    tenant_id, _ = tenant_provisionne
    utilisateur = AuthenticatedUser(
        user_id=uuid4(), tenant_id=tenant_id, role="analyst", souverain_id=uuid4()
    )

    # Le tenant est désactivé APRÈS la construction du "jeton" (ici
    # simulé directement via AuthenticatedUser, la désactivation
    # survenant entre l'émission et cette requête).
    async with pool.acquire() as connexion:
        await connexion.execute(
            "UPDATE shared.tenants_registry SET is_active = false WHERE tenant_id = $1",
            tenant_id,
        )

    with pytest.raises(SessionInvalide):
        await tenant_valide(utilisateur)


@pytest.mark.asyncio
async def test_tenant_inexistant_est_rejete(pool: asyncpg.Pool) -> None:
    utilisateur = AuthenticatedUser(
        user_id=uuid4(), tenant_id=uuid4(), role="analyst", souverain_id=uuid4()
    )

    with pytest.raises(SessionInvalide):
        await tenant_valide(utilisateur)
