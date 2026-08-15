"""Détection de structure en étoile — un émetteur vers de nombreux
destinataires distincts en fenêtre courte (signature Hawala classique).

Seuil MVP (validé, à ajuster après résultats réels) : ≥ 6 destinataires
distincts en ≤ 90 minutes.
"""

from __future__ import annotations

from datetime import timedelta

from brique_04_detection.modeles import DetectionEvent, TransactionObservee
from brique_04_detection.regles.base import EntreeFenetre, FenetreGlissante, RegleDetection

SEUIL_DESTINATAIRES_DISTINCTS = 6
FENETRE_MINUTES = 90


class RegleStructureEtoile(RegleDetection):
    def __init__(
        self,
        seuil: int = SEUIL_DESTINATAIRES_DISTINCTS,
        fenetre_minutes: int = FENETRE_MINUTES,
    ) -> None:
        self._seuil = seuil
        self._duree = timedelta(minutes=fenetre_minutes)
        self._fenetres_par_emetteur: dict[str, FenetreGlissante] = {}

    def traiter(self, transaction: TransactionObservee) -> DetectionEvent | None:
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

        distincts = fenetre.comptes_distincts()
        if len(distincts) >= self._seuil and not fenetre.deja_signale:
            fenetre.deja_signale = True
            entrees = fenetre.entrees
            return DetectionEvent(
                pattern_type="structure_etoile",
                transaction_ids=[e.transaction_id for e in entrees],
                fenetre_debut=entrees[0].horodatage,
                fenetre_fin=entrees[-1].horodatage,
                compte_pivot=emetteur,
                details={"nb_destinataires_distincts": len(distincts)},
            )
        return None
