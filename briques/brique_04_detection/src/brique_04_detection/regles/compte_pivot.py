"""Détection de compte pivot — reçoit de N sources et redistribue vers M
destinations dans la même fenêtre courte (schéma de blanchiment classique).

Seuil MVP (validé) : ≥ 3 réceptions puis ≥ 2 redistributions en ≤ 60 minutes.
"""

from __future__ import annotations

from datetime import timedelta

from brique_04_detection.modeles import DetectionEvent, TransactionObservee
from brique_04_detection.regles.base import EntreeFenetre, FenetreGlissante, RegleDetection

SEUIL_RECEPTIONS = 3
SEUIL_REDISTRIBUTIONS = 2
FENETRE_MINUTES = 60


class ReglePivot(RegleDetection):
    def __init__(
        self,
        seuil_receptions: int = SEUIL_RECEPTIONS,
        seuil_redistributions: int = SEUIL_REDISTRIBUTIONS,
        fenetre_minutes: int = FENETRE_MINUTES,
    ) -> None:
        self._seuil_receptions = seuil_receptions
        self._seuil_redistributions = seuil_redistributions
        self._duree = timedelta(minutes=fenetre_minutes)
        self._receptions: dict[str, FenetreGlissante] = {}
        self._redistributions: dict[str, FenetreGlissante] = {}

    def traiter(self, transaction: TransactionObservee) -> DetectionEvent | None:
        # Chaque transaction est une réception pour le destinataire et une
        # redistribution potentielle pour l'émetteur — on met à jour les
        # deux, dans cet ordre, avant de vérifier si l'émetteur devient un
        # pivot actif.
        self._enregistrer_reception(transaction)
        return self._verifier_redistribution(transaction)

    def _enregistrer_reception(self, transaction: TransactionObservee) -> None:
        compte = transaction.receiver_account
        fenetre = self._receptions.setdefault(compte, FenetreGlissante(self._duree))
        fenetre.purger(transaction.occurred_at)
        fenetre.ajouter(
            EntreeFenetre(
                horodatage=transaction.occurred_at,
                autre_compte=transaction.sender_account,
                transaction_id=transaction.transaction_id,
                montant=transaction.amount,
            )
        )

    def _verifier_redistribution(
        self, transaction: TransactionObservee
    ) -> DetectionEvent | None:
        compte = transaction.sender_account
        fenetre_reception = self._receptions.get(compte)
        if fenetre_reception is None:
            return None
        fenetre_reception.purger(transaction.occurred_at)
        if len(fenetre_reception) < self._seuil_receptions:
            return None

        fenetre_redist = self._redistributions.setdefault(
            compte, FenetreGlissante(self._duree)
        )
        fenetre_redist.purger(transaction.occurred_at)
        fenetre_redist.ajouter(
            EntreeFenetre(
                horodatage=transaction.occurred_at,
                autre_compte=transaction.receiver_account,
                transaction_id=transaction.transaction_id,
                montant=transaction.amount,
            )
        )

        if len(fenetre_redist) < self._seuil_redistributions or fenetre_redist.deja_signale:
            return None

        fenetre_redist.deja_signale = True
        entrees_reception = fenetre_reception.entrees
        entrees_redist = fenetre_redist.entrees
        toutes_entrees = entrees_reception + entrees_redist
        return DetectionEvent(
            pattern_type="compte_pivot",
            transaction_ids=[e.transaction_id for e in toutes_entrees],
            fenetre_debut=min(e.horodatage for e in toutes_entrees),
            fenetre_fin=max(e.horodatage for e in toutes_entrees),
            compte_pivot=compte,
            details={
                "nb_receptions": len(entrees_reception),
                "nb_redistributions": len(entrees_redist),
            },
        )
