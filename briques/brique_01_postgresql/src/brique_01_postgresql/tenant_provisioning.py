"""
Provisioning minimal d'un schéma tenant à partir du template SQL.

IMPORTANT — périmètre de cette brique :
Ce module fournit uniquement la mécanique technique pour créer un
schéma tenant à partir du template. La fonction complète
`create_tenant()` avec gouvernance, RBAC, audit trail et enregistrement
dans shared.tenants_registry appartient à la Brique 8
(Audit + Human-in-the-loop), conformément à la roadmap validée.

Ici, on ne fait que ce qui est nécessaire pour valider concrètement
que le schéma-per-tenant fonctionne (ex: provisionner 'tenant_ne'
pour le MVP Niger et vérifier que la hypertable se crée correctement).
"""

from __future__ import annotations

import re
from importlib import resources

import asyncpg

# Un nom de schéma valide : minuscules, chiffres, underscore, doit
# commencer par une lettre. Cette contrainte est ce qui permet
# d'insérer le nom directement dans le SQL du template SANS risque
# d'injection (asyncpg ne permet pas de paramétrer les noms d'objets
# SQL comme les schémas — la validation stricte est donc la défense).
_SCHEMA_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,40}$")


class InvalidSchemaNameError(ValueError):
    """Levée quand un nom de schéma tenant ne respecte pas le format attendu."""


def validate_schema_name(schema_name: str) -> str:
    """
    Valide qu'un nom de schéma est sûr à insérer dans du SQL brut.

    Args:
        schema_name: nom candidat, ex. "tenant_ne".

    Returns:
        Le même nom, si valide.

    Raises:
        InvalidSchemaNameError: si le format ne correspond pas au
            pattern autorisé (protection contre l'injection SQL,
            puisque les noms de schéma ne peuvent pas être paramétrés
            comme des valeurs classiques).
    """
    if not _SCHEMA_NAME_PATTERN.match(schema_name):
        raise InvalidSchemaNameError(
            f"Nom de schéma invalide : {schema_name!r}. "
            f"Attendu : minuscules/chiffres/underscore, "
            f"commence par une lettre, 3 à 41 caractères."
        )
    return schema_name


def render_tenant_schema_sql(schema_name: str) -> str:
    """
    Charge le template SQL et y injecte le nom de schéma validé.

    Args:
        schema_name: nom du schéma tenant, ex. "tenant_ne".

    Returns:
        Le SQL complet, prêt à être exécuté.
    """
    validated_name = validate_schema_name(schema_name)

    template = (
        resources.files("brique_01_postgresql")
        .joinpath("schema_tenant_template.sql")
        .read_text(encoding="utf-8")
    )
    return template.format(schema_name=validated_name)


async def provision_tenant_schema(
    connection: asyncpg.Connection,
    schema_name: str,
) -> None:
    """
    Crée physiquement le schéma tenant (idempotent — rejouable sans erreur).

    Args:
        connection: connexion asyncpg active.
        schema_name: nom du schéma à créer, ex. "tenant_ne".
    """
    sql = render_tenant_schema_sql(schema_name)
    await connection.execute(sql)
