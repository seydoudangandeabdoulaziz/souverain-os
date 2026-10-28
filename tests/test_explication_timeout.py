"""Timeout Ollama configurable par SOUVERAIN_OLLAMA_TIMEOUT (étape 6B, ADR-007).

Valeur valide : nombre fini entre 5 et 300 secondes, bornes incluses.
Absente, vide, non numérique, NaN, infinie ou hors bornes : 120 secondes.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
from datetime import date
from typing import Any

import pytest

from souverain_app import explication_ia as ia

_VARIABLE = "SOUVERAIN_OLLAMA_TIMEOUT"


def _faits() -> ia.FaitsAlerte:
    return ia.FaitsAlerte(
        compte_pivot="pivot_211",
        score=60,
        seuil=50,
        statut="ouverte",
        motifs=(("structure_etoile", 25),),
        nombre_transactions=None,
        fenetre_debut=date(2026, 9, 14),
        fenetre_fin=date(2026, 9, 21),
    )


def test_la_valeur_par_defaut_et_les_bornes_sont_celles_de_l_adr() -> None:
    assert ia.TIMEOUT_ENV_VAR == _VARIABLE
    assert ia.DEFAULT_TIMEOUT_SECONDS == 120.0
    assert ia.MIN_TIMEOUT_SECONDS == 5.0
    assert ia.MAX_TIMEOUT_SECONDS == 300.0


def test_variable_absente_donne_120_secondes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(_VARIABLE, raising=False)
    assert ia.timeout_configure() == 120.0


@pytest.mark.parametrize(
    ("brut", "attendu"),
    [
        ("5", 5.0),
        ("5.0", 5.0),
        ("300", 300.0),
        ("300.0", 300.0),
        ("60", 60.0),
        ("12.5", 12.5),
        (" 45 ", 45.0),
        ("1e2", 100.0),
        ("120", 120.0),
    ],
)
def test_valeurs_valides_et_bornes_incluses(
    brut: str, attendu: float, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(_VARIABLE, brut)
    assert ia.timeout_configure() == attendu


@pytest.mark.parametrize("brut", ["4.99", "4", "0", "-1", "-300", "300.01", "301", "1e9"])
def test_valeurs_hors_bornes_retombent_sur_120(brut: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(_VARIABLE, brut)
    assert ia.timeout_configure() == 120.0


@pytest.mark.parametrize(
    "brut", ["", "   ", "abc", "30s", "5,5", "nan", "NaN", "inf", "-inf", "Infinity", "0x10"]
)
def test_valeurs_invalides_retombent_sur_120(brut: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(_VARIABLE, brut)
    assert ia.timeout_configure() == 120.0


def test_la_variable_est_lue_a_chaque_appel_pas_a_l_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(_VARIABLE, "20")
    assert ia.timeout_configure() == 20.0
    monkeypatch.setenv(_VARIABLE, "40")
    assert ia.timeout_configure() == 40.0
    monkeypatch.delenv(_VARIABLE)
    assert ia.timeout_configure() == 120.0


def test_la_signature_ne_fige_plus_la_valeur_au_chargement() -> None:
    parametre = inspect.signature(ia.expliquer_alerte).parameters["timeout"]
    assert parametre.default is None


def _espionner(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Capture le timeout transmis à la requête Ollama et à asyncio.wait_for."""
    vu: dict[str, Any] = {}

    def faux(_url: str, _modele: str, faits: ia.FaitsAlerte, timeout: float) -> str:
        vu["requete"] = timeout
        return json.dumps({"claims": list(ia._identifiants_autorises(faits))})

    original = asyncio.wait_for

    async def espion(awaitable: Any, timeout: float | None = None) -> Any:
        vu["wait_for"] = timeout
        return await original(awaitable, timeout=timeout)

    monkeypatch.setattr(ia, "_requete_ollama_sync", faux)
    monkeypatch.setattr(ia.asyncio, "wait_for", espion)
    return vu


@pytest.mark.asyncio
async def test_sans_variable_le_comportement_par_defaut_est_inchange(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(_VARIABLE, raising=False)
    vu = _espionner(monkeypatch)

    texte, repli = await ia.expliquer_alerte(_faits())

    assert repli is False
    assert vu == {"requete": 120.0, "wait_for": 120.0}
    assert texte == " ".join(
        ia._construire_phrases(_faits())[i] for i in ia._identifiants_autorises(_faits())
    )


@pytest.mark.asyncio
async def test_la_variable_valide_est_appliquee_aux_deux_delais(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(_VARIABLE, "30")
    vu = _espionner(monkeypatch)

    await ia.expliquer_alerte(_faits())

    assert vu == {"requete": 30.0, "wait_for": 30.0}


@pytest.mark.asyncio
async def test_une_variable_invalide_donne_120_sans_planter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(_VARIABLE, "pas_un_nombre")
    vu = _espionner(monkeypatch)

    _texte, repli = await ia.expliquer_alerte(_faits())

    assert repli is False
    assert vu == {"requete": 120.0, "wait_for": 120.0}


@pytest.mark.asyncio
async def test_un_timeout_explicite_prime_sur_la_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(_VARIABLE, "200")
    vu = _espionner(monkeypatch)

    await ia.expliquer_alerte(_faits(), timeout=7.5)

    assert vu == {"requete": 7.5, "wait_for": 7.5}


@pytest.mark.asyncio
async def test_la_valeur_brute_de_la_variable_n_est_jamais_journalisee(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(_VARIABLE, "VALEUR_BRUTE_SECRETE")
    monkeypatch.setattr(ia, "_requete_ollama_sync", lambda *_a, **_k: "pas du json")
    caplog.set_level(logging.DEBUG)

    await ia.expliquer_alerte(_faits())

    assert "VALEUR_BRUTE_SECRETE" not in caplog.text
