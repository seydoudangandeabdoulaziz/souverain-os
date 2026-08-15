"""Détection de transactions nocturnes suspectes (22h-4h) sur un compte
avec une activité soudaine.

Seuil MVP (validé) : ≥ 4 transactions entre 22h et 4h (heure locale de
occurred_at, déjà exprimée dans le fuseau Niger par la Brique 3) pour un
même compte émetteur, sur une même plage nocturne.

Fenêtre glissante de 6h (22h→4h) pour couvrir toute la plage nocturne
sans avoir à gérer explicitement le changement de jour calendaire.
"""

from __future__ import annotations

from datetime import timedelta

from brique_04_detection.modeles import DetectionEvent, TransactionObservee
from brique_04_detection.regles.base import EntreeFenetre, FenetreGlissante, RegleDetection

SEUIL_NB_TRANSACTIONS = 4
FENETRE_MINUTES = 6 * 60  # 22h → 4h


def _est_heure_nocturne(heure: int) -> bool:
    return heure >= 22 or heure < 4


class RegleNocturne(RegleDetection):
    def __init__(
        self,
        seuil_nb: int = SEUIL_NB_TRANSACTIONS,
        fenetre_minutes: int = FENETRE_MINUTES,
    ) -> None:
        self._seuil_nb = seuil_nb
        self._duree = timedelta(minutes=fenetre_minutes)
        self._fenetres_par_emetteur: dict[str, FenetreGlissante] = {}

    def traiter(self, transaction: TransactionObservee) -> DetectionEvent | None:
        if not _est_heure_nocturne(transaction.occurred_at.hour):
            return None

        emetteur = transaction.sender_account
        fenetre = self._fenetres_par_emetteur.setdefault(
            emetteur, FenetreGlissante(self._duree)
        )
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
                pattern_type="transactions_nocturnes",
                transaction_ids=[e.transaction_id for e in entrees],
                fenetre_debut=entrees[0].horodatage,
                fenetre_fin=entrees[-1].horodatage,
                compte_pivot=emetteur,
                details={"nb_transactions": len(entrees)},
            )
        return None
