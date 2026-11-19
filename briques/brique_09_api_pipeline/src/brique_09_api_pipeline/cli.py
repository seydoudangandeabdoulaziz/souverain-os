"""CLI opérateur (rôle admin) : provisionnement des tenants et identités techniques.

Jamais appelée par l'API. L'identité PostgreSQL utilisée est celle de
POSTGRES_* (opérateur) ; `--expected-database` protège contre une mauvaise base.
"""

from __future__ import annotations

import argparse
import asyncio
from uuid import UUID

import asyncpg
from brique_01_postgresql.config import get_settings

from brique_09_api_pipeline.identites import (
    SCOPES_VALIDES,
    creer_client,
    lister_clients,
    renouveler_secret,
    revoquer_client,
)
from brique_09_api_pipeline.provisionnement import provisionner_tenant


async def _connexion_operateur(base_attendue: str) -> asyncpg.Connection:
    settings = get_settings()
    if settings.db != base_attendue:
        raise SystemExit("La base configurée ne correspond pas à --expected-database.")
    connexion = await asyncpg.connect(dsn=settings.dsn)
    if await connexion.fetchval("SELECT current_database()") != base_attendue:
        await connexion.close()
        raise SystemExit("La base connectée ne correspond pas à --expected-database.")
    return connexion


async def _provisionner(base: str, tenant_code: str | None) -> None:
    connexion = await _connexion_operateur(base)
    try:
        if tenant_code:
            lignes = await connexion.fetch(
                "SELECT tenant_id, schema_name FROM shared.tenants_registry WHERE tenant_code = $1",
                tenant_code.strip().upper(),
            )
        else:
            lignes = await connexion.fetch(
                "SELECT tenant_id, schema_name FROM shared.tenants_registry ORDER BY tenant_code"
            )
        if not lignes:
            raise SystemExit("Aucun tenant correspondant.")
        for ligne in lignes:
            await provisionner_tenant(connexion, ligne["tenant_id"], ligne["schema_name"])
            print(f"[souverain-api-provisionner] {ligne['schema_name']} : objets B9 prêts.")
    finally:
        await connexion.close()


def main_provisionner() -> None:
    parser = argparse.ArgumentParser(description="Crée les objets B9 par tenant (idempotent).")
    parser.add_argument("--expected-database", required=True)
    cible = parser.add_mutually_exclusive_group(required=True)
    cible.add_argument("--tenant-code")
    cible.add_argument("--tous", action="store_true")
    args = parser.parse_args()
    asyncio.run(_provisionner(args.expected_database, args.tenant_code))


async def _client(args: argparse.Namespace) -> None:
    connexion = await _connexion_operateur(args.expected_database)
    try:
        if args.commande == "creer":
            client_id, secret = await creer_client(
                connexion,
                args.tenant_code,
                args.source,
                args.scopes,
                args.acteur,
                args.expire_jours,
            )
            print(f"client_id={client_id}")
            print(f"client_secret={secret}")
            print("Secret affiché UNE SEULE FOIS : le conserver dans un coffre, jamais dans Git.")
        elif args.commande == "rotation":
            secret = await renouveler_secret(connexion, UUID(args.client_id), args.acteur)
            print(f"client_secret={secret}")
            print("Ancien secret et jetons émis révoqués. Secret affiché une seule fois.")
        elif args.commande == "revoquer":
            await revoquer_client(connexion, UUID(args.client_id), args.acteur)
            print("Identité révoquée.")
        else:
            for ligne in await lister_clients(connexion):
                print(
                    f"{ligne['client_id']} {ligne['tenant_code']} {ligne['source_code']} "
                    f"scopes={','.join(ligne['scopes'])} actif={ligne['is_active']} "
                    f"v{ligne['secret_version']}"
                )
    finally:
        await connexion.close()


def main_client() -> None:
    parser = argparse.ArgumentParser(description="Identités techniques de l'API pipeline.")
    parser.add_argument("--expected-database", required=True)
    sous = parser.add_subparsers(dest="commande", required=True)
    creer = sous.add_parser("creer")
    creer.add_argument("--tenant-code", required=True)
    creer.add_argument("--source", required=True, help="code de source d'ingestion (a-z0-9_)")
    creer.add_argument("--scopes", nargs="+", required=True, choices=SCOPES_VALIDES)
    creer.add_argument("--expire-jours", type=int)
    creer.add_argument("--acteur", required=True, help="opérateur à l'origine de l'action")
    rotation = sous.add_parser("rotation")
    rotation.add_argument("--client-id", required=True)
    rotation.add_argument("--acteur", required=True)
    revoquer = sous.add_parser("revoquer")
    revoquer.add_argument("--client-id", required=True)
    revoquer.add_argument("--acteur", required=True)
    sous.add_parser("lister")
    asyncio.run(_client(parser.parse_args()))
