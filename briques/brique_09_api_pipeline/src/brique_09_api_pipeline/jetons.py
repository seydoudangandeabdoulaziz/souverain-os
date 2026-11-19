"""Jetons d'identité technique (typ=service), distincts des jetons humains B2.

Signés avec une clé dédiée (SOUVERAIN_API_JWT_SECRET) et un `aud` propre :
un jeton humain n'est jamais accepté ici, ni l'inverse (B2 vérifie une autre
clé). L'autorité réelle (actif, version du secret, portées, expiration) reste
la base de données, relue à chaque requête.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from brique_09_api_pipeline.config import ApiSettings

ALGORITHME = "HS256"


class JetonInvalide(Exception):
    """Jeton absent, mal signé, expiré ou d'un autre type."""


@dataclass(frozen=True)
class JetonService:
    client_id: UUID
    tenant_id: UUID
    secret_version: int


def emettre_jeton(
    client_id: UUID,
    tenant_id: UUID,
    scopes: list[str],
    secret_version: int,
    settings: ApiSettings,
) -> str:
    maintenant = datetime.now(UTC)
    charge = {
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "sub": str(client_id),
        "tenant_id": str(tenant_id),
        "typ": "service",
        "scope": " ".join(sorted(scopes)),
        "sv": secret_version,
        "iat": maintenant,
        "exp": maintenant + timedelta(minutes=settings.token_ttl_minutes),
    }
    return jwt.encode(charge, settings.jwt_secret.get_secret_value(), algorithm=ALGORITHME)


def decoder_jeton(jeton: str, settings: ApiSettings) -> JetonService:
    try:
        brut = jwt.decode(
            jeton,
            settings.jwt_secret.get_secret_value(),
            algorithms=[ALGORITHME],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["exp", "iat", "sub", "aud", "iss"]},
        )
        if brut.get("typ") != "service":
            raise JetonInvalide
        return JetonService(
            client_id=UUID(brut["sub"]),
            tenant_id=UUID(brut["tenant_id"]),
            secret_version=int(brut["sv"]),
        )
    except (jwt.PyJWTError, KeyError, ValueError, TypeError) as exc:
        raise JetonInvalide from exc
