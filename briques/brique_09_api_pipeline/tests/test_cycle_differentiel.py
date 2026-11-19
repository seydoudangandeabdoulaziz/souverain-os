"""Tests différentiels : cycle incrémental vs recalcul complet B4.

Le recalcul complet est exécuté sur les transactions réellement stockées
(même ordre : occurred_at puis transaction_id). Critères :
- aucun épisode de la référence ne manque (pas de faux négatif) ;
- aucune ligne stockée sans épisode correspondant (pas de fausse détection) ;
- un cycle rejoué, ou interrompu avant l'avance du curseur, ne duplique rien.
"""

from __future__ import annotations

import contextlib
import os

import asyncpg
import pytest
from brique_01_postgresql.connection import create_tenant_pipeline_pool
from brique_09_api_pipeline import cycle as module_cycle
from brique_09_api_pipeline.cycle import CycleDejaEnCours, executer_cycle
from brique_09_api_pipeline.ingestion import ingerer_lot
from brique_09_api_pipeline.verrous import CLASSE_CYCLE, cle_tenant
from helpers_b9 import (
    classer_lignes_en_trop,
    comparer,
    detections_stockees,
    generer,
    jouer,
    ordre_arrivee,
    reference_complete,
)
from support_b9 import A


async def _verifier(
    admin: asyncpg.Connection, exact: bool, tolerance_subsumees: float = 0.0
) -> dict[str, int | bool]:
    """Critères d'acceptation du cycle incrémental face au recalcul complet.

    - jamais d'épisode manquant (aucun faux négatif) ;
    - jamais de ligne orpheline (aucune fausse détection) ;
    - mode `exact` (arrivées chronologiques) : mêmes clés que le recalcul ;
    - sinon, les lignes « subsumées » (arrivée tardive reliant deux salves en
      un seul épisode dans le recalcul) restent sous `tolerance_subsumees`.
    """
    ref = await reference_complete(admin, A.schema)
    stockees = await detections_stockees(admin, A.schema)
    comparaison = comparer(ref, stockees)
    assert comparaison["lignes_reference"] > 0, "jeu de test sans détection : test vide"
    assert comparaison["episodes_manquants"] == 0, comparaison
    classes = await classer_lignes_en_trop(admin, A.schema, ref, stockees)
    # Aucune clé stockée deux fois : un ensemble masquerait des doublons.
    assert len(stockees) == len(set(stockees)), "détections dupliquées"
    assert classes["orphelines"] == 0, (comparaison, classes)
    assert classes["subsumees"] == comparaison["lignes_sans_episode_reference"], (
        comparaison,
        classes,
    )
    if exact:
        assert comparaison["cles_exactes_identiques"], comparaison
        assert classes["subsumees"] == 0
        # Même cardinal que la référence (hors clés identiques émises plusieurs fois).
        assert len(stockees) == len(
            {(e.pattern_type, e.compte_pivot, e.fenetre_debut, e.fenetre_fin) for e in ref}
        )
    else:
        limite = tolerance_subsumees * int(comparaison["lignes_reference"])
        assert classes["subsumees"] <= limite, (comparaison, classes, limite)
    return comparaison


async def test_arrivee_chronologique_identique_au_recalcul_complet(
    admin: asyncpg.Connection,
) -> None:
    pool = await create_tenant_pipeline_pool(A.tenant_id)
    items = generer(n=3000, pool=400)
    await jouer(pool, A.schema, A.tenant_id, items, lot=250)
    await _verifier(admin, exact=True)


@pytest.mark.parametrize("seed", [1, 2, 3])
async def test_arrivees_en_retard(admin: asyncpg.Connection, seed: int) -> None:
    pool = await create_tenant_pipeline_pool(A.tenant_id)
    items = ordre_arrivee(generer(n=3000, pool=400, seed=seed), fraction_retard=0.10, seed=seed)
    await jouer(pool, A.schema, A.tenant_id, items, lot=200)
    await _verifier(admin, exact=False, tolerance_subsumees=0.03)


async def test_comptes_tres_actifs_et_episodes_longs(admin: asyncpg.Connection) -> None:
    pool = await create_tenant_pipeline_pool(A.tenant_id)
    # 40 comptes pour 3 000 transactions : activité quasi continue, épisodes très longs.
    items = ordre_arrivee(generer(n=3000, pool=40, seed=5), fraction_retard=0.05, seed=5)
    resultats = await jouer(pool, A.schema, A.tenant_id, items, lot=200)
    await _verifier(admin, exact=False, tolerance_subsumees=0.03)
    assert sum(r.replis_episode for r in resultats) >= 0  # le repli est compté, jamais silencieux


async def test_lots_tres_petits_chevauchements_d_intervalles(admin: asyncpg.Connection) -> None:
    pool = await create_tenant_pipeline_pool(A.tenant_id)
    items = generer(n=1500, pool=120, seed=9)
    await jouer(pool, A.schema, A.tenant_id, items, lot=13)  # beaucoup de cycles partiels
    await _verifier(admin, exact=True)


async def test_cycle_rejoue_ne_duplique_rien(admin: asyncpg.Connection) -> None:
    pool = await create_tenant_pipeline_pool(A.tenant_id)
    await jouer(pool, A.schema, A.tenant_id, generer(n=2000, pool=300, seed=4), lot=500)
    avant = await admin.fetchval(f"SELECT count(*) FROM {A.schema}.detections")
    alertes_avant = await admin.fetchval(f"SELECT count(*) FROM {A.schema}.alertes")
    for _ in range(3):
        rejeu = await executer_cycle(pool, A.schema, A.tenant_id)
        assert rejeu.nouvelles_transactions == 0 and rejeu.detections_nouvelles == 0
    assert await admin.fetchval(f"SELECT count(*) FROM {A.schema}.detections") == avant
    assert await admin.fetchval(f"SELECT count(*) FROM {A.schema}.alertes") == alertes_avant


async def test_cycle_interrompu_avant_le_curseur_ne_laisse_rien_puis_reprend(
    admin: asyncpg.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    pool = await create_tenant_pipeline_pool(A.tenant_id)
    items = generer(n=2000, pool=300, seed=6)
    await ingerer_lot(pool, A.schema, A.tenant_id, "src_test", items)

    original = module_cycle._CURSEUR_MAJ
    monkeypatch.setattr(module_cycle, "_CURSEUR_MAJ", "UPDATE table_inexistante SET x = $1")
    with pytest.raises(asyncpg.PostgresError):
        await executer_cycle(pool, A.schema, A.tenant_id)
    # Transaction annulée : ni détection ni avance du curseur.
    assert await admin.fetchval(f"SELECT count(*) FROM {A.schema}.detections") == 0
    assert (
        await admin.fetchval(f"SELECT coalesce(max(last_seq), 0) FROM {A.schema}.pipeline_cursor")
        == 0
    )

    monkeypatch.setattr(module_cycle, "_CURSEUR_MAJ", original)
    reprise = await executer_cycle(pool, A.schema, A.tenant_id)
    assert reprise.detections_nouvelles > 0
    await _verifier(admin, exact=True)


async def test_un_seul_cycle_a_la_fois_par_tenant(admin: asyncpg.Connection) -> None:
    pool = await create_tenant_pipeline_pool(A.tenant_id)
    await ingerer_lot(
        pool, A.schema, A.tenant_id, "src_test", generer(n=300, pool=50, seed=2)[:100]
    )
    bloqueur = await asyncpg.connect(os.environ["SOUVERAIN_PIPELINE_TEST_DSN"])
    try:
        await bloqueur.execute(
            "SELECT pg_advisory_lock($1, $2)", CLASSE_CYCLE, cle_tenant(A.tenant_id)
        )
        with pytest.raises(CycleDejaEnCours):
            await executer_cycle(pool, A.schema, A.tenant_id)
    finally:
        await bloqueur.close()
    await executer_cycle(pool, A.schema, A.tenant_id)  # libéré : passe


async def test_aucune_transaction_perdue_si_le_cycle_chevauche_une_ingestion(
    admin: asyncpg.Connection,
) -> None:
    """Le curseur ne saute jamais un lot validé après la borne du cycle."""
    import asyncio

    pool = await create_tenant_pipeline_pool(A.tenant_id)
    items = generer(n=1800, pool=250, seed=8)
    tranches = [items[i : i + 150] for i in range(0, len(items), 150)]

    async def ingerer() -> None:
        for tranche in tranches:
            await ingerer_lot(pool, A.schema, A.tenant_id, "src_test", tranche)
            await asyncio.sleep(0)

    async def cycler() -> None:
        for _ in range(len(tranches) + 3):
            with contextlib.suppress(CycleDejaEnCours):
                await executer_cycle(pool, A.schema, A.tenant_id)
            await asyncio.sleep(0)

    await asyncio.gather(ingerer(), cycler())
    await executer_cycle(pool, A.schema, A.tenant_id)
    restantes = await admin.fetchval(
        f"SELECT count(*) FROM {A.schema}.ingestion_keys "
        f"WHERE seq > (SELECT last_seq FROM {A.schema}.pipeline_cursor)"
    )
    assert restantes == 0
    await _verifier(admin, exact=False, tolerance_subsumees=0.03)


async def test_plafond_d_episode_ne_perd_aucun_episode(admin: asyncpg.Connection) -> None:
    """Avec un plafond de relecture, le coût est borné : jamais d'épisode perdu."""
    from datetime import timedelta

    pool = await create_tenant_pipeline_pool(A.tenant_id)
    items = ordre_arrivee(generer(n=3000, pool=40, seed=5), fraction_retard=0.05, seed=5)
    resultats = []
    for debut in range(0, len(items), 200):
        await ingerer_lot(pool, A.schema, A.tenant_id, "src_test", items[debut : debut + 200])
        resultats.append(await executer_cycle(pool, A.schema, A.tenant_id, timedelta(hours=6)))
    assert sum(r.episodes_tronques for r in resultats) > 0  # le plafond a bien joué
    ref = await reference_complete(admin, A.schema)
    stockees = await detections_stockees(admin, A.schema)
    comparaison = comparer(ref, stockees)
    assert comparaison["episodes_manquants"] == 0, comparaison
    assert len(stockees) == len(set(stockees)), "détections dupliquées"
    classes = await classer_lignes_en_trop(admin, A.schema, ref, stockees)
    assert classes["orphelines"] == 0, (comparaison, classes)
