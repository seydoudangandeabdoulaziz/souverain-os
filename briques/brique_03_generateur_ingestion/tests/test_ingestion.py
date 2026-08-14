"""Tests d'intégration — insertion réelle en base (pas de mock).

Prérequis avant exécution (comme pour les Briques 1 et 2) :
- Container PostgreSQL démarré : docker compose --profile postgres up -d
- Migrations Brique 1, 2 et 3 appliquées, dans cet ordre
- .env configuré avec DATABASE_URL pointant vers la vraie instance de test
"""

from __future__ import annotations

import random
from datetime import datetime

import asyncpg
import pytest

from souverain_generateur.generateur_legitime import FUSEAU_NIGER, generer_lot_legitime
from souverain_generateur.ingestion import _valider_nom_schema, inserer_transactions
from souverain_generateur.patterns_suspects import generer_structure_etoile
from tests.conftest import TENANT_TEST


@pytest.mark.asyncio
async def test_inserer_transactions_legitimes(pool: asyncpg.Pool) -> None:
    lot = generer_lot_legitime(nb_transactions=20, seed=42)

    nb_insere = await inserer_transactions(pool, TENANT_TEST, lot)

    assert nb_insere == 20

    async with pool.acquire() as connexion:
        (compte,) = await connexion.fetchrow(
            f"SELECT count(*) FROM {TENANT_TEST}.transactions WHERE is_synthetic = true"
        )
    assert compte >= 20


@pytest.mark.asyncio
async def test_inserer_transactions_pattern_suspect_marque_is_synthetic(
    pool: asyncpg.Pool,
) -> None:
    rng = random.Random(1)
    lot = generer_structure_etoile(rng, datetime(2026, 3, 1, 10, 0, 0, tzinfo=FUSEAU_NIGER))

    await inserer_transactions(pool, TENANT_TEST, lot)

    async with pool.acquire() as connexion:
        lignes = await connexion.fetch(
            f"SELECT is_synthetic FROM {TENANT_TEST}.transactions "
            f"ORDER BY occurred_at DESC LIMIT $1",
            len(lot),
        )
    assert all(row["is_synthetic"] is True for row in lignes)


def test_valider_nom_schema_rejette_injection() -> None:
    with pytest.raises(ValueError):
        _valider_nom_schema("tenant_001; DROP TABLE transactions;--")


def test_valider_nom_schema_accepte_nom_valide() -> None:
    _valider_nom_schema("tenant_001")  # ne doit pas lever d'exception
