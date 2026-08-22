"""Constantes de calibrage de la Brique 5 — toutes PROVISOIRES.

Isolées dans ce fichier plutôt que noyées dans agregation.py : ce sont
les 3 valeurs que le fondateur recalibrera après la première exécution
réelle contre les 69 détections de tenant_ne (Brique 4). Les isoler
rend le futur diff Git minimal et explicite (un seul fichier touché).

Statut : point de départ analytique, validé comme provisoire par le
fondateur — pas une mesure calée sur données réelles.
"""

from __future__ import annotations

# Poids par pattern_type, utilisés une seule fois par pattern_type
# distinct présent sur la fenêtre pour un compte_pivot donné (voir
# agregation.py — déduplication avant sommation).
#
# Raisonnement (validé) :
# - compte_pivot (30)          : signal le plus direct de hub de
#                                 redistribution, cœur du Hawala.
# - structure_etoile (25)      : diffusion multi-destinataires
#                                 simultanée, signature Hawala forte.
# - micro_fractionnement (20)  : contournement de seuil délibéré,
#                                 comportement clairement évasif.
# - transactions_nocturnes (15): signal réel mais plus bruité — pattern
#                                 le plus fréquent observé en Brique 4
#                                 (26/69 détections réelles), donc
#                                 moins discriminant seul.
# - flux_frontalier (10)       : documenté en Brique 4 comme un
#                                 placeholder par convention de nommage,
#                                 pas une vraie détection géographique —
#                                 poids volontairement bas tant que ce
#                                 n'est pas une vraie règle.
POIDS_PAR_PATTERN: dict[str, int] = {
    "compte_pivot": 30,
    "structure_etoile": 25,
    "micro_fractionnement": 20,
    "transactions_nocturnes": 15,
    "flux_frontalier": 10,
}

# Durée de la fenêtre glissante sur laquelle les détections d'un même
# compte_pivot sont agrégées. 7 jours : assez long pour capter la
# convergence de plusieurs patterns sur un compte (comptes dormants
# réactivés, redistribution en chaîne — Bloc 7), assez court pour que
# le score reste un reflet de l'activité récente.
FENETRE_JOURS: int = 7

# Score à partir duquel une alerte est créée/mise à jour. 50 : un seul
# pattern isolé, même le plus lourd (compte_pivot = 30), ne déclenche
# pas d'alerte seul — l'alerte naît de la convergence d'au moins deux
# comportements distincts significatifs.
SEUIL_ALERTE: int = 50
