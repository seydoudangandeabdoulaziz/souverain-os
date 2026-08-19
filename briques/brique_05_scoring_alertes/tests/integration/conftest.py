"""Fixtures d'intégration de la Brique 5.

Se connecte à la vraie infrastructure Docker Compose (profile postgres)
plutôt qu'à un squelette : réutilise brique_01_postgresql.connection
pour le pool, et provisionne un schéma de tenant éphémère dédié aux
tests (jamais tenant_ne, pour ne pas polluer les données réelles
utilisées manuellement lors de la validation du 16/08/2026).

Corrections du 17/08/2026 :
- Le schéma tenant (transactions, etc.) n'est pas créé en exécutant
  0001_init_shared_schema.sql brut (ce fichier n'initialise que le
  schéma PARTAGÉ) mais via la vraie fonction de provisioning de la
  Brique 1 : provision_tenant_schema(connection, schema_name),
  signature confirmée dans
  briques/brique_01_postgresql/src/brique_01_postgresql/tenant_provisioning.py.
- Les migrations Briques 3/4/5, elles, restent appliquées par lecture
  directe des fichiers .sql (ce sont de vrais ALTER/CREATE incrémentaux,
  pas un provisioning applicatif).
- Le pool est scope="session" : create_pool() de la Brique 1 est un
  singleton global, le fermer après chaque test (scope="function")
  laissait le singleton fermé pour le test suivant.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import asyncpg
import pytest_asyncio


def _racine_workspace() -> Path:
    """Remonte les dossiers parents jusqu'à la racine du workspace uv.

    Repérée par la présence d'un pyproject.toml ET d'un dossier
    briques/ au même niveau — évite de dépendre du répertoire depuis
    lequel pytest a été lancé.
    """
    courant = Path(__file__).resolve()
    for parent in courant.parents:
        if (parent / "pyproject.toml").is_file() and (parent / "briques").is_dir():
            return parent
    raise RuntimeError(
        "Racine du workspace introuvable en remontant depuis "
        f"{courant} — structure de dépôt inattendue."
    )


# Migrations incrémentales des Briques 3/4/5, appliquées après le
# provisioning de base du schéma tenant (Brique 1). ATTENTION : le nom
# exact de la migration Brique 3 (is_synthetic) n'a pas été reconfirmé
# dans cette session, contrairement aux colonnes de detections.
MIGRATIONS_RELATIVES = [
    "briques/brique_03_generateur_ingestion/migrations/0001_add_is_synthetic.sql",
    "briques/brique_04_detection/migrations/0001_create_detections_table.sql",
    "briques/brique_05_scoring_alertes/migrations/0001_create_alertes_table.sql",
]


@pytest_asyncio.fixture(scope="session")
async def pool() -> AsyncIterator[asyncpg.Pool]:
    """Pool partagé pour toute la session de test.

    Correction du 17/08/2026 : create_pool() de la Brique 1 retourne un
    singleton global. Une fixture scope="function" qui ferme le pool
    après chaque test laissait le singleton fermé pour le test suivant
    (InterfaceError: pool is closed). Scope="session" : un seul pool
    ouvert/fermé pour toute l'exécution de pytest.
    """
    from brique_01_postgresql.connection import create_pool

    p = await create_pool()
    try:
        yield p
    finally:
        await p.close()


def _lire_migrations() -> list[str]:
    """Lecture synchrone, hors coroutine (ruff ASYNC230)."""
    racine = _racine_workspace()
    contenus = []
    for chemin_relatif in MIGRATIONS_RELATIVES:
        chemin = racine / chemin_relatif
        with open(chemin, encoding="utf-8") as fichier:
            contenus.append(fichier.read())
    return contenus


@pytest_asyncio.fixture
async def schema_tenant_ephemere(pool: asyncpg.Pool) -> AsyncIterator[str]:
    """Provisionne un schéma de tenant éphémère, nettoyé en fin de test.

    Nom unique par exécution (uuid4 tronqué) pour permettre des tests
    parallèles sans collision.
    """
    from brique_01_postgresql.tenant_provisioning import provision_tenant_schema

    schema = f"test_scoring_{uuid.uuid4().hex[:8]}"
    sqls = _lire_migrations()

    async with pool.acquire() as connexion:
        await provision_tenant_schema(connexion, schema)
        await connexion.execute(f"SET search_path TO {schema}")
        for sql in sqls:
            await connexion.execute(sql)

    try:
        yield schema
    finally:
        async with pool.acquire() as connexion:
            await connexion.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")

