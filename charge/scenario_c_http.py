"""
Scénario C — Étape 5 (Test de charge), charge HTTP concurrente sur
le dashboard B7/B8.

Script autonome (pas un test pytest — outil de charge, exécuté
manuellement, jamais collecté par `uv run pytest`). Aucune nouvelle
dépendance : httpx est déjà une dépendance du projet (Brique 7,
Brique 8, tests d'intégration).

Usage :
    uv run python charge/scenario_c_http.py \
        --base-url http://localhost:8080 \
        --email admin-test-charge@example.com \
        --mot-de-passe change_me \
        --concurrence 10 \
        --duree 60

Comportement :
- Se connecte une fois (POST /login), le cookie de session est
  conservé automatiquement par httpx.AsyncClient pour toute la suite
  du script — un seul client HTTP, partagé par tous les "clients
  concurrents" logiques (des coroutines asyncio, pas des connexions
  TCP séparées : cohérent avec un vrai navigateur qui réutilise sa
  session).
- Récupère la liste des alertes réelles du tenant (GET /alertes),
  puis pour chaque alerte sa page de détail, d'où sont extraites les
  URLs de fragment graphe — via le même attribut hx-get que celui
  utilisé par le navigateur réel (alerte_detail.html), jamais une URL
  reconstruite à la main.
- Lance N coroutines concurrentes qui répètent, pendant la durée
  donnée, un cycle pondéré parmi : GET /alertes (40%),
  GET /alertes/{id} (35%), GET /alertes/{id}/graphe?compte_pivot=...
  (25%, le plus coûteux — accès Neo4j).
- N'écrit aucune métrique serveur : la latence par requête est déjà
  exposée par souverain_app lui-même via
  souverain_http_request_duration_seconds (Prometheus, Étape 4a).
  Ce script se contente de générer la charge et d'afficher un résumé
  local immédiat (codes de réponse, p50/p95 côté client), pour un
  repère sans attendre une requête Prometheus séparée.
- Uniquement des GET — aucune donnée modifiée, sûr à relancer autant
  de fois que nécessaire sur le tenant de test.
"""

from __future__ import annotations

import argparse
import asyncio
import random
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass, field

import httpx

_MOTIF_ID_ALERTE = re.compile(r'/alertes/([0-9a-fA-F-]{36})"')
_MOTIF_FRAGMENT_GRAPHE = re.compile(
    r'hx-get="(/alertes/[0-9a-fA-F-]{36}/graphe\?compte_pivot=[^"]+)"'
)


@dataclass
class Resultats:
    """Compteurs partagés entre les coroutines concurrentes — un seul
    thread asyncio (pas de vrai parallélisme mémoire), donc pas de
    verrou nécessaire pour ces mises à jour."""

    codes: Counter[int] = field(default_factory=Counter)
    erreurs_reseau: int = 0
    latences_s: list[float] = field(default_factory=list)
    requetes_totales: int = 0


async def se_connecter(client: httpx.AsyncClient, email: str, mot_de_passe: str) -> None:
    """Pose le cookie de session sur le client — toutes les requêtes
    suivantes du même client le réutilisent automatiquement. Le
    client doit avoir follow_redirects=True (login répond 303)."""
    reponse = await client.post("/login", data={"email": email, "mot_de_passe": mot_de_passe})
    if reponse.status_code != 200 or "/alertes" not in str(reponse.url):
        raise RuntimeError(
            f"Échec de connexion (statut final {reponse.status_code}, "
            f"URL finale {reponse.url}) — vérifier email/mot de passe "
            f"et que ce compte existe bien sur le tenant de test."
        )


async def recuperer_cibles(client: httpx.AsyncClient) -> tuple[list[str], list[str]]:
    """Récupère les IDs d'alertes réels et les URLs de fragment
    graphe correspondantes, en suivant exactement ce qu'un navigateur
    réel verrait — jamais une donnée reconstruite ou supposée."""
    reponse_liste = await client.get("/alertes")
    ids_alertes = _MOTIF_ID_ALERTE.findall(reponse_liste.text)

    cibles_graphe: list[str] = []
    for alerte_id in ids_alertes:
        reponse_detail = await client.get(f"/alertes/{alerte_id}")
        trouve = _MOTIF_FRAGMENT_GRAPHE.search(reponse_detail.text)
        if trouve:
            cibles_graphe.append(trouve.group(1))

    return ids_alertes, cibles_graphe


async def coroutine_charge(
    client: httpx.AsyncClient,
    alertes_ids: list[str],
    cibles_graphe: list[str],
    duree_s: float,
    resultats: Resultats,
) -> None:
    fin = time.monotonic() + duree_s
    while time.monotonic() < fin:
        tirage = random.random()
        if tirage < 0.4 or not alertes_ids:
            chemin = "/alertes"
        elif tirage < 0.75:
            chemin = f"/alertes/{random.choice(alertes_ids)}"
        elif cibles_graphe:
            chemin = random.choice(cibles_graphe)
        else:
            chemin = "/alertes"

        debut = time.monotonic()
        try:
            reponse = await client.get(chemin)
        except httpx.HTTPError:
            resultats.erreurs_reseau += 1
            resultats.requetes_totales += 1
            continue
        duree = time.monotonic() - debut

        resultats.codes[reponse.status_code] += 1
        resultats.latences_s.append(duree)
        resultats.requetes_totales += 1


def resumer(resultats: Resultats, duree_s: float) -> str:
    total = resultats.requetes_totales
    latences = sorted(resultats.latences_s)
    p50 = latences[len(latences) // 2] if latences else 0.0
    p95 = latences[int(len(latences) * 0.95)] if latences else 0.0

    return "\n".join(
        [
            f"Requêtes totales : {total}",
            f"Débit observé : {total / duree_s:.1f} req/s",
            f"Codes de réponse : {dict(resultats.codes)}",
            f"Erreurs réseau (hors codes HTTP) : {resultats.erreurs_reseau}",
            f"Latence p50 (mesurée côté client) : {p50 * 1000:.1f} ms",
            f"Latence p95 (mesurée côté client) : {p95 * 1000:.1f} ms",
            "Pour la latence serveur de référence, voir "
            "souverain_http_request_duration_seconds dans Prometheus.",
        ]
    )


async def executer(args: argparse.Namespace) -> int:
    async with httpx.AsyncClient(
        base_url=args.base_url, timeout=30.0, follow_redirects=True
    ) as client:
        try:
            await se_connecter(client, args.email, args.mot_de_passe)
        except RuntimeError as exc:
            print(f"ERREUR : {exc}", file=sys.stderr)
            return 1

        alertes_ids, cibles_graphe = await recuperer_cibles(client)
        print(
            f"{len(alertes_ids)} alerte(s) détectée(s), "
            f"{len(cibles_graphe)} fragment(s) graphe extrait(s)."
        )
        if not alertes_ids:
            print(
                "Aucune alerte trouvée sur ce tenant — cohérent avec la "
                "limite connue du générateur (Scénario B, option a). Le "
                "scénario tournera uniquement sur GET /alertes.",
                file=sys.stderr,
            )

        resultats = Resultats()
        debut = time.monotonic()
        await asyncio.gather(
            *(
                coroutine_charge(client, alertes_ids, cibles_graphe, args.duree, resultats)
                for _ in range(args.concurrence)
            )
        )
        duree_reelle = time.monotonic() - debut

        print("\n--- Résultats Scénario C ---")
        print(resumer(resultats, duree_reelle))

    return 0


def construire_parseur() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Scénario C (Étape 5) — charge HTTP concurrente sur le "
            "dashboard B7/B8. Lecture seule (GET uniquement), sûr à "
            "relancer sur le tenant de test."
        )
    )
    parser.add_argument(
        "--base-url", default="http://localhost:8080", help="URL de souverain_app"
    )
    parser.add_argument(
        "--email", required=True, help="Compte de test du tenant de charge isolé"
    )
    parser.add_argument("--mot-de-passe", required=True)
    parser.add_argument(
        "--concurrence", type=int, default=10, help="Nombre de coroutines concurrentes"
    )
    parser.add_argument("--duree", type=float, default=60.0, help="Durée en secondes")
    return parser


def main() -> None:
    args = construire_parseur().parse_args()
    code_sortie = asyncio.run(executer(args))
    sys.exit(code_sortie)


if __name__ == "__main__":
    main()
