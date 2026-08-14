"""
Émission et vérification de jetons JWT (JSON Web Token).

Un JWT est un jeton auto-porteur : il contient les informations
nécessaires (identité, tenant, rôle) et une signature qui prouve
qu'il n'a pas été modifié depuis son émission. Analogie : un badge
d'accès scellé — pas besoin d'appeler un serveur central à chaque
porte, juste vérifier que le sceau (la signature) est intact.

MVP : signature symétrique HMAC-SHA256 (un seul secret partagé côté
serveur). Une migration vers une signature asymétrique post-quantique
(Dilithium-5) est prévue en phase transverse PQC — pas dans cette
brique.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt

from brique_02_auth_rbac.config import JwtSettings


class InvalidTokenError(Exception):
    """Le jeton est malformé ou sa signature ne correspond pas."""


class ExpiredTokenError(Exception):
    """Le jeton était valide mais a dépassé sa date d'expiration."""


@dataclass(frozen=True)
class TokenPayload:
    """Contenu décodé et validé d'un jeton JWT SOUVERAIN-OS."""

    user_id: uuid.UUID
    tenant_id: uuid.UUID
    role: str
    token_version: int


def create_access_token(
    *,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    role: str,
    token_version: int,
    settings: JwtSettings,
) -> str:
    """
    Émet un nouveau jeton d'accès signé.

    Le claim `token_version` permet une révocation immédiate côté
    serveur (voir repository.py) : si la valeur en base ne correspond
    plus à celle du jeton, le jeton est rejeté malgré une signature
    valide (ex. après changement de mot de passe ou désactivation).
    """
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "role": role,
        "token_version": token_version,
        "iat": now,
        "exp": now + timedelta(hours=settings.expiration_hours),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str, settings: JwtSettings) -> TokenPayload:
    """
    Décode et valide un jeton JWT (signature + expiration).

    Raises:
        ExpiredTokenError: le jeton a dépassé sa date d'expiration.
        InvalidTokenError: signature invalide, ou champs attendus
            manquants/malformés.
    """
    try:
        raw_payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise ExpiredTokenError(
            "Le jeton a expiré, une nouvelle connexion est nécessaire."
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise InvalidTokenError(f"Jeton invalide : {exc}") from exc

    try:
        return TokenPayload(
            user_id=uuid.UUID(raw_payload["sub"]),
            tenant_id=uuid.UUID(raw_payload["tenant_id"]),
            role=raw_payload["role"],
            token_version=raw_payload["token_version"],
        )
    except (KeyError, ValueError) as exc:
        raise InvalidTokenError(f"Contenu du jeton incohérent : {exc}") from exc
