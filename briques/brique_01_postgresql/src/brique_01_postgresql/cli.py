"""
Point d'entrée CLI de la gouvernance de tenants (Brique 1 V2).

Trois sous-commandes :
    uv run souverain-tenant-creer --tenant-code NE --country-code NE \\
        --schema-name tenant_ne --acteur "Seydou (accès serveur direct)"
    uv run souverain-tenant-activer --schema-name tenant_ne --acteur "..."
    uv run souverain-tenant-desactiver --schema-name tenant_ne --acteur "..."

CLI-only par décision verrouillée (docs/MODELISATION_OPERATIONNELLE.md,
section 7bis) — aucune route HTTP n'existe pour ces opérations.

⚠️ --acteur est une DÉCLARATION LIBRE, non authentifiée (voir
gouvernance_audit.py) — saisie manuellement par l'opérateur, jamais
vérifiée. L'attribution forte de l'auteur CLI reste un chantier futur.
"""

from __future__ import annotations

import argparse
import asyncio

from brique_01_postgresql.gouvernance_cli_connection import (
    close_gouvernance_cli_pool,
    create_gouvernance_cli_pool,
)
from brique_01_postgresql.tenant_governance import (
    TenantDejaExistant,
    TenantIntrouvable,
    activate_tenant,
    create_tenant,
    deactivate_tenant,
)
from brique_01_postgresql.tenant_provisioning import InvalidSchemaNameError


async def _creer(args: argparse.Namespace) -> None:
    pool = await create_gouvernance_cli_pool()
    try:
        async with pool.acquire() as connexion:
            tenant_id = await create_tenant(
                connexion,
                tenant_code=args.tenant_code,
                country_code=args.country_code,
                schema_name=args.schema_name,
                data_classification=args.data_classification,
                acteur_declare=args.acteur,
            )
        print(
            f"[souverain-tenant-creer] Tenant créé : "
            f"tenant_id={tenant_id}, schema={args.schema_name}"
        )
    finally:
        await close_gouvernance_cli_pool()


async def _activer(args: argparse.Namespace) -> None:
    pool = await create_gouvernance_cli_pool()
    try:
        async with pool.acquire() as connexion:
            await activate_tenant(
                connexion, schema_name=args.schema_name, acteur_declare=args.acteur
            )
        print(f"[souverain-tenant-activer] Tenant activé : schema={args.schema_name}")
    finally:
        await close_gouvernance_cli_pool()


async def _desactiver(args: argparse.Namespace) -> None:
    pool = await create_gouvernance_cli_pool()
    try:
        async with pool.acquire() as connexion:
            await deactivate_tenant(
                connexion, schema_name=args.schema_name, acteur_declare=args.acteur
            )
        print(
            f"[souverain-tenant-desactiver] Tenant désactivé : schema={args.schema_name} "
            f"(schéma physique conservé, réversible via souverain-tenant-activer)"
        )
    finally:
        await close_gouvernance_cli_pool()


def _construire_parser_creer() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Crée un nouveau tenant (pays).")
    parser.add_argument("--tenant-code", required=True, help="ex: NE, SN")
    parser.add_argument("--country-code", required=True, help="code ISO 3166-1 alpha-2")
    parser.add_argument("--schema-name", required=True, help="ex: tenant_ne")
    parser.add_argument(
        "--data-classification",
        default="confidential",
        choices=["public", "internal", "confidential", "secret"],
    )
    parser.add_argument(
        "--acteur",
        required=True,
        help="Déclaration libre, NON authentifiée, identifiant l'opérateur humain.",
    )
    return parser


def _construire_parser_bascule(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--schema-name", required=True)
    parser.add_argument(
        "--acteur",
        required=True,
        help="Déclaration libre, NON authentifiée, identifiant l'opérateur humain.",
    )
    return parser


def main_creer() -> None:
    args = _construire_parser_creer().parse_args()
    try:
        asyncio.run(_creer(args))
    except (TenantDejaExistant, InvalidSchemaNameError) as exc:
        print(f"[souverain-tenant-creer] ERREUR : {exc}")
        raise SystemExit(1) from exc


def main_activer() -> None:
    args = _construire_parser_bascule("Réactive un tenant désactivé.").parse_args()
    try:
        asyncio.run(_activer(args))
    except TenantIntrouvable as exc:
        print(f"[souverain-tenant-activer] ERREUR : {exc}")
        raise SystemExit(1) from exc


def main_desactiver() -> None:
    parser = _construire_parser_bascule("Désactive un tenant (réversible, ne supprime rien).")
    args = parser.parse_args()
    try:
        asyncio.run(_desactiver(args))
    except TenantIntrouvable as exc:
        print(f"[souverain-tenant-desactiver] ERREUR : {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main_creer()
