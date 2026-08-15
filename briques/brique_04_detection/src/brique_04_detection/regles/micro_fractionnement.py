"""Détection de micro-fractionnement — nombreuses transactions sous un
seuil (< 1000 XOF), même paire émetteur/destinataire, en fenêtre courte.

Seuil MVP (validé) : ≥ 10 transactions < 1000 XOF, même paire, ≤ 20 minutes.
"""

from __future__ import annotations

from datetime import timedelta

from brique_04_detection.modeles import DetectionEvent, TransactionObservee
from brique_04_detection.regles.base import EntreeFenetre, FenetreGlissante, RegleDetection

SEUIL_NB_TRANSACTIONS = 10
SEUIL_MONTANT = 1000.0
FENETRE_MINUTES = 20


class RegleMicroFractionnement(RegleDetection):
    def __init__(
        self,
        seuil_nb: int = SEUIL_NB_TRANSACTIONS,
        seuil_montant: float = SEUIL_MONTANT,
        fenetre_minutes: int = FENETRE_MINUTES,
    ) -> None:
        self._seuil_nb = seuil_nb
        self._seuil_montant = seuil_montant
        self._duree = timedelta(minutes=fenetre_minutes)
        self._fenetres_par_paire: dict[tuple[str, str], FenetreGlissante] = {}

    def traiter(self, transaction: TransactionObservee) -> DetectionEvent | None:
        if transaction.amount >= self._seuil_montant:
            return None

        paire = (transaction.sender_account, transaction.receiver_account)
        fenetre = self._fenetres_par_paire.setdefault(paire, FenetreGlissante(self._duree))
        fenetre.purger(transaction.occurred_at)
        fenetre.ajouter(
            EntreeFenetre(
                horodatage=transaction.occurred_at,
                autre_compte=transaction.receiver_account,
                transaction_id=transaction.transaction_id,
                montant=transaction.amount,
            )
        )

        if len(fenetre) >= self._seuil_nb and not fenetre.deja_signale:
            fenetre.deja_signale = True
            entrees = fenetre.entrees
            return DetectionEvent(
                pattern_type="micro_fractionnement",
                transaction_ids=[e.transaction_id for e in entrees],
                fenetre_debut=entrees[0].horodatage,
                fenetre_fin=entrees[-1].horodatage,
                compte_pivot=transaction.sender_account,
                details={
                    "nb_transactions": len(entrees),
                    "montant_total": sum(e.montant for e in entrees),
                },
            )
        return None
