"""Écriture des scores dans {tenant}.alertes.

Réutilise le même principe que la Brique 4 pour tenant_id/country_code/
data_classification : ces valeurs viennent de shared.tenants_registry,
pas d'une saisie libre. La fonction est dupliquée ici plutôt qu'importée
depuis brique_04_detection.persistence : cette dernière n'est une
dépendance de la Brique 5 qu'en test (dev-group, voir pyproject.toml),
jamais en runtime — même convention déjà en place dans ce dépôt (chaque
brique duplique sa propre petite logique de config/lookup plutôt que de
créer un package partagé prématuré).

Pour chaque ScoreCompte, si score >= SEUIL_ALERTE : upsert explicite sur
l'alerte 'ouverte' du compte_pivot (mise à jour en place si elle existe,
sinon création). C'est la SEULE garantie anti-doublon du système — pas
de table de suivi séparée (voir correction documentée dans lecture.py :
une première version avec {tenant}.detections_traitees a été retirée
car elle cassait le score cumulatif sur la fenêtre glissante). L'index
unique partiel (compte_pivot, WHERE statut='ouverte') garantit qu'il ne
peut exister qu'une seule alerte ouverte par compte, y compris si le
même cycle de scoring est rejoué plusieurs fois de suite sur les mêmes
détections.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import UUID, uuid4

import asyncpg
from brique_01_postgresql.tenant_provisioning import validate_schema_name

from brique_05_scoring_alertes.modeles import ScoreCompte
from brique_05_scoring_alertes.seuils import SEUIL_ALERTE

_REQUETE_METADONNEES_TENANT = """
    SELECT tenant_id, country_code, data_classification
    FROM shared.tenants_registry
    WHERE schema_name = $1 AND is_active = true
"""

_REQUETE_ASSURER_TABLE_ALERTES = """
    CREATE TABLE IF NOT EXISTS {schema}.alertes (
        alerte_id UUID PRIMARY KEY,
        tenant_id UUID NOT NULL,
        country_code TEXT NOT NULL,
        data_classification TEXT NOT NULL,
        compte_pivot TEXT NOT NULL,
        score INTEGER NOT NULL,
        statut TEXT NOT NULL DEFAULT 'ouverte'
            CHECK (statut IN ('ouverte', 'fermee')),
        pattern_types_impliques TEXT[] NOT NULL,
        detection_ids UUID[] NOT NULL,
        fenetre_debut TIMESTAMPTZ NOT NULL,
        fenetre_fin TIMESTAMPTZ NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        details JSONB
    );
"""

_REQUETE_ASSURER_INDEX_ALERTES_OUVERTE = """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_{schema}_alertes_ouverte_compte
    ON {schema}.alertes (compte_pivot)
    WHERE statut = 'ouverte';
"""

_REQUETE_ALERTE_OUVERTE_EXISTANTE = """
    UPDATE {schema}.alertes
    SET score = $2,
        pattern_types_impliques = $3,
        detection_ids = $4,
        fenetre_fin = $5,
        details = $6::jsonb,
        updated_at = now()
    WHERE compte_pivot = $1 AND statut = 'ouverte'
    RETURNING alerte_id
"""

_REQUETE_NOUVELLE_ALERTE = """
    INSERT INTO {schema}.alertes
        (alerte_id, tenant_id, country_code, data_classification,
         compte_pivot, score, pattern_types_impliques, detection_ids,
         fenetre_debut, fenetre_fin, details)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::jsonb)
"""


@dataclass(frozen=True)
class MetadonneesTenant:
    tenant_id: UUID
    country_code: str
    data_classification: str


@dataclass(frozen=True)
class ResultatPersistence:
    """Résumé d'un cycle d'enregistrement, pour affichage CLI."""

    nb_comptes_scores: int
    nb_alertes_creees: int
    nb_alertes_mises_a_jour: int


async def recuperer_metadonnees_tenant(
    pool: asyncpg.Pool, nom_schema_tenant: str
) -> MetadonneesTenant:
    validate_schema_name(nom_schema_tenant)
    async with pool.acquire() as connexion:
        ligne = await connexion.fetchrow(_REQUETE_METADONNEES_TENANT, nom_schema_tenant)

    if ligne is None:
        raise ValueError(
            f"Aucun tenant actif trouvé pour le schéma {nom_schema_tenant!r} dans "
            "shared.tenants_registry."
        )

    return MetadonneesTenant(
        tenant_id=ligne["tenant_id"],
        country_code=ligne["country_code"],
        data_classification=ligne["data_classification"],
    )


async def _assurer_tables(connexion: asyncpg.Connection, nom_schema_tenant: str) -> None:
    await connexion.execute(_REQUETE_ASSURER_TABLE_ALERTES.format(schema=nom_schema_tenant))
    await connexion.execute(
        _REQUETE_ASSURER_INDEX_ALERTES_OUVERTE.format(schema=nom_schema_tenant)
    )


async def _upserter_alerte(
    connexion: asyncpg.Connection,
    nom_schema_tenant: str,
    metadonnees: MetadonneesTenant,
    score_compte: ScoreCompte,
) -> tuple[UUID, bool]:
    """Met à jour l'alerte ouverte du compte si elle existe, sinon en crée une.

    Retourne (alerte_id, a_ete_creee) — a_ete_creee=True seulement si
    aucune alerte ouverte n'existait pour ce compte_pivot avant cet
    appel, pour permettre à l'appelant de distinguer création vs mise
    à jour dans le résumé du cycle.

    pattern_types_impliques et detection_ids sont écrits tels quels
    depuis score_compte (déjà calculés/dédupliqués en agregation.py) —
    aucun recalcul ici.
    """
    details_json = json.dumps(score_compte.details)

    ligne_maj = await connexion.fetchrow(
        _REQUETE_ALERTE_OUVERTE_EXISTANTE.format(schema=nom_schema_tenant),
        score_compte.compte_pivot,
        score_compte.score,
        score_compte.pattern_types_impliques,
        score_compte.detection_ids,
        score_compte.fenetre_fin,
        details_json,
    )

    if ligne_maj is not None:
        alerte_id: UUID = ligne_maj["alerte_id"]
        return alerte_id, False

    nouvelle_alerte_id = uuid4()
    await connexion.execute(
        _REQUETE_NOUVELLE_ALERTE.format(schema=nom_schema_tenant),
        nouvelle_alerte_id,
        metadonnees.tenant_id,
        metadonnees.country_code,
        metadonnees.data_classification,
        score_compte.compte_pivot,
        score_compte.score,
        score_compte.pattern_types_impliques,
        score_compte.detection_ids,
        score_compte.fenetre_debut,
        score_compte.fenetre_fin,
        details_json,
    )
    return nouvelle_alerte_id, True


async def enregistrer_scores(
    pool: asyncpg.Pool,
    nom_schema_tenant: str,
    scores: list[ScoreCompte],
) -> ResultatPersistence:
    """Enregistre un cycle de scoring complet.

    Pour chaque ScoreCompte dont le score franchit SEUIL_ALERTE : crée
    ou met à jour l'alerte ouverte du compte_pivot. Les comptes sous le
    seuil ne produisent aucune écriture — rien à marquer, puisque la
    fenêtre est entièrement recalculée à chaque cycle (voir lecture.py).
    Une transaction par compte_pivot.
    """
    if not scores:
        return ResultatPersistence(0, 0, 0)

    metadonnees = await recuperer_metadonnees_tenant(pool, nom_schema_tenant)

    nb_alertes_creees = 0
    nb_alertes_mises_a_jour = 0

    async with pool.acquire() as connexion:
        await _assurer_tables(connexion, nom_schema_tenant)

        for score_compte in scores:
            if score_compte.score < SEUIL_ALERTE:
                continue

            async with connexion.transaction():
                _, a_ete_creee = await _upserter_alerte(
                    connexion, nom_schema_tenant, metadonnees, score_compte
                )
                if a_ete_creee:
                    nb_alertes_creees += 1
                else:
                    nb_alertes_mises_a_jour += 1

    return ResultatPersistence(
        nb_comptes_scores=len(scores),
        nb_alertes_creees=nb_alertes_creees,
        nb_alertes_mises_a_jour=nb_alertes_mises_a_jour,
    )
