"""
Pool de connexions PostgreSQL DÉDIÉ à la Brique 8.

Distinct du pool de la Brique 1 (create_pool(), rôle souverain_admin,
propriétaire de toutes les tables — donc capable de contourner
n'importe quel GRANT/REVOKE sur ses propres objets). Ce pool utilise le
rôle restreint souverain_brique8_audit (voir migration 0001), qui n'a
JAMAIS le droit UPDATE/DELETE sur {tenant}.audit_log. C'est la
protection par privilège RÉEL validée à l'analyse — pas seulement une
discipline applicative.

Toutes les opérations transactionnelles de cette brique (fermeture
d'alerte + écriture d'audit, dans la MÊME transaction) passent par ce
pool. Seule l'auto-réparation de la table (CREATE TABLE / GRANT, du
DDL) utilise le pool admin de la Brique 1 — le rôle restreint n'a
volontairement aucun privilège DDL, il ne pourrait pas réparer sa
propre table.
"""

from __future__ import annotations

import asyncpg
from brique_01_postgresql.config import get_settings as get_postgres_settings

from brique_08_audit_human_loop.config import get_audit_db_settings

_pool: asyncpg.Pool | None = None


def _build_dsn() -> str:
    pg = get_postgres_settings()
    audit = get_audit_db_settings()
    return f"postgresql://{audit.user}:{audit.password}@{pg.host}:{pg.port}/{pg.db}"


async def create_audit_pool() -> asyncpg.Pool:
    """Crée (ou retourne) le pool dédié global, avec le rôle restreint."""
    global _pool

    if _pool is not None:
        return _pool

    audit_settings = get_audit_db_settings()

    try:
        _pool = await asyncpg.create_pool(
            dsn=_build_dsn(),
            min_size=audit_settings.pool_min_size,
            max_size=audit_settings.pool_max_size,
            # Désactive le cache de requêtes préparées côté serveur.
            # Nécessaire ici précisément : les tests d'intégration
            # DROP SCHEMA CASCADE puis recréent un schéma de même nom
            # à chaque test, sur ce pool SINGLETON jamais fermé entre
            # les tests de test_routes.py (contrairement au pool admin
            # de la Brique 1, systématiquement fermé/recréé par sa
            # fixture à chaque test). PostgreSQL attribue un nouvel OID
            # à la table "audit_log" recréée ; un plan mis en cache par
            # asyncpg pour l'ancien OID devient invalide et lève
            # InvalidCachedStatementError au lieu de UndefinedTableError
            # — bug réel trouvé en testant sur une vraie base (latent
            # aussi dans le pool de la Brique 1, mais invisible ailleurs
            # car ses fixtures ferment toujours le pool entre les
            # tests). statement_cache_size=0 : coût négligeable pour ce
            # volume d'écriture, élimine la classe de bug entière.
            statement_cache_size=0,
        )
    except (OSError, asyncpg.PostgresError) as exc:
        raise ConnectionRefusedError(
            "Impossible de se connecter à PostgreSQL avec le rôle "
            "souverain_brique8_audit — vérifier que la migration 0001 de la "
            "Brique 8 a été appliquée (le rôle doit exister) et que "
            "AUDIT_DB_PASSWORD correspond au mot de passe réel du rôle en base."
        ) from exc

    return _pool


async def close_audit_pool() -> None:
    """Ferme proprement le pool dédié global, s'il existe."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
