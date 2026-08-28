"""Lecture PostgreSQL pour la Brique 7 — strictement lecture seule.

Dupliquée en lecture directe depuis {tenant}.alertes et
{tenant}.detections, sans importer brique_05_scoring_alertes ni
brique_04_detection en runtime — même convention que Brique 5 → Brique 4
et Brique 6 → Brique 5 (chaque brique duplique sa propre petite requête
de lecture plutôt qu'une dépendance runtime, sauf exception documentée —
voir auth (Brique 2) et graphe (Brique 6) dans le README, seules
dépendances runtime réelles de cette brique).

⚠️ Décision actée après un bug réel de validation locale (voir
avancement.md) : {tenant}.alertes n'existe que si la Brique 5 a déjà
tourné au moins une fois pour ce tenant (sa table est créée par
enregistrer_scores(), jamais par cette brique, strictement lecture).
Un tenant fraîchement provisionné, avant tout premier cycle de scoring,
est un état LÉGITIME — pas une erreur de séquencement à faire remonter
brute comme le fait délibérément lire_comptes_alertes() en Brique 6
(brique batch CLI, public développeur). Ici, le public est un humain
qui regarde une page web : UndefinedTableError est interceptée et
traduite en TenantSansDonnees, gérée par app.py comme "0 alerte" —
Option B validée à l'analyse, l'erreur reste tracée (pas avalée
silencieusement), seulement présentée proprement à l'utilisateur.
"""

from __future__ import annotations

import json
from uuid import UUID

import asyncpg
from brique_01_postgresql.tenant_provisioning import validate_schema_name

from brique_07_dashboard.modeles import AlerteDetail, AlerteResume, DetectionLiee


class TenantSansDonnees(Exception):
    """{tenant}.alertes ou {tenant}.detections n'existe pas encore pour ce tenant.

    Levée plutôt que de laisser UndefinedTableError remonter brute —
    voir la décision documentée en tête de ce module. app.py l'attrape
    au niveau global et affiche une page "aucune donnée", tout en
    traçant l'événement (logs) — jamais avalée silencieusement.
    """

    def __init__(self, nom_schema_tenant: str, cause: Exception) -> None:
        super().__init__(
            f"Aucune table de résultats pour le tenant {nom_schema_tenant!r} "
            f"(Brique 5 jamais exécutée pour ce tenant ?) : {cause}"
        )
        self.nom_schema_tenant = nom_schema_tenant


_REQUETE_ALERTES_OUVERTES = """
    SELECT alerte_id, compte_pivot, score, statut, pattern_types_impliques, updated_at
    FROM {schema}.alertes
    WHERE statut = 'ouverte'
    ORDER BY score DESC
"""

_REQUETE_ALERTE_PAR_ID = """
    SELECT alerte_id, compte_pivot, score, statut, pattern_types_impliques,
           fenetre_debut, fenetre_fin, detection_ids, details
    FROM {schema}.alertes
    WHERE alerte_id = $1
"""

_REQUETE_DETECTIONS_PAR_IDS = """
    SELECT detection_id, pattern_type, detected_at
    FROM {schema}.detections
    WHERE detection_id = ANY($1::uuid[])
    ORDER BY detected_at ASC
"""


async def lister_alertes_ouvertes(
    pool: asyncpg.Pool, nom_schema_tenant: str
) -> list[AlerteResume]:
    validate_schema_name(nom_schema_tenant)
    requete = _REQUETE_ALERTES_OUVERTES.format(schema=nom_schema_tenant)

    try:
        async with pool.acquire() as connexion:
            lignes = await connexion.fetch(requete)
    except asyncpg.exceptions.UndefinedTableError as exc:
        raise TenantSansDonnees(nom_schema_tenant, exc) from exc

    return [
        AlerteResume(
            alerte_id=ligne["alerte_id"],
            compte_pivot=ligne["compte_pivot"],
            score=ligne["score"],
            statut=ligne["statut"],
            pattern_types_impliques=list(ligne["pattern_types_impliques"]),
            updated_at=ligne["updated_at"],
        )
        for ligne in lignes
    ]


async def lire_alerte(
    pool: asyncpg.Pool, nom_schema_tenant: str, alerte_id: UUID
) -> AlerteDetail | None:
    """Retourne None si l'alerte n'existe pas — la route traduit ça en 404, pas une exception.

    Lève TenantSansDonnees si {tenant}.alertes n'existe pas du tout —
    cas distinct de "l'alerte demandée n'existe pas" (table présente,
    ligne absente).
    """
    validate_schema_name(nom_schema_tenant)
    requete = _REQUETE_ALERTE_PAR_ID.format(schema=nom_schema_tenant)

    try:
        async with pool.acquire() as connexion:
            ligne = await connexion.fetchrow(requete, alerte_id)
    except asyncpg.exceptions.UndefinedTableError as exc:
        raise TenantSansDonnees(nom_schema_tenant, exc) from exc

    if ligne is None:
        return None

    detection_ids = list(ligne["detection_ids"])
    detections_liees = await _lire_detections_par_ids(pool, nom_schema_tenant, detection_ids)

    # JSONB non décodé automatiquement par asyncpg (aucun codec
    # configuré sur le pool, Brique 1) — désérialisation manuelle.
    details_bruts = ligne["details"]
    details = json.loads(details_bruts) if details_bruts else {}

    return AlerteDetail(
        alerte_id=ligne["alerte_id"],
        compte_pivot=ligne["compte_pivot"],
        score=ligne["score"],
        statut=ligne["statut"],
        pattern_types_impliques=list(ligne["pattern_types_impliques"]),
        fenetre_debut=ligne["fenetre_debut"],
        fenetre_fin=ligne["fenetre_fin"],
        details=details,
        detections_liees=detections_liees,
    )


async def _lire_detections_par_ids(
    pool: asyncpg.Pool, nom_schema_tenant: str, detection_ids: list[UUID]
) -> list[DetectionLiee]:
    if not detection_ids:
        return []

    validate_schema_name(nom_schema_tenant)
    requete = _REQUETE_DETECTIONS_PAR_IDS.format(schema=nom_schema_tenant)

    try:
        async with pool.acquire() as connexion:
            lignes = await connexion.fetch(requete, detection_ids)
    except asyncpg.exceptions.UndefinedTableError as exc:
        raise TenantSansDonnees(nom_schema_tenant, exc) from exc

    return [
        DetectionLiee(
            detection_id=ligne["detection_id"],
            pattern_type=ligne["pattern_type"],
            detected_at=ligne["detected_at"],
        )
        for ligne in lignes
    ]
