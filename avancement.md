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
| 1 | PostgreSQL / TimescaleDB | **VALIDÉE** |
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

## Détail — Brique 1 (PostgreSQL / TimescaleDB multi-tenant)

**Statut : VALIDÉE**

**Date de validation : 13 août 2026, par le fondateur (Seydou Dangande Abdoul Aziz), sur ThinkPad X1 Carbon Gen 6.**

Décision d'architecture actée : isolation **schema-per-tenant** (conforme au Bloc 9 du document fondateur).

Livré :
- Schéma partagé (`shared.tenants_registry`) + template de schéma tenant (`{tenant}.transactions`, hypertable TimescaleDB).
- Provisioning technique bas niveau (`provision_tenant_schema()`), avec validation stricte du nom de schéma (protection injection SQL).
- Pool de connexions asyncpg, configuration via `pydantic-settings`.
- Healthcheck DB (connexion, extension TimescaleDB, schéma partagé).
- Migration versionnée `0001_init_shared_schema.sql`.
- Service `postgres` dans `docker-compose.yml` racine sous le profile `postgres`.

Deux bugs réels détectés et corrigés lors de la vérification locale (non détectables en environnement de génération sans Docker) :
1. `config.py` — résolution du fichier `.env` dépendante du répertoire d'exécution → corrigée pour remonter jusqu'à la racine du dépôt, quel que soit le dossier courant.
2. `docker-compose.yml` — healthcheck `pg_isready` sans flag `-d`, ciblait une base inexistante → corrigé pour cibler explicitement `souverain_os`.

Validation finale effectuée sur la machine réelle du fondateur, contre une vraie instance PostgreSQL/TimescaleDB (pas de mock) :
- `docker compose --profile postgres up -d` — conteneur `healthy`.
- Migration `0001_init_shared_schema.sql` appliquée avec succès.
- `uv run pytest -v` — **15/15 tests passés** (13 unitaires + 2 intégration, contre la vraie base).
- `uv run python scripts/db_healthcheck.py` — **SAIN** (connexion, extension TimescaleDB 2.17.2, schéma partagé tous OK).
- `uv run ruff check .` / `uv run mypy src/` — propres.
- Non-régression Brique 0 confirmée.

**Brique 1 validée. Prête pour l'analyse de la Brique 2 (Auth / RBAC minimal + fondations SOUVERAIN-ID) dès demande explicite du fondateur.**

## Règle

Ne pas marquer une brique comme terminée uniquement parce que son code existe. La validation doit inclure tests, vérification manuelle et validation explicite du fondateur.
