# SOUVERAIN-OS — Avancement

**Source de vérité opérationnelle sur l'état réel du projet.**
Ne jamais faire passer une brique à `VALIDÉE` automatiquement — la validation finale appartient exclusivement au fondateur.

## Statuts possibles

```text
NON COMMENCÉE
EN ANALYSE
EN DÉVELOPPEMENT
EN TEST
EN VALIDATION
VALIDÉE
```

## État des briques

| Brique | Nom | Statut |
|---|---|---|
| 0 | Fondations | **VALIDÉE** |
| 1 | PostgreSQL / TimescaleDB | NON COMMENCÉE |
| 2 | Auth / RBAC | NON COMMENCÉE |
| 3 | Générateur + ingestion | NON COMMENCÉE |
| 4 | Détection Hybrid-Stream | NON COMMENCÉE |
| 5 | Scoring + alertes | NON COMMENCÉE |
| 6 | Neo4j | NON COMMENCÉE |
| 7 | Dashboard / investigation | NON COMMENCÉE |
| 8 | Audit + Human-in-the-loop | NON COMMENCÉE |

## Phase transverse (après le flux principal)

- RAG (LlamaIndex + ChromaDB) — NON COMMENCÉE
- Ollama / Mistral — NON COMMENCÉE
- PQC (Kyber / Dilithium) — NON COMMENCÉE
- Redis / Celery — NON COMMENCÉE
- Prometheus / Grafana — NON COMMENCÉE
- SOUVERAIN-ID complet — NON COMMENCÉE

## Détail — Brique 0 (Fondations)

**Statut : VALIDÉE**

**Date de validation : 12 août 2026, par le fondateur (Seydou Dangande Abdoul Aziz).**

Validation effectuée sur la machine réelle du fondateur (ThinkPad X1 Carbon Gen 6), indépendamment de l'environnement de génération :

- `uv sync` — installation réussie (Python 3.12.13 téléchargé automatiquement par `uv`).
- `uv run pytest -v` — 6/6 tests passés.
- `uv run python scripts/healthcheck_env.py` — healthcheck SAIN, exit code 0.
- `uv run ruff check .` — All checks passed.
- `uv run mypy src/` — Success, no issues found.

Livré :
- Structure complète du repository (cible finale posée, briques futures en préparatoire uniquement).
- Configuration Python via `uv` (workspace, Option A verrouillée).
- Ruff, mypy, pytest, pre-commit configurés.
- Docker Compose socle (sans service métier — profiles vides).
- `.env.example`, `.gitignore`.
- Documentation initiale (README, ARCHITECTURE, ADR-000).
- Tests de base + healthcheck minimal de l'environnement.

Non inclus (explicitement exclu du périmètre de la Brique 0) :
- PostgreSQL / TimescaleDB
- Neo4j
- Auth / RBAC
- SOUVERAIN-ID
- RAG (LlamaIndex / ChromaDB)
- Ollama / Mistral
- PQC (Kyber / Dilithium)
- Redis / Celery
- Monitoring métier (Prometheus / Grafana)

**Brique 0 validée. Prête pour l'analyse de la Brique 1 (PostgreSQL / TimescaleDB) dès demande explicite du fondateur.**

## Règle

Ne pas marquer une brique comme terminée uniquement parce que son code existe. La validation doit inclure tests, vérification manuelle et validation explicite du fondateur.
