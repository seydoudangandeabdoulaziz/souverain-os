"""Tests d'intégration — insertion réelle en base (pas de mock).

CORRECTIF : utilise désormais un tenant de test éphémère
(fixture tenant_provisionne), provisionné et enregistré dans
shared.tenants_registry avant chaque test, nettoyé après — au lieu de
supposer un "tenant_001" préexistant qui n'a jamais existé dans le
schéma réel.

Prérequis avant exécution :
- Container PostgreSQL démarré : docker compose --profile postgres up -d
- Migration Brique 1 appliquée (shared.tenants_registry existe)
- Migration Brique 3 (0001_add_is_synthetic.sql) appliquée
  -> Note : la fixture tenant_provisionne crée le schéma APRÈS la
     migration 0001 si celle-ci a déjà tourné, is_synthetic peut donc
     manquer sur un tenant provisionné après coup. Si les tests
     échouent avec "column is_synthetic does not exist", rejouer
     0001_add_is_synthetic.sql après avoir lancé les tests une première
     fois (elle boucle sur tous les tenants existants au moment où
     elle s'exécute).
"""

import random
from datetime import datetime

import asyncpg
import pytest
from souverain_generateur.generateur_legitime import FUSEAU_NIGER, generer_lot_legitime
from souverain_generateur.ingestion import (
    inserer_transactions,
    recuperer_metadonnees_tenant,
    validate_schema_name,
)
from souverain_generateur.patterns_suspects import generer_structure_etoile


@pytest.mark.asyncio
async def test_recuperer_metadonnees_tenant_leve_si_inexistant(pool: asyncpg.Pool) -> None:
    with pytest.raises(ValueError, match="Aucun tenant actif"):
        await recuperer_metadonnees_tenant(pool, "tenant_inexistant_xyz")


@pytest.mark.asyncio
async def test_recuperer_metadonnees_tenant(
    pool: asyncpg.Pool, tenant_provisionne: str
) -> None:
    metadonnees = await recuperer_metadonnees_tenant(pool, tenant_provisionne)
    assert metadonnees.country_code == "NE"
    assert metadonnees.data_classification == "confidential"


@pytest.mark.asyncio
async def test_inserer_transactions_legitimes(
    pool: asyncpg.Pool, tenant_provisionne: str
) -> None:
    lot = generer_lot_legitime(nb_transactions=20, seed=42)

    nb_insere = await inserer_transactions(pool, tenant_provisionne, lot)

    assert nb_insere == 20

    async with pool.acquire() as connexion:
        compte = await connexion.fetchval(
            f"SELECT count(*) FROM {tenant_provisionne}.transactions WHERE is_synthetic = true"
        )
    assert compte == 20


@pytest.mark.asyncio
async def test_inserer_transactions_pattern_suspect_marque_is_synthetic(
    pool: asyncpg.Pool, tenant_provisionne: str
) -> None:
    rng = random.Random(1)
    lot = generer_structure_etoile(rng, datetime(2026, 3, 1, 10, 0, 0, tzinfo=FUSEAU_NIGER))

    await inserer_transactions(pool, tenant_provisionne, lot)

    async with pool.acquire() as connexion:
        lignes = await connexion.fetch(
            f"SELECT is_synthetic FROM {tenant_provisionne}.transactions "
            f"ORDER BY occurred_at DESC LIMIT $1",
            len(lot),
        )
    assert all(row["is_synthetic"] is True for row in lignes)


def test_valider_nom_schema_rejette_injection() -> None:
    from brique_01_postgresql.tenant_provisioning import InvalidSchemaNameError

    with pytest.raises(InvalidSchemaNameError):
        validate_schema_name("tenant_ne; DROP TABLE transactions;--")


def test_valider_nom_schema_accepte_nom_valide() -> None:
    assert validate_schema_name("tenant_ne") == "tenant_ne"
