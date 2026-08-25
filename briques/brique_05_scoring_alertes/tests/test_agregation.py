"""Tests unitaires de agreger_par_compte() — aucune base de données.

Couvre les cas identifiés pendant l'analyse validée :
- déduplication multi-occurrences d'un même pattern ;
- combinaison de patterns franchissant/ne franchissant pas le seuil ;
- un compte avec un seul pattern lourd (30) qui reste sous le seuil ;
- ScoreCompte.detection_ids contient TOUTES les détections du compte,
  pas seulement une par pattern déduplié.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from brique_05_scoring_alertes.agregation import agreger_par_compte
from brique_05_scoring_alertes.modeles import DetectionNonTraitee
from brique_05_scoring_alertes.seuils import SEUIL_ALERTE

FENETRE_DEBUT = datetime(2026, 8, 1, tzinfo=UTC)
FENETRE_FIN = datetime(2026, 8, 8, tzinfo=UTC)


def _detection(compte_pivot: str, pattern_type: str) -> DetectionNonTraitee:
    return DetectionNonTraitee(
        detection_id=uuid4(),
        compte_pivot=compte_pivot,
        pattern_type=pattern_type,
        detected_at=FENETRE_DEBUT,
    )


def test_pattern_repete_ne_compte_qu_une_fois() -> None:
    """10 occurrences du même pattern pour un compte = 1 seule contribution au score."""
    detections = [_detection("compte_a", "micro_fractionnement") for _ in range(10)]

    resultats = agreger_par_compte(detections, FENETRE_DEBUT, FENETRE_FIN)

    assert len(resultats) == 1
    score = resultats[0]
    assert score.compte_pivot == "compte_a"
    assert score.pattern_types_impliques == ["micro_fractionnement"]
    assert score.score == 20
    # Mais TOUTES les détections doivent rester tracées, pour être
    # marquées traitées — la dédup n'affecte que le score.
    assert len(score.detection_ids) == 10


def test_combinaison_de_patterns_franchit_le_seuil() -> None:
    """compte_pivot (30) + micro_fractionnement (20) = 50 >= SEUIL_ALERTE."""
    detections = [
        _detection("compte_b", "compte_pivot"),
        _detection("compte_b", "micro_fractionnement"),
    ]

    resultats = agreger_par_compte(detections, FENETRE_DEBUT, FENETRE_FIN)

    assert len(resultats) == 1
    assert resultats[0].score == 50
    assert resultats[0].score >= SEUIL_ALERTE
    assert resultats[0].pattern_types_impliques == ["compte_pivot", "micro_fractionnement"]


def test_pattern_lourd_seul_reste_sous_le_seuil() -> None:
    """compte_pivot (30) seul ne suffit pas à franchir SEUIL_ALERTE (50)."""
    detections = [_detection("compte_c", "compte_pivot")]

    resultats = agreger_par_compte(detections, FENETRE_DEBUT, FENETRE_FIN)

    assert len(resultats) == 1
    assert resultats[0].score == 30
    assert resultats[0].score < SEUIL_ALERTE


def test_structure_etoile_et_nocturne_reste_sous_le_seuil() -> None:
    """25 + 15 = 40 < 50 : combinaison volontairement insuffisante (cas validé à l'analyse)."""
    detections = [
        _detection("compte_d", "structure_etoile"),
        _detection("compte_d", "transactions_nocturnes"),
    ]

    resultats = agreger_par_compte(detections, FENETRE_DEBUT, FENETRE_FIN)

    assert resultats[0].score == 40
    assert resultats[0].score < SEUIL_ALERTE


def test_plusieurs_comptes_distincts_sont_agreges_separement() -> None:
    detections = [
        _detection("compte_e", "compte_pivot"),
        _detection("compte_f", "flux_frontalier"),
    ]

    resultats = agreger_par_compte(detections, FENETRE_DEBUT, FENETRE_FIN)

    comptes = {r.compte_pivot: r for r in resultats}
    assert len(resultats) == 2
    assert comptes["compte_e"].score == 30
    assert comptes["compte_f"].score == 10


def test_details_contient_le_poids_par_pattern_present() -> None:
    detections = [
        _detection("compte_g", "structure_etoile"),
        _detection("compte_g", "compte_pivot"),
    ]

    resultats = agreger_par_compte(detections, FENETRE_DEBUT, FENETRE_FIN)

    assert resultats[0].details == {"structure_etoile": 25, "compte_pivot": 30}


def test_fenetre_reportee_telle_quelle_sur_chaque_score() -> None:
    detections = [_detection("compte_h", "nocturne_inconnu_pattern")]

    resultats = agreger_par_compte(detections, FENETRE_DEBUT, FENETRE_FIN)

    assert resultats[0].fenetre_debut == FENETRE_DEBUT
    assert resultats[0].fenetre_fin == FENETRE_FIN
    # Pattern inconnu (défensif, ex. future règle) : poids 0, pas de crash.
    assert resultats[0].score == 0


def test_aucune_detection_donne_aucun_resultat() -> None:
    assert agreger_par_compte([], FENETRE_DEBUT, FENETRE_FIN) == []
