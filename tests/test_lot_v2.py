"""Lot de validation v2 — blocs A (couche déterministe) et C (contrôleur).

Définition : docs/ETAPE_6B_LOT_VALIDATION_V2.md. Données : docs/etape_6b_donnees/.
Ces tests ne font appel ni au modèle ni à la base de données. Le bloc B
(modèle réel) est exécuté par le script de campagne, après le gel du lot.
"""

from __future__ import annotations

import itertools
import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from souverain_app.traductions import t
from souverain_app.traductions.fr import TEXTES_FR

from souverain_app import explication_ia as ia

_RACINE = Path(__file__).resolve().parents[1]
_DONNEES = _RACINE / "docs" / "etape_6b_donnees"
_LOT: dict[str, Any] = json.loads((_DONNEES / "lot_v2.json").read_text("utf-8"))
_TERMES: dict[str, Any] = json.loads((_DONNEES / "termes_interdits_v1.json").read_text("utf-8"))


def _faits(donnees: dict[str, Any]) -> ia.FaitsAlerte:
    return ia.FaitsAlerte(
        compte_pivot=donnees["compte_pivot"],
        score=donnees["score"],
        seuil=donnees["seuil"],
        statut=donnees["statut"],
        motifs=tuple((nom, poids) for nom, poids in donnees["motifs"]),
        nombre_transactions=donnees["nombre_transactions"],
        fenetre_debut=(
            date.fromisoformat(donnees["fenetre_debut"]) if donnees["fenetre_debut"] else None
        ),
        fenetre_fin=(
            date.fromisoformat(donnees["fenetre_fin"]) if donnees["fenetre_fin"] else None
        ),
    )


def _normaliser(texte: str) -> str:
    """Minuscules, sans accents, apostrophes droites, espaces unifiés."""
    decompose = unicodedata.normalize("NFD", texte.lower())
    sans_accents = "".join(c for c in decompose if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", sans_accents.replace("’", "'"))


def _termes_interdits_trouves(texte: str) -> list[str]:
    """Applique la liste de la grille §6 au texte normalisé."""
    n = _normaliser(texte)
    debut = r"(?<![a-z0-9_])"
    trouves: list[str] = []
    for mot in _TERMES["mots_exacts"]:
        if re.search(rf"{debut}{re.escape(mot)}[a-z]{{0,2}}(?![a-z0-9_])", n):
            trouves.append(mot)
    for prefixe in _TERMES["prefixes"]:
        if re.search(rf"{debut}{re.escape(prefixe)}[a-z]*", n):
            trouves.append(prefixe + "*")
    for expression in _TERMES["expressions"]:
        if expression in n:
            trouves.append(expression)
    for motif in _TERMES["motifs_regex"]:
        if re.search(motif, n):
            trouves.append(motif)
    return trouves


_BLOC_A_ACCEPTEES = [c for c in _LOT["bloc_a"] if c["attendu"]["controle"] == "acceptee"]
_BLOC_A_REJETEES = [c for c in _LOT["bloc_a"] if c["attendu"]["controle"] == "rejetee"]


def test_le_lot_a_la_composition_prevue() -> None:
    assert len(_LOT["bloc_a"]) == 16
    assert len(_LOT["bloc_b"]) == 8
    assert len(_LOT["bloc_c"]["invalides"]) == 12  # C05 à C16, C01 à C04 = témoins
    assert len(_LOT["bloc_c"]["valides"]) == 5


# --------------------------------------------------------------------------
# Bloc A — couche déterministe
# --------------------------------------------------------------------------


@pytest.mark.parametrize("cas", _BLOC_A_ACCEPTEES, ids=lambda c: c["id"])
def test_bloc_a_c1_c2_nombres_exacts_avec_leur_nature(cas: dict[str, Any]) -> None:
    """C1 : aucun nombre inventé ni manquant. C2 : chaque nombre suit sa nature."""
    faits = _faits(cas["faits"])
    texte = ia.construire_repli(faits)

    # On retire les identifiants et les dates, qui relèvent de C4 : il reste
    # uniquement les nombres de valeur (score, seuil, poids, transactions).
    reste = texte.replace(faits.compte_pivot, "")
    for nom, _poids in faits.motifs:
        reste = reste.replace(nom, "")
    reste = re.sub(r"\d{4}-\d{2}-\d{2}", "", reste)
    trouves = sorted(int(x) for x in re.findall(r"\d+", reste))

    attendus = [faits.score, faits.seuil, *[p for _n, p in faits.motifs]]
    if faits.nombre_transactions is not None:
        attendus.append(faits.nombre_transactions)
    assert trouves == sorted(attendus)

    # C2 : chaque rôle est relié à son propre libellé, même si deux valeurs
    # sont égales (cas A1 et A2).
    assert re.search(rf"Le score est de {faits.score},", texte)
    assert re.search(rf"seuil de {faits.seuil}\.", texte)
    for nom, poids in faits.motifs:
        assert f"{nom} (poids {poids})" in texte
    if faits.nombre_transactions is not None:
        assert re.search(rf"transactions fourni est {faits.nombre_transactions}\.", texte)
    else:
        assert "n'est pas disponible" in texte


@pytest.mark.parametrize("cas", _BLOC_A_ACCEPTEES, ids=lambda c: c["id"])
def test_bloc_a_comparaison_score_seuil(cas: dict[str, Any]) -> None:
    faits = _faits(cas["faits"])
    attendu = TEXTES_FR[f"explication.comparaison.{cas['attendu']['comparaison']}"]
    assert attendu in ia.construire_repli(faits)


@pytest.mark.parametrize("cas", _BLOC_A_ACCEPTEES, ids=lambda c: c["id"])
def test_bloc_a_c4_aucun_identifiant_etranger(cas: dict[str, Any]) -> None:
    faits = _faits(cas["faits"])
    texte = ia.construire_repli(faits)
    autorises = {faits.compte_pivot, *(nom for nom, _p in faits.motifs)}
    cites = set(re.findall(r"\b[A-Za-z0-9]+(?:_[A-Za-z0-9]+)+\b", texte))
    assert cites <= autorises, f"identifiants étrangers : {cites - autorises}"
    assert "hub_010" not in texte


@pytest.mark.parametrize("cas", _BLOC_A_ACCEPTEES, ids=lambda c: c["id"])
def test_bloc_a_c3_aucun_terme_interdit_dans_les_phrases(cas: dict[str, Any]) -> None:
    faits = _faits(cas["faits"])
    phrases = ia._construire_phrases(faits)
    for identifiant, phrase in phrases.items():
        if identifiant == "statut":
            phrase = phrase.replace(faits.statut, "")  # exception de la grille §6
        assert _termes_interdits_trouves(phrase) == [], (identifiant, phrase)


@pytest.mark.parametrize("cas", _BLOC_A_ACCEPTEES, ids=lambda c: c["id"])
def test_bloc_a_c7_forme(cas: dict[str, Any]) -> None:
    faits = _faits(cas["faits"])
    texte = ia.construire_repli(faits)
    assert len(texte.split()) <= ia.MAX_WORDS
    assert len(ia._identifiants_autorises(faits)) <= 6  # une phrase par identifiant
    assert not re.search(r"[*#`]|^\s*[-•]\s", texte, flags=re.MULTILINE)


def test_bloc_a_f09_reproduit_f01() -> None:
    par_id = {c["id"]: c for c in _LOT["bloc_a"]}
    f01 = ia.construire_repli(_faits(par_id["F01"]["faits"]))
    f09 = ia.construire_repli(_faits(par_id["F09"]["faits"]))
    assert f01 == f09


@pytest.mark.asyncio
@pytest.mark.parametrize("cas", _BLOC_A_REJETEES, ids=lambda c: c["id"])
async def test_bloc_a_entrees_hostiles_rejetees_avant_le_modele(
    cas: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    appels: list[int] = []

    def espion(*_args: object, **_kwargs: object) -> str:
        appels.append(1)
        return ""

    monkeypatch.setattr(ia, "_requete_ollama_sync", espion)
    texte, repli = await ia.expliquer_alerte(_faits(cas["faits"]))

    assert appels == [], "Le modèle ne doit jamais voir une entrée invalide."
    assert repli is True
    assert texte == t("explication.donnees_insuffisantes")


def test_exception_statut_fermee_n_est_pas_un_terme_interdit() -> None:
    faits = _faits({**_BLOC_A_ACCEPTEES[0]["faits"], "statut": "fermee"})
    phrase = ia._construire_phrases(faits)["statut"]
    assert _termes_interdits_trouves(phrase) != []  # sans l'exception : « ferm* »
    assert _termes_interdits_trouves(phrase.replace(faits.statut, "")) == []


# Gabarits applicatifs fixes : relus par un humain, avec exceptions explicites.
# Toute nouvelle occurrence d'un terme interdit fait échouer le test.
_EXCEPTIONS_GABARITS = {
    # « Une vérification des données est nécessaire » : texte applicatif, pas
    # une sortie du modèle. À confirmer par le fondateur (voir compte rendu).
    "explication.donnees_insuffisantes": {"verifi*"},
    # « réponse rejetée » décrit l'état du système (réponse du modèle refusée
    # par le contrôleur), ce n'est pas une instruction à l'utilisateur.
    "explication.origine_repli": {"rejet*"},
}


@pytest.mark.parametrize("cle", sorted(TEXTES_FR))
def test_gabarits_fixes_sans_terme_interdit_hors_exceptions(cle: str) -> None:
    trouves = set(_termes_interdits_trouves(TEXTES_FR[cle]))
    assert trouves <= _EXCEPTIONS_GABARITS.get(cle, set()), (cle, trouves)


# --------------------------------------------------------------------------
# Bloc C — contrôleur
# --------------------------------------------------------------------------

_PROFILS = {nom: _faits(f) for nom, f in _LOT["bloc_c"]["profils"].items()}


def test_c01_a_c04_temoins_historiques_rejetes() -> None:
    temoins = _LOT["bloc_c"]["temoins_historiques"]
    sorties = json.loads((_RACINE / temoins["fichier"]).read_text("utf-8"))
    par_id = {item["id"]: item["texte"] for item in sorties}

    assert set(temoins["ids"]) <= par_id.keys()
    for identifiant in temoins["ids"]:
        assert ia._valider_selection(par_id[identifiant], _PROFILS["complet"]) is None


@pytest.mark.parametrize("cas", _LOT["bloc_c"]["invalides"], ids=lambda c: c["id"])
def test_c05_a_c16_reponses_invalides_rejetees(cas: dict[str, Any]) -> None:
    assert ia._valider_selection(cas["reponse"], _PROFILS["complet"]) is None


@pytest.mark.parametrize("cas", _LOT["bloc_c"]["valides"], ids=lambda c: c["id"])
def test_v01_a_v05_reponses_valides_acceptees(cas: dict[str, Any]) -> None:
    attendu = json.loads(cas["reponse"])["claims"]
    assert ia._valider_selection(cas["reponse"], _PROFILS[cas["profil"]]) == attendu


def test_toutes_les_permutations_sont_acceptees_et_aucune_alteration_ne_passe() -> None:
    faits = _PROFILS["complet"]
    autorises = list(ia._identifiants_autorises(faits))
    assert len(autorises) == 6

    for ordre in itertools.permutations(autorises):
        reponse = json.dumps({"claims": list(ordre)})
        assert ia._valider_selection(reponse, faits) == list(ordre)

    for position in range(len(autorises)):
        altere = list(autorises)
        altere[position] = "inconnu"
        assert ia._valider_selection(json.dumps({"claims": altere}), faits) is None
        double = list(autorises)
        double[position] = double[(position + 1) % len(double)]
        assert ia._valider_selection(json.dumps({"claims": double}), faits) is None


@pytest.mark.asyncio
async def test_selection_valide_produit_le_texte_dans_l_ordre_choisi(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    faits = _PROFILS["complet"]
    inverse = json.dumps({"claims": list(ia._identifiants_autorises(faits))[::-1]})
    monkeypatch.setattr(ia, "_requete_ollama_sync", lambda *_a, **_k: inverse)

    texte, repli = await ia.expliquer_alerte(faits)

    phrases = ia._construire_phrases(faits)
    attendu = " ".join(phrases[i] for i in reversed(ia._identifiants_autorises(faits)))
    assert repli is False
    assert texte == attendu


@pytest.mark.asyncio
async def test_reponse_invalide_declenche_le_repli_sans_nouvelle_tentative(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    faits = _PROFILS["complet"]
    appels: list[int] = []

    def faux(*_args: object, **_kwargs: object) -> str:
        appels.append(1)
        return "Ce compte est un fraudeur."

    monkeypatch.setattr(ia, "_requete_ollama_sync", faux)
    texte, repli = await ia.expliquer_alerte(faits)

    assert repli is True
    assert appels == [1], "Aucune régénération : un seul appel au modèle."
    assert texte == ia.construire_repli(faits)
