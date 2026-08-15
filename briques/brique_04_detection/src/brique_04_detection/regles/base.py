"""Interface commune des règles de détection + fenêtre glissante réutilisable.

Principe "Hybrid" (décision actée) : chaque règle est un objet à état,
alimenté transaction par transaction (traiter()), plutôt qu'une fonction
qui reçoit tout le lot d'un coup. C'est ce qui permettra de brancher une
vraie source de flux plus tard (Kafka/Redis, phase transverse) sans
réécrire la logique de détection — seule la source d'appel change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from brique_04_detection.modeles import DetectionEvent, TransactionObservee


class RegleDetection(ABC):
    """Interface commune : reçoit une transaction, émet 0 ou 1 événement."""

    @abstractmethod
    def traiter(self, transaction: TransactionObservee) -> DetectionEvent | None:
        """Traite une transaction et retourne un événement si un seuil est franchi.

        Suppose que les transactions arrivent dans l'ordre chronologique
        (occurred_at croissant) — c'est la responsabilité de l'appelant
        (lecture.py trie par occurred_at avant d'alimenter les règles).
        """
        raise NotImplementedError


@dataclass
class EntreeFenetre:
    """Une entrée dans une fenêtre glissante — un événement observé pour un compte."""

    horodatage: datetime
    autre_compte: str
    transaction_id: UUID
    montant: float


class FenetreGlissante:
    """Fenêtre glissante générique : conserve les entrées des N dernières minutes.

    purger() doit être appelé avant toute lecture, avec l'horodatage de la
    transaction courante comme référence — c'est ce qui rend la structure
    "état-plein" cohérente avec un traitement séquentiel (pas besoin de
    connaître l'heure actuelle du système, seulement l'heure de la
    dernière transaction reçue).
    """

    def __init__(self, duree: timedelta) -> None:
        self._duree = duree
        self._entrees: deque[EntreeFenetre] = deque()
        self.deja_signale = False

    def purger(self, reference: datetime) -> None:
        while self._entrees and reference - self._entrees[0].horodatage > self._duree:
            self._entrees.popleft()
        if not self._entrees:
            # Fenêtre vidée ⇒ nouvel épisode possible plus tard.
            self.deja_signale = False

    def ajouter(self, entree: EntreeFenetre) -> None:
        self._entrees.append(entree)

    @property
    def entrees(self) -> list[EntreeFenetre]:
        return list(self._entrees)

    def comptes_distincts(self) -> set[str]:
        return {e.autre_compte for e in self._entrees}

    def __len__(self) -> int:
        return len(self._entrees)
