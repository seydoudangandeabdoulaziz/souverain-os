"""Explication contrôlée d'une alerte par Ollama — étape 6B.

Le modèle ne rédige aucun fait : il retourne des identifiants d'affirmations.
Le serveur vérifie ces identifiants et construit lui-même le texte français.
Aucune base de données n'est consultée dans ce module.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.request import Request, urlopen

from brique_05_scoring_alertes.seuils import POIDS_PAR_PATTERN

MAX_WORDS = 120
DEFAULT_TIMEOUT_SECONDS = 120.0


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

    if faits.statut not in {"ouverte", "fermee"}:
        raise ValueError("Statut d'alerte invalide")

    if faits.nombre_transactions is not None and (
        not isinstance(faits.nombre_transactions, int)
        or isinstance(faits.nombre_transactions, bool)
        or faits.nombre_transactions < 0
    ):
        raise ValueError("Nombre de transactions invalide")

    motifs_vus: set[str] = set()
    for nom, poids in faits.motifs:
        if (
            nom not in POIDS_PAR_PATTERN
            or nom in motifs_vus
            or not isinstance(poids, int)
            or isinstance(poids, bool)
            or poids < 0
        ):
            raise ValueError("Motif ou poids non autorisé")
        motifs_vus.add(nom)

    debut, fin = faits.fenetre_debut, faits.fenetre_fin
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


def _construire_phrases(faits: FaitsAlerte) -> dict[str, str]:
    """Construit chaque phrase à partir des faits, jamais du texte du modèle."""
    if faits.score < faits.seuil:
        comparaison = "inférieur au seuil"
    elif faits.score == faits.seuil:
        comparaison = "égal au seuil"
    else:
        comparaison = "supérieur au seuil"

    phrases = {
        "compte": f"L'alerte concerne le compte {faits.compte_pivot}.",
        "comparaison_score_seuil": (
            f"Le score est de {faits.score}, {comparaison} de {faits.seuil}."
        ),
        "statut": f"Le statut enregistré est : {faits.statut}.",
    }

    if faits.fenetre_debut is not None and faits.fenetre_fin is not None:
        phrases["fenetre"] = (
            "Fenêtre enregistrée : "
            f"{faits.fenetre_debut.isoformat()} au "
            f"{faits.fenetre_fin.isoformat()}."
        )

    if faits.motifs:
        details = ", ".join(
            f"{nom} (poids {poids})" for nom, poids in faits.motifs
        )
        phrases["motifs"] = f"Motifs contributifs enregistrés : {details}."

    if faits.nombre_transactions is None:
        phrases["transactions_indisponibles"] = (
            "Le nombre de transactions n'est pas disponible."
        )
    else:
        phrases["transactions_disponibles"] = (
            "Le nombre de transactions fourni est "
            f"{faits.nombre_transactions}."
        )

    return phrases


def construire_repli(faits: FaitsAlerte) -> str:
    """Produit une explication déterministe sans dépendre du modèle."""
    phrases = _construire_phrases(faits)
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


async def expliquer_alerte(
    faits: FaitsAlerte,
    *,
    url: str | None = None,
    modele: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> tuple[str, bool]:
    """Retourne (texte, repli_utilise), sans afficher de sortie libre du modèle."""
    base_url = url or os.getenv(
        "SOUVERAIN_OLLAMA_URL", "http://127.0.0.1:11434"
    )
    nom_modele = modele or os.getenv(
        "SOUVERAIN_OLLAMA_MODEL", "ministral-3:8b-instruct-2512-q4_K_M"
    )

    try:
        contenu = await asyncio.wait_for(
            asyncio.to_thread(
                _requete_ollama_sync, base_url, nom_modele, faits, timeout
            ),
            timeout=timeout,
        )
        selection = _valider_selection(contenu, faits)

        if selection is not None:
            phrases = _construire_phrases(faits)
            texte = " ".join(phrases[identifiant] for identifiant in selection)
            if len(texte.split()) <= MAX_WORDS:
                return texte, False
    except Exception:
        # Ne pas exposer les détails techniques à l'utilisateur.
        pass

    return construire_repli(faits), True
