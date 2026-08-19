"""Modèles de données de la Brique 5.

Indépendants de la Brique 4 (même principe que modeles.py en Brique 4,
indépendant de la Brique 3) : DetectionAgregee est un sous-ensemble de
ce qu'expose réellement {tenant}.detections, jamais un import direct
du modèle DetectionEvent de la Brique 4 en runtime.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DetectionAgregee(BaseModel):
    """Représentation minimale d'une détection, utile au scoring.

    Correspond à un sous-ensemble des colonnes réelles de
    {tenant}.detections (vérifiées contre la vraie migration Brique 4) :
    detection_id, pattern_type, compte_pivot, transaction_ids, detected_at.
    """

    detection_id: UUID
    pattern_type: str
    compte_pivot: str
    transaction_ids: list[UUID]
    detected_at: datetime


class ScoreCompte(BaseModel):
    """Résultat du calcul de score pour un compte_pivot donné."""

    compte_pivot: str
    score: int
    types_presents: set[str]
    premiere_detection_at: datetime
    derniere_detection_at: datetime
    detection_ids: list[UUID]


class DecisionAlerte(BaseModel):
    """Résultat de la comparaison au seuil de déclenchement."""

    compte_pivot: str
    score: int
    doit_alerter: bool
    detection_ids: list[UUID]
    premiere_detection_at: datetime
    derniere_detection_at: datetime


class Alerte(BaseModel):
    """Objet final prêt à persister dans {tenant}.alertes."""

    id: UUID | None = None
    tenant_id: UUID
    country_code: str
    data_classification: str
    compte_pivot: str
    score: int
    statut: str = "ouverte"
    premiere_detection_at: datetime
    derniere_detection_at: datetime
    is_synthetic: bool
    detection_ids: list[UUID]
