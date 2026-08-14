"""Fixtures partagées pour les tests de la Brique 3.

Suit le même principe que les Briques 1 et 2 : tests d'intégration contre
une vraie instance PostgreSQL/TimescaleDB, jamais de mock (cf. avancement.md).

HYPOTHÈSE À VÉRIFIER : si un conftest.py racine du workspace fournit déjà
une fixture `pool` réutilisable (probable, vu que les Briques 1 et 2 testent
aussi contre une vraie base), remplace ce fichier par un import de cette
fixture partagée plutôt que d'en recréer une ici.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import asyncpg
import pytest_asyncio

from souverain_generateur.config import ParametresGenerateur

TENANT_TEST = "tenant_001"


@pytest_asyncio.fixture
async def pool() -> AsyncIterator[asyncpg.Pool]:
    parametres = ParametresGenerateur()
    pool_connexions = await asyncpg.create_pool(
        dsn=parametres.database_url, min_size=1, max_size=3
    )
    try:
        yield pool_connexions
    finally:
        await pool_connexions.close()
