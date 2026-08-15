"""Écriture des événements de détection dans {tenant}.detections.

Réutilise le même principe que la Brique 3 pour tenant_id/country_code/
data_classification : ces valeurs viennent de shared.tenants_registry, pas
d'une saisie libre. La fonction est dupliquée ici plutôt qu'importée
depuis souverain_generateur.ingestion (Brique 3) : cette dernière n'est
une dépendance de la Brique 4 qu'en test (dev-group, voir pyproject.toml),
jamais en runtime — la duplication est le prix assumé de cette séparation,
cohérent avec la convention déjà en place dans ce dépôt (chaque brique
duplique sa propre petite logique de config/lookup plutôt que de créer
un package partagé prématuré).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import UUID, uuid4

import asyncpg
from brique_01_postgresql.tenant_provisioning import validate_schema_name

from brique_04_detection.modeles import DetectionEvent

_REQUETE_METADONNEES_TENANT = """
    SELECT tenant_id, country_code, data_classification
    FROM shared.tenants_registry
    WHERE schema_name = $1 AND is_active = true
"""

_REQUETE_ASSURER_TABLE_DETECTIONS = """
    CREATE TABLE IF NOT EXISTS {schema}.detections (
        detection_id UUID PRIMARY KEY,
        tenant_id UUID NOT NULL,
        country_code TEXT NOT NULL,
        data_classification TEXT NOT NULL,
        pattern_type TEXT NOT NULL,
        transaction_ids UUID[] NOT NULL,
        compte_pivot TEXT,
        fenetre_debut TIMESTAMPTZ NOT NULL,
        fenetre_fin TIMESTAMPTZ NOT NULL,
        detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        details JSONB
    );
"""

_REQUETE_INSERT_DETECTION = """
    INSERT INTO {schema}.detections
        (detection_id, tenant_id, country_code, data_classification,
         pattern_type, transaction_ids, compte_pivot, fenetre_debut,
         fenetre_fin, details)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb)
"""


@dataclass(frozen=True)
class MetadonneesTenant:
    tenant_id: UUID
    country_code: str
    data_classification: str


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


async def enregistrer_detections(
    pool: asyncpg.Pool,
    nom_schema_tenant: str,
    evenements: list[DetectionEvent],
) -> int:
    """Insère les événements de détection, après s'être assuré que la table existe.

    Retourne le nombre d'événements insérés.
    """
    if not evenements:
        return 0

    metadonnees = await recuperer_metadonnees_tenant(pool, nom_schema_tenant)

    async with pool.acquire() as connexion:
        await connexion.execute(
            _REQUETE_ASSURER_TABLE_DETECTIONS.format(schema=nom_schema_tenant)
        )

        requete = _REQUETE_INSERT_DETECTION.format(schema=nom_schema_tenant)
        valeurs = [
            (
                uuid4(),
                metadonnees.tenant_id,
                metadonnees.country_code,
                metadonnees.data_classification,
                evenement.pattern_type,
                evenement.transaction_ids,
                evenement.compte_pivot,
                evenement.fenetre_debut,
                evenement.fenetre_fin,
                _details_vers_json(evenement.details),
            )
            for evenement in evenements
        ]
        async with connexion.transaction():
            await connexion.executemany(requete, valeurs)

    return len(evenements)


def _details_vers_json(details: dict[str, str | int | float]) -> str:
    return json.dumps(details)
