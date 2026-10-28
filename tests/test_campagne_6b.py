"""Tests du script scripts/campagne_6b.py avec un faux serveur Ollama local.

Aucun vrai modèle : ces tests vérifient la mécanique du gel et du bloc B
(plan d'appels, détection d'écart, critère bloquant, synthèse). La campagne
réelle se joue sur la machine du fondateur.
"""

from __future__ import annotations

import importlib.util
import json
import threading
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "campagne_6b.py"
_MODELE = "ministral-3:8b-instruct-2512-q4_K_M"
_DIGEST = "1922accd5827" + "0" * 52


def _charger_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("campagne_6b", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


campagne = _charger_script()


class _Etat:
    mode = "valide"  # « valide » ou « invalide »
    ps = "ok"  # « ok », « absent » (404), « invalide » (corps non JSON) ou « sans_modele »
    appels_chat = 0


class _Gestionnaire(BaseHTTPRequestHandler):
    def log_message(self, *_args: object) -> None:
        return

    def _repondre(self, corps: dict[str, Any]) -> None:
        donnees = json.dumps(corps).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(donnees)))
        self.end_headers()
        self.wfile.write(donnees)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/api/ps":
            self._repondre_ps()
            return
        self._repondre({"models": [{"name": _MODELE, "digest": _DIGEST}]})

    def _repondre_ps(self) -> None:
        if _Etat.ps == "absent":
            self.send_error(404)
            return
        if _Etat.ps == "invalide":
            donnees = b"ceci n'est pas du json"
            self.send_response(200)
            self.send_header("Content-Length", str(len(donnees)))
            self.end_headers()
            self.wfile.write(donnees)
            return
        if _Etat.ps == "sans_modele":
            self._repondre({"models": []})
            return
        expire = (datetime.now(UTC) + timedelta(seconds=300)).isoformat()
        self._repondre(
            {"models": [{"name": _MODELE, "context_length": 4096, "expires_at": expire}]}
        )

    def do_POST(self) -> None:  # noqa: N802
        longueur = int(self.headers["Content-Length"])
        requete = json.loads(self.rfile.read(longueur))
        _Etat.appels_chat += 1
        if _Etat.mode == "invalide":
            contenu = "Ce compte est un fraudeur."
        else:
            utilisateur = json.loads(requete["messages"][1]["content"])
            contenu = json.dumps({"claims": list(reversed(utilisateur["identifiants_autorises"]))})
        self._repondre({"message": {"content": contenu}})


@pytest.fixture
def faux_ollama(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    _Etat.mode = "valide"
    _Etat.ps = "ok"
    _Etat.appels_chat = 0
    serveur = ThreadingHTTPServer(("127.0.0.1", 0), _Gestionnaire)
    fil = threading.Thread(target=serveur.serve_forever, daemon=True)
    fil.start()
    url = f"http://127.0.0.1:{serveur.server_address[1]}"
    monkeypatch.setenv("SOUVERAIN_OLLAMA_URL", url)
    monkeypatch.setenv("SOUVERAIN_OLLAMA_MODEL", _MODELE)
    yield url
    serveur.shutdown()
    serveur.server_close()


def _geler(tmp_path: Path) -> Path:
    gel = tmp_path / "gel.json"
    assert campagne.main(["geler", "--gel", str(gel)]) == 0
    return gel


def _executer(gel: Path, sortie: Path, *extra: str) -> int:
    code: int = campagne.main(
        ["executer", "--gel", str(gel), "--sortie", str(sortie), "--sans-docker", *extra]
    )
    return code


def _rapport(sortie: Path) -> dict[str, Any]:
    fichiers = sorted(sortie.glob("resultats_bloc_b_*.json"))
    assert len(fichiers) == 1
    rapport: dict[str, Any] = json.loads(fichiers[0].read_text("utf-8"))
    return rapport


def test_le_gel_consigne_les_empreintes(faux_ollama: str, tmp_path: Path) -> None:
    gel = json.loads(_geler(tmp_path).read_text("utf-8"))

    assert gel["modele_digest_complet"].startswith("1922accd5827")
    assert gel["options"] == {"temperature": 0, "seed": 42}
    assert gel["format"] == "json" and gel["stream"] is False
    assert len(gel["prompt_systeme_sha256"]) == 64
    assert len(gel["controleur_sha256"]) == 64
    assert set(gel["fichiers_lot"]) == {"lot_v2.json", "termes_interdits_v1.json"}
    assert gel["image_ollama_compose"].startswith("ollama/ollama@sha256:")


def test_le_gel_existant_n_est_pas_ecrase(faux_ollama: str, tmp_path: Path) -> None:
    gel = _geler(tmp_path)
    assert campagne.main(["geler", "--gel", str(gel)]) == 2


def test_le_bloc_b_joue_24_appels_plus_un_appel_a_froid(faux_ollama: str, tmp_path: Path) -> None:
    gel = _geler(tmp_path)
    assert _executer(gel, tmp_path, "--froid") == 0

    rapport = _rapport(tmp_path)
    synthese = rapport["synthese"]
    assert len(rapport["appels"]) == 25
    assert _Etat.appels_chat == 25
    assert synthese["appels_chauds"] == 24
    assert synthese["bloquant_acceptee_non_conforme"] == 0
    assert synthese["taux_repli_global"] == 0
    assert synthese["duree_froid_s"] is not None
    assert all(e["repetable"] for e in synthese["par_entree"].values())
    assert len(synthese["par_entree"]) == 8
    assert synthese["timeout_cible_s"] >= synthese["duree_froid_s"]


def test_des_reponses_invalides_donnent_des_replis_sans_echec_bloquant(
    faux_ollama: str, tmp_path: Path
) -> None:
    gel = _geler(tmp_path)
    _Etat.mode = "invalide"

    assert _executer(gel, tmp_path) == 0

    synthese = _rapport(tmp_path)["synthese"]
    assert synthese["taux_repli_global"] == 1.0
    assert synthese["bloquant_acceptee_non_conforme"] == 0


def test_un_lot_modifie_apres_le_gel_empeche_l_execution(faux_ollama: str, tmp_path: Path) -> None:
    gel = _geler(tmp_path)
    contenu = json.loads(gel.read_text("utf-8"))
    contenu["fichiers_lot"]["lot_v2.json"] = "0" * 64
    gel.write_text(json.dumps(contenu), "utf-8")

    assert _executer(gel, tmp_path) == 2
    assert _Etat.appels_chat == 0, "Aucun appel ne doit partir si le gel est rompu."


def test_executer_sans_gel_est_refuse(faux_ollama: str, tmp_path: Path) -> None:
    assert _executer(tmp_path / "absent.json", tmp_path) == 2


def test_un_digest_different_rompt_le_gel(faux_ollama: str, tmp_path: Path) -> None:
    gel = _geler(tmp_path)
    contenu = json.loads(gel.read_text("utf-8"))
    contenu["modele_digest_complet"] = "ffff" + contenu["modele_digest_complet"][4:]
    gel.write_text(json.dumps(contenu), "utf-8")

    assert _executer(gel, tmp_path) == 2


def test_une_selection_acceptee_non_conforme_est_un_echec_bloquant(
    faux_ollama: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gel = _geler(tmp_path)
    monkeypatch.setattr(campagne.ia, "_valider_selection", lambda _brut, _faits: ["compte"])

    assert _executer(gel, tmp_path) == 1
    assert _rapport(tmp_path)["synthese"]["bloquant_acceptee_non_conforme"] == 24


def test_percentile_et_analyse_de_la_memoire_docker() -> None:
    valeurs = [float(i) for i in range(1, 25)]
    assert campagne.percentile(valeurs, 0.5) == 12.0
    assert campagne.percentile(valeurs, 0.95) == 23.0
    assert campagne.octets_depuis_docker("6.53GiB / 15.4GiB") == int(6.53 * 1024**3)
    assert campagne.octets_depuis_docker("512MiB / 15GiB") == 512 * 1024**2
    assert campagne.octets_depuis_docker("n/a") is None


def test_ollama_injoignable_donne_un_message_clair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SOUVERAIN_OLLAMA_URL", "http://127.0.0.1:9")
    assert campagne.main(["geler", "--gel", str(tmp_path / "gel.json")]) == 3


def test_le_gel_consigne_la_variable_de_timeout_et_ses_bornes(
    faux_ollama: str, tmp_path: Path
) -> None:
    gel = json.loads(_geler(tmp_path).read_text("utf-8"))

    assert gel["timeout_code_secondes"] == 120.0
    assert gel["timeout_variable"] == "SOUVERAIN_OLLAMA_TIMEOUT"
    assert (gel["timeout_min_s"], gel["timeout_max_s"]) == (5.0, 300.0)


def test_le_rapport_enregistre_le_contexte_et_le_keep_alive_effectifs(
    faux_ollama: str, tmp_path: Path
) -> None:
    gel = _geler(tmp_path)
    assert _executer(gel, tmp_path) == 0

    rapport = _rapport(tmp_path)
    assert rapport["timeout_utilise_s"] == 120.0
    assert set(rapport["releves_api_ps"]) == {"apres_premier_appel", "fin_campagne"}
    for releve in rapport["releves_api_ps"].values():
        assert releve["disponible"] is True
        assert releve["context_length"] == 4096
        assert 290 <= releve["keep_alive_effectif_approx_s"] <= 300


@pytest.mark.parametrize("mode_ps", ["absent", "invalide", "sans_modele"])
def test_api_ps_indisponible_ne_fait_pas_echouer_la_campagne(
    mode_ps: str, faux_ollama: str, tmp_path: Path
) -> None:
    gel = _geler(tmp_path)
    _Etat.ps = mode_ps

    assert _executer(gel, tmp_path) == 0

    rapport = _rapport(tmp_path)
    assert rapport["synthese"]["appels_chauds"] == 24
    for releve in rapport["releves_api_ps"].values():
        assert releve["disponible"] is False
        assert releve["raison"]
        assert "context_length" not in releve


def test_un_timeout_different_du_gel_empeche_la_campagne(
    faux_ollama: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gel = _geler(tmp_path)
    monkeypatch.setenv("SOUVERAIN_OLLAMA_TIMEOUT", "60")

    assert _executer(gel, tmp_path) == 2
    assert _Etat.appels_chat == 0, "Aucun appel ne doit partir hors des conditions gelées."


@pytest.mark.parametrize("valeur", ["120", "pas_un_nombre", "9999"])
def test_une_variable_equivalente_a_120_secondes_reste_acceptee(
    valeur: str, faux_ollama: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """« 120 » vaut le défaut ; une valeur invalide ou hors bornes retombe à 120."""
    gel = _geler(tmp_path)
    monkeypatch.setenv("SOUVERAIN_OLLAMA_TIMEOUT", valeur)

    assert _executer(gel, tmp_path) == 0
    assert _rapport(tmp_path)["timeout_utilise_s"] == 120.0
