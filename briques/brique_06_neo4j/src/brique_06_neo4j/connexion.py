"""
Driver Neo4j asynchrone (async driver officiel), en singleton.

Même principe que create_pool()/close_pool() en Brique 1 : une seule
instance partagée, créée à la demande, fermée proprement en fin de
programme.
"""

from __future__ import annotations

from neo4j import AsyncDriver, AsyncGraphDatabase

from brique_06_neo4j.config import Neo4jSettings, get_settings

_driver: AsyncDriver | None = None


async def create_driver(settings: Neo4jSettings | None = None) -> AsyncDriver:
    """
    Crée (ou retourne) le driver Neo4j global.

    Raises:
        ConnectionRefusedError: si Neo4j n'est pas joignable (message
            reformulé, même esprit que create_pool() en Brique 1).
    """
    global _driver

    if _driver is not None:
        return _driver

    resolved_settings = settings or get_settings()

    driver = AsyncGraphDatabase.driver(
        resolved_settings.uri,
        auth=(resolved_settings.user, resolved_settings.password),
    )

    try:
        await driver.verify_connectivity()
    except Exception as exc:  # noqa: BLE001 — reformulé en message compréhensible
        await driver.close()
        raise ConnectionRefusedError(
            f"Impossible de joindre Neo4j sur {resolved_settings.uri} — "
            f"vérifier que le conteneur est démarré "
            f"(docker compose --profile neo4j up)."
        ) from exc

    _driver = driver
    return _driver


async def close_driver() -> None:
    """Ferme proprement le driver global, s'il existe."""
    global _driver
    if _driver is not None:
        await _driver.close()
        _driver = None
