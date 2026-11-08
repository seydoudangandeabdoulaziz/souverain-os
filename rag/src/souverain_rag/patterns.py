"""Vocabulaire fermé des requêtes documentaires approuvées."""

from enum import StrEnum


class PatternType(StrEnum):
    COMPTE_PIVOT = "compte_pivot"
    FLUX_FRONTALIER = "flux_frontalier"
    MICRO_FRACTIONNEMENT = "micro_fractionnement"
    STRUCTURE_ETOILE = "structure_etoile"
    TRANSACTIONS_NOCTURNES = "transactions_nocturnes"


CANONICAL_QUERIES: dict[PatternType, str] = {
    PatternType.COMPTE_PIVOT: (
        "Références documentaires décrivant un compte pivot qui reçoit des fonds de plusieurs "
        "sources puis les redistribue rapidement à plusieurs destinataires."
    ),
    PatternType.FLUX_FRONTALIER: (
        "Références documentaires sur les flux financiers transfrontaliers et les risques associés "
        "aux transferts vers des zones frontalières."
    ),
    PatternType.MICRO_FRACTIONNEMENT: (
        "Références documentaires décrivant le fractionnement de montants en transactions "
        "répétées de faible valeur pour contourner des seuils de déclaration."
    ),
    PatternType.STRUCTURE_ETOILE: (
        "Références documentaires décrivant une structure en étoile où un émetteur transfère des "
        "fonds à de nombreux destinataires dans une courte période."
    ),
    PatternType.TRANSACTIONS_NOCTURNES: (
        "Références documentaires sur les transactions nocturnes inhabituelles effectuées depuis "
        "un compte jusque-là peu actif."
    ),
}


def construire_requete(type_pattern: PatternType) -> str:
    """Construit une requête depuis l'enum ; aucun texte libre n'est accepté."""
    if not isinstance(type_pattern, PatternType):
        raise TypeError("Le type de pattern doit appartenir au vocabulaire fermé.")
    return CANONICAL_QUERIES[type_pattern]
