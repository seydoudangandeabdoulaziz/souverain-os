"""Modèles de données de la Brique 4.

TransactionObservee est volontairement indépendant de TransactionSynthetique
(Brique 3) : le moteur de détection ne doit rien savoir de la façon dont une
transaction a été produite (synthétique ou réelle plus tard) — il ne reçoit
que les champs dont il a besoin pour détecter, lus depuis la base via
lecture.py. C'est ce découplage qui permettra, en phase transverse, de
brancher une vraie source de flux (Kafka/Redis) sans toucher aux règles.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class TransactionObservee:
    """Une transaction telle que vue par le moteur de détection.

    Ne contient JAMAIS is_synthetic ni pattern_label — le moteur ne doit
    pas pouvoir tricher en lisant une étiquette plutôt qu'en détectant
    un vrai comportement (même principe que pour la Brique 3).
    """

    transaction_id: UUID
    sender_account: str
    receiver_account: str
    amount: float
    channel: str
    occurred_at: datetime


@dataclass
class DetectionEvent:
    """Un événement de détection émis par une règle.

    transaction_ids référence les transactions ayant contribué à la
    détection (la fenêtre glissante au moment du déclenchement).
    """

    pattern_type: str
    transaction_ids: list[UUID]
    fenetre_debut: datetime
    fenetre_fin: datetime
    compte_pivot: str | None = None
    details: dict[str, str | int | float] = field(default_factory=dict)
