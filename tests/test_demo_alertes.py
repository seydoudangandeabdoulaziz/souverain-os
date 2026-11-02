"""Script de démonstration : le mot de passe ne doit plus être dans le dépôt."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "demo_alertes.py"
_ANCIEN_MOT_DE_PASSE = "Demo-Souverain" + "-2026!"  # construit pour ne pas le réécrire en clair


def _charger() -> object:
    spec = importlib.util.spec_from_file_location("demo_alertes", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


demo = _charger()


def test_aucun_mot_de_passe_ecrit_en_clair_dans_le_script() -> None:
    source = _SCRIPT.read_text(encoding="utf-8")
    assert _ANCIEN_MOT_DE_PASSE not in source
    assert not hasattr(demo, "MOT_DE_PASSE")
    assert not re.search(r"(?i)(mot_de_passe|password)\s*=\s*[\"'][^\"']+[\"']", source)


def test_la_variable_d_environnement_est_utilisee(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOUVERAIN_DEMO_PASSWORD", "  choisi-par-le-fondateur-42  ")
    assert demo.mot_de_passe_demo() == "choisi-par-le-fondateur-42"  # type: ignore[attr-defined]


@pytest.mark.parametrize("valeur", [None, "", "   "])
def test_sans_variable_le_mot_de_passe_est_aleatoire(
    valeur: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    if valeur is None:
        monkeypatch.delenv("SOUVERAIN_DEMO_PASSWORD", raising=False)
    else:
        monkeypatch.setenv("SOUVERAIN_DEMO_PASSWORD", valeur)

    premier = demo.mot_de_passe_demo()  # type: ignore[attr-defined]
    second = demo.mot_de_passe_demo()  # type: ignore[attr-defined]

    assert len(premier) >= 16
    assert re.fullmatch(r"[A-Za-z0-9_-]+", premier)
    assert premier != second
    assert premier != _ANCIEN_MOT_DE_PASSE
