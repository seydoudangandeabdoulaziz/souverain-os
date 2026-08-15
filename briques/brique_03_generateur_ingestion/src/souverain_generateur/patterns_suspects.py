"""Génération des patterns criminels sahéliens (document fondateur, Bloc 7).

Niveau retenu : INTERMÉDIAIRE — chaque pattern est paramétrable (intensité,
fenêtre temporelle, montants) et introduit un bruit contrôlé via une seed,
pour rester reproductible en test tout en n'étant pas une simple règle figée.

Chaque fonction renvoie une liste de TransactionSynthetique avec
pattern_label renseigné, pour que la Brique 4 (et les tests de cette brique)
puissent vérifier si un pattern injecté a bien été détecté.

Intensité attendue : "legere" | "moyenne" | "forte".
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Literal

from souverain_generateur.generateur_legitime import (
    DEVISE_UNIQUE,
    TransactionSynthetique,
    identifiant_compte,
)

Intensite = Literal["legere", "moyenne", "forte"]

_FACTEUR_INTENSITE: dict[Intensite, float] = {
    "legere": 0.6,
    "moyenne": 1.0,
    "forte": 1.6,
}


def _echelonner(base: int, intensite: Intensite) -> int:
    return max(1, round(base * _FACTEUR_INTENSITE[intensite]))


def generer_transactions_nocturnes(
    rng: random.Random,
    base_time: datetime,
    intensite: Intensite = "moyenne",
) -> list[TransactionSynthetique]:
    """Transactions nocturnes suspectes (22h-4h) sur un compte dormant.

    Un compte quasi inactif enchaîne soudain plusieurs transferts nocturnes.
    """
    nb = _echelonner(6, intensite)
    compte_dormant = identifiant_compte(rng, "cpt")
    debut_nuit = base_time.replace(hour=22, minute=0, second=0, microsecond=0)
    transactions = []
    for _ in range(nb):
        decalage = timedelta(minutes=rng.randint(0, 6 * 60))  # 22h → 4h
        transactions.append(
            TransactionSynthetique(
                sender_account=compte_dormant,
                receiver_account=identifiant_compte(rng),
                amount=round(rng.uniform(20_000, 150_000), 2),
                currency=DEVISE_UNIQUE,
                channel=rng.choice(["orange_money", "airtel_money"]),
                occurred_at=debut_nuit + decalage,
                pattern_label="transactions_nocturnes",
            )
        )
    return transactions


def generer_structure_etoile(
    rng: random.Random,
    base_time: datetime,
    intensite: Intensite = "moyenne",
) -> list[TransactionSynthetique]:
    """Structure en étoile : un émetteur vers de nombreux destinataires
    en une fenêtre temporelle courte — signature Hawala classique.
    """
    nb_destinataires = _echelonner(8, intensite)
    emetteur = identifiant_compte(rng, "hub")
    fenetre_minutes = rng.randint(30, 90)
    transactions = []
    for _ in range(nb_destinataires):
        decalage = timedelta(minutes=rng.randint(0, fenetre_minutes))
        montant = rng.uniform(30_000, 80_000) * rng.uniform(0.8, 1.2)  # bruit ±20%
        transactions.append(
            TransactionSynthetique(
                sender_account=emetteur,
                receiver_account=identifiant_compte(rng),
                amount=round(montant, 2),
                currency=DEVISE_UNIQUE,
                channel=rng.choice(["orange_money", "airtel_money", "moov_money"]),
                occurred_at=base_time + decalage,
                pattern_label="structure_etoile",
            )
        )
    return transactions


def generer_micro_fractionnement(
    rng: random.Random,
    base_time: datetime,
    intensite: Intensite = "moyenne",
) -> list[TransactionSynthetique]:
    """Micro-transactions haute fréquence (< 1000 FCFA) pour fractionner
    un montant total et éviter les seuils de déclaration.
    """
    nb = _echelonner(15, intensite)
    emetteur = identifiant_compte(rng)
    receveur = identifiant_compte(rng)
    transactions = []
    for i in range(nb):
        decalage = timedelta(seconds=rng.randint(0, 20 * 60))
        transactions.append(
            TransactionSynthetique(
                sender_account=emetteur,
                receiver_account=receveur,
                amount=round(rng.uniform(200, 950), 2),
                currency=DEVISE_UNIQUE,
                channel="orange_money",
                occurred_at=base_time + decalage,
                pattern_label="micro_fractionnement",
                metadata={"sequence": str(i)},
            )
        )
    return transactions


def generer_saisonnalite(
    rng: random.Random,
    base_time: datetime,
    evenement: Literal["tabaski", "ramadan", "campagne_agricole", "elections"],
    intensite: Intensite = "moyenne",
) -> list[TransactionSynthetique]:
    """Pic de transactions autour d'un événement calendaire à risque.

    Le pic lui-même est un comportement légitime dans l'écrasante majorité
    des cas (envois familiaux en période de fête) — c'est un pattern de
    contexte pour tester les faux positifs, pas un pattern criminel isolé.
    """
    nb = _echelonner(20, intensite)
    transactions = []
    for _ in range(nb):
        decalage = timedelta(hours=rng.randint(-48, 48))
        transactions.append(
            TransactionSynthetique(
                sender_account=identifiant_compte(rng),
                receiver_account=identifiant_compte(rng),
                amount=round(rng.uniform(5_000, 60_000), 2),
                currency=DEVISE_UNIQUE,
                channel=rng.choice(["orange_money", "airtel_money", "moov_money"]),
                occurred_at=base_time + decalage,
                pattern_label=f"saisonnalite_{evenement}",
            )
        )
    return transactions


def generer_flux_frontalier(
    rng: random.Random,
    base_time: datetime,
    intensite: Intensite = "moyenne",
) -> list[TransactionSynthetique]:
    """Flux Niamey → zones frontalières Mali/Burkina Faso."""
    nb = _echelonner(5, intensite)
    zones = ("frontiere_mali_01", "frontiere_burkina_01", "frontiere_burkina_02")
    transactions = []
    for _ in range(nb):
        decalage = timedelta(hours=rng.randint(0, 12))
        transactions.append(
            TransactionSynthetique(
                sender_account=identifiant_compte(rng, "niamey"),
                receiver_account=identifiant_compte(rng, rng.choice(zones)),
                amount=round(rng.uniform(40_000, 200_000), 2),
                currency=DEVISE_UNIQUE,
                channel=rng.choice(["orange_money", "airtel_money"]),
                occurred_at=base_time + decalage,
                pattern_label="flux_frontalier",
            )
        )
    return transactions


def generer_compte_pivot(
    rng: random.Random,
    base_time: datetime,
    intensite: Intensite = "moyenne",
) -> list[TransactionSynthetique]:
    """Compte pivot : reçoit de N sources et redistribue vers M destinations
    en moins d'une heure — schéma de blanchiment classique.
    """
    nb_sources = _echelonner(5, intensite)
    nb_destinations = _echelonner(4, intensite)
    pivot = identifiant_compte(rng, "pivot")
    transactions = []

    # Phase de réception : N sources → pivot
    for _ in range(nb_sources):
        decalage = timedelta(minutes=rng.randint(0, 30))
        transactions.append(
            TransactionSynthetique(
                sender_account=identifiant_compte(rng),
                receiver_account=pivot,
                amount=round(rng.uniform(30_000, 100_000), 2),
                currency=DEVISE_UNIQUE,
                channel=rng.choice(["orange_money", "airtel_money"]),
                occurred_at=base_time + decalage,
                pattern_label="compte_pivot_reception",
            )
        )

    # Phase de redistribution : pivot → M destinations, dans l'heure suivante
    for _ in range(nb_destinations):
        decalage = timedelta(minutes=rng.randint(30, 60))
        transactions.append(
            TransactionSynthetique(
                sender_account=pivot,
                receiver_account=identifiant_compte(rng),
                amount=round(rng.uniform(20_000, 90_000), 2),
                currency=DEVISE_UNIQUE,
                channel=rng.choice(["orange_money", "airtel_money"]),
                occurred_at=base_time + decalage,
                pattern_label="compte_pivot_redistribution",
            )
        )
    return transactions


PATTERNS_DISPONIBLES = (
    "transactions_nocturnes",
    "structure_etoile",
    "micro_fractionnement",
    "saisonnalite",
    "flux_frontalier",
    "compte_pivot",
)
