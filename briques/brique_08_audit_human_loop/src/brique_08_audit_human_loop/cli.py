"""Point d'entrée CLI : uv run souverain-audit-provisionner --tenant tenant_ne | --tous.

Provisionne l'audit B8 (table audit_log + privilèges du rôle restreint) pour
un tenant créé APRÈS la migration 0001 — `create_tenant()` (Brique 1) ne
connaît pas la Brique 8. Idempotent : rejouable sans effet (ADR-005, D6).

Codes de sortie :
  0  tout conforme ou réparé
  1  au moins un échec d'exécution (SQL, verrou, schéma absent, anomalie...)
  2  erreur d'usage ou d'identification (argument invalide, tenant inconnu)
  3  refus de politique : --tenant sur un tenant désactivé
"""

from __future__ import annotations

import argparse
import asyncio
import sys

import asyncpg
from brique_01_postgresql.connection import close_pool, create_pool
from brique_01_postgresql.tenant_provisioning import InvalidSchemaNameError, validate_schema_name

from brique_08_audit_human_loop.modeles import AuditNonProvisionne
from brique_08_audit_human_loop.persistence import provisionner_audit

_PREFIXE = "[souverain-audit-provisionner]"

CODE_OK = 0
CODE_ECHEC = 1
CODE_USAGE = 2
CODE_INACTIF = 3


async def _provisionner_un(schema: str) -> tuple[str, str]:
    """Retourne (état, détail) — des CODES, jamais le message brut d'une exception."""
    try:
        repares = await provisionner_audit(schema)
    except AuditNonProvisionne as exc:
        return "échec", exc.raison.value
    except (asyncpg.PostgresError, OSError) as exc:
        return "échec", f"{type(exc).__name__}/{getattr(exc, 'sqlstate', None)}"
    if repares:
        return "réparé", ",".join(repares)
    return "conforme", ""


def _afficher(schema: str, etat: str, detail: str) -> None:
    suffixe = f" ({detail})" if detail else ""
    flux = sys.stderr if etat == "échec" else sys.stdout
    print(f"{_PREFIXE} {schema} : {etat}{suffixe}", file=flux)


async def _executer(tenant: str | None, tous: bool) -> int:
    try:
        pool = await create_pool()
    except ConnectionRefusedError:
        print(f"{_PREFIXE} PostgreSQL injoignable.", file=sys.stderr)
        return CODE_ECHEC

    try:
        async with pool.acquire() as connexion:
            if tous:
                lignes = await connexion.fetch(
                    "SELECT schema_name, is_active FROM shared.tenants_registry "
                    "ORDER BY schema_name"
                )
            else:
                assert tenant is not None
                try:
                    validate_schema_name(tenant)
                except InvalidSchemaNameError:
                    print(f"{_PREFIXE} nom de schéma invalide.", file=sys.stderr)
                    return CODE_USAGE
                lignes = await connexion.fetch(
                    "SELECT schema_name, is_active FROM shared.tenants_registry "
                    "WHERE schema_name = $1",
                    tenant,
                )
                if not lignes:
                    print(f"{_PREFIXE} tenant inconnu du registre.", file=sys.stderr)
                    return CODE_USAGE
                if not lignes[0]["is_active"]:
                    print(
                        f"{_PREFIXE} tenant désactivé : réactiver d'abord "
                        f"(souverain-tenant-activer).",
                        file=sys.stderr,
                    )
                    return CODE_INACTIF

        if not lignes:
            print(f"{_PREFIXE} aucun tenant dans le registre.")
            return CODE_OK

        bilan = {"conforme": 0, "réparé": 0, "ignoré": 0, "échec": 0}
        # Une transaction et un verrou PAR tenant (dans provisionner_audit) :
        # l'échec d'un tenant n'annule pas les autres et n'arrête pas la suite.
        for ligne in lignes:
            schema = ligne["schema_name"]
            if not ligne["is_active"]:
                _afficher(schema, "ignoré", "inactif")
                bilan["ignoré"] += 1
                continue
            etat, detail = await _provisionner_un(schema)
            _afficher(schema, etat, detail)
            bilan[etat] += 1

        if tous:
            print(
                f"{_PREFIXE} bilan : {bilan['conforme']} conforme(s), "
                f"{bilan['réparé']} réparé(s), {bilan['ignoré']} ignoré(s), "
                f"{bilan['échec']} échec(s)."
            )
        return CODE_ECHEC if bilan["échec"] else CODE_OK
    finally:
        await close_pool()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Provisionne l'audit B8 d'un ou de tous les tenants actifs (idempotent)."
    )
    groupe = parser.add_mutually_exclusive_group(required=True)
    groupe.add_argument("--tenant", help="Nom du schéma tenant (ex. tenant_ne).")
    groupe.add_argument("--tous", action="store_true", help="Tous les tenants actifs.")
    args = parser.parse_args()  # argparse sort avec le code 2 sur un usage invalide

    sys.exit(asyncio.run(_executer(args.tenant, args.tous)))


if __name__ == "__main__":
    main()
