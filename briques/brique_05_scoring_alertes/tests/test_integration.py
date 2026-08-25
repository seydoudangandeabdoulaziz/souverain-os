"""Test d'intégration — insertion réelle en base (pas de mock).

⚠️ NON VÉRIFIÉ dans l'environnement de génération (pas de PostgreSQL
disponible) — à exécuter sur ta machine réelle, comme pour les Briques
3 et 4.

Prérequis :
- Container PostgreSQL démarré
- Migrations Briques 1, 4 et 5 appliquées
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import asyncpg
import pytest
from brique_04_detection.modeles import DetectionEvent
from brique_04_detection.persistence import enregistrer_detections
from brique_05_scoring_alertes.agregation import agreger_par_compte
from brique_05_scoring_alertes.lecture import lire_detections_fenetre
from brique_05_scoring_alertes.persistence import enregistrer_scores
from brique_05_scoring_alertes.seuils import FENETRE_JOURS


def _detection_event(pattern_type: str, compte_pivot: str) -> DetectionEvent:
    maintenant = datetime.now(UTC)
    return DetectionEvent(
        pattern_type=pattern_type,
        transaction_ids=[uuid4(), uuid4()],
        fenetre_debut=maintenant - timedelta(minutes=30),
        fenetre_fin=maintenant,
        compte_pivot=compte_pivot,
    )


async def _executer_cycle(pool: asyncpg.Pool, tenant: str) -> tuple[int, object]:
    fenetre_debut = datetime.now(UTC) - timedelta(days=FENETRE_JOURS)
    detections = await lire_detections_fenetre(pool, tenant, fenetre_debut)
    scores = agreger_par_compte(detections, fenetre_debut, datetime.now(UTC))
    resultat = await enregistrer_scores(pool, tenant, scores)
    return len(detections), resultat


@pytest.mark.asyncio
async def test_cycle_complet_franchit_le_seuil_et_cree_une_alerte(
    pool: asyncpg.Pool, tenant_provisionne: str
) -> None:
    """compte_pivot (30) + micro_fractionnement (20) = 50 >= seuil ⇒ une alerte 'ouverte'."""
    evenements = [
        _detection_event("compte_pivot", "hub_test_001"),
        _detection_event("micro_fractionnement", "hub_test_001"),
    ]
    await enregistrer_detections(pool, tenant_provisionne, evenements)

    nb_lues, resultat = await _executer_cycle(pool, tenant_provisionne)

    assert nb_lues == 2
    assert resultat.nb_alertes_creees == 1
    assert resultat.nb_alertes_mises_a_jour == 0

    async with pool.acquire() as connexion:
        lignes = await connexion.fetch(
            f"SELECT * FROM {tenant_provisionne}.alertes WHERE compte_pivot = 'hub_test_001'"
        )
    assert len(lignes) == 1
    assert lignes[0]["score"] == 50
    assert lignes[0]["statut"] == "ouverte"
    assert set(lignes[0]["pattern_types_impliques"]) == {"compte_pivot", "micro_fractionnement"}


@pytest.mark.asyncio
async def test_rejouer_le_cycle_sur_les_memes_detections_ne_duplique_rien(
    pool: asyncpg.Pool, tenant_provisionne: str
) -> None:
    """Le point le plus important : rejouer le scoring sur EXACTEMENT les mêmes
    détections (aucune nouvelle insertion) doit relire la fenêtre entière, recalculer
    le même score, et mettre à jour l'alerte existante en place — jamais en créer
    une seconde. C'est l'UPSERT qui porte cette garantie, pas une exclusion en lecture."""
    evenements = [
        _detection_event("compte_pivot", "hub_test_002"),
        _detection_event("structure_etoile", "hub_test_002"),
    ]
    await enregistrer_detections(pool, tenant_provisionne, evenements)

    nb_lues_1, resultat_1 = await _executer_cycle(pool, tenant_provisionne)
    assert nb_lues_1 == 2
    assert resultat_1.nb_alertes_creees == 1
    assert resultat_1.nb_alertes_mises_a_jour == 0

    # Deuxième cycle, sans nouvelle détection insérée entre-temps : la
    # fenêtre est intégralement relue (comportement voulu).
    nb_lues_2, resultat_2 = await _executer_cycle(pool, tenant_provisionne)
    assert nb_lues_2 == 2  # les 2 mêmes détections sont bien relues
    assert resultat_2.nb_alertes_creees == 0
    assert resultat_2.nb_alertes_mises_a_jour == 1  # mise à jour en place, pas création

    async with pool.acquire() as connexion:
        lignes = await connexion.fetch(
            f"SELECT * FROM {tenant_provisionne}.alertes WHERE compte_pivot = 'hub_test_002'"
        )
    # Toujours une seule alerte, jamais dupliquée.
    assert len(lignes) == 1
    assert lignes[0]["score"] == 55  # compte_pivot (30) + structure_etoile (25)


@pytest.mark.asyncio
async def test_detection_ancienne_toujours_dans_la_fenetre_continue_de_compter(
    pool: asyncpg.Pool, tenant_provisionne: str
) -> None:
    """Le scénario exact du bug corrigé : une détection scorée une première fois
    (sous le seuil, pas d'alerte) doit continuer à compter dans le score cumulatif
    lors d'un cycle ultérieur, une fois combinée à une nouvelle détection — la
    fenêtre glissante ne doit jamais "oublier" une détection qui reste dans les
    7 jours, même après un premier cycle de scoring."""
    await enregistrer_detections(
        pool, tenant_provisionne, [_detection_event("compte_pivot", "hub_test_003")]
    )
    nb_lues_1, resultat_1 = await _executer_cycle(pool, tenant_provisionne)
    assert nb_lues_1 == 1
    assert resultat_1.nb_alertes_creees == 0  # 30 < 50, pas encore d'alerte

    async with pool.acquire() as connexion:
        lignes_avant = await connexion.fetch(
            f"SELECT * FROM {tenant_provisionne}.alertes WHERE compte_pivot = 'hub_test_003'"
        )
    assert len(lignes_avant) == 0

    # Nouvelle détection sur le même compte : le cycle suivant doit
    # relire LES DEUX détections (l'ancienne + la nouvelle), pas
    # seulement la nouvelle.
    await enregistrer_detections(
        pool, tenant_provisionne, [_detection_event("micro_fractionnement", "hub_test_003")]
    )
    nb_lues_2, resultat_2 = await _executer_cycle(pool, tenant_provisionne)
    assert nb_lues_2 == 2  # les 2 détections cumulées, pas 1
    assert resultat_2.nb_alertes_creees == 1

    async with pool.acquire() as connexion:
        lignes = await connexion.fetch(
            f"SELECT * FROM {tenant_provisionne}.alertes WHERE compte_pivot = 'hub_test_003'"
        )
    assert len(lignes) == 1
    assert lignes[0]["score"] == 50  # 30 + 20, score cumulatif correct
