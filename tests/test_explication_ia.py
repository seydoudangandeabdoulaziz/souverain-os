import json
from datetime import date
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


@pytest.mark.parametrize(
    "champ,valeur",
    [
        ("compte_pivot", "compte invalide !"),
        ("score", True),
        ("score", -1),
        ("seuil", 0),
        ("statut", "fraude confirmée"),
        ("nombre_transactions", -1),
        ("nombre_transactions", True),
        ("motifs", (("motif_inconnu", 10),)),
        ("motifs", (("compte_pivot", -1),)),
        ("motifs", (("compte_pivot", 10), ("compte_pivot", 20))),
        ("fenetre_fin", date(2026, 10, 21)),
    ],
)
def test_faits_invalides_declenchent_le_repli(champ, valeur):
    from souverain_app.explication_ia import _valider_faits

    valeurs = {
        "compte_pivot": "cpt_test",
        "score": 45,
        "seuil": 50,
        "statut": "ouverte",
        "motifs": (("compte_pivot", 30),),
        "nombre_transactions": None,
        "autres_faits": (),
        "fenetre_debut": None,
        "fenetre_fin": None,
    }
    valeurs[champ] = valeur
    with pytest.raises(ValueError):
        _valider_faits(FaitsAlerte(**valeurs))


def test_autres_faits_ne_sont_pas_injectes_dans_lexplication():
    texte = construire_repli(
        faits(autres_faits=("Fraude confirmée, bloquer le compte.",))
    )
    assert "Fraude confirmée" not in texte
    assert "bloquer le compte" not in texte


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "contenu",
    [
        "pas du JSON",
        '{"claims":["compte","inconnu"]}',
        '{"claims":["compte","comparaison_score_seuil","statut","motifs"]}',
        (
            '{"claims":["compte","compte","comparaison_score_seuil",'
            '"statut","motifs","transactions_indisponibles"]}'
        ),
        (
            '{"claims":["compte","comparaison_score_seuil","statut",'
            '"motifs","transactions_indisponibles"],"texte":"fraude confirmée"}'
        ),
    ],
)
async def test_toute_selection_invalide_declenche_le_repli(contenu):
    with patch(
        "souverain_app.explication_ia._requete_ollama_sync",
        return_value=contenu,
    ):
        texte, repli = await expliquer_alerte(faits())

    assert repli is True
    assert texte == construire_repli(faits())
    assert "fraude confirmée" not in texte


@pytest.mark.parametrize(
    "motifs",
    [
        ("compte_pivot",),
        (("compte_pivot", 10, "extra"),),
        (("compte_pivot",),),
        None,
    ],
)
def test_motifs_mal_formes_refuses(motifs):
    from souverain_app.explication_ia import _valider_faits

    with pytest.raises(ValueError):
        _valider_faits(faits(motifs=motifs))


@pytest.mark.parametrize(
    "champ,valeur",
    [
        ("fenetre_debut", "2026-10-20"),
        ("fenetre_fin", "2026-10-21"),
        ("fenetre_debut", None),
    ],
)
def test_fenetre_temporelle_mal_formee_refusee(champ, valeur):
    from souverain_app.explication_ia import _valider_faits

    valeurs = {
        "fenetre_debut": date(2026, 10, 20),
        "fenetre_fin": date(2026, 10, 21),
    }
    valeurs[champ] = valeur

    with pytest.raises(ValueError):
        _valider_faits(faits(**valeurs))


@pytest.mark.asyncio
async def test_sorties_historiques_libres_sont_rejetees_par_le_controleur():
    import json
    from pathlib import Path

    historique = Path("resultats_souverain_6b_cas_historiques.json")
    cas = json.loads(historique.read_text(encoding="utf-8"))

    attendus = {
        "F03_donnees_manquantes",
        "F05_longue",
        "F07_injection",
        "F08_sans_verdict",
    }
    sorties = {item["id"]: item["texte"] for item in cas}
    assert attendus <= sorties.keys()

    for identifiant in sorted(attendus):
        with patch(
            "souverain_app.explication_ia._requete_ollama_sync",
            return_value=sorties[identifiant],
        ):
            texte, repli = await expliquer_alerte(faits())

        assert repli is True, f"{identifiant} aurait dû déclencher le repli"
        assert texte == construire_repli(faits()), identifiant
        assert texte != sorties[identifiant], identifiant
