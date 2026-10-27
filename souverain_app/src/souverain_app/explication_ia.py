"""Explication contrôlée d'une alerte par Ollama — étape 6B.

Le modèle ne rédige aucun fait : il retourne des identifiants d'affirmations.
Le serveur vérifie ces identifiants et construit lui-même le texte français.
Aucune base de données n'est consultée dans ce module.

Chaque repli est journalisé (étape 6B, critère C5) : horodatage, identifiant
d'alerte, code de cause et durée. Jamais de texte généré, de message
d'exception, de réponse du modèle ni d'identifiant de compte.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from time import monotonic
from typing import Any, Literal
from urllib.error import URLError
from urllib.request import Request, urlopen
from uuid import UUID

from brique_05_scoring_alertes.seuils import POIDS_PAR_PATTERN

from souverain_app.traductions import t

MAX_WORDS = 120
DEFAULT_TIMEOUT_SECONDS = 120.0

CauseRepli = Literal[
    "faits_invalides",
    "modele_indisponible",
    "delai_depasse",
    "reponse_invalide",
    "texte_trop_long",
]
# Liste fermée des causes de repli : aucun texte libre n'entre dans le journal.
CAUSES_REPLI: frozenset[str] = frozenset(
    {
        "faits_invalides",
        "modele_indisponible",
        "delai_depasse",
        "reponse_invalide",
        "texte_trop_long",
    }
)

# Même principe que les journaux HTTP de main.py : une ligne JSON par événement.
_journal = logging.getLogger("souverain_app.explication")
_journal.setLevel(logging.WARNING)
if not _journal.handlers:
    _gestionnaire = logging.StreamHandler()
    _gestionnaire.setFormatter(logging.Formatter("%(message)s"))
    _journal.addHandler(_gestionnaire)


@dataclass(frozen=True)
class FaitsAlerte:
    """Faits structurés autorisés pour expliquer une alerte."""

    compte_pivot: str
    score: int
    seuil: int
    statut: str
    motifs: tuple[tuple[str, int], ...] = ()
    nombre_transactions: int | None = None
    autres_faits: tuple[str, ...] = ()
    fenetre_debut: date | None = None
    fenetre_fin: date | None = None

def _valider_faits(faits: FaitsAlerte) -> None:
    """Valide les faits avant de construire le texte affiché."""
    if not isinstance(faits, FaitsAlerte):
        raise ValueError("Structure des faits invalide")

    if (
        not isinstance(faits.compte_pivot, str)
        or not faits.compte_pivot
        or len(faits.compte_pivot) > 128
        or not re.fullmatch(r"[A-Za-z0-9+._:/-]+", faits.compte_pivot)
    ):
        raise ValueError("Identifiant de compte invalide")

    for nom, valeur, minimum in (
        ("score", faits.score, 0),
        ("seuil", faits.seuil, 1),
    ):
        if (
            not isinstance(valeur, int)
            or isinstance(valeur, bool)
            or valeur < minimum
        ):
            raise ValueError(f"{nom} invalide")

    if (
        not isinstance(faits.statut, str)
        or faits.statut not in {"ouverte", "fermee"}
    ):
        raise ValueError("Statut d'alerte invalide")

    if faits.nombre_transactions is not None and (
        not isinstance(faits.nombre_transactions, int)
        or isinstance(faits.nombre_transactions, bool)
        or faits.nombre_transactions < 0
    ):
        raise ValueError("Nombre de transactions invalide")

    if not isinstance(faits.motifs, (tuple, list)):
        raise ValueError("Liste des motifs invalide")

    motifs_vus: set[str] = set()
    for motif in faits.motifs:
        if not isinstance(motif, (tuple, list)) or len(motif) != 2:
            raise ValueError("Format de motif invalide")

        nom, poids = motif
        if (
            not isinstance(nom, str)
            or nom not in POIDS_PAR_PATTERN
            or nom in motifs_vus
            or not isinstance(poids, int)
            or isinstance(poids, bool)
            or poids < 0
        ):
            raise ValueError("Motif ou poids non autorisé")
        motifs_vus.add(nom)

    if not isinstance(faits.autres_faits, (tuple, list)) or not all(
        isinstance(fait, str) for fait in faits.autres_faits
    ):
        raise ValueError("Autres faits invalides")

    debut, fin = faits.fenetre_debut, faits.fenetre_fin

    for nom_borne, borne in (
        ("fenetre_debut", debut),
        ("fenetre_fin", fin),
    ):
        if borne is not None and not isinstance(borne, date):
            raise ValueError(f"{nom_borne} invalide")

    if (debut is None) != (fin is None):
        raise ValueError("Fenêtre temporelle incomplète")

    if debut is not None and fin is not None and debut > fin:
        raise ValueError("Fenêtre temporelle incohérente")


def _identifiants_autorises(faits: FaitsAlerte) -> tuple[str, ...]:
    """Liste les affirmations que le serveur sait formuler sans inférence."""
    _valider_faits(faits)
    identifiants = ["compte", "comparaison_score_seuil", "statut"]

    if faits.motifs:
        identifiants.append("motifs")

    if faits.nombre_transactions is None:
        identifiants.append("transactions_indisponibles")
    else:
        identifiants.append("transactions_disponibles")

    if faits.fenetre_debut is not None:
        identifiants.append("fenetre")

    return tuple(identifiants)


def _construire_phrases(faits: FaitsAlerte, langue: str = "fr") -> dict[str, str]:
    """Construit chaque phrase à partir des faits, jamais du texte du modèle.

    Les textes viennent du dictionnaire de traductions (ADR-001, ADR-007).
    """
    if faits.score < faits.seuil:
        cle_comparaison = "explication.comparaison.inferieur"
    elif faits.score == faits.seuil:
        cle_comparaison = "explication.comparaison.egal"
    else:
        cle_comparaison = "explication.comparaison.superieur"
    comparaison = t(cle_comparaison, langue)

    phrases = {
        "compte": t("explication.phrase.compte", langue).format(
            compte=faits.compte_pivot
        ),
        "comparaison_score_seuil": t(
            "explication.phrase.comparaison_score_seuil", langue
        ).format(score=faits.score, comparaison=comparaison, seuil=faits.seuil),
        "statut": t("explication.phrase.statut", langue).format(
            statut=faits.statut
        ),
    }

    if faits.fenetre_debut is not None and faits.fenetre_fin is not None:
        phrases["fenetre"] = t("explication.phrase.fenetre", langue).format(
            debut=faits.fenetre_debut.isoformat(),
            fin=faits.fenetre_fin.isoformat(),
        )

    if faits.motifs:
        details = ", ".join(
            t("explication.motif_detail", langue).format(nom=nom, poids=poids)
            for nom, poids in faits.motifs
        )
        phrases["motifs"] = t("explication.phrase.motifs", langue).format(
            details=details
        )

    if faits.nombre_transactions is None:
        phrases["transactions_indisponibles"] = t(
            "explication.phrase.transactions_indisponibles", langue
        )
    else:
        phrases["transactions_disponibles"] = t(
            "explication.phrase.transactions_disponibles", langue
        ).format(nombre=faits.nombre_transactions)

    return phrases


def construire_repli(faits: FaitsAlerte, langue: str = "fr") -> str:
    """Produit une explication déterministe sans dépendre du modèle."""
    phrases = _construire_phrases(faits, langue)
    ordre = _identifiants_autorises(faits)
    return " ".join(phrases[identifiant] for identifiant in ordre)


def _valider_selection(
    contenu: str, faits: FaitsAlerte
) -> list[str] | None:
    """Accepte uniquement une liste JSON exacte d'identifiants autorisés."""
    try:
        objet = json.loads(contenu)
    except (json.JSONDecodeError, TypeError):
        return None

    if not isinstance(objet, dict) or set(objet) != {"claims"}:
        return None

    claims = objet["claims"]
    autorises = _identifiants_autorises(faits)

    if not isinstance(claims, list) or not all(
        isinstance(claim, str) for claim in claims
    ):
        return None

    # Chaque affirmation autorisée doit apparaître une seule fois.
    # Le modèle peut ordonner les faits, mais ne peut ni en inventer ni en omettre.
    if len(claims) != len(autorises) or set(claims) != set(autorises):
        return None

    if len(set(claims)) != len(claims):
        return None

    return claims


def _requete_ollama_sync(
    url: str, modele: str, faits: FaitsAlerte, timeout: float
) -> str:
    """Demande au modèle de choisir uniquement l'ordre des identifiants."""
    autorises = list(_identifiants_autorises(faits))
    payload: dict[str, Any] = {
        "model": modele,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0, "seed": 42},
        "messages": [
            {
                "role": "system",
                "content": (
                    "Tu organises les identifiants d'une explication d'alerte. "
                    "Réponds uniquement en JSON sous la forme "
                    '{"claims":["identifiant", ...]}. '
                    "Utilise chaque identifiant autorisé exactement une fois. "
                    "N'ajoute aucun texte, aucune clé et aucun identifiant. "
                    "Ne produis aucune phrase ni valeur factuelle."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {"identifiants_autorises": autorises},
                    ensure_ascii=False,
                ),
            },
        ],
    }

    requete = Request(
        url.rstrip("/") + "/api/chat",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urlopen(requete, timeout=timeout) as response:
        donnees = json.loads(response.read().decode("utf-8"))

    contenu = donnees.get("message", {}).get("content")
    if not isinstance(contenu, str):
        raise ValueError("Réponse Ollama sans contenu textuel")

    return contenu.strip()


def _est_delai_depasse(exc: BaseException) -> bool:
    """Reconnaît un dépassement de délai, côté asyncio comme côté socket."""
    if isinstance(exc, TimeoutError):
        return True
    return isinstance(exc, URLError) and isinstance(exc.reason, TimeoutError)


def _journaliser_repli(
    cause: CauseRepli, alerte_id: UUID | None, debut: float
) -> None:
    """Journalise un repli : horodatage, alerte, cause, durée (horloge monotone).

    N'enregistre jamais de texte généré, de contenu d'exception ni de compte.
    `alerte_id` n'est retenu que s'il s'agit bien d'un UUID : toute autre
    valeur (par exemple un identifiant de compte) est remplacée par null.
    """
    with contextlib.suppress(Exception):  # La journalisation ne casse jamais le flux.
        _journal.warning(
            json.dumps(
                {
                    "evenement": "explication_repli",
                    "horodatage": datetime.now(UTC).isoformat(timespec="milliseconds"),
                    "alerte_id": (
                        str(alerte_id) if isinstance(alerte_id, UUID) else None
                    ),
                    "cause": cause,
                    "duree_ms": round((monotonic() - debut) * 1000, 1),
                },
                ensure_ascii=False,
            )
        )


async def expliquer_alerte(
    faits: FaitsAlerte,
    *,
    langue: str = "fr",
    url: str | None = None,
    modele: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    alerte_id: UUID | None = None,
) -> tuple[str, bool]:
    """Retourne (texte, repli_utilise), sans afficher de sortie libre du modèle.

    Chaque repli est journalisé avec sa cause (voir `CAUSES_REPLI`).
    """
    debut = monotonic()
    try:
        _valider_faits(faits)
    except (TypeError, ValueError):
        _journaliser_repli("faits_invalides", alerte_id, debut)
        return t("explication.donnees_insuffisantes", langue), True

    base_url: str = url or os.environ.get(
        "SOUVERAIN_OLLAMA_URL", "http://127.0.0.1:11434"
    )
    nom_modele: str = modele or os.environ.get(
        "SOUVERAIN_OLLAMA_MODEL", "ministral-3:8b-instruct-2512-q4_K_M"
    )

    cause: CauseRepli
    try:
        contenu = await asyncio.wait_for(
            asyncio.to_thread(
                _requete_ollama_sync, base_url, nom_modele, faits, timeout
            ),
            timeout=timeout,
        )
    except Exception as exc:
        # Ne pas exposer les détails techniques à l'utilisateur ni au journal.
        cause = "delai_depasse" if _est_delai_depasse(exc) else "modele_indisponible"
    else:
        cause = "reponse_invalide"
        try:
            selection = _valider_selection(contenu, faits)
            if selection is not None:
                phrases = _construire_phrases(faits, langue)
                texte = " ".join(phrases[identifiant] for identifiant in selection)
                if len(texte.split()) <= MAX_WORDS:
                    return texte, False
                cause = "texte_trop_long"
        except Exception:
            # Tout échec inattendu du contrôle est traité comme une réponse invalide.
            cause = "reponse_invalide"

    _journaliser_repli(cause, alerte_id, debut)
    return construire_repli(faits, langue), True
