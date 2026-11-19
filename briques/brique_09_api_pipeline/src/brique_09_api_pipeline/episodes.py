"""Logique pure de relecture par épisode d'activité (sans base de données).

Chaque règle de la Brique 4 garde son état par compte pivot, avec une fenêtre
d'au plus 6 h. Un trou de plus de 6 h dans l'activité d'un compte (émetteur
ou destinataire) vide donc toutes ses fenêtres : l'état de départ du moteur
est alors exactement celui d'un recalcul complet. On relit l'historique d'un
compte depuis le début de son épisode d'activité courant.
"""

from __future__ import annotations

from bisect import bisect_left
from datetime import datetime, timedelta

ECART_EPISODE = timedelta(hours=6)
# Largeur de relecture à chaque étape ; None = tout l'historique (repli).
ETAPES: tuple[timedelta | None, ...] = (
    timedelta(hours=6),
    timedelta(hours=24),
    timedelta(hours=96),
    None,
)


def debut_episode(
    horodatages: list[datetime],
    t_min: datetime,
    borne_basse: datetime | None,
    ecart: timedelta = ECART_EPISODE,
) -> tuple[int, bool]:
    """Indice de début d'épisode dans `horodatages` (triés, tous >= borne_basse).

    Retourne (indice, besoin_plus_ancien). `besoin_plus_ancien` vaut True si
    l'épisode peut se prolonger au-delà de `borne_basse` : il faut alors
    relire plus loin. `borne_basse=None` signifie « historique complet ».
    """
    if not horodatages:
        return 0, False
    p = min(bisect_left(horodatages, t_min), len(horodatages) - 1)
    s = p
    while s > 0 and horodatages[s] - horodatages[s - 1] <= ecart:
        s -= 1
    besoin = s == 0 and borne_basse is not None and horodatages[0] - borne_basse <= ecart
    return s, besoin
