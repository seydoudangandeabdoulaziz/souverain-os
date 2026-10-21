# SOUVERAIN-OS

**Système Ouvert et Unifié pour la Veille Souveraine, l'Espace de Renseignement et l'ANalyse des Opérations de Sécurité.**

Mission : premier système immunitaire numérique africain — détection et analyse de criminalité financière, souveraineté des données sur le sol africain.

Porteur du projet : **Seydou Dangande Abdoul Aziz** — EMIG, Niamey, Niger.

> **Statut actuel :** les briques 0 à 8 sont indiquées comme validées dans le suivi du projet.
> **Étape 6A :** clôturée le 20 octobre 2026.
> **Étape 6B :** non commencée.
>
> Consulter [`avancement.md`](./avancement.md) pour l'état détaillé,
> les validations et les réserves éventuelles.
---

## Principe de lecture de ce dépôt

```text
STRUCTURE ≠ IMPLÉMENTATION
```

La présence d'un dossier `briques/brique_XX_nom/` **ne signifie pas** que cette brique est développée. Chaque brique future ne contient, tant qu'elle n'est pas commencée, qu'un `README.md` décrivant son objectif — jamais de code métier anticipé.

## État réel du projet

Voir [`avancement.md`](./avancement.md) pour le statut détaillé de chaque brique.

## Architecture

Voir [`ARCHITECTURE.md`](./ARCHITECTURE.md) pour la vue d'ensemble technique et [`docs/architecture/`](./docs/architecture/) pour le détail.

## Ordre des briques du projet

0. Fondations
1. PostgreSQL / TimescaleDB multi-tenant
2. Auth / RBAC minimal + fondations SOUVERAIN-ID
3. Générateur + ingestion de transactions synthétiques
4. Moteur de détection Hybrid-Stream
5. Scoring + alertes
6. Graphe Neo4j
7. Dashboard / investigation
8. Audit trail + Human-in-the-loop

Les briques 0 à 8 sont indiquées comme validées dans le suivi du projet.

Les composants transverses — RAG, Ollama/Mistral, PQC,
Redis/Celery, Prometheus/Grafana et SOUVERAIN-ID complet —
doivent être suivis selon leur état réel dans `avancement.md`.

L'étape 6 est divisée en deux phases :
- **6A — Faisabilité de l'inférence locale :** clôturée le 20 octobre 2026.
- **6B — Explication des alertes par l'IA :** non commencée.
## Démarrage rapide (Brique 0)

```bash
cd briques/brique_00_fondations
uv sync
uv run pytest
uv run python scripts/healthcheck_env.py
```

## Contraintes non négociables

- 100 % open source et auditable.
- Inférence IA locale (Ollama) — aucune donnée ne quitte le territoire national.
- Multi-tenant natif dès le départ.
- Validation de la faisabilité mémoire avant chaque brique.
- Distinction explicite MVP / Vision pour chaque composant.
- Fallback défini pour tout composant critique.

## Environnement de développement

- ThinkPad X1 Carbon Gen 6 — Intel i7-8650U — **16 Go DDR4** — 512 Go SSD — Ubuntu 26.04 LTS
- Python 3.12 via `uv`
- Ruff, mypy, pytest, pre-commit

## Contribuer

Voir [`CONTRIBUTING.md`](./CONTRIBUTING.md).

## Sécurité

Voir [`SECURITY.md`](./SECURITY.md).

## Licence

Voir [`LICENSE`](./LICENSE).
