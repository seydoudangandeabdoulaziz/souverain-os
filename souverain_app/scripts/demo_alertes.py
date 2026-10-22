from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from brique_01_postgresql.connection import close_pool, create_pool
from brique_01_postgresql.tenant_provisioning import provision_tenant_schema
from brique_02_auth_rbac.password_hashing import hash_password
from brique_02_auth_rbac.repository import create_user
from brique_02_auth_rbac.souverain_id import generate_souverain_id
from brique_04_detection.modeles import DetectionEvent
from brique_04_detection.persistence import enregistrer_detections
from brique_05_scoring_alertes.cli import executer_cycle_scoring

TENANT = "tenant_demo_souverain"
CODE = "DE"
EMAIL = "analyste-demo@souverain.local"
MOT_DE_PASSE = "Demo-Souverain-2026!"
COMPTE = "DEMO_COMPTE_001"


async def main() -> None:
    pool = await create_pool()
    try:
        async with pool.acquire() as conn:
            existant = await conn.fetchrow(
                """
                SELECT tenant_id FROM shared.tenants_registry
                WHERE schema_name = $1
                """,
                TENANT,
            )
            if existant:
                raise RuntimeError(
                    f"Le tenant {TENANT} existe déjà. "
                    "Arrêt sans modifier ses données."
                )

            tenant_id = await conn.fetchval(
                """
                INSERT INTO shared.tenants_registry
                    (tenant_code, country_code, schema_name,
                     data_classification, is_active)
                VALUES ($1, 'NE', $2, 'confidential', true)
                RETURNING tenant_id
                """,
                CODE,
                TENANT,
            )

            try:
                await provision_tenant_schema(conn, TENANT)

                await create_user(
                    conn,
                    tenant_id=tenant_id,
                    souverain_id=generate_souverain_id(CODE, EMAIL),
                    email=EMAIL,
                    password_hash=hash_password(MOT_DE_PASSE),
                    role="analyst",
                )
            except Exception:
                await conn.execute(f"DROP SCHEMA IF EXISTS {TENANT} CASCADE")
                await conn.execute(
                    "DELETE FROM shared.tenants_registry WHERE schema_name = $1",
                    TENANT,
                )
                raise

        maintenant = datetime.now(UTC)
        evenements = [
            DetectionEvent(
                pattern_type="compte_pivot",
                transaction_ids=[uuid4(), uuid4()],
                fenetre_debut=maintenant - timedelta(minutes=20),
                fenetre_fin=maintenant,
                compte_pivot=COMPTE,
                details={"scenario": "demonstration"},
            ),
            DetectionEvent(
                pattern_type="micro_fractionnement",
                transaction_ids=[uuid4(), uuid4()],
                fenetre_debut=maintenant - timedelta(minutes=15),
                fenetre_fin=maintenant,
                compte_pivot=COMPTE,
                details={"scenario": "demonstration"},
            ),
        ]

        inserees = await enregistrer_detections(pool, TENANT, evenements)
        print(f"Détections de démonstration enregistrées : {inserees}")

    finally:
        await close_pool()

    # Utilise le cycle réel : lecture, agrégation, seuil et persistance.
    await executer_cycle_scoring(TENANT)

    pool_verification = await create_pool()
    try:
        async with pool_verification.acquire() as conn:
            alertes = await conn.fetch(
                f"""
                SELECT compte_pivot, score, statut
                FROM {TENANT}.alertes
                WHERE compte_pivot = $1
                ORDER BY created_at DESC
                """,
                COMPTE,
            )

        if not alertes:
            raise RuntimeError(
                "Aucune alerte créée. Vérifie les logs du scoring et le schéma."
            )

        print("\n=== ALERTE DE DÉMONSTRATION ===")
        for alerte in alertes:
            print(
                f"Compte : {alerte['compte_pivot']} | "
                f"Score : {alerte['score']} | Statut : {alerte['statut']}"
            )

        print("\n=== CONNEXION AU DASHBOARD ===")
        print("URL : http://127.0.0.1:8080/login")
        print(f"Email : {EMAIL}")
        print(f"Mot de passe : {MOT_DE_PASSE}")
        print("Après connexion, ouvre : http://127.0.0.1:8080/alertes")
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
