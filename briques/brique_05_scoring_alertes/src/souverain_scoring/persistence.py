"""Persistance de la Brique 5.

Écrit dans {tenant}.alertes, {tenant}.alertes_detections et
{tenant}.detections_traitees, dans une seule transaction par
compte_pivot recalculé (cohérence : jamais d'alerte écrite sans que
les détections contributrices soient marquées traitées, et
inversement).
"""

from __future__ import annotations

import asyncpg

from souverain_scoring.modeles import Alerte


async def upsert_alerte(connexion: asyncpg.Connection, schema: str, alerte: Alerte) -> None:
    """Crée ou met à jour l'alerte 'ouverte' pour ce compte_pivot (Q5).

    S'appuie sur l'index unique partiel
    (tenant_id, compte_pivot) WHERE statut = 'ouverte'
    pour un upsert atomique et sans course.
    """
    async with connexion.transaction():
        ligne = await connexion.fetchrow(
            f"""
            INSERT INTO {schema}.alertes (
                tenant_id, country_code, data_classification, compte_pivot,
                score, statut, premiere_detection_at, derniere_detection_at,
                is_synthetic, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, 'ouverte', $6, $7, $8, now())
            ON CONFLICT (tenant_id, compte_pivot)
                WHERE statut = 'ouverte'
            DO UPDATE SET
                score = EXCLUDED.score,
                derniere_detection_at = EXCLUDED.derniere_detection_at,
                is_synthetic = EXCLUDED.is_synthetic,
                updated_at = now()
            RETURNING id
            """,
            alerte.tenant_id,
            alerte.country_code,
            alerte.data_classification,
            alerte.compte_pivot,
            alerte.score,
            alerte.premiere_detection_at,
            alerte.derniere_detection_at,
            alerte.is_synthetic,
        )
        alerte_id = ligne["id"]

        await connexion.executemany(
            f"""
            INSERT INTO {schema}.alertes_detections (alerte_id, detection_id)
            VALUES ($1, $2)
            ON CONFLICT (alerte_id, detection_id) DO NOTHING
            """,
            [(alerte_id, detection_id) for detection_id in alerte.detection_ids],
        )

        await connexion.executemany(
            f"""
            INSERT INTO {schema}.detections_traitees (detection_id)
            VALUES ($1)
            ON CONFLICT (detection_id) DO NOTHING
            """,
            [(detection_id,) for detection_id in alerte.detection_ids],
        )


async def verifier_schema(connexion: asyncpg.Connection, schema: str) -> None:
    """Auto-réparation minimale : vérifie la présence des tables Brique 5.

    Même mécanique que persistence.py de la Brique 4 : si la migration
    n'a pas encore été appliquée, on échoue tôt avec un message clair
    plutôt qu'une erreur SQL opaque plus loin dans le pipeline.
    """
    tables_attendues = {"alertes", "alertes_detections", "detections_traitees"}
    lignes = await connexion.fetch(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = $1
          AND table_name = ANY($2::text[])
        """,
        schema,
        list(tables_attendues),
    )
    tables_presentes = {ligne["table_name"] for ligne in lignes}
    manquantes = tables_attendues - tables_presentes
    if manquantes:
        raise RuntimeError(
            f"Tables Brique 5 manquantes dans le schéma '{schema}' : {manquantes}. "
            "Appliquer 0001_create_alertes_table.sql avant d'exécuter le scoring."
        )
