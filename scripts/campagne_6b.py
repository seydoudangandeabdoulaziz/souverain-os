"""Étape 6B — gel du lot v2 et campagne du bloc B (modèle réel).

Deux commandes, à lancer depuis la racine du dépôt :

    uv run python scripts/campagne_6b.py geler
    uv run python scripts/campagne_6b.py executer --froid

`geler` écrit docs/etape_6b_donnees/gel_v2.json (empreintes, digest du modèle,
prompt, options). `executer` refuse de démarrer si l'une des empreintes a
changé depuis le gel, puis joue le bloc B : 8 entrées x 3 passages, plus un
appel à froid. Le script réutilise le chemin de production
(`explication_ia._requete_ollama_sync` et `_valider_selection`) : il ne
réimplémente ni le prompt ni le contrôleur.

Les réponses brutes vont dans le fichier de résultats, jamais dans les
journaux. Les données sont synthétiques.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import threading
import time
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.request import urlopen

from souverain_app import explication_ia as ia

RACINE = Path(__file__).resolve().parents[1]
DONNEES = RACINE / "docs" / "etape_6b_donnees"
FICHIERS_LOT = ("lot_v2.json", "termes_interdits_v1.json")
GEL_PAR_DEFAUT = DONNEES / "gel_v2.json"
DIGEST_COURT_ATTENDU = "1922accd5827"
PASSAGES = 3
ENTREE_FROID = "B7"  # entrée la plus réaliste (motifs + fenêtre, transactions inconnues)


# --------------------------------------------------------------------------
# Outils
# --------------------------------------------------------------------------


def sha256_octets(donnees: bytes) -> str:
    return hashlib.sha256(donnees).hexdigest()


def sha256_fichier(chemin: Path) -> str:
    return sha256_octets(chemin.read_bytes())


def url_ollama() -> str:
    return os.environ.get("SOUVERAIN_OLLAMA_URL", "http://127.0.0.1:11434")


def nom_modele() -> str:
    return os.environ.get("SOUVERAIN_OLLAMA_MODEL", "ministral-3:8b-instruct-2512-q4_K_M")


def api_get(url: str, chemin: str, timeout: float = 10.0) -> dict[str, Any]:
    with urlopen(url.rstrip("/") + chemin, timeout=timeout) as reponse:
        donnees: dict[str, Any] = json.loads(reponse.read().decode("utf-8"))
    return donnees


def digest_du_modele(url: str, modele: str) -> str:
    for entree in api_get(url, "/api/tags").get("models", []):
        if entree.get("name") == modele or entree.get("model") == modele:
            return str(entree["digest"])
    raise RuntimeError(f"Modèle introuvable dans Ollama : {modele}")


def commande(args: list[str]) -> str | None:
    try:
        sortie = subprocess.run(  # noqa: S603
            args, cwd=RACINE, capture_output=True, text=True, timeout=60, check=True
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return sortie.stdout.strip()


def percentile(valeurs: list[float], q: float) -> float:
    """Rang le plus proche (nearest-rank), q entre 0 et 1."""
    triees = sorted(valeurs)
    return triees[max(0, math.ceil(q * len(triees)) - 1)]


_UNITES = {
    "B": 1,
    "KIB": 1024,
    "MIB": 1024**2,
    "GIB": 1024**3,
    "KB": 1000,
    "MB": 1000**2,
    "GB": 1000**3,
}


def octets_depuis_docker(texte: str) -> int | None:
    """Extrait la première valeur de « 6.53GiB / 15.4GiB »."""
    m = re.match(r"\s*([\d.]+)\s*([A-Za-z]+)", texte)
    if not m or m.group(2).upper() not in _UNITES:
        return None
    return int(float(m.group(1)) * _UNITES[m.group(2).upper()])


def faits_bloc_b(entree: dict[str, Any]) -> ia.FaitsAlerte:
    """Construit les faits d'une des 8 entrées du bloc B."""
    avec_motifs = bool(entree["motifs"])
    return ia.FaitsAlerte(
        compte_pivot="pivot_211",
        score=60 if avec_motifs else 0,
        seuil=50,
        statut="ouverte",
        motifs=(
            (("structure_etoile", 25), ("micro_fractionnement", 20), ("transactions_nocturnes", 15))
            if avec_motifs
            else ()
        ),
        nombre_transactions=26 if entree["transactions_disponibles"] else None,
        fenetre_debut=date(2026, 9, 14) if entree["fenetre"] else None,
        fenetre_fin=date(2026, 9, 21) if entree["fenetre"] else None,
    )


class _Capture(Exception):  # noqa: N818
    pass


def capturer_payload(faits: ia.FaitsAlerte) -> dict[str, Any]:
    """Récupère la requête exacte que la production enverrait, sans l'envoyer."""
    capture: dict[str, Any] = {}

    def faux_urlopen(requete: Any, timeout: float | None = None) -> Any:
        capture["payload"] = json.loads(requete.data.decode("utf-8"))
        raise _Capture

    original = ia.urlopen
    ia.urlopen = faux_urlopen  # type: ignore[assignment]
    try:
        ia._requete_ollama_sync("http://invalide.local", "modele", faits, 1.0)
    except _Capture:
        pass
    finally:
        ia.urlopen = original  # type: ignore[assignment]
    payload: dict[str, Any] = capture["payload"]
    return payload


def empreintes_courantes(url: str, modele: str) -> dict[str, Any]:
    """Toutes les empreintes comparées entre le gel et l'exécution."""
    lot = json.loads((DONNEES / "lot_v2.json").read_text("utf-8"))
    payload = capturer_payload(faits_bloc_b(lot["bloc_b"][-1]))
    traductions = Path(ia.__file__).parent / "traductions" / "fr.py"
    return {
        "modele_digest_complet": digest_du_modele(url, modele),
        "prompt_systeme_sha256": sha256_octets(payload["messages"][0]["content"].encode("utf-8")),
        "options": payload["options"],
        "format": payload["format"],
        "stream": payload["stream"],
        "controleur_sha256": sha256_fichier(Path(ia.__file__)),
        "traductions_fr_sha256": sha256_fichier(traductions),
        "max_words": ia.MAX_WORDS,
        "timeout_code_secondes": ia.DEFAULT_TIMEOUT_SECONDS,
        "fichiers_lot": {n: sha256_fichier(DONNEES / n) for n in FICHIERS_LOT},
    }


# --------------------------------------------------------------------------
# Gel
# --------------------------------------------------------------------------


def construire_gel(url: str, modele: str) -> dict[str, Any]:
    courant = empreintes_courantes(url, modele)
    if not courant["modele_digest_complet"].startswith(DIGEST_COURT_ATTENDU):
        raise RuntimeError(
            f"Digest inattendu : {courant['modele_digest_complet'][:12]} "
            f"(attendu {DIGEST_COURT_ATTENDU})."
        )
    compose = (RACINE / "docker-compose.yml").read_text("utf-8")
    image = re.search(r"image:\s*(ollama/ollama@sha256:[0-9a-f]{64})", compose)
    return {
        "version_lot": "v2",
        "date_gel": datetime.now(UTC).isoformat(timespec="seconds"),
        "commit": commande(["git", "rev-parse", "HEAD"]),
        "arbre_de_travail_propre": commande(["git", "status", "--porcelain"]) == "",
        "modele_nom": modele,
        "image_ollama_compose": image.group(1) if image else None,
        **courant,
    }


def commande_geler(args: argparse.Namespace) -> int:
    chemin = Path(args.gel)
    if chemin.exists() and not args.force:
        print(f"Gel déjà présent : {chemin}. Un changement impose un lot v3.")
        return 2
    gel = construire_gel(url_ollama(), nom_modele())
    chemin.write_text(json.dumps(gel, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(f"Gel écrit : {chemin}")
    if not gel["arbre_de_travail_propre"]:
        print(
            "ATTENTION : des modifications non commitées existent. "
            "Commite avant de considérer le lot comme gelé."
        )
    return 0


# --------------------------------------------------------------------------
# Campagne
# --------------------------------------------------------------------------


class EchantillonneurMemoire:
    """Relève périodiquement la mémoire du conteneur Ollama (docker stats)."""

    def __init__(self, conteneur: str | None, intervalle: float = 2.0) -> None:
        self.conteneur = conteneur
        self.intervalle = intervalle
        self.pic_octets = 0
        self.mesures = 0
        self._stop = threading.Event()
        self._fil = threading.Thread(target=self._boucle, daemon=True)

    def _boucle(self) -> None:
        while not self._stop.is_set():
            sortie = commande(
                ["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", str(self.conteneur)]
            )
            valeur = octets_depuis_docker(sortie) if sortie else None
            if valeur is not None:
                self.pic_octets = max(self.pic_octets, valeur)
                self.mesures += 1
            self._stop.wait(self.intervalle)

    def demarrer(self) -> None:
        if self.conteneur:
            self._fil.start()

    def arreter(self) -> None:
        self._stop.set()
        if self.conteneur:
            self._fil.join(timeout=10)


def evaluer_appel(faits: ia.FaitsAlerte, url: str, modele: str, timeout: float) -> dict[str, Any]:
    autorises = list(ia._identifiants_autorises(faits))
    brut: str | None = None
    erreur: str | None = None
    debut = time.perf_counter()
    try:
        brut = ia._requete_ollama_sync(url, modele, faits, timeout)
    except Exception as exc:  # noqa: BLE001 - on consigne le type, jamais le message
        erreur = type(exc).__name__
    duree = time.perf_counter() - debut

    selection = ia._valider_selection(brut, faits) if brut is not None else None
    permutation_exacte = selection is not None and sorted(selection) == sorted(autorises)
    longueur_ok: bool | None = None
    if selection is not None:
        phrases = ia._construire_phrases(faits)
        texte = " ".join(phrases[i] for i in selection)
        longueur_ok = len(texte.split()) <= ia.MAX_WORDS

    return {
        "duree_s": round(duree, 3),
        "reponse_brute": brut,
        "erreur": erreur,
        "selection": selection,
        "acceptee": selection is not None and bool(longueur_ok),
        "permutation_exacte": permutation_exacte,
        # Critère bloquant : acceptée par le contrôleur sans être une permutation exacte.
        "acceptee_non_conforme": selection is not None and not permutation_exacte,
        "repli": selection is None or not longueur_ok,
    }


def resumer(appels: list[dict[str, Any]], pic_octets: int) -> dict[str, Any]:
    chauds = [a for a in appels if a["entree"] != "froid"]
    froid = [a for a in appels if a["entree"] == "froid"]
    durees = [a["duree_s"] for a in chauds]
    par_entree: dict[str, Any] = {}
    for ident in sorted({a["entree"] for a in chauds}):
        groupe = [a for a in chauds if a["entree"] == ident]
        signatures = {
            json.dumps(a["selection"])
            if a["selection"] is not None
            else f"brut:{a['reponse_brute']}|{a['erreur']}"
            for a in groupe
        }
        par_entree[ident] = {
            "appels": len(groupe),
            "repetable": len(signatures) == 1,
            "taux_repli": sum(a["repli"] for a in groupe) / len(groupe),
            "duree_mediane_s": round(percentile([a["duree_s"] for a in groupe], 0.5), 3),
        }
    duree_froid = froid[0]["duree_s"] if froid else None
    p95 = percentile(durees, 0.95) if durees else None
    timeout_cible = None
    if p95 is not None:
        # Arrondi vers le haut : jamais en dessous de l'appel à froid mesuré.
        timeout_cible = math.ceil(max(1.5 * p95, duree_froid or 0.0) * 10) / 10
    return {
        "appels_chauds": len(chauds),
        "bloquant_acceptee_non_conforme": sum(a["acceptee_non_conforme"] for a in appels),
        "taux_repli_global": (sum(a["repli"] for a in chauds) / len(chauds) if chauds else None),
        "erreurs": sorted({a["erreur"] for a in appels if a["erreur"]}),
        "duree_froid_s": duree_froid,
        "duree_mediane_s": round(percentile(durees, 0.5), 3) if durees else None,
        "duree_p95_s": round(p95, 3) if p95 is not None else None,
        "timeout_cible_s": timeout_cible,
        "pic_memoire_conteneur_gio": round(pic_octets / 1024**3, 3) if pic_octets else None,
        "par_entree": par_entree,
    }


def attendre_ollama(url: str, delai: float = 120.0) -> None:
    fin = time.monotonic() + delai
    while time.monotonic() < fin:
        try:
            api_get(url, "/api/tags", timeout=5.0)
            return
        except OSError:
            time.sleep(2.0)
    raise RuntimeError("Ollama ne répond pas après le redémarrage.")


def commande_executer(args: argparse.Namespace) -> int:
    url, modele = url_ollama(), nom_modele()
    chemin_gel = Path(args.gel)
    if not chemin_gel.exists():
        print("Aucun gel : lance d'abord « geler ».")
        return 2

    gel = json.loads(chemin_gel.read_text("utf-8"))
    courant = empreintes_courantes(url, modele)
    ecarts = [cle for cle, valeur in courant.items() if gel.get(cle) != valeur]
    if ecarts:
        print("Le lot n'est plus celui qui a été gelé. Écarts : " + ", ".join(ecarts))
        print("Tout changement impose un lot v3 et un nouveau gel.")
        return 2

    lot = json.loads((DONNEES / "lot_v2.json").read_text("utf-8"))
    timeout = float(ia.DEFAULT_TIMEOUT_SECONDS)

    conteneur: str | None = None
    if not args.sans_docker:
        conteneur = commande(["docker", "compose", "--profile", "ollama", "ps", "-q", "ollama"])
        if args.froid:
            commande(["docker", "compose", "--profile", "ollama", "restart", "ollama"])
            attendre_ollama(url)

    echantillonneur = EchantillonneurMemoire(conteneur)
    echantillonneur.demarrer()
    appels: list[dict[str, Any]] = []
    try:
        entrees = {e["id"]: e for e in lot["bloc_b"]}
        plan: list[tuple[str, str, int]] = []
        if args.froid:
            plan.append(("froid", ENTREE_FROID, 1))
        for ident in entrees:
            plan.extend((ident, ident, p) for p in range(1, PASSAGES + 1))
        for etiquette, ident, passage in plan:
            resultat = evaluer_appel(faits_bloc_b(entrees[ident]), url, modele, timeout)
            appels.append({"entree": etiquette, "source": ident, "passage": passage, **resultat})
            etat = "repli" if resultat["repli"] else "ok"
            print(
                f"{etiquette:>6} p{passage}  {resultat['duree_s']:>7.2f}s  {etat}"
                f"{'  erreur=' + resultat['erreur'] if resultat['erreur'] else ''}"
            )
    finally:
        echantillonneur.arreter()

    synthese = resumer(appels, echantillonneur.pic_octets)
    rapport = {
        "gel": str(chemin_gel.name),
        "date": datetime.now(UTC).isoformat(timespec="seconds"),
        "commit": commande(["git", "rev-parse", "HEAD"]),
        "synthese": synthese,
        "appels": appels,
    }
    sortie = Path(args.sortie)
    sortie.mkdir(parents=True, exist_ok=True)
    nom = f"resultats_bloc_b_{datetime.now(UTC):%Y%m%d_%H%M%S}.json"
    (sortie / nom).write_text(json.dumps(rapport, ensure_ascii=False, indent=2) + "\n", "utf-8")

    print("\n=== Synthèse bloc B ===")
    print(
        json.dumps(
            {k: v for k, v in synthese.items() if k != "par_entree"}, ensure_ascii=False, indent=2
        )
    )
    print(f"Résultats : {sortie / nom}")
    return 1 if synthese["bloquant_acceptee_non_conforme"] else 0


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sous = analyseur.add_subparsers(dest="cmd", required=True)
    geler = sous.add_parser("geler", help="écrit le fichier de gel du lot v2")
    geler.add_argument("--gel", default=str(GEL_PAR_DEFAUT))
    geler.add_argument("--force", action="store_true")
    geler.set_defaults(fonction=commande_geler)
    executer = sous.add_parser("executer", help="joue le bloc B")
    executer.add_argument("--gel", default=str(GEL_PAR_DEFAUT))
    executer.add_argument("--sortie", default=str(DONNEES))
    executer.add_argument(
        "--froid", action="store_true", help="redémarre Ollama et mesure un appel à froid"
    )
    executer.add_argument(
        "--sans-docker", action="store_true", help="ne pas piloter ni mesurer le conteneur (tests)"
    )
    executer.set_defaults(fonction=commande_executer)
    args = analyseur.parse_args(argv)
    try:
        code: int = args.fonction(args)
    except (OSError, RuntimeError) as exc:
        print(f"Échec : {type(exc).__name__}. Ollama est-il démarré et le modèle présent ?")
        print("  docker compose --profile ollama up -d ollama")
        print(f"  URL utilisée : {url_ollama()}")
        return 3
    return code


if __name__ == "__main__":
    sys.exit(main())
