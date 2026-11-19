"""Schémas d'entrée/sortie de l'API (Pydantic v2, champs inconnus refusés).

Le corps d'une requête ne contient JAMAIS : tenant_id, country_code,
data_classification, is_synthetic ni source. Le serveur les impose à partir
de l'identité technique authentifiée. Un champ inconnu est refusé (422).
"""

from __future__ import annotations

import hashlib
from datetime import UTC
from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

MAX_LOT = 1000
CANAUX = ("orange_money", "airtel_money", "moov_money")


class TransactionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:\-]+$")
    sender_account: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_\-]+$")
    receiver_account: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_\-]+$")
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    currency: Literal["XOF"]
    channel: Literal["orange_money", "airtel_money", "moov_money"]
    occurred_at: AwareDatetime

    @model_validator(mode="after")
    def _comptes_differents(self) -> TransactionIn:
        if self.sender_account == self.receiver_account:
            raise ValueError("sender_account et receiver_account doivent différer")
        return self

    def content_hash(self) -> bytes:
        """Empreinte canonique du contenu (détection d'un rejeu modifié)."""
        canon = "\x1f".join(
            (
                self.sender_account,
                self.receiver_account,
                f"{self.amount:.2f}",
                self.currency,
                self.channel,
                self.occurred_at.astimezone(UTC).isoformat(timespec="microseconds"),
            )
        )
        return hashlib.sha256(canon.encode("utf-8")).digest()


class LotTransactions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transactions: list[TransactionIn] = Field(min_length=1, max_length=MAX_LOT)


class DemandeJeton(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_code: str = Field(min_length=2, max_length=16)
    client_id: str = Field(min_length=1, max_length=64)
    client_secret: str = Field(min_length=1, max_length=256)


class ReponseJeton(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    scope: str


class ReponseIngestion(BaseModel):
    recues: int
    inserees: int
    doublons_ignores: int


class ReponseCycle(BaseModel):
    nouvelles_transactions: int
    comptes_touches: int
    transactions_relues: int
    detections_nouvelles: int
    replis_episode: int
    episodes_tronques: int
    comptes_scores: int
    alertes_creees: int
    alertes_mises_a_jour: int
