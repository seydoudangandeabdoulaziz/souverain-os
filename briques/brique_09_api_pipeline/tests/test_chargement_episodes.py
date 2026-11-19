"""Le chargement par tranches doit égaler un oracle indépendant, ligne à ligne.

Oracle : pour chaque compte touché, tout son historique est trié en Python et
l'épisode courant est calculé sur l'historique COMPLET (aucune tranche) ; la
sélection attendue est l'union des lignes depuis le début de chaque épisode.
Un trou dans une tranche, une tranche en trop ou un mauvais début d'épisode
change cet ensemble : contrairement à la comparaison des détections, ce test
est sensible à la moindre ligne manquante.
"""

from __future__ import annotations

import random
from datetime import timedelta

import asyncpg
from brique_01_postgresql.connection import create_tenant_pipeline_pool
from brique_09_api_pipeline.cycle import _charger_episodes
from brique_09_api_pipeline.episodes import debut_episode
from brique_09_api_pipeline.ingestion import ingerer_lot
from helpers_b9 import generer
from support_b9 import A


async def _charger_jeux(pool: asyncpg.Pool) -> None:
    # Comptes très actifs (épisodes de plusieurs jours : plusieurs tranches) …
    actifs = generer(n=2400, pool=60, jours=2, seed=3, patterns=False)
    # … et comptes épars (épisodes courts : une seule tranche).
    epars = generer(n=600, pool=4000, jours=2, seed=4, patterns=False)
    for source, jeu in (("actifs", actifs), ("epars", epars)):
        for i in range(0, len(jeu), 500):
            await ingerer_lot(pool, A.schema, A.tenant_id, source, jeu[i : i + 500])


async def _oracle(admin: asyncpg.Connection, touches: dict[str, object]) -> set[object]:
    lignes = await admin.fetch(
        f"SELECT transaction_id, sender_account, receiver_account, occurred_at "
        f"FROM {A.schema}.transactions"
    )
    activite: dict[str, list[tuple[object, object]]] = {}
    for r in lignes:
        for compte in {r["sender_account"], r["receiver_account"]}:
            activite.setdefault(compte, []).append((r["occurred_at"], r["transaction_id"]))
    attendu: set[object] = set()
    for compte, t_min in touches.items():
        historique = sorted(activite[compte])  # type: ignore[type-var]
        debut, _ = debut_episode(
            [h[0] for h in historique],
            t_min,  # type: ignore[arg-type]
            None,
            timedelta(
                hours=6
            ),  # valeur écrite en dur : l'oracle ne partage pas la constante testée
        )
        attendu |= {identifiant for _, identifiant in historique[debut:]}
    return attendu


async def _touches(admin: asyncpg.Connection, graine: int) -> dict[str, object]:
    rng = random.Random(graine)
    lignes = await admin.fetch(
        f"SELECT sender_account, receiver_account, occurred_at FROM {A.schema}.transactions"
    )
    par_compte: dict[str, list[object]] = {}
    for r in lignes:
        for compte in {r["sender_account"], r["receiver_account"]}:
            par_compte.setdefault(compte, []).append(r["occurred_at"])
    comptes = rng.sample(sorted(par_compte), 120)
    # t_min : un instant réel de transaction du compte, tiré au hasard dans son historique.
    return {c: rng.choice(par_compte[c]) for c in comptes}


async def test_chargement_par_tranches_egal_a_l_oracle(admin: asyncpg.Connection) -> None:
    pool = await create_tenant_pipeline_pool(A.tenant_id)
    await _charger_jeux(pool)
    for graine in (1, 2, 3):
        touches = await _touches(admin, graine)
        async with pool.acquire() as connexion:
            selection, replis, tronques = await _charger_episodes(connexion, A.schema, touches)  # type: ignore[arg-type]
        assert set(selection) == await _oracle(admin, touches), f"graine {graine}"
        assert tronques == 0
        # Les épisodes de plusieurs jours ont bien exigé les élargissements.
        assert len(selection) > 300


async def test_plafond_ne_charge_jamais_plus_que_l_exact(admin: asyncpg.Connection) -> None:
    pool = await create_tenant_pipeline_pool(A.tenant_id)
    await _charger_jeux(pool)
    touches = await _touches(admin, 9)
    async with pool.acquire() as connexion:
        exact, _, _ = await _charger_episodes(connexion, A.schema, touches)  # type: ignore[arg-type]
        plafonne, _, tronques = await _charger_episodes(
            connexion,
            A.schema,
            touches,  # type: ignore[arg-type]
            timedelta(hours=6),
        )
    assert tronques > 0
    assert set(plafonne) <= set(exact)
    assert len(plafonne) < len(exact)
