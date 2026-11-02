"""Garde-fou : les fichiers couverts par le gel du lot v2 ne changent pas par accident.

Toute modification volontaire de l'un d'eux impose un lot v3 et le rejeu complet
de la campagne (docs/ETAPE_6B_LOT_VALIDATION_V2.md, §6). Ce test échoue alors,
et c'est voulu : la décision doit être explicite.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from souverain_app import explication_ia as ia

_RACINE = Path(__file__).resolve().parents[1]
_DONNEES = _RACINE / "docs" / "etape_6b_donnees"
_GEL = json.loads((_DONNEES / "gel_v2.json").read_text(encoding="utf-8"))
_MESSAGE = "Fichier couvert par le gel du lot v2 : une modification impose un lot v3."


def _sha(chemin: Path) -> str:
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def test_le_controleur_est_celui_du_gel() -> None:
    assert _sha(Path(ia.__file__)) == _GEL["controleur_sha256"], _MESSAGE


def test_les_traductions_sont_celles_du_gel() -> None:
    fr = Path(ia.__file__).parent / "traductions" / "fr.py"
    assert _sha(fr) == _GEL["traductions_fr_sha256"], _MESSAGE


@pytest.mark.parametrize("nom", sorted(_GEL["fichiers_lot"]))
def test_les_fichiers_du_lot_sont_ceux_du_gel(nom: str) -> None:
    assert _sha(_DONNEES / nom) == _GEL["fichiers_lot"][nom], _MESSAGE


def test_le_prompt_et_les_options_sont_ceux_du_gel() -> None:
    spec = importlib.util.spec_from_file_location(
        "campagne_6b", _RACINE / "scripts" / "campagne_6b.py"
    )
    assert spec and spec.loader
    campagne = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(campagne)
    lot = json.loads((_DONNEES / "lot_v2.json").read_text(encoding="utf-8"))

    payload = campagne.capturer_payload(campagne.faits_bloc_b(lot["bloc_b"][-1]))

    systeme = payload["messages"][0]["content"].encode("utf-8")
    assert hashlib.sha256(systeme).hexdigest() == _GEL["prompt_systeme_sha256"], _MESSAGE
    assert payload["options"] == _GEL["options"]
    assert payload["format"] == _GEL["format"]
    assert payload["stream"] == _GEL["stream"]
