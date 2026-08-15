"""Détection de flux Niamey → zones frontalières Mali/Burkina Faso.

⚠️ LIMITE MVP IMPORTANTE, à ne pas perdre de vue :
Cette règle ne peut identifier l'origine/destination géographique d'un
compte QUE via une convention de nommage (préfixes "niamey_"/"frontiere"),
qui n'existe que dans le générateur synthétique de la Brique 3. En
production réelle, aucun identifiant de compte Mobile Money ne contient ce
genre d'information — il faudrait un référentiel compte→région (KYC/
déclaratif), qui n'existe dans aucune brique actuelle et sera nécessaire
en Vision (probablement Brique 8, gouvernance des données, ou un
référentiel dédié).

Cette règle reste donc un PLACEHOLDER fonctionnel uniquement contre les
données synthétiques de test — elle ne doit pas être présentée comme une
détection géographique réelle. Documenté explicitement ici et dans
ARCHITECTURE.md pour qu'aucune IA ni développeur futur ne suppose le
contraire par erreur.

Pas de seuil de fréquence en MVP (décision actée) : chaque transaction
correspondant au motif déclenche un événement individuel.
"""

from __future__ import annotations

from brique_04_detection.modeles import DetectionEvent, TransactionObservee
from brique_04_detection.regles.base import RegleDetection

PREFIXE_NIAMEY = "niamey_"
MARQUEUR_FRONTIERE = "frontiere"


class RegleFluxFrontalier(RegleDetection):
    """Sans état : chaque transaction est évaluée indépendamment."""

    def traiter(self, transaction: TransactionObservee) -> DetectionEvent | None:
        if transaction.sender_account.startswith(
            PREFIXE_NIAMEY
        ) and MARQUEUR_FRONTIERE in transaction.receiver_account:
            return DetectionEvent(
                pattern_type="flux_frontalier",
                transaction_ids=[transaction.transaction_id],
                fenetre_debut=transaction.occurred_at,
                fenetre_fin=transaction.occurred_at,
                compte_pivot=transaction.sender_account,
                details={"destinataire": transaction.receiver_account},
            )
        return None
