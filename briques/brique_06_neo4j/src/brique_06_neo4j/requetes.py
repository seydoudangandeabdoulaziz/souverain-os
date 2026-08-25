"""Couche de présentation — traduit les résultats bruts de Neo4j
(dicts issus de garde_isolation.py, eux-mêmes issus de Record.data())
en objets Python typés (Chemin, ComptePont).

Aucune ligne de Cypher ici : ce fichier ne fait qu'appeler
garde_isolation.py et convertir son résultat. Décision actée à
l'analyse — garde_isolation.py est le SEUL fichier autorisé à
connaître Neo4j ; ce fichier ne connaît que la représentation Python
interne (même découplage que modeles.py appliqué partout ailleurs
dans le projet, source brute vs représentation interne).
"""

from __future__ import annotations

from uuid import UUID

from neo4j import AsyncDriver

from brique_06_neo4j import garde_isolation
from brique_06_neo4j.modeles import Chemin, ComptePont


def _dict_vers_chemin(brut: dict[str, object]) -> Chemin:
    comptes = brut["comptes"]
    transaction_ids = brut["transaction_ids"]
    assert isinstance(comptes, list)
    assert isinstance(transaction_ids, list)
    return Chemin(
        comptes=list(comptes),
        transaction_ids=[UUID(str(tid)) for tid in transaction_ids],
    )


def _dict_vers_compte_pont(brut: dict[str, object]) -> ComptePont:
    return ComptePont(
        compte_pont=str(brut["compte_pont"]),
        compte_alerte_source=str(brut["compte_alerte_source"]),
        compte_alerte_cible=str(brut["compte_alerte_cible"]),
        transaction_entrante_id=UUID(str(brut["transaction_entrante_id"])),
        transaction_sortante_id=UUID(str(brut["transaction_sortante_id"])),
    )


async def chaines_redistribution(driver: AsyncDriver, tenant_id: str) -> list[Chemin]:
    """Requête métier a) — voir garde_isolation.detecter_chaines_redistribution()."""
    bruts = await garde_isolation.detecter_chaines_redistribution(driver, tenant_id)
    return [_dict_vers_chemin(b) for b in bruts]


async def comptes_pont(
    driver: AsyncDriver, tenant_id: str, comptes_alertes: list[str]
) -> list[ComptePont]:
    """Requête métier b) — voir garde_isolation.detecter_comptes_pont()."""
    bruts = await garde_isolation.detecter_comptes_pont(driver, tenant_id, comptes_alertes)
    return [_dict_vers_compte_pont(b) for b in bruts]


async def plus_courts_chemins_entre_alertes(
    driver: AsyncDriver, tenant_id: str, comptes_alertes: list[str]
) -> list[Chemin]:
    """Requête métier c) — voir garde_isolation.chemin_le_plus_court_entre_alertes()."""
    bruts = await garde_isolation.chemin_le_plus_court_entre_alertes(
        driver, tenant_id, comptes_alertes
    )
    return [_dict_vers_chemin(b) for b in bruts]
