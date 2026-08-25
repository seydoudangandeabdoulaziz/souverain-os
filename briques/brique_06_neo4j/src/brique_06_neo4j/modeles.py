"""Modèles de données de la Brique 6.

TransactionAImporter : lu depuis {tenant}.transactions (Brique 1),
indépendant de tout modèle des autres briques — même principe de
découplage déjà appliqué partout ailleurs dans le projet.

Chemin/ComptePont : objets typés retournés par requetes.py, traduits
depuis les Records bruts Neo4j par garde_isolation.py. requetes.py ne
fait que cette traduction ; il ne contient aucun Cypher (voir
garde_isolation.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True)
class TransactionAImporter:
    """Une transaction telle que lue depuis {tenant}.transactions, prête à projeter dans Neo4j.

    Noms de champs alignés sur le schéma réel de la Brique 1
    (amount/currency/channel — vérifié dans schema_tenant_template.sql,
    pas supposé).
    """

    transaction_id: UUID
    sender_account: str
    receiver_account: str
    amount: Decimal
    currency: str
    channel: str
    occurred_at: datetime
    is_synthetic: bool


@dataclass(frozen=True)
class Chemin:
    """Une séquence de comptes reliés par des transactions successives.

    Utilisé pour les requêtes a) chaîne de redistribution multi-sauts
    et c) plus court chemin entre deux comptes alertés — même forme de
    résultat dans les deux cas, un chemin dans le graphe.

    comptes[0] est le point de départ, comptes[-1] le point d'arrivée.
    transaction_ids[i] relie comptes[i] à comptes[i+1] — donc toujours
    len(transaction_ids) == len(comptes) - 1.
    """

    comptes: list[str]
    transaction_ids: list[UUID]

    @property
    def nb_sauts(self) -> int:
        return len(self.transaction_ids)


@dataclass(frozen=True)
class ComptePont:
    """Un compte qui relie deux comptes déjà alertés (Brique 5), sans être lui-même alerté.

    Résultat de la requête b). Le compte pont n'a jamais franchi le
    seuil de scoring individuellement — c'est sa position topologique
    entre deux investigations distinctes qui le rend intéressant,
    invisible au scoring par compte isolé de la Brique 5.
    """

    compte_pont: str
    compte_alerte_source: str
    compte_alerte_cible: str
    transaction_entrante_id: UUID
    transaction_sortante_id: UUID
