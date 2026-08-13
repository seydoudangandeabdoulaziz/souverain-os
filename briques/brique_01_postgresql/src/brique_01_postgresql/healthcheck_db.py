"""
Healthcheck de connexion réelle à PostgreSQL/TimescaleDB.

Dans la continuité du healthcheck de la Brique 0 (qui vérifiait
l'environnement local), ce module vérifie que le SERVICE PostgreSQL
est joignable et correctement configuré (extension TimescaleDB
présente, schéma partagé accessible).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import asyncpg

from brique_01_postgresql.config import PostgresSettings, get_settings
from brique_01_postgresql.connection import create_pool


@dataclass
class DbHealthcheckResult:
    ok: bool
    label: str
    detail: str = ""


@dataclass
class DbHealthcheckReport:
    results: list[DbHealthcheckResult] = field(default_factory=list)

    @property
    def all_ok(self) -> bool:
        return all(result.ok for result in self.results)

    def add(self, result: DbHealthcheckResult) -> None:
        self.results.append(result)


async def check_connection(settings: PostgresSettings) -> DbHealthcheckResult:
    """Vérifie qu'une connexion basique à PostgreSQL peut être établie."""
    try:
        pool = await create_pool(settings)
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return DbHealthcheckResult(
            ok=True,
            label="Connexion PostgreSQL",
            detail=f"connecté à {settings.host}:{settings.port}/{settings.db}",
        )
    except ConnectionRefusedError as exc:
        return DbHealthcheckResult(ok=False, label="Connexion PostgreSQL", detail=str(exc))


async def check_timescaledb_extension(settings: PostgresSettings) -> DbHealthcheckResult:
    """Vérifie que l'extension TimescaleDB est bien installée sur la base."""
    try:
        pool = await create_pool(settings)
        async with pool.acquire() as conn:
            version = await conn.fetchval(
                "SELECT extversion FROM pg_extension WHERE extname = 'timescaledb'"
            )
        if version is None:
            return DbHealthcheckResult(
                ok=False,
                label="Extension TimescaleDB",
                detail="extension non installée sur cette base",
            )
        return DbHealthcheckResult(
            ok=True, label="Extension TimescaleDB", detail=f"version {version}"
        )
    except (ConnectionRefusedError, asyncpg.PostgresError) as exc:
        return DbHealthcheckResult(ok=False, label="Extension TimescaleDB", detail=str(exc))


async def check_shared_schema(settings: PostgresSettings) -> DbHealthcheckResult:
    """Vérifie que le schéma partagé (shared.tenants_registry) existe."""
    try:
        pool = await create_pool(settings)
        async with pool.acquire() as conn:
            exists = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'shared' AND table_name = 'tenants_registry'
                )
                """
            )
        if not exists:
            return DbHealthcheckResult(
                ok=False,
                label="Schéma partagé",
                detail="shared.tenants_registry introuvable — migration non appliquée ?",
            )
        return DbHealthcheckResult(
            ok=True, label="Schéma partagé", detail="shared.tenants_registry présent"
        )
    except (ConnectionRefusedError, asyncpg.PostgresError) as exc:
        return DbHealthcheckResult(ok=False, label="Schéma partagé", detail=str(exc))


async def run_db_healthcheck(settings: PostgresSettings | None = None) -> DbHealthcheckReport:
    """Point d'entrée principal : exécute toutes les vérifications DB."""
    resolved_settings = settings or get_settings()
    report = DbHealthcheckReport()
    report.add(await check_connection(resolved_settings))

    # Si la connexion échoue, inutile de tester le reste — évite des
    # messages d'erreur redondants et confus.
    if not report.results[0].ok:
        return report

    report.add(await check_timescaledb_extension(resolved_settings))
    report.add(await check_shared_schema(resolved_settings))
    return report
