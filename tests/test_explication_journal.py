"""Journalisation C5 des replis de l'explication IA (étape 6B).

Vérifie, sur chacun des chemins de repli : une seule ligne JSON, les champs
requis, une cause appartenant à la liste fermée, et l'absence de tout texte
généré, message d'exception, identifiant de compte ou donnée sensible.
"""

from __future__ import annotations

import itertools
import json
import logging
import time
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.error import URLError
from uuid import UUID, uuid4

import pytest

from souverain_app import explication_ia as ia

_LOGGER = "souverain_app.explication"
_CHAMPS = {"evenement", "horodatage", "alerte_id", "cause", "duree_ms"}
_COMPTE_SECRET = "compte_secret_001"
_TEXTE_MODELE_SECRET = "TEXTE_GENERE_SECRET Ce compte est un fraudeur."
_MESSAGE_EXCEPTION_SECRET = "http://hote-interne-secret:11434 mot_de_passe_secret"


def _faits(compte: str = _COMPTE_SECRET) -> ia.FaitsAlerte:
    return ia.FaitsAlerte(
        compte_pivot=compte,
        score=60,
        seuil=50,
        statut="ouverte",
        motifs=(("structure_etoile", 25), ("micro_fractionnement", 20)),
        nombre_transactions=None,
        fenetre_debut=date(2026, 9, 14),
        fenetre_fin=date(2026, 9, 21),
    )


def _selection_valide(faits: ia.FaitsAlerte) -> str:
    return json.dumps({"claims": list(ia._identifiants_autorises(faits))})


def _installer(
    monkeypatch: pytest.MonkeyPatch, comportement: Callable[..., str]
) -> list[int]:
    appels: list[int] = []

    def faux(*_args: object, **_kwargs: object) -> str:
        appels.append(1)
        return comportement()

    monkeypatch.setattr(ia, "_requete_ollama_sync", faux)
    return appels


def _lever(exception: BaseException) -> Callable[[], str]:
    def lever() -> str:
        raise exception

    return lever


# Un scénario par chemin de repli : (cause attendue, préparation).
def _scenarios() -> dict[str, tuple[str, Callable[[pytest.MonkeyPatch], None], dict]]:
    def sans_modele(_mp: pytest.MonkeyPatch) -> None:
        return None

    def reseau(exc: BaseException) -> Callable[[pytest.MonkeyPatch], None]:
        def preparer(mp: pytest.MonkeyPatch) -> None:
            _installer(mp, _lever(exc))

        return preparer

    def reponse(texte: str) -> Callable[[pytest.MonkeyPatch], None]:
        def preparer(mp: pytest.MonkeyPatch) -> None:
            _installer(mp, lambda: texte)

        return preparer

    def trop_long(mp: pytest.MonkeyPatch) -> None:
        _installer(mp, lambda: _selection_valide(_faits()))
        mp.setattr(ia, "MAX_WORDS", 5)

    def controle_en_panne(mp: pytest.MonkeyPatch) -> None:
        _installer(mp, lambda: _selection_valide(_faits()))

        def panne(*_a: object, **_k: object) -> list[str]:
            raise RuntimeError(_MESSAGE_EXCEPTION_SECRET)

        mp.setattr(ia, "_valider_selection", panne)

    def delai_asyncio(mp: pytest.MonkeyPatch) -> None:
        def lent() -> str:
            time.sleep(0.4)
            return _selection_valide(_faits())

        _installer(mp, lent)

    return {
        "faits_invalides": (
            "faits_invalides",
            sans_modele,
            {"faits": _faits("compte avec espaces " + _COMPTE_SECRET)},
        ),
        "delai_socket": (
            "delai_depasse",
            reseau(TimeoutError(_MESSAGE_EXCEPTION_SECRET)),
            {},
        ),
        "delai_urllib": (
            "delai_depasse",
            reseau(URLError(TimeoutError(_MESSAGE_EXCEPTION_SECRET))),
            {},
        ),
        "delai_asyncio": ("delai_depasse", delai_asyncio, {"timeout": 0.05}),
        "reseau_refuse": (
            "modele_indisponible",
            reseau(ConnectionRefusedError(_MESSAGE_EXCEPTION_SECRET)),
            {},
        ),
        "erreur_ollama": (
            "modele_indisponible",
            reseau(ValueError(_MESSAGE_EXCEPTION_SECRET)),
            {},
        ),
        "texte_libre": ("reponse_invalide", reponse(_TEXTE_MODELE_SECRET), {}),
        "json_cle_en_trop": (
            "reponse_invalide",
            reponse(json.dumps({"claims": [], "texte": _TEXTE_MODELE_SECRET})),
            {},
        ),
        "controle_en_panne": ("reponse_invalide", controle_en_panne, {}),
        "texte_trop_long": ("texte_trop_long", trop_long, {}),
    }


_SCENARIOS = _scenarios()


def _evenements(caplog: pytest.LogCaptureFixture) -> list[dict[str, Any]]:
    return [
        json.loads(r.getMessage())
        for r in caplog.records
        if r.name == _LOGGER and r.levelno >= logging.WARNING
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("nom", sorted(_SCENARIOS))
async def test_chaque_chemin_de_repli_journalise_une_ligne_complete(
    nom: str, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    cause, preparer, options = _SCENARIOS[nom]
    preparer(monkeypatch)
    caplog.set_level(logging.WARNING, logger=_LOGGER)
    alerte_id = uuid4()

    texte, repli = await ia.expliquer_alerte(
        options.get("faits", _faits()),
        alerte_id=alerte_id,
        **{k: v for k, v in options.items() if k != "faits"},
    )

    assert repli is True
    evenements = _evenements(caplog)
    assert len(evenements) == 1, "Un repli, une seule ligne de journal."
    evenement = evenements[0]
    assert set(evenement) == _CHAMPS
    assert evenement["evenement"] == "explication_repli"
    assert evenement["cause"] == cause
    assert evenement["cause"] in ia.CAUSES_REPLI
    assert evenement["alerte_id"] == str(alerte_id)
    assert isinstance(evenement["duree_ms"], int | float) and evenement["duree_ms"] >= 0
    horodatage = datetime.fromisoformat(evenement["horodatage"])
    assert horodatage.tzinfo is not None
    assert abs((datetime.now(UTC) - horodatage).total_seconds()) < 60


@pytest.mark.asyncio
async def test_les_cinq_codes_sont_tous_atteints_et_seuls_ces_codes_existent(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    caplog.set_level(logging.WARNING, logger=_LOGGER)
    observees: set[str] = set()
    for _cause, preparer, options in _SCENARIOS.values():
        with monkeypatch.context() as mp:
            preparer(mp)
            caplog.clear()
            await ia.expliquer_alerte(
                options.get("faits", _faits()),
                **{k: v for k, v in options.items() if k != "faits"},
            )
            observees |= {e["cause"] for e in _evenements(caplog)}

    assert observees == ia.CAUSES_REPLI
    assert len(ia.CAUSES_REPLI) == 5


@pytest.mark.asyncio
@pytest.mark.parametrize("nom", sorted(_SCENARIOS))
async def test_le_journal_ne_contient_aucune_donnee_sensible(
    nom: str, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    _cause, preparer, options = _SCENARIOS[nom]
    preparer(monkeypatch)
    caplog.set_level(logging.DEBUG)  # on capture tout, tous loggers confondus

    await ia.expliquer_alerte(
        options.get("faits", _faits()),
        alerte_id=uuid4(),
        **{k: v for k, v in options.items() if k != "faits"},
    )

    journal = caplog.text + " ".join(str(r.__dict__) for r in caplog.records)
    for interdit in (
        _COMPTE_SECRET,
        "TEXTE_GENERE_SECRET",
        "fraudeur",
        "hote-interne-secret",
        "mot_de_passe_secret",
        "structure_etoile",  # les faits eux-mêmes n'ont rien à faire dans le journal
        "Le score est de",
    ):
        assert interdit not in journal, f"{interdit!r} fuit dans le journal ({nom})"


@pytest.mark.asyncio
async def test_aucun_journal_quand_le_modele_est_accepte(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    faits = _faits()
    _installer(monkeypatch, lambda: _selection_valide(faits))
    caplog.set_level(logging.DEBUG)

    texte, repli = await ia.expliquer_alerte(faits, alerte_id=uuid4())

    assert repli is False
    assert [r for r in caplog.records if r.name == _LOGGER] == []


@pytest.mark.asyncio
async def test_alerte_id_none_est_journalise_comme_null_sans_erreur(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    _installer(monkeypatch, lambda: _TEXTE_MODELE_SECRET)
    caplog.set_level(logging.WARNING, logger=_LOGGER)

    texte, repli = await ia.expliquer_alerte(_faits())  # alerte_id omis

    assert repli is True
    assert texte == ia.construire_repli(_faits())
    (evenement,) = _evenements(caplog)
    assert set(evenement) == _CHAMPS
    assert evenement["alerte_id"] is None
    assert evenement["cause"] == "reponse_invalide"


@pytest.mark.asyncio
async def test_un_alerte_id_qui_n_est_pas_un_uuid_n_est_jamais_journalise(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    _installer(monkeypatch, lambda: "pas du json")
    caplog.set_level(logging.WARNING, logger=_LOGGER)

    await ia.expliquer_alerte(_faits(), alerte_id=_COMPTE_SECRET)  # type: ignore[arg-type]

    (evenement,) = _evenements(caplog)
    assert evenement["alerte_id"] is None
    assert _COMPTE_SECRET not in caplog.text


@pytest.mark.asyncio
async def test_la_duree_vient_de_l_horloge_monotone(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    _installer(monkeypatch, lambda: "pas du json")
    horloge = itertools.chain([1000.0, 1002.5], itertools.repeat(1002.5))
    monkeypatch.setattr(ia, "monotonic", lambda: next(horloge))
    # Une horloge murale qui recule ne doit rien changer à la durée mesurée.
    monkeypatch.setattr(time, "time", lambda: 0.0)
    caplog.set_level(logging.WARNING, logger=_LOGGER)

    await ia.expliquer_alerte(_faits(), alerte_id=uuid4())

    (evenement,) = _evenements(caplog)
    assert evenement["duree_ms"] == 2500.0


def test_le_module_n_utilise_pas_l_horloge_murale_pour_les_durees() -> None:
    source = Path(ia.__file__).read_text(encoding="utf-8")
    assert "monotonic" in source
    assert "time.time(" not in source
    assert "perf_counter" not in source


@pytest.mark.asyncio
async def test_le_comportement_fonctionnel_est_inchange(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Le texte et l'indicateur de repli ne dépendent pas de la journalisation."""
    faits = _faits()
    _installer(monkeypatch, lambda: _TEXTE_MODELE_SECRET)
    sans_id = await ia.expliquer_alerte(faits)
    avec_id = await ia.expliquer_alerte(faits, alerte_id=uuid4())

    assert sans_id == avec_id == (ia.construire_repli(faits), True)
    assert isinstance(uuid4(), UUID)
