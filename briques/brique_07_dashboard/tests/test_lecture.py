"""Tests de lecture.py — contre la vraie alerte produite par le pipeline
Brique 4 -> Brique 5 (fixture alerte_test, conftest.py).

Distingue explicitement deux cas trouvés confondus lors de la
validation locale (voir avancement.md) :
- {tenant}.alertes n'existe pas du tout -> TenantSansDonnees.
- {tenant}.alertes existe mais l'alerte_id demandé est absent -> None.

⚠️ NON VÉRIFIÉ dans l'environnement de génération (pas de PostgreSQL
disponible) — à exécuter sur ta machine réelle.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import asyncpg
import pytest
from brique_07_dashboard import lecture

# Dupliqué depuis conftest.py plutôt qu'importé : conftest.py n'est pas
# un module du package brique_07_dashboard, seulement un fichier de
# fixtures pytest — même précaution que la collision documentée en
# Brique 4 (jamais d'import direct depuis un fichier de test).
COMPTE_ALERTE_TEST = "compte_test_dashboard_01"


@pytest.mark.asyncio
async def test_lister_alertes_leve_tenant_sans_donnees_si_table_absente(
    pool: asyncpg.Pool, tenant_provisionne: tuple[UUID, str]
) -> None:
    """Aucune fixture de données ici — {tenant}.alertes n'existe pas du
    tout (Brique 5 jamais exécutée pour ce tenant). C'est le scénario
    exact qui a fait échouer 3 tests avant cette correction."""
    _, schema_name = tenant_provisionne

    with pytest.raises(lecture.TenantSansDonnees):
        await lecture.lister_alertes_ouvertes(pool, schema_name)


@pytest.mark.asyncio
async def test_lister_alertes_ouvertes_contient_lalerte_de_test(
    pool: asyncpg.Pool, tenant_provisionne: tuple[UUID, str], alerte_test: None
) -> None:
    _, schema_name = tenant_provisionne

    alertes = await lecture.lister_alertes_ouvertes(pool, schema_name)

    assert len(alertes) == 1
    assert alertes[0].compte_pivot == COMPTE_ALERTE_TEST
    assert alertes[0].score == 50
    assert alertes[0].statut == "ouverte"


@pytest.mark.asyncio
async def test_lister_alertes_table_presente_mais_vide_retourne_liste_vide(
    pool: asyncpg.Pool,
    tenant_provisionne: tuple[UUID, str],
    alertes_table_creee_sans_alerte: None,
) -> None:
    """Distinct du cas table absente : ici la table existe (un score
    sous le seuil l'a créée), mais aucune alerte ne la peuple."""
    _, schema_name = tenant_provisionne

    alertes = await lecture.lister_alertes_ouvertes(pool, schema_name)

    assert alertes == []


@pytest.mark.asyncio
async def test_lire_alerte_retourne_le_detail_complet(
    pool: asyncpg.Pool, tenant_provisionne: tuple[UUID, str], alerte_test: None
) -> None:
    _, schema_name = tenant_provisionne
    alertes = await lecture.lister_alertes_ouvertes(pool, schema_name)
    alerte_id = alertes[0].alerte_id

    detail = await lecture.lire_alerte(pool, schema_name, alerte_id)

    assert detail is not None
    assert detail.compte_pivot == COMPTE_ALERTE_TEST
    assert detail.details == {"compte_pivot": 30, "micro_fractionnement": 20}
    # Une ligne par DetectionEvent inséré dans la fixture (2), pas une
    # par transaction_id sous-jacent — voir la correction du bug de
    # conftest.py (detection_ids != transaction_ids).
    assert len(detail.detections_liees) == 2
    assert {d.pattern_type for d in detail.detections_liees} == {
        "compte_pivot",
        "micro_fractionnement",
    }


@pytest.mark.asyncio
async def test_lire_alerte_inexistante_dans_table_presente_retourne_none(
    pool: asyncpg.Pool,
    tenant_provisionne: tuple[UUID, str],
    alertes_table_creee_sans_alerte: None,
) -> None:
    """Table PRÉSENTE (voir fixture), alerte_id absent -> None, pas
    TenantSansDonnees. Corrige le test original qui, sans cette
    fixture, tombait par erreur dans le cas table absente."""
    _, schema_name = tenant_provisionne

    detail = await lecture.lire_alerte(pool, schema_name, uuid4())

    assert detail is None
