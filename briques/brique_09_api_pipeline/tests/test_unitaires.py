"""Tests sans base : schémas, épisodes, limiteur, jetons."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import jwt
import pytest
from brique_09_api_pipeline.config import ApiSettings
from brique_09_api_pipeline.episodes import ECART_EPISODE, debut_episode
from brique_09_api_pipeline.jetons import JetonInvalide, decoder_jeton, emettre_jeton
from brique_09_api_pipeline.limiteur import LimiteurEchecs
from brique_09_api_pipeline.schemas import LotTransactions, TransactionIn
from pydantic import ValidationError

T0 = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)


def _tx(**surcharges: object) -> dict[str, object]:
    base: dict[str, object] = {
        "external_id": "ext-1",
        "sender_account": "cpt_1",
        "receiver_account": "cpt_2",
        "amount": "1500.50",
        "currency": "XOF",
        "channel": "orange_money",
        "occurred_at": "2026-03-01T12:00:00+00:00",
    }
    base.update(surcharges)
    return base


# ----------------------------------------------------------------- schémas
@pytest.mark.parametrize(
    "champ",
    ["tenant_id", "country_code", "data_classification", "is_synthetic", "source"],
)
def test_champs_imposes_par_le_serveur_refuses(champ: str) -> None:
    with pytest.raises(ValidationError):
        TransactionIn.model_validate(_tx(**{champ: "x"}))


@pytest.mark.parametrize(
    "surcharge",
    [
        {"amount": "0"},
        {"amount": "-5"},
        {"amount": "1.234"},
        {"currency": "EUR"},
        {"channel": "visa"},
        {"external_id": ""},
        {"external_id": "a b"},
        {"sender_account": "cpt_2"},  # identique au destinataire
        {"sender_account": "a;drop"},
        {"occurred_at": "2026-03-01T12:00:00"},  # sans fuseau
    ],
)
def test_transactions_invalides_refusees(surcharge: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        TransactionIn.model_validate(_tx(**surcharge))


def test_lot_borne() -> None:
    with pytest.raises(ValidationError):
        LotTransactions.model_validate({"transactions": []})
    lot = [_tx(external_id=f"e{i}") for i in range(1001)]
    with pytest.raises(ValidationError):
        LotTransactions.model_validate({"transactions": lot})


def test_empreinte_stable_et_sensible_au_contenu() -> None:
    a = TransactionIn.model_validate(_tx())
    b = TransactionIn.model_validate(_tx(occurred_at="2026-03-01T13:00:00+01:00"))  # même instant
    c = TransactionIn.model_validate(_tx(amount="1500.51"))
    assert a.content_hash() == b.content_hash()
    assert a.content_hash() != c.content_hash()
    assert a.amount == Decimal("1500.50")


# ---------------------------------------------------------------- épisodes
def _suite(*minutes: int) -> list[datetime]:
    return [T0 + timedelta(minutes=m) for m in minutes]


def test_episode_borne_par_un_trou_de_plus_de_6h() -> None:
    h = _suite(0, 30, 60 * 8, 60 * 8 + 10, 60 * 8 + 20)
    debut, besoin = debut_episode(h, h[4], T0 - timedelta(hours=6))
    assert debut == 2 and besoin is False  # trou de 7 h 30 entre h[1] et h[2]


def test_episode_exactement_6h_continue() -> None:
    h = _suite(0, 360, 361)
    debut, _ = debut_episode(h, h[2], None)
    assert debut == 0  # un écart de 6 h pile reste dans l'épisode


def test_episode_demande_plus_ancien_quand_la_borne_est_proche() -> None:
    h = _suite(0, 10)
    borne = T0 - timedelta(hours=3)  # le premier point est à 3 h de la borne : <= 6 h
    assert debut_episode(h, h[1], borne) == (0, True)
    assert debut_episode(h, h[1], T0 - timedelta(hours=7)) == (0, False)
    assert debut_episode(h, h[1], None) == (0, False)  # historique complet


def test_episode_ecart_constant() -> None:
    assert timedelta(hours=6) == ECART_EPISODE


# ----------------------------------------------------------------- limiteur
def test_limiteur_bloque_puis_libere() -> None:
    horloge = [0.0]
    lim = LimiteurEchecs(3, 60, 120, horloge=lambda: horloge[0])
    for _ in range(3):
        assert not lim.verrouille("k")
        lim.enregistrer_echec("k")
    assert lim.verrouille("k")
    horloge[0] = 119
    assert lim.verrouille("k")
    horloge[0] = 121
    assert not lim.verrouille("k")


def test_limiteur_succes_reinitialise_et_fenetre_glissante() -> None:
    horloge = [0.0]
    lim = LimiteurEchecs(3, 60, 120, horloge=lambda: horloge[0])
    lim.enregistrer_echec("k")
    lim.enregistrer_echec("k")
    lim.reinitialiser("k")
    lim.enregistrer_echec("k")
    assert not lim.verrouille("k")
    horloge[0] = 100  # les échecs anciens sortent de la fenêtre
    lim.enregistrer_echec("k")
    lim.enregistrer_echec("k")
    assert not lim.verrouille("k")


# ------------------------------------------------------------------- jetons
def _settings(secret: str = "s" * 40) -> ApiSettings:
    return ApiSettings(jwt_secret=secret)  # type: ignore[arg-type]


def test_jeton_aller_retour() -> None:
    cid, tid = uuid4(), uuid4()
    jeton = emettre_jeton(cid, tid, ["cycle", "ingest"], 3, _settings())
    decode = decoder_jeton(jeton, _settings())
    assert (decode.client_id, decode.tenant_id, decode.secret_version) == (cid, tid, 3)


def test_jetons_etrangers_refuses() -> None:
    cle = "s" * 40
    reglages = _settings(cle)
    maintenant = datetime.now(UTC)
    valide = {
        "iss": reglages.jwt_issuer,
        "aud": reglages.jwt_audience,
        "sub": str(uuid4()),
        "tenant_id": str(uuid4()),
        "typ": "service",
        "sv": 1,
        "iat": maintenant,
        "exp": maintenant + timedelta(minutes=5),
    }
    assert decoder_jeton(jwt.encode(valide, cle, algorithm="HS256"), reglages)
    cas = {
        "autre clé": jwt.encode(valide, "x" * 40, algorithm="HS256"),
        "type humain": jwt.encode({**valide, "typ": "user"}, cle, algorithm="HS256"),
        "sans typ": jwt.encode(
            {k: v for k, v in valide.items() if k != "typ"}, cle, algorithm="HS256"
        ),
        "mauvaise audience": jwt.encode({**valide, "aud": "autre"}, cle, algorithm="HS256"),
        "expiré": jwt.encode(
            {**valide, "exp": maintenant - timedelta(seconds=5)}, cle, algorithm="HS256"
        ),
        "sans exp": jwt.encode(
            {k: v for k, v in valide.items() if k != "exp"}, cle, algorithm="HS256"
        ),
        "alg none": jwt.encode(valide, "", algorithm="none"),
        "ordure": "pas.un.jeton",
    }
    for nom, jeton in cas.items():
        with pytest.raises(JetonInvalide):
            decoder_jeton(jeton, reglages)
        assert nom
