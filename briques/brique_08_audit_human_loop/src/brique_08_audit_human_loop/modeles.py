"""Objets de la Brique 8 — motif de fermeture (liste fermée, validée à
l'analyse) et entrée d'audit affichable.

Découplés des modèles internes des autres briques, même principe déjà
appliqué partout ailleurs dans ce dépôt (AlerteResume en Brique 7,
TransactionAImporter en Brique 6, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class MotifFermeture(StrEnum):
    """Liste fermée validée à l'analyse — pas de texte libre en motif
    principal (un commentaire optionnel complète, voir EntreeAudit).
    """

    FAUX_POSITIF = "faux_positif"
    CONFIRME = "confirme"
    EN_COURS_INVESTIGATION = "en_cours_investigation"


@dataclass(frozen=True)
class EntreeAudit:
    """Une ligne de {tenant}.audit_log, avec l'email résolu pour affichage
    (jointure sur shared.users faite côté lecture.py — jamais stockée
    en dur dans audit_log, qui ne connaît que user_id).
    """

    id: UUID
    alerte_id: UUID
    user_id: UUID
    email_utilisateur: str | None
    motif: str
    commentaire: str | None
    created_at: datetime


class AlerteNonFermable(Exception):
    """L'alerte n'existe pas, ou n'est plus au statut 'ouverte'.

    Levée par persistence.py plutôt que de laisser un UPDATE silencieux
    ne rien faire — la route traduit ceci en réponse HTTP explicite
    (409), jamais un succès silencieux sur une alerte déjà fermée par
    quelqu'un d'autre entre l'affichage du formulaire et sa soumission
    (la vraie garantie anti-course reste l'UPDATE ... WHERE statut =
    'ouverte' ... RETURNING, atomique côté SQL — voir persistence.py).
    """

    def __init__(self, alerte_id: UUID) -> None:
        super().__init__(
            f"Alerte {alerte_id} introuvable ou déjà fermée — aucune action effectuée."
        )
        self.alerte_id = alerte_id


class RaisonAudit(StrEnum):
    """Raisons (codes sûrs, sans donnée sensible) pour lesquelles l'audit B8
    est indisponible. Seuls ces codes sont journalisés et affichés — jamais
    le texte brut d'une exception PostgreSQL (ADR-005, D5).
    """

    NON_PROVISIONNE = "NON_PROVISIONNE"
    ROLE_ABSENT = "ROLE_ABSENT"
    SCHEMA_ABSENT = "SCHEMA_ABSENT"
    VERROU_TIMEOUT = "VERROU_TIMEOUT"
    REPARATION_ECHOUEE = "REPARATION_ECHOUEE"
    ANOMALIE_PRIVILEGE = "ANOMALIE_PRIVILEGE"


class AuditNonProvisionne(Exception):
    """L'audit B8 n'est pas utilisable pour ce tenant (provisionnement absent
    ou réparation impossible). La route la traduit en HTTP 503 générique ;
    elle n'est JAMAIS convertie en historique vide.
    """

    def __init__(self, raison: RaisonAudit) -> None:
        super().__init__(f"audit B8 indisponible : {raison.value}")
        self.raison = raison
