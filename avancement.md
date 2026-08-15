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
| 2 | Auth / RBAC | **VALIDÉE** |
| 3 | Générateur + ingestion | **VALIDÉE** |
| 4 | Détection Hybrid-Stream | **VALIDÉE** |
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

## Détail — Brique 2 (Auth / RBAC minimal + fondations SOUVERAIN-ID)

**Statut : VALIDÉE**

**Date de validation : 13 août 2026, par le fondateur (Seydou Dangande Abdoul Aziz), sur ThinkPad X1 Carbon Gen 6.**

Décisions d'architecture actées (validées avant implémentation, en deux passes d'analyse) :
- Utilisateurs dans `shared.users`, FK vers `shared.tenants_registry` (`ON DELETE RESTRICT`).
- Hachage Argon2id (`argon2-cffi`).
- JWT signé HMAC-SHA256 (MVP).
- Révocation via `token_version` (implémentée dès cette brique, pas reportée).
- Rôles MVP : `admin`, `analyst`, `auditor`.
- SOUVERAIN-ID : fondation uniquement (UUID5 déterministe, séparé de `user_id`).
- Migrations numérotées localement par brique (dépendance d'ordre documentée en texte).
- Dépendance interne vers la Brique 1 via le workspace `uv` (`py.typed` ajouté à la Brique 1 pour exposer son typage).

Livré :
- `password_hashing.py`, `jwt_tokens.py`, `souverain_id.py`, `rbac.py`, `session.py`, `repository.py`, `api.py` (`/auth/login`, `/auth/me`).
- Migration `0001_init_users_table.sql`.
- 24 tests : 17 unitaires + 7 intégration (login réel, révocation, désactivation, contrainte email unique).

Bug réel détecté et corrigé lors de la validation locale (non détectable en environnement de génération sans Docker) :
- `tests/test_api.py` utilisait `fastapi.testclient.TestClient`, qui exécute l'application dans un thread séparé avec sa propre boucle asyncio. Le pool de connexions `asyncpg`, créé dans la boucle du test, devenait inutilisable depuis ce thread (`RuntimeError: ... attached to a different loop`). **Ce n'était pas un bug de l'API elle-même** (fonctionnelle sous Uvicorn en production), uniquement un défaut de l'outillage de test. Corrigé en remplaçant `TestClient` par `httpx.AsyncClient` + `ASGITransport`, qui exécute tout dans la même boucle asyncio que les fixtures — pattern actuellement recommandé pour tester une application ASGI de manière asynchrone.

Validation finale effectuée sur la machine réelle du fondateur, contre une vraie instance PostgreSQL/TimescaleDB avec les migrations Brique 1 ET Brique 2 appliquées :
- `uv run pytest -v` — **24/24 tests passés** (aucun skip, aucun échec).
- `uv run ruff check .` / `uv run mypy src/` — propres.
- Non-régression Briques 0 et 1 confirmée.

**Brique 2 validée. Prête pour l'analyse de la Brique 3 (Générateur + ingestion de transactions synthétiques) dès demande explicite du fondateur.**

## Détail — Brique 3 (Générateur + ingestion de transactions synthétiques)

**Statut : VALIDÉE**

**Date de validation : 15 août 2026, par le fondateur (Seydou Dangande Abdoul Aziz), sur ThinkPad X1 Carbon Gen 6.**

Décisions d'architecture actées (analyse validée avant implémentation) :
- Niveau de réalisme des patterns criminels sahéliens (Bloc 7) : Intermédiaire — paramétrable (intensité, fenêtre temporelle, montants), bruit contrôlé, seed fixe pour reproductibilité.
- Mode de génération : batch (one-shot). Le mode stream continu reste porté par la Brique 4 (Hybrid-Stream).
- Stockage : table `transactions` réelle de la Brique 1, colonne `is_synthetic` ajoutée par une migration portée par la Brique 3 (ne modifie aucun fichier de la Brique 1).
- Déclenchement : CLI uniquement (`uv run souverain-generer`), pas d'endpoint API en MVP.
- Volumétrie : configurable, défaut 5 000 transactions, jusqu'à 50 000 recommandé.
- Tenant MVP : un seul (`tenant_ne`, Niger), `tenant_id` générique dans `inserer_transactions()` pour extension future.

Dépendance réelle découverte et traitée pendant l'implémentation :
- `{tenant}.transactions.tenant_id/country_code/data_classification` sont des colonnes `NOT NULL` référençant `shared.tenants_registry`, qui n'a aucun mécanisme d'enregistrement avant la Brique 8 (`create_tenant()` complet). Ajout d'un bootstrap MVP minimal et explicitement provisoire (`scripts/bootstrap_tenant_ne.sql`), à remplacer par la vraie gouvernance en Brique 8.

Livré :
- `generateur_legitime.py` (transactions Mobile Money légitimes, distribution log-normale des montants), `patterns_suspects.py` (6 patterns du Bloc 7 : nocturne, structure en étoile, micro-fractionnement, saisonnalité, flux frontalier, compte pivot), `ingestion.py` (insertion par lots de 500, réutilise `create_pool()`/`validate_schema_name()` de la Brique 1), `cli.py` (`uv run souverain-generer`), `config.py`.
- Migration `0001_add_is_synthetic.sql` + auto-réparation de la colonne dans `inserer_transactions()` (idempotent, indépendant de l'ordre d'exécution de la migration).
- `scripts/bootstrap_tenant_ne.sql`.
- 21 tests : 15 unitaires (génération pure, sans DB) + 6 intégration (contre une vraie instance PostgreSQL/TimescaleDB, tenant éphémère provisionné et nettoyé automatiquement).

Bug corrigé pendant la validation locale (non détectable en environnement de génération sans accès au dépôt réel) :
- Le `pyproject.toml` racine faisait échouer `uv sync` (hatchling ne trouvait pas de répertoire correspondant au nom du projet racine, qui n'est qu'un point d'ancrage de workspace sans code propre). Corrigé par l'ajout de `[tool.uv]` / `package = false`. Découverte annexe : `uv sync` seul n'installe aucune brique du workspace, `uv sync --all-packages` est nécessaire.

Validation finale effectuée sur la machine réelle du fondateur, contre une vraie instance PostgreSQL/TimescaleDB avec les migrations Briques 1, 2 et 3 appliquées, tenant `tenant_ne` bootstrapé et provisionné :
- `uv run pytest` — **21/21 tests passés** (15 unitaires + 6 intégration).
- `uv run ruff check briques/brique_03_generateur_ingestion` — All checks passed.
- `uv run mypy src` (depuis le dossier de la brique) — Success, no issues found.
- `uv run souverain-generer --tenant tenant_ne` — **5000 transactions insérées**, `is_synthetic = true` sur 5000/5000, répartition des canaux cohérente avec la configuration (55 % Orange Money, 30 % Airtel Money, 15 % Moov Money).
- Non-régression Briques 0, 1 et 2 confirmée.

**Brique 3 validée. Prête pour l'analyse de la Brique 4 (Moteur de détection Hybrid-Stream) dès demande explicite du fondateur.**

## Détail — Brique 4 (Moteur de détection Hybrid-Stream)

**Statut : VALIDÉE**

**Date de validation : 15 août 2026, par le fondateur (Seydou Dangande Abdoul Aziz), sur ThinkPad X1 Carbon Gen 6.**

Décisions d'architecture actées (analyse validée avant implémentation) :
- "Hybrid" = traitement batch en source (lecture SQL triée par `occurred_at`), mais séquentiel et état-plein dans le moteur — chaque règle reçoit les transactions une par une et maintient sa propre fenêtre glissante par compte. Une composante statistique/calibrée reste documentée comme Vision, hors périmètre MVP.
- Sortie : table dédiée `{tenant}.detections`, migration portée par la Brique 4 (`0001_create_detections_table.sql`), même mécanique que `is_synthetic` en Brique 3 — ne modifie aucun fichier des briques précédentes.
- Seuils MVP validés tels quels dès la première implémentation (structure étoile ≥ 6 destinataires/90min, compte pivot ≥ 3 réceptions puis ≥ 2 redistributions/60min, micro-fractionnement ≥ 10 transactions <1000 XOF/20min, nocturne ≥ 4 transactions 22h-4h, flux frontalier sans seuil).
- Saisonnalité explicitement exclue des règles de détection MVP (facteur de contexte réservé à la Vision).
- `is_synthetic` jamais utilisé comme critère de détection — même principe que `pattern_label` en Brique 3, pour que le moteur ne puisse pas "tricher".
- Dépendance vers la Brique 3 (`patterns_suspects.py`) strictement scopée aux tests (`dev` dependency group), jamais importée en runtime.

Limite MVP documentée explicitement :
- La règle `flux_frontalier` ne détecte le motif Niamey→frontière que via la convention de nommage du générateur synthétique (`niamey_*`/`*frontiere*`) — un placeholder fonctionnel pour les données de test, pas une vraie détection géographique. Un référentiel compte→région réel est nécessaire en Vision.

Livré :
- `modeles.py` (TransactionObservee, DetectionEvent, indépendants de la Brique 3), `regles/base.py` (fenêtre glissante réutilisable), 5 règles à état (`structure_etoile.py`, `compte_pivot.py`, `micro_fractionnement.py`, `nocturne.py`, `flux_frontalier.py`), `moteur.py` (orchestration séquentielle), `lecture.py` (source batch triée), `persistence.py` (écriture + auto-réparation de la table), `cli.py` (`uv run souverain-detecter`).
- Migration `0001_create_detections_table.sql`.
- 15 tests : 13 unitaires (règles + moteur, réutilisent `patterns_suspects.py` de la Brique 3 en mémoire, jamais persisté avec label) + 2 intégration (contre une vraie instance PostgreSQL/TimescaleDB, tenant éphémère + lecture réelle sur les 5000 transactions de `tenant_ne`).

Bug corrigé pendant la validation locale (non détectable en environnement de génération sans accès au dépôt réel) :
- Le dépôt possède un dossier `tests/` à la racine du workspace (`tests/integration/`), entrant en collision avec `briques/brique_04_detection/tests/` quand `pytest` est invoqué depuis la racine — Python résolvait `import tests` vers le mauvais dossier. Corrigé en remplaçant l'import direct `from tests.conftest import ...` par une vraie fixture `pytest` dans `conftest.py`, immunisée contre ce type de collision de nom.
- Erreur de nommage dans `pyproject.toml` de la Brique 4 : la dépendance de test vers la Brique 3 référençait `brique-03-generateur-ingestion`, alors que le nom réel du paquet déclaré dans `briques/brique_03_generateur_ingestion/pyproject.toml` est `souverain-generateur`. Corrigé.

Validation finale effectuée sur la machine réelle du fondateur, contre une vraie instance PostgreSQL/TimescaleDB avec les migrations Briques 1, 3 et 4 appliquées, sur les 5000 transactions réelles de `tenant_ne` :
- `uv run pytest` — **15/15 tests passés** (13 unitaires + 2 intégration).
- `uv run ruff check briques/brique_04_detection` — All checks passed.
- `uv run mypy src` (depuis le dossier de la brique) — Success, no issues found.
- `uv run souverain-detecter --tenant tenant_ne` — **69 détections générées et enregistrées** dans `tenant_ne.detections` : compte_pivot (8), flux_frontalier (25), micro_fractionnement (4), structure_etoile (6), transactions_nocturnes (26). Répartition confirmée par requête SQL directe.
- Non-régression Briques 0, 1, 2 et 3 confirmée.

**Brique 4 validée. Prête pour l'analyse de la Brique 5 (Scoring + alertes) dès demande explicite du fondateur.**

## Règle

Ne pas marquer une brique comme terminée uniquement parce que son code existe. La validation doit inclure tests, vérification manuelle et validation explicite du fondateur.
