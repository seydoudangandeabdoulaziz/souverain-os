"""Données synthétiques et comparaison cycle incrémental / recalcul complet."""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import asyncpg
from brique_04_detection.modeles import DetectionEvent, TransactionObservee
from brique_04_detection.moteur import detecter_sequentiellement
from brique_09_api_pipeline.cycle import ResultatCycle, executer_cycle
from brique_09_api_pipeline.ingestion import ingerer_lot
from brique_09_api_pipeline.schemas import TransactionIn
from souverain_generateur import patterns_suspects as ps

FUSEAU = timezone(timedelta(hours=1))
DEBUT = datetime(2026, 3, 1, tzinfo=FUSEAU)


def generer(
    n: int,
    pool: int,
    jours: int = 3,
    seed: int = 42,
    patterns: bool = True,
    comptes_chauds: int = 0,
    part_chaude: float = 0.0,
) -> list[TransactionIn]:
    """n transactions légitimes sur `pool` comptes + patterns suspects B3 injectés."""
    rng = random.Random(seed)
    par_jour = n // jours
    brut: list[tuple[str, str, float, datetime]] = []
    for j in range(jours):
        base = DEBUT + timedelta(days=j)
        for _ in range(par_jour):
            if comptes_chauds and rng.random() < part_chaude:
                # Agents/marchands très actifs : transactions entre comptes « chauds ».
                s, r = rng.randint(1, comptes_chauds), rng.randint(1, comptes_chauds)
                if s == r:
                    r = (r % comptes_chauds) + 1
                nom_s, nom_r = f"agent_{s}", f"agent_{r}"
            else:
                s, r = rng.randint(1, pool), rng.randint(1, pool)
                if s == r:
                    r = (r % pool) + 1
                nom_s, nom_r = f"cpt_{s}", f"cpt_{r}"
            brut.append(
                (
                    nom_s,
                    nom_r,
                    round(math.exp(rng.gauss(9.5, 1.2)), 2),
                    base + timedelta(seconds=rng.randint(0, 86399)),
                )
            )
        if patterns:
            for fonction in (
                ps.generer_structure_etoile,
                ps.generer_compte_pivot,
                ps.generer_micro_fractionnement,
                ps.generer_transactions_nocturnes,
                ps.generer_flux_frontalier,
            ):
                for _ in range(max(1, par_jour // 400)):
                    t0 = base + timedelta(seconds=rng.randint(0, 80_000))
                    for t in fonction(rng, t0):
                        if t.sender_account != t.receiver_account:
                            brut.append(
                                (t.sender_account, t.receiver_account, t.amount, t.occurred_at)
                            )
    brut.sort(key=lambda x: x[3])
    return [
        TransactionIn(
            external_id=f"e{i:07d}",
            sender_account=s,
            receiver_account=r,
            amount=Decimal(f"{max(m, 1.0):.2f}"),
            currency="XOF",
            channel="orange_money",
            occurred_at=q,
        )
        for i, (s, r, m, q) in enumerate(brut)
    ]


def ordre_arrivee(
    items: list[TransactionIn], fraction_retard: float, seed: int = 7
) -> list[TransactionIn]:
    """Arrivée chronologique, avec une fraction de transactions livrées en retard."""
    rng = random.Random(seed)
    retards: list[tuple[datetime, int]] = []
    for i, item in enumerate(items):
        delai = timedelta(0)
        if rng.random() < fraction_retard:
            delai = timedelta(minutes=rng.randint(5, 120))
            if rng.random() < 0.1:
                delai = timedelta(hours=rng.randint(3, 48))
        retards.append((item.occurred_at + delai, i))
    return [items[i] for _, i in sorted(retards)]


async def jouer(
    pool: asyncpg.Pool, schema: str, tenant_id: UUID, items: list[TransactionIn], lot: int = 200
) -> list[ResultatCycle]:
    """Ingère par lots puis lance un cycle après chaque lot."""
    resultats = []
    for debut in range(0, len(items), lot):
        await ingerer_lot(pool, schema, tenant_id, "src_test", items[debut : debut + lot])
        resultats.append(await executer_cycle(pool, schema, tenant_id))
    return resultats


async def reference_complete(admin: asyncpg.Connection, schema: str) -> list[DetectionEvent]:
    """Recalcul complet B4 sur tout l'historique stocké (même ordre que le cycle)."""
    lignes = await admin.fetch(
        f"SELECT transaction_id, sender_account, receiver_account, amount, channel, occurred_at "
        f"FROM {schema}.transactions"
    )
    txs = [
        TransactionObservee(
            transaction_id=r["transaction_id"],
            sender_account=r["sender_account"],
            receiver_account=r["receiver_account"],
            amount=float(r["amount"]),
            channel=r["channel"],
            occurred_at=r["occurred_at"],
        )
        for r in lignes
    ]
    txs.sort(key=lambda t: (t.occurred_at, str(t.transaction_id)))
    return detecter_sequentiellement(txs)


Intervalle = tuple[datetime, datetime]


def _par_paire(
    rows: list[tuple[str, str, datetime, datetime]],
) -> dict[tuple[str, str], list[Intervalle]]:
    sortie: dict[tuple[str, str], list[Intervalle]] = {}
    for pattern, compte, debut, fin in rows:
        sortie.setdefault((pattern, compte), []).append((debut, fin))
    return sortie


def _chevauche(a: Intervalle, liste: list[Intervalle]) -> bool:
    return any(d <= a[1] and a[0] <= f for d, f in liste)


async def detections_stockees(
    admin: asyncpg.Connection, schema: str
) -> list[tuple[str, str, datetime, datetime]]:
    lignes = await admin.fetch(
        f"SELECT pattern_type, compte_pivot, fenetre_debut, fenetre_fin FROM {schema}.detections"
    )
    return [
        (r["pattern_type"], r["compte_pivot"], r["fenetre_debut"], r["fenetre_fin"]) for r in lignes
    ]


def comparer(
    reference: list[DetectionEvent], stockees: list[tuple[str, str, datetime, datetime]]
) -> dict[str, int | bool]:
    """Compare les épisodes (chevauchement) et les clés exactes."""
    ref_rows = [
        (e.pattern_type, e.compte_pivot or "", e.fenetre_debut, e.fenetre_fin) for e in reference
    ]
    ref, sto = _par_paire(ref_rows), _par_paire(stockees)
    manquants = sum(1 for k, v in ref.items() for a in v if not _chevauche(a, sto.get(k, [])))
    en_trop = sum(1 for k, v in sto.items() for a in v if not _chevauche(a, ref.get(k, [])))
    cles_ref, cles_sto = set(ref_rows), set(stockees)
    return {
        "episodes_manquants": manquants,
        "lignes_sans_episode_reference": en_trop,
        "cles_exactes_identiques": cles_ref == cles_sto,
        "lignes_reference": len(ref_rows),
        "lignes_stockees": len(stockees),
    }


async def classer_lignes_en_trop(
    admin: asyncpg.Connection,
    schema: str,
    reference: list[DetectionEvent],
    stockees: list[tuple[str, str, datetime, datetime]],
    ecart: timedelta = timedelta(hours=6),
) -> dict[str, int]:
    """Classe les lignes stockées sans chevauchement avec la référence.

    Une ligne est « subsumée » si, dans la MÊME activité continue du compte
    (suite de transactions séparées par au plus `ecart`), la référence contient
    une détection du même type : c'est le cas d'une arrivée tardive qui relie
    deux salves en un seul épisode. Une ligne « orpheline » serait une fausse
    détection (aucune détection de ce type dans cette activité) : interdite.
    """
    lignes = await admin.fetch(
        f"SELECT sender_account, receiver_account, occurred_at FROM {schema}.transactions"
    )
    activite: dict[str, list[datetime]] = {}
    for r in lignes:
        for compte in (r["sender_account"], r["receiver_account"]):
            activite.setdefault(compte, []).append(r["occurred_at"])
    episodes: dict[str, list[tuple[datetime, datetime]]] = {}
    for compte, temps in activite.items():
        temps.sort()
        debut = precedent = temps[0]
        liste = []
        for t in temps[1:]:
            if t - precedent > ecart:
                liste.append((debut, precedent))
                debut = t
            precedent = t
        liste.append((debut, precedent))
        episodes[compte] = liste

    def episode(compte: str, quand: datetime) -> int:
        for i, (d, f) in enumerate(episodes.get(compte, [])):
            if d <= quand <= f:
                return i
        return -1

    ref = _par_paire(
        [(e.pattern_type, e.compte_pivot or "", e.fenetre_debut, e.fenetre_fin) for e in reference]
    )
    sto = _par_paire(stockees)
    subsumees = orphelines = 0
    for (pattern, compte), intervalles in sto.items():
        for intervalle in intervalles:
            if _chevauche(intervalle, ref.get((pattern, compte), [])):
                continue
            mon_episode = episode(compte, intervalle[0])
            if any(
                episode(compte, d) == mon_episode != -1 for d, _ in ref.get((pattern, compte), [])
            ):
                subsumees += 1
            else:
                orphelines += 1
    return {"subsumees": subsumees, "orphelines": orphelines}
