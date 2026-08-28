"""Objets d'affichage de la Brique 7 — découplés des modèles internes
des autres briques, même principe de découplage appliqué partout
ailleurs dans le projet (TransactionAImporter en Brique 6, etc.).

Les résultats de requetes.py (Brique 6 — Chemin, ComptePont) sont
réutilisés TELS QUELS, sans réencapsulation : ce sont déjà des objets
d'affichage appropriés, en créer une copie ici serait une indirection
sans valeur.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class AlerteResume:
    """Une ligne de la liste des alertes ouvertes."""

    alerte_id: UUID
    compte_pivot: str
    score: int
    statut: str
    pattern_types_impliques: list[str]
    updated_at: datetime


@dataclass(frozen=True)
class DetectionLiee:
    """Une détection contributrice, affichée dans le détail d'une alerte."""

    detection_id: UUID
    pattern_type: str
    detected_at: datetime


@dataclass(frozen=True)
class AlerteDetail:
    """Détail complet d'une alerte, contexte PostgreSQL uniquement.

    Les résultats du graphe (chaînes, comptes pont, chemins) sont
    chargés séparément par la route (via HTMX, fragments distincts —
    voir le point de vigilance documenté au README sur la latence de
    ces requêtes) et ne font pas partie de cet objet.
    """

    alerte_id: UUID
    compte_pivot: str
    score: int
    statut: str
    pattern_types_impliques: list[str]
    fenetre_debut: datetime
    fenetre_fin: datetime
    details: dict[str, int] = field(default_factory=dict)
    detections_liees: list[DetectionLiee] = field(default_factory=list)
