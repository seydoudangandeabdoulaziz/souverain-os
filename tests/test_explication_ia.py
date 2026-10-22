import json
from unittest.mock import patch

import pytest
from souverain_app.explication_ia import (
    FaitsAlerte,
    _valider_selection,
    construire_repli,
    expliquer_alerte,
)


def faits(**overrides):
    valeurs = {
        "compte_pivot": "cpt_test",
        "score": 45,
        "seuil": 50,
        "statut": "ouverte",
        "motifs": (("compte_pivot", 30), ("transactions_nocturnes", 15)),
        "nombre_transactions": None,
        "autres_faits": (),
    }
    valeurs.update(overrides)
    return FaitsAlerte(**valeurs)


def selection_valide(faits_alerte=None):
    faits_alerte = faits_alerte or faits()
    return {
        "claims": [
            "compte",
            "comparaison_score_seuil",
            "statut",
            "motifs",
            "transactions_indisponibles",
        ]
    }


def test_repli_distingue_score_et_seuil():
    texte = construire_repli(faits())
    assert "score est de 45, inférieur au seuil de 50" in texte
    assert "nombre de transactions n'est pas disponible" in texte


@pytest.mark.parametrize(
    "score,attendu",
    [
        (40, "inférieur au seuil"),
        (50, "égal au seuil"),
        (60, "supérieur au seuil"),
    ],
)
def test_repli_compare_score_et_seuil(score, attendu):
    assert attendu in construire_repli(faits(score=score))


def test_repli_separe_poids_et_nombre_transactions():
    texte = construire_repli(faits(nombre_transactions=20))
    assert "poids 30" in texte
    assert "nombre de transactions fourni est 20" in texte


def test_selection_json_valide():
    assert _valider_selection(
        json.dumps(selection_valide()), faits()
    ) == selection_valide()["claims"]


@pytest.mark.parametrize(
    "contenu",
    [
        "pas du JSON",
        "[]",
        "{}",
        '{"claims": "compte"}',
        '{"claims": ["compte", 42]}',
        '{"claims": ["compte", "inconnu"]}',
        '{"claims": ["compte", "compte", "statut", "motifs", "transactions_indisponibles"]}',
        '{"claims": ["compte", "comparaison_score_seuil", "statut", "motifs"]}',
        (
            '{"claims": ["compte", "comparaison_score_seuil", "statut", "motifs", '
            '"transactions_indisponibles"], "texte": "fraude confirmée"}'
        ),
        "null",
    ],
)
def test_selection_rejette_json_invalide_ou_non_autorise(contenu):
    assert _valider_selection(contenu, faits()) is None


def test_selection_refuse_motif_si_aucun_motif_fourni():
    donnees = {
        "claims": [
            "compte",
            "comparaison_score_seuil",
            "statut",
            "motifs",
            "transactions_indisponibles",
        ]
    }
    assert _valider_selection(
        json.dumps(donnees), faits(motifs=())
    ) is None


def test_selection_transactions_disponibles():
    donnees = {
        "claims": [
            "compte",
            "comparaison_score_seuil",
            "statut",
            "motifs",
            "transactions_disponibles",
        ]
    }
    assert _valider_selection(
        json.dumps(donnees), faits(nombre_transactions=20)
    ) == donnees["claims"]


@pytest.mark.asyncio
async def test_expliquer_alerte_construit_texte_cote_serveur():
    claims = selection_valide()["claims"]
    with patch(
        "souverain_app.explication_ia._requete_ollama_sync",
        return_value=json.dumps({"claims": claims}),
    ):
        texte, repli = await expliquer_alerte(faits())

    assert repli is False
    assert "cpt_test" in texte
    assert "score est de 45" in texte
    assert "poids 30" in texte
    assert "15 transactions" not in texte


@pytest.mark.asyncio
async def test_expliquer_alerte_repli_si_selection_invalide():
    with patch(
        "souverain_app.explication_ia._requete_ollama_sync",
        return_value='{"claims":["compte","inconnu"]}',
    ):
        texte, repli = await expliquer_alerte(faits())

    assert repli is True
    assert texte == construire_repli(faits())


@pytest.mark.asyncio
async def test_expliquer_alerte_repli_si_ollama_echoue():
    with patch(
        "souverain_app.explication_ia._requete_ollama_sync",
        side_effect=RuntimeError("erreur interne"),
    ):
        texte, repli = await expliquer_alerte(faits())

    assert repli is True
    assert texte == construire_repli(faits())
    assert "erreur interne" not in texte


def test_accepte_poids_historique_different_de_la_configuration():
    faits_historiques = faits(motifs=(("compte_pivot", 25),))
    texte = construire_repli(faits_historiques)

    assert "compte_pivot (poids 25)" in texte
