"""Génération de transactions Mobile Money légitimes (bruit de fond).

Ce module ne connaît rien de la détection : il produit simplement des
transactions plausibles, pour que les patterns suspects (patterns_suspects.py)
ne soient pas les seules données du jeu de test — sinon la Brique 4 n'aurait
rien à distinguer.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

# Niger = WAT, UTC+1 fixe, pas de changement d'heure (pas de DST à gérer).
FUSEAU_NIGER = timezone(timedelta(hours=1))

CANAUX = ("orange_money", "airtel_money", "moov_money")
# Poids approximatifs de parts de marché Mobile Money au Niger — à ajuster
# si des chiffres officiels plus précis sont disponibles.
POIDS_CANAUX = (0.55, 0.30, 0.15)

DEVISE_UNIQUE = "XOF"  # Franc CFA — zone UEMOA


@dataclass
class TransactionSynthetique:
    """Une transaction générée, prête à être insérée en base.

    pattern_label vaut None pour une transaction légitime, et le nom du
    pattern (ex. "structure_etoile") pour une transaction issue d'un
    pattern suspect injecté volontairement.
    """

    sender_id: str
    receiver_id: str
    amount: float
    currency: str
    channel: str
    occurred_at: datetime
    is_synthetic: bool = True
    pattern_label: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


def identifiant_compte(rng: random.Random, prefixe: str = "cpt") -> str:
    """Génère un identifiant de compte pseudo-anonyme et reproductible."""
    return f"{prefixe}_{rng.randint(100000, 999999)}"


def _montant_legitime(rng: random.Random) -> float:
    """Distribution log-normale : beaucoup de petits montants, quelques gros.

    Reflète le comportement réel Mobile Money : la majorité des transactions
    sont de petits transferts quotidiens, une minorité sont plus importantes
    (loyers, commerce, transferts familiaux).
    """
    valeur = rng.lognormvariate(mu=8.5, sigma=1.1)  # ~ centré autour de 5000 XOF
    return round(min(valeur, 500_000), 2)


def generer_transaction_legitime(
    rng: random.Random,
    base_time: datetime,
    nb_comptes_pool: int = 2000,
) -> TransactionSynthetique:
    """Génère une transaction légitime isolée.

    nb_comptes_pool sert uniquement à borner l'espace des identifiants
    générés pour ce lot — ce n'est pas une contrainte d'unicité stricte.
    """
    sender = identifiant_compte(rng)
    receiver = identifiant_compte(rng)
    decalage = timedelta(seconds=rng.randint(0, 24 * 3600))
    return TransactionSynthetique(
        sender_id=sender,
        receiver_id=receiver,
        amount=_montant_legitime(rng),
        currency=DEVISE_UNIQUE,
        channel=rng.choices(CANAUX, weights=POIDS_CANAUX, k=1)[0],
        occurred_at=base_time + decalage,
        pattern_label=None,
    )


def generer_lot_legitime(
    nb_transactions: int,
    seed: int,
    base_time: datetime | None = None,
) -> list[TransactionSynthetique]:
    """Génère un lot de transactions légitimes, reproductible via seed.

    Même seed + même nb_transactions + même base_time ⇒ résultat identique.
    """
    rng = random.Random(seed)
    base_time = base_time or datetime(2026, 1, 1, 0, 0, 0, tzinfo=FUSEAU_NIGER)
    return [
        generer_transaction_legitime(rng, base_time) for _ in range(nb_transactions)
    ]


def nouvel_id_transaction() -> str:
    """Identifiant unique pour une transaction (indépendant de la seed)."""
    return str(uuid.uuid4())
