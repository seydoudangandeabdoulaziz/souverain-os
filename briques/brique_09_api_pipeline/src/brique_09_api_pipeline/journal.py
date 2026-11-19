"""Journal JSON minimal : jamais de compte, montant, secret ni corps de requête."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

_logger = logging.getLogger("souverain.api.pipeline")
_CHAMPS_AUTORISES = frozenset(
    {
        "client_id",
        "tenant_id",
        "recues",
        "inserees",
        "doublons_ignores",
        "conflits",
        "nouvelles_transactions",
        "comptes_touches",
        "transactions_relues",
        "detections_nouvelles",
        "replis_episode",
        "alertes_creees",
        "alertes_mises_a_jour",
        "duree_ms",
        "code",
        "scope",
    }
)


def journaliser(evenement: str, **champs: object) -> None:
    ligne = {"ts": datetime.now(UTC).isoformat(), "evenement": evenement}
    ligne.update({k: str(v) for k, v in champs.items() if k in _CHAMPS_AUTORISES})
    _logger.info(json.dumps(ligne, ensure_ascii=False, sort_keys=True))
