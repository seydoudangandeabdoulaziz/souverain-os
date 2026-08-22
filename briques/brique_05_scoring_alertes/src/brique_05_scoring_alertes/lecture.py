"""Lecture des détections d'un tenant, sur la fenêtre glissante.

Isole la seule requête SQL qui alimente le moteur de scoring — même
principe que lecture.py en Brique 4.

Correction actée (voir avancement.md) : cette fonction relit
TOUJOURS l'intégralité de la fenêtre glissante à chaque cycle, sans
mécanisme d'exclusion des détections déjà vues par un cycle précédent.
Une première version filtrait via une table de suivi
({tenant}.detections_traitees), mais cassait le score cumulatif sur
la fenêtre : une détection ancienne "déjà traitée" mais toujours dans
la fenêtre de 7 jours devait continuer à compter dans le score, ce que
l'exclusion empêchait silencieusement. L'anti-doublon des alertes est
entièrement porté par l'UPSERT sur l'index unique partiel côté
persistence.py (compte_pivot, WHERE statut='ouverte') — relire et
recalculer plusieurs fois la même fenêtre est donc sans risque.

Limite MVP documentée, non implémentée maintenant : à 69 détections
(volume réel actuel de tenant_ne), aucun souci de performance. Si le
volume grossit significativement (Vision), un index
(compte_pivot, detected_at) sur {tenant}.detections pourrait être
ajouté via une migration future portée par la Brique 5, sans toucher
aux fichiers de la Brique 4.

Triée par compte_pivot : facilite le regroupement dans agregation.py
sans avoir besoin de re-grouper explicitement côté Python.
"""

from __future__ import annotations

from datetime import datetime

import asyncpg
from brique_01_postgresql.tenant_provisioning import validate_schema_name

from brique_05_scoring_alertes.modeles import DetectionNonTraitee

_REQUETE_DETECTIONS_FENETRE = """
    SELECT d.detection_id, d.compte_pivot, d.pattern_type, d.detected_at
    FROM {schema}.detections d
    WHERE d.detected_at >= $1
      AND d.compte_pivot IS NOT NULL
    ORDER BY d.compte_pivot ASC
"""


async def lire_detections_fenetre(
    pool: asyncpg.Pool,
    nom_schema_tenant: str,
    fenetre_debut: datetime,
) -> list[DetectionNonTraitee]:
    """Lit toutes les détections d'un tenant sur la fenêtre glissante.

    d.compte_pivot IS NOT NULL par prudence défensive : les 5 règles
    actuelles de la Brique 4 renseignent toutes ce champ, mais rien
    dans le schéma ne l'impose au niveau base — une future règle qui
    l'omettrait ne doit pas casser l'agrégation en aval.
    """
    validate_schema_name(nom_schema_tenant)
    requete = _REQUETE_DETECTIONS_FENETRE.format(schema=nom_schema_tenant)

    async with pool.acquire() as connexion:
        lignes = await connexion.fetch(requete, fenetre_debut)

    return [
        DetectionNonTraitee(
            detection_id=ligne["detection_id"],
            compte_pivot=ligne["compte_pivot"],
            pattern_type=ligne["pattern_type"],
            detected_at=ligne["detected_at"],
        )
        for ligne in lignes
    ]
