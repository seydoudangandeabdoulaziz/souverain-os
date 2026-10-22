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
| 5 | Scoring + alertes | **VALIDÉE** |
| 6 | Neo4j | **VALIDÉE** |
| 7 | Dashboard / investigation | **VALIDÉE** |
| 8 | Audit + Human-in-the-loop | **VALIDÉE** |

## Extensions V2 (après le flux principal 0–8)

| Extension | Nom | Statut |
|---|---|---|
| Brique 1 V2 | Gouvernance des tenants (CLI) | **VALIDÉE** |
| Brique 2 V2 | Gouvernance des utilisateurs (routes web) | **VALIDÉE** |

## Phase transverse — Étapes (ordre consolidé après revue d'architecture)

| Étape | Nom | Statut |
|---|---|---|
| 1 | Hygiène de socle (backup/restore, /health, logs structurés) | **VALIDÉE** |
| 2 | Intégrité des données métier | **VALIDÉE** |
| 3 | UX/UI (fondations) | **VALIDÉE** |
| 4 | Prometheus/Grafana | **VALIDÉE** (4a + 4b) |
| 5 | Test de charge du pipeline actuel | **VALIDÉE** |
| 6 | Ollama/Mistral (→ Ministral 3 8B, voir détail) | 6a VALIDÉE (clôture simplifiée le 20 octobre 2026), 6b NON COMMENCÉE — grille de fidélité validée en principe (22 octobre 2026), tests à réussir avant démarrage |
| 7 | Sécurité IA/RAG (conception) | NON COMMENCÉE |
| 8 | RAG | NON COMMENCÉE |
| 9 | Redis/Celery (conditionnel à l'étape 5) | NON COMMENCÉE |
| 10 | SOUVERAIN-ID complet | NON COMMENCÉE |
| 11 | PQC (ML-KEM + ML-DSA) | NON COMMENCÉE |
| 12 | Résilience inter-États (conception) | NON COMMENCÉE |

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
- `{tenant}.transactions.tenant_id/country_code/data_classification` sont des colonnes `NOT NULL` référençant `shared.tenants_registry`, qui n'a aucun mécanisme d'enregistrement automatisé. Ajout d'un bootstrap MVP minimal et explicitement provisoire (`scripts/bootstrap_tenant_ne.sql`), à remplacer par une vraie gouvernance multi-tenant (`create_tenant()`) — **correction du 28 août 2026** : cette référence pointait initialement vers "la Brique 8", mais le périmètre de la Brique 8 a depuis été confirmé strictement limité à Audit + Human-in-the-loop (`00_DECISIONS_VERROUILLEES.md`). `create_tenant()` reste un besoin réel non positionné dans l'ordre numéroté, au même titre que les notifications citoyens — voir le point en suspens ajouté à `06_ROADMAP_ET_BRIQUES.md`.

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

## Détail — Brique 5 (Scoring + alertes)

**Statut : VALIDÉE**

**Date de validation : 21 août 2026, par le fondateur (Seydou Dangande Abdoul Aziz), sur ThinkPad X1 Carbon Gen 6.**

Décisions d'architecture actées (analyse validée avant implémentation) :
- Granularité du score : `compte_pivot` seul (déjà renseigné par les 5 règles de la Brique 4). La fenêtre glissante n'est pas un axe de granularité séparé — un paramètre de la formule d'agrégation.
- Fenêtre glissante : 7 jours (`FENETRE_JOURS`), provisoire.
- Formule : somme pondérée par `pattern_type`, dédupliquée (un même pattern détecté N fois sur la fenêtre ne compte qu'une fois). Poids provisoires : `compte_pivot` (30), `structure_etoile` (25), `micro_fractionnement` (20), `transactions_nocturnes` (15), `flux_frontalier` (10).
- Seuil d'alerte : 50 (`SEUIL_ALERTE`), provisoire — à recalibrer après la première exécution réelle sur `tenant_ne`.
- Anti-doublon : une alerte `'ouverte'` par `compte_pivot`, mise à jour en place (UPSERT sur index unique partiel), jamais dupliquée. Une alerte `'fermee'` n'est jamais rouverte — une nouvelle détection franchissant à nouveau le seuil crée une nouvelle alerte (historique distinct, auditabilité).
- Déclenchement : CLI uniquement (`uv run souverain-scorer`), pas d'endpoint API — contradiction avec le Bloc 10 du document fondateur signalée mais non réimplémentée, cohérence avec Briques 3/4.

Correction actée pendant l'implémentation (avant toute validation, donc pas un bug de "validation locale" comme pour les briques précédentes — trouvé en écrivant les tests d'intégration) :
- Une première version de `lecture.py` excluait les détections déjà "traitées" via une table de suivi (`{tenant}.detections_traitees`), pour éviter de recréer des alertes en double. Cette table a été retirée : elle cassait le score cumulatif sur la fenêtre glissante (une détection ancienne "déjà traitée" restait exclue des cycles suivants même si toujours dans la fenêtre de 7 jours). `lecture.py` relit désormais l'intégralité de la fenêtre à chaque cycle ; l'UPSERT sur l'index unique partiel de `{tenant}.alertes` reste la seule garantie anti-doublon, et suffit puisqu'il est idempotent.

Bug réel détecté et corrigé lors de la validation locale (non détectable en environnement de génération sans accès à la vraie base du fondateur) :
- `tenant_ne.alertes` existait déjà sur la base réelle avant l'application de la migration Brique 5 — vestige d'une tentative d'implémentation antérieure de cette même brique (schéma différent : colonnes `id`/`premiere_detection_at`/`derniere_detection_at`/`is_synthetic`, table de jonction séparée `alertes_detections`, index unique sur `(tenant_id, compte_pivot)` au lieu de `(compte_pivot)` seul). `CREATE TABLE IF NOT EXISTS` a silencieusement conservé cette ancienne table au lieu de créer celle du schéma validé (`NOTICE: relation "alertes" already exists, skipping`), faisant échouer toute vérification manuelle en aval (`column "pattern_types_impliques" does not exist`). Les deux tables résiduelles étaient vides (aucune donnée perdue) : corrigé par `DROP TABLE tenant_ne.alertes_detections` puis `DROP TABLE tenant_ne.alertes`, suivi d'une réapplication de `0001_create_alertes_table.sql`. Schéma résultant vérifié conforme (`\d tenant_ne.alertes`) avant de continuer.

Livré :
- `modeles.py` (`DetectionNonTraitee`, `ScoreCompte`, indépendants de `DetectionEvent` de la Brique 4), `seuils.py` (constantes provisoires isolées), `agregation.py` (fonction pure de calcul, dédup par pattern_type), `lecture.py` (lecture pleine fenêtre), `persistence.py` (UPSERT alerte + auto-réparation de la table), `cli.py` (`uv run souverain-scorer`).
- Migration `0001_create_alertes_table.sql` (une seule table `alertes`, pas de `detections_traitees`).
- 8 tests unitaires (`agregation.py`, sans DB) : tous exécutés en environnement de génération, **8/8 passés**. Couvrent la dédup multi-occurrences, les combinaisons de patterns franchissant/ne franchissant pas le seuil, un pattern lourd seul sous le seuil, plusieurs comptes distincts, le détail JSONB, et le cas défensif d'un `pattern_type` inconnu (poids 0, pas de crash).
- 3 tests d'intégration (`test_integration.py`, contre vraie DB, tenant éphémère) : **non exécutés dans l'environnement de génération** (pas de PostgreSQL disponible) — à exécuter sur machine réelle avant validation. Couvrent le cycle complet, le rejeu du même cycle sans nouvelle détection (vérifie l'UPSERT plutôt qu'une exclusion en lecture), et le scénario exact du bug corrigé (détection ancienne toujours dans la fenêtre qui doit continuer à compter).

Vérifié en environnement de génération (dépôt réel cloné, pas de suppositions sur le schéma) :
- `uv sync --all-packages` — installation réussie, Brique 5 ajoutée à `[tool.uv.workspace].members`.
- `uv run pytest briques/brique_05_scoring_alertes/tests/test_agregation.py` — **8/8 tests passés**.
- `uv run ruff check briques/brique_05_scoring_alertes` — All checks passed (après `--fix` sur 8 erreurs mineures : alias `datetime.UTC`, un import inutilisé, un tri d'imports).
- `uv run mypy src` (depuis le dossier de la brique) — Success, no issues found.
- Non-régression Briques 0 à 4 : `uv run pytest` sur les suites unitaires (hors tests nécessitant une DB) des 5 briques précédentes — aucun échec imputable à la Brique 5 ; les échecs observés (connexion PostgreSQL refusée, plugin asyncio de la Brique 2) sont uniquement liés à l'absence de conteneur Docker dans cet environnement, déjà documentés comme limite de l'environnement de génération sur les briques précédentes.

Vérifié sur la machine réelle du fondateur (ThinkPad X1 Carbon Gen 6), contre une vraie instance PostgreSQL/TimescaleDB :
- `uv sync --all-packages` — installation réussie, Brique 5 ajoutée au workspace.
- `docker compose --profile postgres up -d` — conteneur `healthy`.
- Migration `0001_create_alertes_table.sql` appliquée (après correction du bug de table résiduelle ci-dessus).
- `uv run pytest briques/brique_05_scoring_alertes/tests/test_integration.py -v -s` — **3/3 tests passés**, dont le test du scénario exact du bug de fenêtre glissante corrigé pendant l'implémentation.
- `uv run ruff check briques/brique_05_scoring_alertes` — All checks passed.
- `uv run mypy src` (depuis le dossier de la brique) — Success, no issues found.
- `uv run souverain-scorer --tenant tenant_ne` — **69 détections lues, 51 comptes scorés, 0 alerte créée**. Confirmé correct par requête directe sur `tenant_ne.detections` : 18 comptes ont 2 patterns distincts sur la fenêtre actuelle, la meilleure combinaison réelle atteint 45/50 (`compte_pivot` + `transactions_nocturnes`) — aucun compte n'a encore 3 patterns distincts, donc 0 alerte est le résultat correct de la formule sur ce jeu de données, pas un défaut.
- Non-régression Briques 0 à 4 confirmée (tests unitaires, hors dépendance DB).

**Décision du fondateur sur le seuil, actée sans réserve :**
0 alerte sur `tenant_ne` n'est pas un signe de sous-calibration. Le
générateur de la Brique 3 utilise un préfixe de compte distinct et fixe
par pattern (`hub_` → `structure_etoile`, `pivot_` → `compte_pivot`,
`cpt_` → `micro_fractionnement`/`transactions_nocturnes`, `niamey_` →
`flux_frontalier`) : un compte ne peut donc jamais cumuler deux patterns
différents avec ce générateur, quel que soit le volume généré —
augmenter le volume n'aurait rien changé. 0 alerte est le résultat
mathématiquement correct de la formule contre les données actuelles.

La formule elle-même reste validée indépendamment de cette contrainte :
`test_agregation.py` construit ses combinaisons de patterns librement en
mémoire (sans passer par le générateur), et `test_integration.py`
construit directement des `DetectionEvent` multi-patterns sur un même
compte contre une vraie base — les deux confirment que la formule
fonctionne correctement dès qu'un compte cumule effectivement plusieurs
patterns.

Limite MVP documentée dans le README de la Brique 5 : le chemin complet
"détection réelle → alerte réelle" n'est pas observable sur `tenant_ne`
en l'état. Une évolution du générateur Brique 3 (scénario de test
composite) pourrait lever cette limite plus tard — modification du code
déjà validé de la Brique 3, nécessitant sa propre validation explicite,
non traitée dans cette session.

Bugs de configuration workspace détectés et corrigés pendant la vérification combinée post-validation (révélés par la Brique 5, mais pas des bugs de la Brique 5 elle-même — tracés ici comme pour les bugs réels des briques précédentes) :
- **`asyncio_mode` manquant à la racine.** Chaque brique (`brique_01`, `brique_02`, `brique_04`, `brique_05`) déclare `asyncio_mode = "auto"` dans son propre `pyproject.toml`, mais la racine ne le déclarait pas. Lancer `uv run pytest` sur une seule brique fonctionnait (pytest résout alors le `pyproject.toml` de cette brique), mais lancer plusieurs briques ensemble depuis la racine faisait résoudre le `pyproject.toml` racine à la place — retombant sur le défaut `strict` de pytest-asyncio, qui casse les fixtures/tests async des Briques 1 et 2 (`db_settings_or_skip`, `test_require_role_*`). Corrigé par l'ajout de `asyncio_mode = "auto"` à `[tool.pytest.ini_options]` du `pyproject.toml` racine, aligné sur ce que chaque brique déclare déjà — aucun changement pour les runs scopés par brique.
- **Collision d'import entre `test_integration.py` de la Brique 4 et de la Brique 5.** Une fois le bug ci-dessus corrigé, un second problème est apparu : aucun dossier `tests/` de brique ne contient de `__init__.py`, donc le mode d'import par défaut de pytest (`prepend`) importe chaque fichier de test comme un module de premier niveau nommé d'après son seul nom de fichier — deux briques ayant chacune un `test_integration.py` entrent en collision dès qu'elles sont testées dans la même session (`import file mismatch`). Corrigé par l'ajout de `addopts = "--import-mode=importlib"` au même bloc `[tool.pytest.ini_options]` : ce mode d'import identifie chaque module par son chemin de fichier complet plutôt que par son seul nom de base, éliminant la collision sans renommer aucun fichier de test ni toucher au contenu d'aucune brique précédente (une seule ligne, un seul fichier — le `pyproject.toml` racine, déjà en cours de correction pour le bug précédent).

Les deux corrections confirmées sur la machine réelle du fondateur (`uv run pytest` sur les 6 briques 0 à 5 combinées, PostgreSQL démarré et sain) : **92/92 tests passés, 0 skip, 0 erreur.** Aucune régression sur les Briques 0 à 4, cycle complet de la Brique 5 vérifié de bout en bout.

**Brique 5 validée. Prête pour l'analyse de la Brique 6 (Graphe Neo4j) dès demande explicite du fondateur.**

## Détail — Brique 6 (Graphe criminel Neo4j)

**Statut : VALIDÉE**

**Date de validation : 25 août 2026, par le fondateur (Seydou Dangande Abdoul Aziz), sur ThinkPad X1 Carbon Gen 6.**

Décisions d'architecture actées (analyse validée avant implémentation) :
- **Contradiction identifiée et tranchée avant tout code** : Neo4j Community Edition ne supporte qu'une seule base de données (multi-base = Enterprise), en tension avec l'exigence multi-tenant natif et le niveau d'isolation physique déjà obtenu en Brique 1 (schema-per-tenant). Deux options présentées ; Option A retenue — isolation logique par `tenant_id` sur chaque nœud/relation, une seule base. Option B (une instance Neo4j par tenant) écartée : contredit le principe fondateur "ajouter un pays = ajouter un tenant, pas réécrire le système".
- **Point de passage unique** : `garde_isolation.py` est le seul fichier autorisé à contenir du Cypher (générique et métier confondus) — `requetes.py` ne fait que traduire ses résultats bruts en objets typés, `cli.py` n'appelle jamais Neo4j directement. Discipline documentée en tête de fichier : chaque `MATCH` filtre `tenant_id` sur tous les nœuds, y compris après plusieurs sauts ; double vérification défensive `ALL(...)` sur les traversées à longueur variable ; contrainte de schéma composite `(tenant_id, compte_id)` en renfort (vérifiée disponible en Community Edition).
- **Modèle** : pas de nœud `Transaction` séparé, chaque transaction est une relation `:ENVOIE`. `transaction_id` comme clé du `MERGE`, documenté comme reposant sur son unicité garantie (UUID Brique 1), pas une supposition implicite.
- **Portée du graphe** : import complet de `{tenant}.transactions` (pas seulement les comptes déjà détectés) — limite MVP documentée explicitement (import incrémental = Vision, coûteux à l'échelle UEMOA).
- **Double dépendance de lecture, jamais vers la Brique 4 directement** : `{tenant}.transactions` (Brique 1) et `{tenant}.alertes` statut `'ouverte'` (Brique 5), dupliquées en lecture directe sans import runtime — même principe que Brique 5 → Brique 4.
- **3 requêtes métier** : a) chaînes de redistribution multi-sauts, b) comptes pont entre deux comptes alertés, c) plus court chemin entre comptes alertés (`shortestPath`, remplace la proposition initiale "cluster dense" écartée car nécessitait le plugin GDS non installé et recouvrait la règle `structure_etoile` de la Brique 4).
- Déclenchement : CLI uniquement (`uv run souverain-grapher`), cohérent avec les briques précédentes.

Exigence de test explicite, respectée : `test_isolation_tenant.py` écrit en premier, avant tout autre test de la brique — scénario délibérément défavorable (deux tenants avec les mêmes `compte_id`), vérifie qu'aucune requête ne fuit d'un tenant à l'autre y compris via traversée multi-sauts, et que la contrainte composite empêche la fusion silencieuse de deux comptes de tenants différents.

Livré :
- `config.py`/`connexion.py` (driver Neo4j async, singleton, même principe que le pool asyncpg Brique 1), `modeles.py` (`TransactionAImporter`, `Chemin`, `ComptePont`), `lecture.py` (transactions + comptes alertés, double dépendance documentée), `garde_isolation.py` (contraintes, synchronisation par lots de 500, 3 requêtes métier — seul fichier Cypher), `requetes.py` (traduction Record → objets typés), `synchronisation.py` (orchestration), `cli.py` (`uv run souverain-grapher`).
- `docker-compose.yml` : service `neo4j` ajouté sous le profile réservé depuis la Brique 0, configuration mémoire JVM explicite (heap 512m-1G, page cache 512m).
- `.env.example` : section Brique 6 activée (URI, user, password, ports).
- 4 fichiers de test : `test_isolation_tenant.py` (5 tests, écrit en premier), `test_synchronisation.py` (3 tests, idempotence MERGE), `test_requetes.py` (3 tests, couche de présentation + cas `{tenant}.alertes` vide explicitement couvert).

Vérifié en environnement de génération (pas de Neo4j disponible, donc pas d'exécution réelle des tests) :
- `uv sync --all-packages` — réussi, Brique 6 ajoutée au workspace, driver `neo4j` résolu (v6.2.0).
- Tous les modules s'importent sans erreur (`python -c "from brique_06_neo4j import ..."`), aucune erreur de syntaxe ni d'import circulaire.
- `uv run ruff check briques/brique_06_neo4j` — All checks passed (après corrections mineures : f-strings au lieu de `%`, tri des imports).
- `uv run mypy src` (depuis le dossier de la brique) — Success, no issues found (9 fichiers).
- Non-régression Briques 0 à 5 : `uv run pytest` sur les 6 briques précédentes — **74 passed, 9 skipped, 9 erreurs** (uniquement `ConnectionRefusedError` PostgreSQL, absence de Docker ici — aucune régression imputable à la Brique 6).

Bug de répartition de code trouvé et corrigé pendant l'implémentation, avant tout run (pas un bug de validation locale — trouvé en écrivant `garde_isolation.py`) :
- Première version de `garde_isolation.py` faisait la traduction Record Neo4j → objets typés (`Chemin`, `ComptePont`) directement dans ses fonctions, alors que l'analyse avait explicitement acté que ce rôle appartient à `requetes.py`. Corrigé avant tout test écrit : `garde_isolation.py` retourne désormais des `dict` bruts (`Record.data()`), `requetes.py` porte la traduction.

Bug réel détecté et corrigé lors de la validation locale (non détectable en environnement de génération sans Neo4j) :
- Défaut de mot de passe incohérent entre `config.py` (`password: str = Field(default="")`) et `docker-compose.yml` (`NEO4J_AUTH: ${NEO4J_PASSWORD:-change_me}`). Le conteneur démarre avec `change_me` par défaut, mais le driver Python tentait une chaîne vide si `.env` ne surchargeait pas explicitement la variable — échec d'authentification silencieux (`AuthError`), sans lien avec la disponibilité du conteneur. Aggravé par la ligne `NEO4J_PASSWORD` commentée par défaut dans le `.env` réel du fondateur. Corrigé par l'alignement du défaut `config.py` sur `change_me` (cohérent avec `docker-compose.yml`), et décommentée côté `.env` réel. Un défaut identique des deux côtés est désormais la garantie — plus seulement une bonne pratique de configuration explicite.

Toutes les vérifications confirmées sur la machine réelle du fondateur, contre une vraie instance Neo4j Community + PostgreSQL/TimescaleDB :
- `uv run pytest briques/brique_06_neo4j/tests/ -v` — **11/11 tests passés** (5 isolation, 3 requêtes, 3 synchronisation), aucun skip.
- `uv run ruff check briques/brique_06_neo4j` — All checks passed.
- `uv run mypy src` (depuis le dossier de la brique) — Success, no issues found (9 fichiers).
- `SHOW CONSTRAINTS` (`cypher-shell`) — **les deux contraintes composites confirmées acceptées en Community Edition** : `compte_tenant_unique` (`UNIQUENESS`, `(tenant_id, compte_id)` sur `:Compte`) et `transaction_tenant_unique` (`RELATIONSHIP_UNIQUENESS`, `(tenant_id, transaction_id)` sur `:ENVOIE`) — point le plus incertain de toute l'analyse, levé.
- `uv run souverain-grapher --tenant tenant_ne` — **5000 transactions lues et synchronisées**, **88 chaînes de redistribution détectées** (3-6 sauts), 0 compte pont et 0 chemin entre alertés (cohérent avec 0 alerte ouverte sur `tenant_ne`, déjà établi en Brique 5 — pas un défaut).
- **Confirmation croisée inattendue** : les chaînes détectées suivent systématiquement la structure `cpt_XXX -> pivot_XXX -> cpt_XXX -> cpt_XXX` — le graphe redécouvre par la seule topologie des transactions la structure du pattern `compte_pivot` généré par la Brique 3, sans jamais lire `pattern_label` ni aucune sortie de la Brique 4. Signal fort que la Brique 6 capture une réalité structurelle, pas du bruit.
- `docker stats` — **931 Mo** réels pour le conteneur Neo4j, sous l'estimation initiale (~1,5-2 Go), confortable sur 14,87 Go disponibles pour Docker.
- Non-régression Briques 0 à 5 confirmée (aucun test cassé par l'ajout de la Brique 6).

**Brique 6 validée. Prête pour l'analyse de la Brique 7 (Dashboard / investigation) dès demande explicite du fondateur.**

## Détail — Brique 7 (Dashboard / investigation)

**Statut : VALIDÉE**

**Date de validation : 28 août 2026, par le fondateur (Seydou Dangande Abdoul Aziz), sur ThinkPad X1 Carbon Gen 6.**

Décisions d'architecture actées (analyse validée avant implémentation) :
- **Périmètre strictement lecture seule** : aucun déclenchement de calcul, aucun changement d'état d'alerte (`'ouverte' → 'fermee'` appartient entièrement à la Brique 8, non commencée).
- **Authentification — Option A** : `auth_cookie.py` lit le JWT depuis un cookie `httpOnly`, réutilise les primitives de la Brique 2 (`decode_token`, `get_user_by_id`) sans jamais modifier `session.py` (déjà validé) ni son wrapper `HTTPBearer`, inadapté à un dashboard HTMX.
- **Revalidation défensive du tenant** : `tenant_valide()` revérifie `tenant_id` du JWT contre `shared.tenants_registry.is_active` à chaque requête — un JWT signé ne prouve pas que le tenant est toujours actif maintenant. Testé explicitement (tenant désactivé après émission du jeton → rejeté).
- **Requêtes graphe exclusivement via `garde_isolation.py`** (Brique 6) — aucun Cypher dans cette brique, extension de la règle du point de passage unique.
- **Multilinguisme posé dès cette brique** (ADR-001, pas un ajout futur) : `t(cle, langue)` en global Jinja2, aucun texte français en dur, seul `fr.py` livré.
- **Rapports signés retirés du périmètre MVP** : la PQC (Dilithium-5) n'existe pas encore — aucun export, signé ou non, avant son existence. Évite de reconstruire deux fois la même fonctionnalité.
- **HTMX vendorisé localement** (récupéré via npm, domaine autorisé) — jamais de CDN étranger, conforme au Bloc 5.
- **Filtrage des résultats du graphe — Option A** : les 3 fonctions de la Brique 6 retournent les résultats pour tout le tenant, filtrage côté Python dans `routes/alertes.py`, aucune modification de la Brique 6 déjà figée.

Point de vigilance documenté explicitement (pas une correction — une limite assumée, différente des précédentes) :
- Contrairement aux limites d'échelle déjà acceptées en Brique 4/5/6 (traitements batch CLI, latence indifférente), le filtrage Option A du fragment graphe touche directement le temps de réponse d'une page web consultée par un humain qui attend. Atténué par la scission de la page de détail (chargement immédiat) et du fragment graphe (chargé après coup via HTMX, `hx-trigger="load"`, avec état de chargement visible). Pas un problème au volume actuel — à surveiller si le volume grossit, avant de passer à l'Option B (non implémentée).

Manque découvert, non corrigé silencieusement pendant l'implémentation :
- La Brique 2 est la seule brique du projet sans `py.typed` — jamais nécessaire jusqu'ici, personne n'en dépendait pour son typage. La Brique 7 est la première. Corriger proprement demande de toucher deux points de la Brique 2 déjà validée (fichier `py.typed` + son enregistrement dans `artifacts` de `pyproject.toml`, même traitement que la Brique 1). Non fait : contournement local autonome dans `pyproject.toml` de la Brique 7 (`ignore_missing_imports` ciblé), en attendant une décision explicite du fondateur.

Bug réel trouvé et corrigé pendant l'écriture des tests, avant tout run (pas un bug de validation locale) :
- La fixture `alerte_test` (conftest.py) confondait initialement `detection_ids` (à passer à `ScoreCompte`) avec les `transaction_id` des événements sources — deux identifiants différents. Corrigé par une relecture explicite de `{tenant}.detections` après insertion, pour récupérer les vrais `detection_id` générés côté persistence.

Bug réel détecté et corrigé lors de la validation locale (non détectable en environnement de génération sans PostgreSQL) :
- 3 tests échouaient (`test_lire_alerte_inexistante_retourne_none`, `test_liste_alertes_vide_affiche_le_message_dedie`, `test_detail_alerte_inexistante_retourne_404`) — cause commune : aucun n'utilisait la fixture `alerte_test`, donc `{tenant}.alertes` n'existait pas du tout pour ce tenant éphémère (la table est créée par `enregistrer_scores()` côté Brique 5, jamais par la Brique 7, strictement lecture). `asyncpg.exceptions.UndefinedTableError: relation "tenant_test_dashboard.alertes" does not exist` remontait brute jusqu'à l'utilisateur — inacceptable pour une page web consultée par un humain (contrairement à la Brique 6, où la même situation fait volontairement remonter l'erreur brute, public développeur d'un batch CLI). Corrigé par une nouvelle exception dédiée `TenantSansDonnees` (`lecture.py`), interceptée globalement dans `app.py` et présentée comme une page propre ("aucun cycle de scoring encore exécuté pour ce tenant"), tout en restant tracée (logs) — Option B validée après diagnostic. Les 3 tests corrigés distinguent maintenant explicitement ce cas ("table absente") du cas qu'ils prétendaient tester à l'origine ("table présente, ligne absente") via une nouvelle fixture dédiée `alertes_table_creee_sans_alerte`, et 2 tests supplémentaires couvrent le cas `TenantSansDonnees` lui-même, à la fois côté `lecture.py` et côté HTTP.
- Risque connexe identifié **et corrigé** : `brique_06_neo4j.lecture.lire_comptes_alertes()` (appelée par le fragment graphe de cette brique) lit elle aussi `{tenant}.alertes` et laisse délibérément la même exception remonter brute (philosophie assumée côté Brique 6, public développeur d'un batch CLI). Un accès direct/manuel à `/alertes/{id}/graphe` sur un tenant sans table (URL en favori, sans passer par la page de détail au préalable) exposait le même risque de 500 brut. Corrigé dans `routes/alertes.py` uniquement (`try/except UndefinedTableError` → liste vide) — fonctionnellement équivalent à "0 compte alerté" pour cette requête précise, comportement déjà validé par les tests existants de la Brique 6. **Aucune modification de la Brique 6.**
- Bug de fuite de driver Neo4j entre tests, révélé par l'ajout du test du point précédent (pas introduit par lui — préexistant, simplement jamais déclenché tant qu'un seul test du fichier touchait Neo4j via `client`) : `create_driver()` (Brique 6) est un singleton, mais chaque test pytest-asyncio tourne dans sa propre boucle asyncio (scope function). La fixture `driver` fermait bien le driver en fin de test ; la fixture `client` (Brique 7), elle, ne le faisait jamais — un driver créé dans la boucle d'un test fuyait vers le test suivant, lié à une boucle déjà détruite, provoquant un échec de `session.run()` sans rapport avec la logique métier testée. Corrigé par l'ajout de `close_driver()` en teardown de la fixture `client` (`tests/conftest.py`), même précaution que la fixture `driver`.

Livré :
- `config.py`, `auth_cookie.py` (adaptateur cookie, primitives Brique 2 réutilisées), `tenant_garde.py` (revalidation défensive), `traductions/` (`t()`, `fr.py`), `lecture.py` (alertes/détections, lecture seule, `TenantSansDonnees`), `modeles.py` (objets d'affichage), `routes/auth.py` (login/logout), `routes/alertes.py` (liste, détail, fragment graphe, protection contre le risque connexe), `app.py` (construction FastAPI, gestion `SessionInvalide` + `TenantSansDonnees`), `cli.py` (`uv run souverain-dashboard`), templates Jinja2 + HTMX (dont `tenant_sans_donnees.html`), `static/htmx.min.js` vendorisé.
- 20 tests : `test_tenant_garde.py` (3), `test_auth_cookie.py` (3), `test_lecture.py` (5), `test_routes_alertes.py` (9, dont le test du risque connexe), HTTP de bout en bout via `httpx.AsyncClient` + `ASGITransport`, jamais `TestClient`.

Vérifié sur la machine réelle du fondateur, contre une vraie instance PostgreSQL + Neo4j :
- `uv run pytest` sur les 8 briques (0 à 7) combinées — **123/123 tests passés**, aucun échec, aucune erreur (20 tests propres à la Brique 7 : 3 `test_tenant_garde.py` + 3 `test_auth_cookie.py` + 5 `test_lecture.py` + 9 `test_routes_alertes.py`).
- `uv run ruff check briques/brique_07_dashboard` — All checks passed.
- `uv run mypy src` (depuis le dossier de la brique) — Success, no issues found (13 fichiers).
- Utilisateur réel créé via script ponctuel (`creer_utilisateur_dashboard.py`, hors périmètre de la brique, cf. décision ci-dessous), connexion réussie dans un vrai navigateur (`http://localhost:8080`) : redirection `/login` → cookie `httpOnly` posé → `/alertes` → déconnexion fonctionnelle.
- Alerte réelle créée via un second script ponctuel (`creer_alerte_demo.py`, même principe — réutilise `enregistrer_detections`/`enregistrer_scores` déjà validées, aucune modification des Briques 4/5) : liste → détail → **fragment graphe vérifié en conditions réelles**, chargé après la page (comportement de scission voulu, observé), 3 sections rendues correctement, "Aucun résultat" correctement affiché (le compte de démo n'ayant jamais été synchronisé dans Neo4j — comportement attendu, pas un bug).

Deux bugs réels trouvés et corrigés lors de la validation locale (non détectables en environnement de génération sans PostgreSQL/Neo4j) :
- **Risque connexe sur le fragment graphe** : `brique_06_neo4j.lecture.lire_comptes_alertes()` laissait `UndefinedTableError` remonter brute si `{tenant}.alertes` n'existe pas — un accès direct à `/alertes/{id}/graphe` (URL en favori, sans passer par la page de détail) sur un tenant neuf exposait un 500 brut. Corrigé dans `routes/alertes.py` uniquement (`try/except` → liste vide), aucune modification de la Brique 6.
- **Fuite de driver Neo4j entre tests** : la fixture `client` (tests) ne fermait jamais le driver singleton de la Brique 6 — un driver créé dans la boucle asyncio d'un test fuyait vers le test suivant (boucle différente), provoquant un échec de `session.run()` sans rapport avec la logique testée. Révélé par l'ajout du test du point précédent, pas causé par lui. Corrigé par `close_driver()` en teardown de la fixture `client`, même précaution que la fixture `driver`.

Décision actée après validation : la création d'utilisateur via interface (route API dédiée dans la Brique 2) est **reportée explicitement**, pas oubliée — traitée pour l'instant par un script ponctuel hors périmètre des briques (`creer_utilisateur_dashboard.py`, non committé). Aucune modification de la Brique 2 pour cela, conformément à la décision du fondateur.

**Brique 7 validée. Prête pour l'analyse de la Brique 8 (Audit + Human-in-the-loop) dès demande explicite du fondateur.**

## Détail — Brique 8 (Audit trail + Human-in-the-loop)

**Statut : VALIDÉE le 4 septembre 2026, par le fondateur, sur ThinkPad X1 Carbon Gen 6. Implémentée, 138/138 tests passés sur PostgreSQL et Neo4j réels, zéro régression sur les Briques 0 à 7. La vérification manuelle dans un vrai navigateur a été effectuée ; la vérification visuelle du rôle `auditor` reste couverte par les tests automatisés, jugés suffisants par le fondateur.**

Décisions d'architecture actées (analyse validée avant implémentation, en plusieurs passes) :
- Actions humaines couvertes : fermeture d'alerte avec motif structuré (liste fermée : `faux_positif`, `confirme`, `en_cours_investigation`) + commentaire optionnel. Pas de réouverture, pas de modification du score, pas d'assignation.
- RBAC : `analyst` et `admin` peuvent fermer une alerte ; `auditor` voit l'historique seul (formulaire masqué côté affichage, refus `403` côté exécution même en cas de requête forgée).
- Interface : extension du dashboard Brique 7 via un nouveau module d'assemblage racine (`souverain_app/`), pas une modification interne de la Brique 7 — zéro fichier Brique 7 modifié en logique, un seul ajout additif (une div HTMX) dans `alerte_detail.html`.
- Immuabilité de `audit_log` : défense en profondeur actée explicitement — rôle PostgreSQL dédié (`souverain_brique8_audit`, privilèges `INSERT`/`SELECT` uniquement sur `audit_log`, jamais `UPDATE`/`DELETE`) **et** discipline applicative (aucune route de modification/suppression). Ce rôle a aussi `SELECT`/`UPDATE` sur `{tenant}.alertes`, nécessaire pour que la fermeture d'alerte et l'écriture d'audit restent atomiques (une seule transaction, un seul rôle) — l'absence d'`UPDATE`/`DELETE` spécifiquement sur `audit_log` constitue la garantie recherchée.
- Retouche de `require_role()` (Brique 2, déjà validée) : ajout d'un paramètre `user_dependency`, défaut inchangé (`get_current_user`) — rétrocompatible, nécessaire car `require_role()` était câblé en dur sur l'authentification par header `Bearer`, inutilisable pour une route cookie-based comme celle du dashboard.

Bug réel trouvé et corrigé pendant l'implémentation, avant tout test écrit (pas une correction de validation locale) :
- Le routeur de cette brique (`router = APIRouter()`) était initialement déclaré au niveau module, comme dans `brique_07_dashboard/routes/alertes.py` et `routes/auth.py` — motif reproduit sans intention. Ce pattern accumule les routes à chaque appel de `construire_routes_audit()` dans le même process Python (chaque test reconstruisant l'app ré-enregistrerait les mêmes routes sur le même routeur partagé). Corrigé pour cette brique en déplaçant la construction du routeur à l'intérieur de la fonction, vérifié par deux appels successifs de `creer_application_complete()` ne produisant plus aucun doublon. **Le même motif existe toujours dans la Brique 7 (`routes/alertes.py`, `routes/auth.py`) — signalé ici pour information, fichiers déjà validés, non corrigés.**

Incohérence documentaire relevée, signalée, non corrigée silencieusement :
- `brique_01_postgresql/tenant_provisioning.py` contient un commentaire affirmant que `create_tenant()` « appartient à la Brique 8 », antérieur à la correction du 28 août 2026 qui a explicitement retiré `create_tenant()` du périmètre de cette brique (voir `06_ROADMAP_ET_BRIQUES.md`). Le commentaire n'a jamais été mis à jour en conséquence. Aucune ligne de ce fichier n'a été modifiée par la Brique 8 — reste à corriger par décision explicite du fondateur.

Livré :
- `config.py`, `connection.py` (pool PostgreSQL dédié, rôle restreint, distinct du pool admin de la Brique 1), `modeles.py` (`MotifFermeture`, `EntreeAudit`, `AlerteNonFermable`), `persistence.py` (fermeture + audit dans une seule transaction, auto-réparation de la table via le pool admin), `lecture.py` (historique d'audit, jointure `shared.users`), `csrf.py` (double-submit cookie), `routes.py` (2 routes, instance `Jinja2Templates` propre à la brique), `traductions/` (mécanisme `t()` isolé de celui de la Brique 7, ADR-001), `templates/fermeture_fragment.html`.
- `migrations/0001_create_audit_log_table.sql` (rôle dédié + table + grants, par tenant déjà enregistré).
- `souverain_app/` — nouveau module racine d'assemblage FastAPI (Brique 7 + Brique 8), point d'entrée `uv run souverain-app`.
- Ajout d'une variable `user_dependency` à `require_role()` (Brique 2).
- Ajout d'une div HTMX dans `alerte_detail.html` (Brique 7) — seule modification de ce fichier.
- 15 tests : `test_csrf.py` (4, sans DB), `test_persistence.py` (5, intégration — dont le test du privilège PostgreSQL réel), `test_routes.py` (6, HTTP de bout en bout via `httpx.AsyncClient` + `ASGITransport`).

Vérifié en environnement de génération (dépôt réel cloné, pas de suppositions sur le code existant) :
- `uv sync --all-packages` — installation réussie, Brique 8 et `souverain_app` ajoutés au workspace.
- Import de tous les modules + assemblage complet de l'application (`souverain_app.main.creer_application_complete()`) — sans erreur, 7 routes confirmées dans le schéma OpenAPI dont `GET`/`POST /alertes/{id}/fermeture`.
- `uv run ruff check briques/brique_08_audit_human_loop souverain_app` — All checks passed (après `--fix` sur un `SIM117`, et ajout de `# noqa: B008` sur les paramètres `Form`/`Depends`, motif déjà présent dans la Brique 7).
- `uv run mypy src` (Brique 8, `souverain_app`) — Success, no issues found.
- Non-régression **stricte** de `test_rbac.py` (Brique 2) après la retouche de `require_role()` : **3/3 passés**, fichier de test inchangé.
- Non-régression mypy de la Brique 7 après l'ajout de la div HTMX : Success, no issues found (13 fichiers).
- `uv run pytest tests/test_csrf.py` (Brique 8) — **4/4 passés**.
- `uv run pytest` sur l'ensemble du workspace (Briques 0 à 8) — **81 passed, 9 skipped, 48 errors** ; toutes les erreurs sont des `ConnectionRefusedError` sur `localhost:5432` (pas de conteneur Docker dans cet environnement), même limite déjà documentée pour chaque brique précédente depuis la Brique 1 — rien d'imputable à la Brique 8.

Vérifié sur la machine réelle du fondateur (ThinkPad X1 Carbon Gen 6), contre une vraie instance PostgreSQL/TimescaleDB et Neo4j — trois allers-retours de correction en conditions réelles, chacun documenté ci-dessous car aucun n'était détectable en environnement de génération :

1. **Migration** : le rôle `souverain_brique8_audit` et la table étaient déjà présents (relance idempotente confirmée, `NOTICE: relation already exists, skipping`).
2. **Bug réel #1** (`conftest.py`) : la fixture `tenant_provisionne` tentait `GRANT ... ON alertes` avant que cette table existe (créée paresseusement par `enregistrer_scores()` de la Brique 5, pas par le provisioning) — l'erreur survenait avant le `try/yield/finally` de la fixture, laissant un tenant de test orphelin dans `shared.tenants_registry`. Corrigé : le GRANT déplacé après la création réelle de la table.
2bis. **Bug réel #2** (`persistence.py`) : `fermer_alerte_avec_audit()` traitait toute `UndefinedTableError` comme "audit_log manquante, à réparer" — alors qu'une alerte sur un tenant où `alertes` elle-même n'existe pas (Brique 5 jamais exécutée) est un cas différent (alerte introuvable, rien à réparer). Corrigé via `to_regclass()` pour distinguer les deux causes.
3. **Bug réel #3** (`csrf.py`/`routes.py`) : injecter un `Response` via `Depends` et poser un cookie dessus ne fonctionne pas quand la route retourne un `TemplateResponse` — FastAPI ne fusionne les headers/cookies d'un Response injecté que si la route retourne autre chose qu'un Response. Corrigé en posant le cookie directement sur l'objet réellement retourné.
4. **Bug réel #4** (`connection.py`) : cache de requêtes préparées côté serveur invalidé par le cycle `DROP SCHEMA CASCADE` / recréation des tests d'intégration (nouveaux OID pour des tables de même nom) — `InvalidCachedStatementError` au lieu de `UndefinedTableError`, donc jamais intercepté. Corrigé via `statement_cache_size=0` sur le pool dédié.
5. **Bug réel #5** (`test_routes.py`) : le pool dédié de la Brique 8, singleton créé par la route elle-même, n'était fermé par aucune fixture des tests HTTP — fuite entre tests avec boucles asyncio différentes (`Event loop is closed`), même classe de bug déjà rencontrée et corrigée pour le driver Neo4j en Brique 7. Corrigé par `close_audit_pool()` en teardown de `_client_pour()`.

Après ces cinq corrections :
- `uv run pytest` sur l'ensemble du workspace (Briques 0 à 8), PostgreSQL et Neo4j réels démarrés — **138/138 tests passés, 0 échec**.
- Détail Brique 8 : `test_csrf.py` 4/4, `test_persistence.py` 5/5 (dont `test_role_restreint_ne_peut_pas_modifier_l_audit_log`, confirmant concrètement le privilège PostgreSQL réel), `test_routes.py` 6/6.
- Non-régression confirmée sur les Briques 0 à 7 (aucun test cassé par l'ajout de la Brique 8).

**Vérification manuelle dans un vrai navigateur, effectuée par le fondateur :**
- Fermeture réelle de l'alerte `demo_dashboard_test_01` (motif `faux_positif`, commentaire libre) — historique affiché correctement avec l'email résolu (`azo@gmail.com`, jointure `shared.users`), horodatage et message de confirmation via le mécanisme `t()` propre à la Brique 8.
- Les 3 requêtes Neo4j du fragment graphe (Brique 6) ont correctement retourné "Aucun résultat" pour ce compte de démo, jamais synchronisé dans Neo4j — comportement déjà documenté et attendu depuis la Brique 7, confirmé non cassé par l'ajout de la Brique 8.
- Rôle `auditor` (formulaire masqué, historique seul) : **non vérifié visuellement** dans le navigateur (aucun compte `auditor` créé sur l'environnement de démo du fondateur) — confirmé uniquement par `test_fragment_masque_le_formulaire_pour_un_auditor`, qui crée un vrai utilisateur `auditor` et vérifie l'absence du `<form>` dans une vraie réponse HTTP contre la base réelle. Le fondateur juge cette couverture automatisée suffisante, la vérification visuelle n'étant qu'un bonus de confiance et non une condition de validation.

**Brique 8 (Audit trail + Human-in-the-loop) VALIDÉE le 4 septembre 2026, par le fondateur (Seydou Dangande Abdoul Aziz), sur ThinkPad X1 Carbon Gen 6.**

## Détail — Extensions V2 : Gouvernance des tenants (Brique 1) et des utilisateurs (Brique 2)

**Statut : VALIDÉES le 6 septembre 2026, par le fondateur (Seydou Dangande Abdoul Aziz), sur ThinkPad X1 Carbon Gen 6.**

Précédées d'une étape de conception documentée séparément :
- `docs/MODELISATION_OPERATIONNELLE.md` — modélisation opérationnelle de l'état réel du système (acteurs, permissions, cycle de vie d'une alerte, architecture multi-tenant), rédigée avant toute extension.
- `docs/DIFFERENCIATION_STRATEGIQUE.md` — analyse de différenciation face aux solutions comparables (Quantexa, Tazama, MaiGuard/PayGuard, GIABA/ECOAML), révisée après recherche externe.

Décisions d'architecture actées avant tout code (plusieurs passes d'analyse, cf. conversation de conception) :
- **Aucun rôle "Platform Operator"** : la gouvernance des tenants reste CLI-only — analysé et explicitement différé, pas ajouté par défaut. Un `admin` est structurellement scopé à un seul tenant (`shared.users.tenant_id NOT NULL`) ; créer un tenant est une opération cross-tenant qu'aucun rôle actuel ne peut porter sans introduire un concept nouveau, reporté jusqu'à un besoin réel (Phase 2, premier export UEMOA).
- **Première différenciation fonctionnelle réelle entre `admin` et `analyst`** : `admin` gère les comptes de son tenant (création, changement de rôle, désactivation/réactivation), `analyst` et `auditor` n'ont aucun accès à cette gestion — première fois que les trois rôles se comportent différemment au-delà de la fermeture d'alerte (Brique 8).
- **Auto-protection** : un `admin` ne peut ni se désactiver, ni se rétrograder lui-même, ni désactiver/rétrograder un utilisateur d'un autre tenant — vérifié par tests d'intégration réels (requêtes forgées) et par la revue manuelle.
- **Table d'audit transverse unique** : `shared.gouvernance_audit_log`, distincte de `{tenant}.audit_log` (Brique 8, décisions métier sur les alertes) — couvre à la fois la gouvernance des tenants et celle des utilisateurs, avec un champ `domaine` (`'tenant'`/`'utilisateur'`) plutôt que deux tables séparées, décision justifiée par l'existence simultanée des deux besoins au moment de la conception (pas une généralisation prématurée).
- **Distinction structurelle acteur CLI vs acteur web** : contrainte SQL `acteur_coherent` (pas une simple convention) rendant impossible de confondre une déclaration CLI non authentifiée (`acteur_declare`) avec une identité web authentifiée (`acteur_user_id`, FK réelle vers `shared.users`).
- **Deux rôles PostgreSQL dédiés, privilèges différents par nécessité** : `souverain_gouvernance_cli` (Brique 1, a besoin de `CREATE` sur la base pour le provisioning de schéma) et `souverain_gouvernance_web` (Brique 2, DML seul sur `shared.users`, aucun privilège DDL) — analyse explicite écartant une simple reprise mécanique du modèle de la Brique 8, la valeur de sécurité du rôle CLI étant différente en nature (l'opérateur a de toute façon un accès serveur complet).
- **`create_tenant()` réellement atomique** : vérifié avant d'écrire le code, pas supposé — `provision_tenant_schema()` (Brique 1, déjà validée) accepte déjà une connexion en paramètre et son template SQL ne contient aucun contrôle de transaction interne, donc participe telle quelle à la transaction unique (registre + provisioning + audit), sans aucune adaptation.
- **`reactivate_user()` ne touche jamais `token_version`** : conclusion vérifiée en traçant `get_current_user()` et `login()` (pas supposée) — l'incrémentation irréversible faite par `deactivate_user()` suffit à elle seule à garantir l'invalidation permanente d'un ancien jeton ; testé par la chaîne complète rejouée (création → connexion → JWT v.N → désactivation → révocation → réactivation → ancien JWT toujours invalide → nouvelle connexion → nouveau JWT valide).
- **Duplication volontaire, pas un import** : l'extension de la Brique 2 duplique la résolution de session par cookie (originaire de la Brique 7) et le mécanisme CSRF (originaire de la Brique 8) plutôt que de les importer — la Brique 2 est censée être en amont de ces deux briques dans le graphe de dépendances, les importer l'aurait inversé.

Bug réel trouvé et corrigé pendant l'écriture du template HTML, avant tout run (pas une correction de validation locale) :
- `method="patch"` sur un formulaire HTML n'est pas supporté par les navigateurs (retombe silencieusement en `GET`) — l'extension de la Brique 2 n'utilise pas HTMX (contrairement aux Briques 7/8, qui supportent `hx-patch`). Corrigé en `POST` partout, cohérent avec un formulaire HTML simple.

Livré :
- Brique 1 : `tenant_governance.py` (`create_tenant()`, `activate_tenant()`, `deactivate_tenant()`), `gouvernance_audit.py` (helper d'écriture partagé avec la Brique 2), `gouvernance_cli_config.py`/`gouvernance_cli_connection.py` (pool dédié), `cli.py` (`souverain-tenant-creer`/`-activer`/`-desactiver`), migration `0002_create_gouvernance_audit_log.sql`.
- Brique 2 : `repository.py` étendu (`+update_user_role()`, `+reactivate_user()`), nouveau sous-package `gouvernance/` (session cookie et CSRF dupliqués, `persistence.py`, `lecture.py`, `routes.py`, `traductions/`, `templates/`), migration `0002_gouvernance_web_role.sql`.
- `souverain_app/` étendu pour inclure le nouveau routeur (`include_router()`, aucune modification de fichier existant).

Vérifié en environnement de génération (dépôt réel cloné) :
- `uv sync --all-packages` — résolution propre.
- `ruff check`/`mypy` — propres sur Brique 1, Brique 2, `souverain_app` ; non-régression confirmée sur Brique 7 et Brique 8.
- Assemblage complet de l'application sans erreur, 5 nouvelles routes (`/utilisateurs*`) confirmées dans le schéma OpenAPI.
- 18 nouveaux tests collectés, SKIP proprement (pas d'erreur) sans PostgreSQL disponible.

Un bug réel trouvé et corrigé lors de la validation sur la machine réelle du fondateur (non détectable en environnement de génération sans base réelle) :
- **GRANT manquant** : `souverain_gouvernance_web` n'avait reçu aucun privilège sur `shared.tenants_registry`, alors que `creer_utilisateur()` y lit `tenant_code` pour générer le SOUVERAIN-ID — `InsufficientPrivilegeError` à la création du tout premier utilisateur via l'interface. Corrigé par l'ajout de `GRANT SELECT ON shared.tenants_registry TO souverain_gouvernance_web` dans la migration `0002` de la Brique 2, après vérification qu'aucun autre privilège n'avait été omis ailleurs dans le module `gouvernance/`.

Après cette correction, sur la machine réelle du fondateur (ThinkPad X1 Carbon Gen 6), PostgreSQL et Neo4j réels démarrés, les deux migrations appliquées dans l'ordre (Brique 1 puis Brique 2) :
- `uv run pytest` sur l'ensemble du workspace (Briques 0 à 8 + extensions V2) — **156/156 tests passés, 0 échec**.
- Détail : `test_tenant_governance.py` 6/6 (Brique 1, dont le test de privilège PostgreSQL réel sur `gouvernance_audit_log` et le test de non-suppression du schéma à la désactivation), `test_gouvernance_persistence.py` 6/6 et `test_gouvernance_routes.py` 6/6 (Brique 2, dont la chaîne complète désactivation/réactivation/JWT et le test de privilège réel).
- Non-régression confirmée sur l'ensemble des Briques 0 à 8.

**Vérification manuelle effectuée par le fondateur, en conditions réelles :**
- CLI Brique 1 : création d'un tenant de test (`tenant_sn_test`), désactivation, réactivation — chaque opération confirmée tracée dans `shared.gouvernance_audit_log` avec l'`acteur_declare` exact saisi en paramètre, horodatage précis.
- Interface web Brique 2 : bootstrap du tout premier compte `admin` (remontée manuelle en base du seul compte existant, `azo@gmail.com`, `analyst` → `admin` — cas de démarrage inévitable, aucun compte admin ne préexistait), puis entièrement via l'interface : création de deux comptes supplémentaires (`abdoul@gmail.com` en admin, `aziz@gmail.com` en auditor), désactivation/réactivation d'un compte, historique de gouvernance affiché correctement avec `acteur_user_id` réel (authentifié) — distinct du `acteur_declare` du CLI, confirmant visuellement la séparation structurelle actée à la conception.
- **RBAC confirmé en conditions réelles, pas seulement par test automatisé** : connexion successive avec un compte `auditor` puis un compte `analyst`, tentative d'accès à `/utilisateurs` dans les deux cas — refus `403` (`"Vous n'avez pas les droits nécessaires pour cette action."`) confirmé pour les deux rôles, seul `admin` passe.

**Extensions V2 (Gouvernance des tenants — Brique 1, Gouvernance des utilisateurs — Brique 2) VALIDÉES le 6 septembre 2026, par le fondateur (Seydou Dangande Abdoul Aziz), sur ThinkPad X1 Carbon Gen 6.**

## Phase transverse — Revue d'architecture préalable

**Date : 6-7 septembre 2026.** Avant tout code de la phase transverse,
une revue d'architecture complète a été menée (fondations B0-8+V2,
chaque capacité transverse envisagée, critères de production, threat
model) — non résumée ici en détail, voir la conversation de conception
correspondante. Conclusion : aucun bloqueur absolu, mais l'absence de
sauvegarde/restauration a été identifiée comme le point le plus
sérieux. Roadmap consolidée actée, incluant l'ajout d'UX/UI et la
correction terminologique PQC (ML-KEM/ML-DSA, successeurs
Kyber/Dilithium renommés par le NIST — FIPS 203/204).

**Ordre validé** : (1) Hygiène de socle, (2) Intégrité des données
métier, (3) UX/UI, (4) Prometheus/Grafana, (5) Test de charge, (6)
Ollama/Mistral, (7) Sécurité IA/RAG (conception), (8) RAG, (9)
Redis/Celery (conditionnel), (10) SOUVERAIN-ID complet, (11) PQC, (12)
Résilience inter-États.

## Détail — Étape 1 : Hygiène de socle

**Statut : VALIDÉE le 7 septembre 2026, par le fondateur (Seydou Dangande Abdoul Aziz), sur ThinkPad X1 Carbon Gen 6.**

Périmètre volontairement minimal, acté à l'analyse avant tout code :
- `/health` (PostgreSQL uniquement — Neo4j explicitement hors périmètre, décision actée pas un oubli), détail minimal exposé publiquement (jamais host/port/db ni message d'erreur brut).
- Logs structurés JSON sur un seul point d'entrée (`souverain_app`, middleware HTTP) — aucune nouvelle dépendance, aucune modification de brique existante.
- Backup/restore : un test unique prouvant que la mécanique fonctionne, explicitement PAS une stratégie de production (pas d'automatisation, pas de rétention, pas de stockage distant, pas de chiffrement — tout FUTUR).

Livré :
- `souverain_app/src/souverain_app/main.py` étendu (endpoint `/health` réutilisant `run_db_healthcheck()` de la Brique 1 inchangée, middleware de logs JSON avec `X-Request-ID`).
- `scripts/backup_postgres.sh` / `scripts/restore_postgres.sh` (nouveaux, `pg_dump --format=plain`).
- `tests/integration/test_health_endpoint.py` (3 tests, dans `tests/integration/` — préexistant, prévu pour ce type de test transverse).

Bug réel trouvé et corrigé **en conditions réelles sur la machine du fondateur** (non détectable en environnement de génération, nécessite un vrai `.env` + une vraie tentative de restauration ciblée) :
- **Priorité des variables d'environnement inversée** : `source .env` à l'intérieur des deux scripts écrasait silencieusement toute variable déjà positionnée par l'appelant (ex. `POSTGRES_DB=autre_base ./restore_postgres.sh ...`). Conséquence réelle : une première tentative de restauration vers une base de test (`souverain_os_test_restore`) s'est exécutée contre `souverain_os` (la vraie base) à la place — confirmation affichée déjà erronée, donc rien ne permettait de le détecter avant coup. Analysé précisément : aucune commande destructrice dans le dump (`DROP`/`DELETE`/`TRUNCATE` absents), tout ce qui a réussi silencieusement était idempotent (restauration d'une base contre elle-même, même instant) — vérifié sans dommage après coup (`SELECT count(*)` sur `tenants_registry`, `transactions`, `alertes`, résultats cohérents : 2/5000/1).
- Corrigé : les deux scripts préservent maintenant explicitement toute variable déjà définie par l'appelant avant de charger `.env`. `restore_postgres.sh` renforcé en plus : confirmation par re-saisie exacte du nom de la base cible (plus seulement "oui"), rendant ce bug précis structurellement impossible à reproduire silencieusement. Logique de priorité testée isolément avant livraison du correctif.

Vérifié sur la machine réelle du fondateur, contre une vraie instance PostgreSQL :
- `/health` : `200` PostgreSQL up, testé également en conditions dégradées côté génération (sans PostgreSQL, `503`, détail minimal confirmé, aucune fuite de host/port/db).
- Cycle complet backup → restauration sur une base réellement vide (`souverain_os_test_restore`) → **zéro erreur** (`CREATE SCHEMA`/`CREATE TABLE`/`COPY 5000` pour les transactions, `COPY 2` pour les tenants, etc.) — contrairement à la première tentative (contre la mauvaise base, déjà peuplée, donc uniquement des `ERROR: already exists`).
- `SELECT count(*) FROM shared.tenants_registry` sur la base restaurée : `2`, cohérent.
- Base de test nettoyée après vérification (`DROP DATABASE souverain_os_test_restore`), confirmé par `\l` que `souverain_os` (la vraie base) reste intacte et présente.
- `uv run pytest` — 84 passed (+3 vs. avant cette étape), même nombre de skip/erreurs qu'avant (limite déjà documentée, absence de PostgreSQL/Neo4j en environnement de génération) — zéro régression.

**Étape 1 (Hygiène de socle) VALIDÉE le 7 septembre 2026, par le fondateur (Seydou Dangande Abdoul Aziz), sur ThinkPad X1 Carbon Gen 6.**

## Détail — Étape 2 : Intégrité des données métier

**Statut : VALIDÉE le 8 septembre 2026, par le fondateur (Seydou Dangande Abdoul Aziz), sur ThinkPad X1 Carbon Gen 6.**

Mécanisme : Event Trigger PostgreSQL (`ddl_command_end`, filtré sur `CREATE TABLE`) — décision actée après analyse détaillée de 3 options, avec revirement du fondateur en cours de conception (Option C d'abord choisie provisoirement, puis Option A retenue après que l'analyse a montré que C créait une dépendance architecturale de la Brique 1 vers les structures internes de Briques 4/5, rompant la séparation des responsabilités). Détail complet dans `docs/adr/ADR-003-event-trigger-integrite-donnees.md`.

Décisions clés :
- **Détection, jamais blocage** : `AFTER UPDATE OR DELETE` sur `{tenant}.alertes`/`{tenant}.detections` uniquement — `INSERT` (fonctionnement normal) jamais journalisé.
- **`transactions` explicitement exclue** de cette étape (hypertable TimescaleDB, volume et complexité — reporté en FUTUR).
- **Journalisation sans distinction** légitime/suspecte — une fermeture normale (Brique 8) produit à la fois une entrée `{tenant}.audit_log` (qui a décidé) et `{tenant}.integrite_donnees_log` (que la ligne a changé), redondance assumée.
- **`SECURITY DEFINER` + `session_user`** (pas `current_user`, qui refléterait le propriétaire de la fonction sous `SECURITY DEFINER`) pour capturer le rôle réel à l'origine de la modification — vérifié concrètement avant implémentation que Brique 8 utilise bien `souverain_brique8_audit` (pas `souverain_admin`) pour ses fermetures.
- **Limite reconnue, non résolue** : `souverain_admin` (superutilisateur, propriétaire de toutes les tables) pourrait désactiver ou supprimer ce mécanisme — protection contre une modification directe non accompagnée d'une désactivation délibérée, pas contre un compte admin compromis.
- **Zéro modification de Brique 4/5/7/8** — Brique 1 ne connaît que deux noms de table et un nom de colonne de clé primaire chacune, jamais leur structure complète.

Bugs réels trouvés et corrigés, tous avant validation finale :
- **En écrivant les tests** (pas en validation locale) : `assurer_protection_integrite()` n'est pas protégée contre une table cible absente (`CREATE TRIGGER ... ON` une table inexistante lève une vraie erreur) — comportement voulu et désormais testé explicitement (la garantie vient de l'appelant, qui vérifie l'existence au préalable, pas d'une protection interne silencieuse).
- **En test sur machine réelle** : un test (`donnees_avant`/`donnees_apres`) tentait d'indexer directement une colonne `JSONB` comme un dict Python — même piège déjà rencontré et documenté en Brique 7 (asyncpg ne décode pas `JSONB` automatiquement sans codec enregistré), corrigé par `json.loads()` explicite dans le test. Le mécanisme SQL lui-même n'était pas en cause — confirmé par les assertions précédentes du même test, qui passaient déjà.
- **En test sur machine réelle** : le pool admin (singleton) fuyait entre les tests de `tests/integration/test_health_endpoint.py` (Étape 1, révélé seulement maintenant que PostgreSQL tournait réellement pendant ces tests) — même classe de bug déjà rencontrée pour le driver Neo4j (Brique 7) et les pools dédiés (Brique 8, gouvernance V2). Corrigé par une fixture `autouse` fermant le pool après chaque test.

Vérifié sur la machine réelle du fondateur, PostgreSQL et Neo4j réels démarrés, les deux migrations (`0003`, `0004`) appliquées dans l'ordre :
- `uv run pytest briques/brique_01_postgresql/tests/test_integrite_donnees.py` — **6/6 passés**, y compris le test de privilège réel (rôle non-superutilisateur ne peut pas toucher l'event trigger) et le test central (création de `alertes` par du SQL brut simulant Brique 5 → trigger attaché automatiquement, sans aucun code applicatif impliqué).
- `uv run pytest` sur l'ensemble du workspace — **165/165 tests passés, 0 échec**, zéro régression sur les Briques 0 à 8, extensions V2, et Étape 1.
- Vérification manuelle : `UPDATE` direct sur une alerte réelle de `tenant_ne` → entrée confirmée dans `tenant_ne.integrite_donnees_log`, `role_postgresql = souverain_admin`, horodatée correctement.

**Étape 2 (Intégrité des données métier) VALIDÉE le 8 septembre 2026, par le fondateur (Seydou Dangande Abdoul Aziz), sur ThinkPad X1 Carbon Gen 6.**

## Détail — Étape 3 : UX/UI (fondations)

**Statut : VALIDÉE le 14 septembre 2026, par le fondateur (Seydou Dangande Abdoul Aziz).**

Précédée d'un audit UX/UI explicite (pas seulement une passe de style),
menée sous trois angles persona (admin, analyste, auditeur) contre les
écrans réels (captures d'écran fournies par le fondateur). Verdict de
l'audit : socle CSS fonctionnel mais interface encore "back-office
technique", pas institutionnelle — classé en CRITIQUE / IMPORTANT /
AMÉLIORATION / FUTUR, périmètre validé explicitement avant tout code :
#1, #2, #4 à #13 pour ce cycle ; #1b et #3 (résolution email dans
l'historique de gouvernance — nécessite une nouvelle requête SQL) et
#14 à #17 (vraie visualisation de graphe, page d'audit transverse,
responsive, design system Jinja) explicitement reportés.

Contraintes strictes actées avant implémentation : aucune nouvelle
route, aucune nouvelle requête SQL, aucune modification du modèle de
données ni du RBAC, aucune nouvelle dépendance JS, `confirm()` natif
uniquement.

Deux vérifications empiriques faites avant tout code (pas supposées) :
- **Changement de rôle** (Brique 2 V2) : confirmé par lecture du code
  que le `<select>` de rôle faisait un `onchange="this.form.requestSubmit()"`
  — auto-soumission instantanée, zéro confirmation. Une modification
  CSS seule ne pouvait pas corriger ce point.
- **Contexte utilisateur déjà disponible** : `AuthenticatedUser`
  (Brique 2, session déjà résolue à chaque requête) porte `role` et
  `tenant_id` gratuitement. `tenant_id` est un UUID, pas un code
  lisible — afficher un tenant lisible (#1b) nécessiterait une
  requête de plus, donc explicitement exclu de ce cycle.
- **Historique de gouvernance** (Brique 2 V2) : confirmé par lecture
  de `lire_historique_gouvernance()` que `acteur_user_id`/`cible_id`
  sont retournés en UUID bruts, jamais résolus en email — contrairement
  à `EntreeAudit` (Brique 8) qui résout déjà l'email. Écart de données
  réel, pas un oubli de template — traité comme #3, hors périmètre.

Décision d'architecture actée pour exposer le rôle sans nouvelle
requête (#1) : `routes/alertes.py` (Brique 7) ne recevait que
`MetadonneesTenant` (via `tenant_valide()`), pas `AuthenticatedUser`
directement, alors que `tenant_valide()` le résout déjà en interne.
Ajout d'un second `Depends(get_current_user_from_cookie)` sur les 2
routes qui rendent `base.html` — vérifié que FastAPI met en cache la
résolution d'une dépendance par requête (`use_cache=True` par défaut),
donc **zéro requête SQL supplémentaire**, seul le résultat déjà
calculé devient accessible au handler. Même principe côté Brique 2 V2
(`gouvernance/routes.py`) : `utilisateur` était déjà résolu et présent
dans `_rendre_page()`, une seule ligne ajoutée au contexte.

Livré (12 fichiers, zéro nouveau fichier `.py`, une seule nouvelle
Python logique additive — l'ajout de `Depends` ci-dessus) :
- `briques/brique_07_dashboard/.../static/souverain.css` : système de
  badges (rôle, statut, score), tags de patterns, hiérarchie de
  boutons (primaire/secondaire/danger), échelle typographique h1-h3,
  icônes CSS sur `.erreur`/`.succes`, classe `.avertissement` distincte
  de `.vide`.
- `base.html`, `alertes_liste.html`, `alerte_detail.html`,
  `tenant_sans_donnees.html`, `traductions/fr.py` (Brique 7) : bandeau
  rôle + état actif nav, bandeau "indice d'investigation, pas une
  preuve de culpabilité" sur le détail d'alerte, badges/tags appliqués,
  message de contexte réel distinct de l'état vide simple.
- `routes/alertes.py` (Brique 7) : exposition du rôle (voir ci-dessus).
- `gouvernance/routes.py`, `liste_utilisateurs.html`,
  `gouvernance/traductions/fr.py` (Brique 2 V2) : badge rôle + état
  actif nav, **confirmation native avant tout changement de rôle**
  (`confirm()` + restauration de la valeur précédente si annulé),
  boutons hiérarchisés, badges statut/rôle, historique restylé avec
  les mêmes classes que la Brique 8 (`.audit-historique`) pour un
  langage visuel unifié — contenu (UUID bruts) inchangé, hors périmètre.
- `fermeture_fragment.html` (Brique 8) : un seul attribut `class`
  ajouté sur le bouton de fermeture existant — aucune autre ligne
  touchée.
- `tests/integration/test_socle_ux_ui.py` : étendu (7 assertions au
  total) — vérifie que `/static/souverain.css` est servi et contient
  les classes attendues, et que `/login` ne contient plus de `<style>`
  inline. Fonctionne sans PostgreSQL/Neo4j par construction (aucune
  des deux pages testées n'en dépend).

Vérifié en environnement de génération (sans PostgreSQL/Neo4j
disponibles) :
- `uv run pytest tests/integration/test_socle_ux_ui.py` — **2/2 passés**.
- `uv run pytest` sur l'ensemble du workspace — **86 passed**, 48
  erreurs — **toutes confirmées `ConnectionRefusedError`** (classification
  explicite du type d'exception, pas une supposition), aucune nouvelle
  erreur, aucune régression de collecte introduite par le changement de
  signature des routes `/alertes` et `/alertes/{id}`.
- `uv run ruff check` / `uv run mypy src` — propres sur les Briques 7,
  2 et 8.

Vérifié manuellement par le fondateur dans un vrai navigateur, contre
une checklist dédiée (bandeau rôle, état actif de la nav, badges,
tags, confirmation de changement de rôle dans ses deux issues —
annuler et confirmer —, boutons hiérarchisés, historique restylé) :
**conforme, aucune anomalie remontée.** Un point d'incertitude soulevé
sur l'affichage du graphe d'investigation a été vérifié comme non lié
à cette étape (`git diff` confirme que `routes/alertes.py` (partie
`/graphe`) et `graphe_fragment.html` n'ont reçu aucune modification
dans ce cycle) — écarté de la validation, à traiter séparément si
besoin (dépend de la synchronisation Neo4j, Brique 6, hors périmètre
UX/UI).

Explicitement non traité dans ce cycle, le fondateur ayant exprimé le
souhait d'une amélioration visuelle plus poussée au-delà du socle :
reporté à un futur cycle de conception dédié (COMPRENDRE → ARCHITECTURER
séparé), pas ajouté silencieusement ici. Recoupe les points #14 à #17
déjà identifiés par l'audit (design system réutilisable, vraie
identité visuelle, densité d'information retravaillée, visualisation
de graphe interactive).

**Étape 3 (UX/UI — fondations) VALIDÉE le 14 septembre 2026, par le fondateur (Seydou Dangande Abdoul Aziz).**

## Détail — Étape 4a : Observabilité (Prometheus + Grafana)

**Statut : VALIDÉE ET GELÉE le 19 septembre 2026, par le fondateur (Seydou Dangande Abdoul Aziz), sur ThinkPad X1 Carbon Gen 6.**

Précédée d'un cycle de conception en trois passes : COMPRENDRE (inspection
exhaustive de `docker-compose.yml` — services, profiles, ports, healthchecks,
absence de toute limite `resources:`), une proposition initiale du fondateur,
puis une contre-proposition motivée du modèle (découpage 4a/4b pour isoler
le seul risque touchant une brique verrouillée), les deux comparées
point par point avant décision. Périmètre 4a validé : Prometheus,
Grafana, `/metrics` FastAPI (instrumentation manuelle), provisioning
Grafana minimal, profile `monitoring` réutilisé. **postgres-exporter et
la migration Brique 1 explicitement exclus**, réservés à l'Étape 4b.

Décisions actées avant tout code :
- Budget RAM de travail : 13 Go (chiffre du fondateur, distinct des
  14,87 Go documentés en Brique 6 — écart signalé, non tranché en
  silence).
- `prometheus-client` seul, instrumentation manuelle (pas d'auto-
  instrumentator) — le label `chemin` utilise le patron de route
  matché (`request.scope["route"].path`), jamais `request.url.path`
  brut, pour éviter toute fuite d'UUID de compte/tenant en label
  Prometheus et tout risque de cardinalité non bornée.
- Aucun port hôte par défaut pour Prometheus/Grafana — accès local
  ponctuel documenté dans `docker-compose.override.yml.example`
  (mécanisme déjà existant depuis la Brique 0, jamais mobilisé avant
  cette étape).
- Aucune limite `resources:` ajoutée (cohérent avec leur absence sur
  tout le fichier).
- Pas de `pg_stat_statements`, pas de métriques métier du pipeline
  batch (B3-B6) en MVP.

Deux erreurs réelles commises et corrigées **avant** la machine réelle
du fondateur, trouvées par vérification systématique plutôt que
suppositions :
- Versions d'images figées à l'analyse (`prom/prometheus:v3.0.1`,
  `grafana/grafana-oss:11.4.0`) vérifiées obsolètes par recherche web
  avant tout code — corrigées en `prom/prometheus:v3.14.0` et
  `grafana/grafana:13.2.1` (le dépôt `grafana-oss` n'est plus mis à
  jour depuis Grafana 12.4.0 selon Grafana Labs).
- `souverain_app` tourne en natif sur l'hôte (`uv run souverain-app`),
  jamais en conteneur — vérifié avant d'écrire la config de scrape.
  `host.docker.internal` ne résout pas nativement sous Linux
  (contrairement à Docker Desktop) : `extra_hosts:
  ["host.docker.internal:host-gateway"]` ajouté au service
  `prometheus`.

**Incident réel en conditions réelles — métriques Neo4j natives,
retirées du périmètre après investigation empirique complète :**
trois tentatives de nom de réglage (`metrics.prometheus.endpoint`,
`server.metrics.prometheus.endpoint`, `server.metrics.prometheus.enabled`
seul) toutes rejetées par `strict_validation` sur la machine réelle du
fondateur (Neo4j 5.26.30 Community), malgré une documentation Neo4j
générale qui les présente comme valides sans distinguer clairement
Community/Enterprise. Le premier échec a fait crasher le conteneur
Neo4j (aucun `restart:` défini) — restauré dans son état connu-
fonctionnel (Brique 6) à chaque itération, jamais laissé cassé entre
deux tentatives. Preuve définitive obtenue directement depuis le
Neo4j du fondateur, pas depuis une doc externe :
`CALL dbms.listConfig() YIELD name WHERE name CONTAINS 'prometheus'`
retourne une liste vide, alors que la même requête sur `'heap'`
retourne bien des résultats — confirmant que la requête fonctionne et
que c'est le réglage lui-même qui n'est pas déclaré dans cette
édition. **Conclusion : métriques Prometheus natives non disponibles
sur Neo4j Community 5.26.30, retirées définitivement du périmètre
4a** (pas reportées à 4b — un besoin réel non satisfait, CSV/JMX
restant une alternative possible en FUTUR si nécessaire un jour).

Second incident, réseau, sans lien avec la configuration du dépôt :
la cible Prometheus `souverain_app` restait `DOWN` (timeout) malgré
`/health` répondant en local et `host.docker.internal` résolvant
correctement (`172.17.0.1`, vérifié depuis le conteneur Prometheus) —
cause trouvée par élimination méthodique : `ufw` actif sur la machine
du fondateur bloquait le trafic entrant depuis le réseau Docker
`souverain-net` (sous-réseau réel `172.18.0.0/16`, vérifié via
`docker network inspect` — une première règle sur `172.17.0.0/16`,
le sous-réseau du bridge Docker par défaut, était insuffisante).
Réglage machine locale, hors du dépôt versionné — non documenté dans
un fichier projet, mais tracé ici pour toute réinstallation future.

Livré :
- `briques/brique_07_dashboard/.../static/` : aucun changement (rappel
  — 4a ne touche aucun fichier de Brique 7, contrairement à l'Étape 3).
- `docker-compose.yml` : services `prometheus`/`grafana` sous
  `profiles: ["monitoring"]`, réseau `souverain-net`, aucun port hôte,
  2 volumes nommés (`prometheus_data`, `grafana_data`), `extra_hosts`
  sur `prometheus`. Aucune métrique Neo4j (retirée, voir ci-dessus).
- `observabilite/prometheus/prometheus.yml` : scrute uniquement
  `souverain_app` (`host.docker.internal:8080`).
- `observabilite/grafana/provisioning/datasources/prometheus.yml` :
  source de données provisionnée automatiquement, aucun dashboard
  pré-construit.
- `.env.example` : `GRAFANA_ADMIN_USER`/`GRAFANA_ADMIN_PASSWORD`.
- `docker-compose.override.yml.example` : exemple commenté pour
  ouvrir ponctuellement les ports Grafana/Prometheus en local.
- `souverain_app/src/souverain_app/main.py` : `/metrics`
  (2 métriques — compteur de requêtes, histogramme de durée — label
  `chemin` = patron de route, jamais brut).
- `souverain_app/pyproject.toml` : dépendance `prometheus-client`
  (première dépendance tierce de ce module) ; contournement mypy pour
  un manque préexistant découvert en vérifiant (Brique 2 sans
  `py.typed`, même contournement déjà en place en Brique 7 — pas une
  régression de cette étape).
- `tests/integration/test_observabilite.py` : 3 tests (format
  d'exposition valide, label = patron de route, absence d'UUID),
  aucun ne dépend de PostgreSQL/Neo4j.

Vérifié en environnement de génération (sans Docker, comme pour
chaque étape précédente) :
- `uv run pytest tests/integration/test_observabilite.py` — 3/3.
- `uv run pytest` — 89 passed, zéro régression introduite.
- `ruff check` / `mypy src` — propres sur `souverain_app` et les 4
  briques adjacentes (B1, B2, B7, B8).
- Validation YAML de `docker-compose.yml` et des 2 fichiers
  `observabilite/` — structure conforme.

Vérifié sur la machine réelle du fondateur, après résolution des deux
incidents ci-dessus :
- `uv run pytest` — **170/170 tests passés**, PostgreSQL et Neo4j
  réels démarrés.
- `docker compose ps` — 4 conteneurs (`postgres`, `neo4j`,
  `prometheus`, `grafana`) sains, sans port hôte sur les deux
  derniers par défaut.
- Cible Prometheus `souverain_app` : **UP**, 159 ms de latence.
- Grafana : source de données Prometheus provisionnée automatiquement
  et marquée par défaut, sans action manuelle — confirmé visuellement.
- `docker stats --no-stream`, les 4 conteneurs ensemble — **première
  mesure réelle de PostgreSQL de tout ce projet** (jamais mesuré
  avant, y compris aux Briques 1 et 5) :

| Conteneur | RAM mesurée |
|---|---|
| Prometheus | 88.6 MiB |
| Grafana | 425.3 MiB (au-dessus de l'estimation initiale 150-250 Mo) |
| Neo4j | 136.5 MiB au repos |
| PostgreSQL | 141 MiB |
| **Total** | **~791 MiB** |

Sur le budget de travail de 13 Go : **~12,2 Go de marge restante** —
écart Grafana sans aucune conséquence sur la faisabilité mémoire.

**Étape 4a (Observabilité — Prometheus/Grafana) VALIDÉE ET GELÉE le 19 septembre 2026, par le fondateur (Seydou Dangande Abdoul Aziz), sur ThinkPad X1 Carbon Gen 6.**

## Détail — Étape 4b : Observabilité PostgreSQL (postgres-exporter + rôle monitoring)

**Statut : VALIDÉE le 19 septembre 2026, par le fondateur (Seydou Dangande Abdoul Aziz), sur ThinkPad X1 Carbon Gen 6.**

Précédée d'un cycle de conception détaillé (versions vérifiées par
recherche web : `postgres_exporter` v0.20.1, image
`quay.io/prometheuscommunity/postgres-exporter`, port 9187,
mécanisme `DATA_SOURCE_URI`/`DATA_SOURCE_USER`/`DATA_SOURCE_PASS`
confirmé comme la convention actuelle, pas l'ancien
`DATA_SOURCE_NAME`). Relecture du fondateur avant implémentation :
architecture validée, ajout de 2 tests supplémentaires
(`test_role_n_est_pas_superuser`, `test_role_peut_se_connecter_a_la_base`),
et un point de vigilance sur le mot de passe de la migration —
vérifié par grep direct que c'est exactement le mécanisme déjà
utilisé 3 fois dans ce projet (audit B8, gouvernance_cli B1,
gouvernance_web B2) : placeholder SQL en dur, changé via `ALTER ROLE`
avant tout déploiement réel, pas une lacune propre à cette migration.

Migration `0005_create_monitoring_role.sql` (Brique 1, verrouillée) :
rôle `souverain_monitoring`, membre de `pg_monitor` uniquement —
**aucune boucle par tenant nécessaire**, contrairement au rôle
d'audit de la Brique 8 : `pg_monitor` est un privilège cluster-level
(`pg_stat_activity`, `pg_stat_database`), pas accordé schéma par
schéma. Aucun module de connexion Python de production créé pour ce
rôle (contrairement aux 3 précédents) : aucun code applicatif ne se
connecte jamais sous `souverain_monitoring`, seul l'exportateur
(binaire Go, hors Python) le fait — un module dédié aurait été du
code mort, le pool de test est construit directement dans
`test_monitoring_role.py`.

Service `postgres-exporter` (`docker-compose.yml`, profile
`monitoring`) : premier `depends_on` de tout ce fichier
(`postgres: condition: service_healthy`), validé explicitement par
le fondateur comme sans risque (n'affecte que l'ordre de démarrage
sous ce profile). Aucun port hôte par défaut, même politique qu'en
4a. Aucun collector explicite ajouté (métriques par défaut v0.20.1
uniquement), pas de `pg_stat_statements` (décision actée en 4a,
reconfirmée).

**Contrainte d'usage découverte en conditions réelles, à retenir** :
à cause du `depends_on`, **toute commande touchant `postgres-exporter`
(`up`, `logs`, `restart`) exige `--profile postgres` en plus de
`--profile monitoring`** — `--profile monitoring` seul fait échouer
Compose (`service "postgres-exporter" depends on undefined service
"postgres"`). Pas un bug, une conséquence directe et attendue du
`depends_on`, mais suffisamment non intuitive pour être documentée
ici plutôt que redécouverte plus tard :
```
docker compose --profile postgres --profile neo4j --profile monitoring up -d
docker compose --profile postgres --profile neo4j --profile monitoring logs postgres-exporter --tail 30
```

Livré :
- `briques/brique_01_postgresql/migrations/0005_create_monitoring_role.sql`.
- `briques/brique_01_postgresql/tests/test_monitoring_role.py` — 6
  tests (existence, appartenance `pg_monitor`, non-superuser,
  `CONNECT` réel, refus d'écriture, refus de lecture des données
  tenant).
- `docker-compose.yml` — service `postgres-exporter`.
- `.env.example` — `MONITORING_DB_USER`/`MONITORING_DB_PASSWORD`.
- `observabilite/prometheus/prometheus.yml` — cible `postgres`
  (`postgres-exporter:9187`).

Manque préexistant découvert en vérifiant, non lié à cette étape,
signalé et non corrigé (hors périmètre) : `mypy tests/` sur
l'ensemble du dossier de tests de la Brique 1 révèle 3 erreurs dans
`test_connection.py` (jamais vérifié ainsi avant — seul `mypy src/`
et des fichiers de test isolés l'avaient été jusqu'ici). Même nature
que le manque `py.typed` découvert sur `souverain_app` en 4a.

Vérifié en environnement de génération (sans Docker) : `ruff`/`mypy`
propres, 6 tests collectés, suite complète 89 passed/39 skipped
(+6 propres)/48 erreurs (toutes `ConnectionRefusedError`, rien de
nouveau), YAML valide.

Vérifié sur la machine réelle du fondateur, cycle complet incluant un
incident réel et sa résolution :
- Migration appliquée avec succès (`docker exec ... psql ... < 0005...sql`).
- `uv run pytest briques/brique_01_postgresql/tests/test_monitoring_role.py` — **6/6 passés**.
- `uv run pytest` (suite complète, PostgreSQL + Neo4j réels) — **176/176 passés**.
- Logs `postgres-exporter` : `Established new database connection` +
  détection de version PostgreSQL 16.6 — authentification confirmée.
- `docker exec ... wget -qO- http://localhost:9187/metrics` —
  métriques PostgreSQL réelles confirmées (`pg_database_size_bytes`,
  `pg_locks_count`, `pg_exporter_last_scrape_error 0`), pas seulement
  les métriques internes du processus Go de l'exportateur.
- Cible Prometheus `postgres` (`/targets`) — **UP**, 170 ms.
- **Rollback réel testé** : `REVOKE pg_monitor FROM
  souverain_monitoring; DROP ROLE IF EXISTS souverain_monitoring;`
  exécuté sans erreur → rôle confirmé absent (`SELECT ... pg_roles`,
  0 ligne) → redémarrage de l'exportateur → **échec d'authentification
  réel capturé dans les logs** (`password authentication failed for
  user "souverain_monitoring"`), preuve directe que le rôle contrôle
  effectivement l'accès, pas seulement en théorie → migration
  réappliquée → exportateur redémarré → 6/6 tests de nouveau au vert.

**Étape 4b (Observabilité PostgreSQL) VALIDÉE le 19 septembre 2026, par le fondateur (Seydou Dangande Abdoul Aziz), sur ThinkPad X1 Carbon Gen 6.**

**Étape 4 (Observabilité — Prometheus/Grafana) entièrement close, 4a et 4b comprises.**

**Prête pour l'analyse de l'Étape 5 (Test de charge du pipeline actuel) dès demande explicite du fondateur**, conformément à l'ordre validé — sauf si le fondateur préfère d'abord ouvrir le cycle de conception UX/UI approfondi resté en attente depuis l'Étape 3.

## Détail — Étape 5 : Test de charge du pipeline B3→B4→B5→B6→B7/B8

**Statut : VALIDÉE le 19 septembre 2026, par le fondateur (Seydou Dangande Abdoul Aziz), sur ThinkPad X1 Carbon Gen 6.**

Précédée d'une analyse complète (COMPRENDRE) avant tout code : le
pipeline n'est pas homogène — B3 à B6 sont des jobs batch CLI
(déclenchement manuel), seul B7/B8 est un service HTTP continu.
Constat structurant : seul B3 a un volume configurable
(`--nb-transactions`), B4/B5/B6 traitent tout ce qui existe pour le
tenant donné. Limite déjà documentée (validation Brique 5)
confirmée applicable ici : le générateur B3 ne peut jamais produire
de compte cumulant deux patterns différents (préfixes de compte
fixes par pattern) — donc **aucun volume ne fera apparaître
d'alerte réelle** avec le générateur actuel.

Décisions actées avant exécution :
- **Scénario B (scoring/alertes réel) : option (a) retenue** — limite
  du générateur acceptée provisoirement, aucun développement de
  générateur composite avant ce test. Réévaluation de la qualité de
  détection reportée à une campagne dédiée, distincte de l'Étape 5.
- **Scénario C (charge HTTP B7/B8) : `asyncio`+`httpx`**, pas
  `locust` — zéro nouvelle dépendance (choix explicite pour cette
  étape, cohérent avec la discipline déjà appliquée en 4a/4b).
- **Paliers retenus : 5 000 → 20 000 → 50 000** (la borne
  "recommandée" du générateur B3, correspondant à l'ordre de
  grandeur de la cible de débit du document fondateur). Pas de test
  au-delà de 50 000 pour cette première campagne.
- **13 Go = seuil d'alerte, pas arrêt automatique** — arrêt
  seulement en cas de pression mémoire critique, OOM, instabilité ou
  dégradation dangereuse (ajustement du fondateur au protocole
  initialement proposé).
- **Vérification explicite post-nettoyage entre paliers** (PostgreSQL
  ET Neo4j confirmés vides avant de poursuivre) — ajout du fondateur
  au protocole, appliqué aux deux transitions de palier.
- Débit B3 et débit global B3→B6 **calculés séparément** (ajustement
  du fondateur) — le débit global était dominé par B6, un débit B3
  seul isolé était nécessaire pour ne pas le masquer.
- La mesure <500 ms Neo4j est **conservée mais jamais présentée comme
  une validation de la cible officielle 1M nœuds** (ajustement du
  fondateur) — les volumes testés ici restent trois ordres de
  grandeur en dessous de ce scénario.

Isolation : tenant dédié `tenant_test_charge` (jamais mélangé à
`tenant_ne`), créé via `souverain-tenant-creer`, avec un compte admin
de test bootstrapé par script ponctuel (même geste que le tout
premier bootstrap de `tenant_ne`, réutilisant les fonctions réelles
de la Brique 2 — `hash_password`, `generate_souverain_id`,
`create_user` — jamais de SQL brut inventé).

Livré : `charge/scenario_c_http.py` — nouveau répertoire transverse
(même principe que `observabilite/` en Étape 4), script autonome hors
suite pytest. Se connecte une fois, extrait les IDs d'alertes et les
URLs de fragment graphe réelles depuis le HTML retourné (même
attribut `hx-get` que le navigateur réel), lance N coroutines
concurrentes sur un cycle pondéré (`/alertes` 40%, détail 35%, graphe
25%). Aucune métrique dupliquée côté client au-delà d'un résumé
immédiat — la latence de référence reste
`souverain_http_request_duration_seconds` (Prometheus, Étape 4a).
Vérifié statiquement avant livraison (`ruff`, `mypy` propres) — jamais
exécuté avant validation explicite du fondateur, conformément à la
méthode.

**Résultats — campagne complète (5 000 / 20 000 / 50 000) :**

| Palier | Volume | B3 | B4 | B5 | B6 | Débit B3 | Débit global B3→B6 | RAM max Postgres | RAM max Neo4j | Scénario C p50/p95 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 5 000 | 2,216s | 0,908s | 0,777s | 8,367s | 2256 tx/s | 408 tx/s | 193,7 MiB | 998,1 MiB | 119,8/205,0 ms |
| 2 | 20 000 | 5,278s | 1,099s | 0,730s | 9,210s | 3790 tx/s | 1225 tx/s | 160,8 MiB | 1,312 GiB | 121,3/195,6 ms |
| 3 | 50 000 | 13,421s | 1,699s | 0,588s | 19,026s | 3726 tx/s | 1440 tx/s | 191,8 MiB | 1,51 GiB | 120,5/208,0 ms |

Chaque palier suivi d'une vérification explicite post-nettoyage
(`SELECT count(*)` PostgreSQL + `MATCH ... RETURN count(n)` Neo4j,
filtré par `tenant_id`) — confirmée à `0` avant chaque transition,
sans exception.

**Constats :**
- Aucune dégradation détectée jusqu'à 50 000 transactions — le débit
  global s'améliore avec le volume (coût fixe de B6 qui s'amortit
  sur un plus gros lot), pas l'inverse.
- Scénario B : 0 alerte à chaque palier, conforme à la limite actée
  — rien de nouveau appris sur le scoring réel sous charge, comme
  attendu de l'option (a).
- Scénario C : latence stable (~120 ms p50) sur les 3 paliers, 0
  erreur HTTP sur 13 750 requêtes cumulées au total.
- RAM PostgreSQL : stable entre paliers (nettoyage efficace).
- **Point de vigilance réel, à ne pas glisser sous le tapis** : RAM
  Neo4j croît avec le volume (998 Mo → 1,31 Go → 1,51 Go) et **atteint
  quasiment le plafond `heap_max=1G` + `pagecache=512m` déjà configuré
  en Brique 6** pour un contexte de quelques milliers de transactions.
  Pas un échec de ce test, mais un signal explicite pour toute future
  campagne à volume supérieur : ce plafond devra être révisé avant
  d'aller au-delà de 50 000, pas aujourd'hui.

Nettoyage final effectué : `souverain-tenant-desactiver` puis
`DROP SCHEMA tenant_test_charge CASCADE` (confirmé par le fondateur,
6 objets supprimés en cascade, aucune perte de données réelle — le
schéma était déjà vide après les `TRUNCATE` de fin de campagne).

**Étape 5 (Test de charge du pipeline actuel) VALIDÉE le 19 septembre 2026, par le fondateur (Seydou Dangande Abdoul Aziz), sur ThinkPad X1 Carbon Gen 6.**

**Prête pour l'analyse de l'Étape 6 (Ollama/Mistral) dès demande explicite du fondateur**, conformément à l'ordre validé — sauf si le fondateur préfère d'abord ouvrir le cycle de conception UX/UI approfondi resté en attente depuis l'Étape 3, ou traiter le point de vigilance Neo4j (plafond mémoire) avant d'aller plus loin.

## Vérification manuelle ponctuelle — parcours analyste complet (29-30 septembre 2026)

**Contexte** : avant de commencer l'Étape 6 (Ollama/Mistral), vérification
empirique ciblée du parcours humain complet avec une vraie alerte produite
par le pipeline (jamais observé auparavant — Étape 5 n'avait produit aucune
alerte réelle). Tenant temporaire dédié `tenant_verif_b8`
(`tenant_id=b1e689f8-de34-4cdd-ac21-7e408fa83845`), un seul scénario
combiné (structure_etoile + micro_fractionnement + transactions_nocturnes,
score 60), jamais mélangé à `tenant_ne` ni aux autres tenants.

**Résultat principal** : pipeline B3→B4→B5→B6→B7→B8 confirmé fonctionnel
de bout en bout en conditions réelles — 3 détections, 1 alerte réelle
créée (score 60), dashboard affichant correctement score/statut/motifs,
fermeture réelle effectuée (`en_cours_investigation`), entrée d'audit
visible avec email résolu, RBAC confirmé (`analyst` voit et utilise le
formulaire, `auditor` ne le voit pas).

**Bug réel trouvé et corrigé ponctuellement pour ce test** : la migration
`0001_create_audit_log_table.sql` (Brique 8) ne crée `{tenant}.audit_log`
et ses privilèges (`souverain_brique8_audit`) que pour les tenants déjà
enregistrés **au moment de son exécution**. Un tenant créé après coup
(comme `tenant_verif_b8`) n'a ni la table ni les privilèges. La logique
de réparation documentée dans `persistence.py` ne s'exécute qu'au moment
d'une **écriture** (fermeture d'alerte) — jamais au moment de la
**lecture** de l'historique (`GET /alertes/{id}/fermeture`, appelée par
tous les rôles pour afficher le fragment). Conséquence réelle observée :
`500 Internal Server Error` (`InsufficientPrivilegeError`, puis
`relation does not exist` une fois le GRANT ajouté manuellement) au
premier chargement de la page de détail d'une alerte — **avant** toute
tentative de fermeture, pour n'importe quel rôle, y compris `auditor`
qui ne peut jamais fermer d'alerte.

Contourné manuellement pour ce test (table créée, GRANT ajoutés à la
main, identiques à ceux de la migration) — **aucune modification de
code de la Brique 8**. Le bug de fond reste réel et non corrigé : tout
nouveau tenant créé en production (Phase 2, premier export UEMOA)
rencontrera ce même 500 au premier chargement d'une page de détail
d'alerte. À corriger par décision explicite séparée — probablement :
étendre la réparation déjà existante de `persistence.py` au chemin de
lecture (`lecture.py`), ou la déclencher dans `tenant_valide()`.

**Limite assumée de ce test** : scénario volontairement minimal (étoile
pure, un seul compte alerté) — les 3 requêtes du fragment graphe
(Brique 6) retournent "Aucun résultat" par construction (pas de
redistribution multi-sauts, pas de second compte alerté à relier).
Le rendu d'un graphe réellement peuplé reste à vérifier lors de la
campagne fonctionnelle finale.

Nettoyage : tenant temporaire, ses 3 utilisateurs de test et toutes ses
données supprimés après vérification complète.

## Détail — Étape 6a (faisabilité du modèle LLM local)

**Statut : VALIDÉE — faisabilité confirmée le 7 octobre 2026, étape
clôturée le 20 octobre 2026 (clôture simplifiée, décision du fondateur
Seydou Dangande Abdoul Aziz), sur ThinkPad X1 Carbon Gen 6.
Intégration (6b) non commencée.**

Décision de direction actée avant tout test (28 septembre 2026) : pas
de benchmark comparatif multi-modèles — test de faisabilité ciblé sur
un candidat unique, choisi après vérification que Mistral 7B v0.3 est
présenté par son éditeur comme retiré des nouvelles intégrations
recommandées, au profit de Ministral 3. Ministral 3 3B envisagé
uniquement comme secours en cas d'échec matériel mesuré — non
nécessaire, le candidat principal ayant passé le test.

**Modèle retenu et testé** : Ministral 3 8B Instruct, quantification
Q4_K_M (tag Ollama `ministral-3:8b-instruct-2512-q4_K_M`, digest
`1922accd5827`, 6,0 Go, licence Apache 2.0 vérifiée directement depuis
le modèle installé). Détail complet du protocole, des 10 fiches de
test et de la grille PASS/FAIL dans `VERDICT_ETAPE_6A.md` et l'ADR
correspondant (`docs/adr/ADR-004-changement-modele-llm.md`) —
non résumés intégralement ici.

**Incident réel rencontré et contourné, non résolu avec certitude** :
le protocole initial prévoyait Ollama en conteneur Docker
(`souverain-bench-ollama`), cohérent avec le reste de l'architecture
du projet. Tout conteneur Docker sur la machine de développement,
sans exception (vérifié avec un conteneur `curl` neuf et sans lien
avec Ollama), s'est révélé incapable de faire sortir le moindre
trafic vers internet — diagnostic approfondi (DNS, règles `ufw`,
NAT/`MASQUERADE`, `ip_forward`, `DOCKER-USER`/`FORWARD`, capture
`tcpdump`) sans cause unique confirmée avec certitude ; la capture
`tcpdump` a montré le paquet retour bien reçu par la machine
(`wlp2s0 In`) mais rejeté par une erreur `ICMP time exceeded
in-transit`, évoquant un problème de suivi de connexion (`conntrack`)
plutôt qu'un simple blocage de pare-feu. **Contourné par une
installation native d'Ollama** (`curl -fsSL https://ollama.com/
install.sh | sh`, service `systemd`), qui n'a rencontré aucun
problème réseau. Une explication (TTL des paquets entrants réécrit par
le WiFi, contournement par une règle `nft` temporaire) est consignée
dans `docs/architecture/decisions.md` ; cette règle n'était plus
présente le 20 octobre 2026.

**Décision du 20 octobre 2026** : l'exécution se fera **en conteneur
Docker** (service `ollama` du `docker-compose.yml`) ; l'installation
native n'a servi qu'au test de faisabilité. Une fois le modèle dans le
volume, l'inférence fonctionne sans réseau : le blocage réseau ne gêne
que les téléchargements.

**Résultats** : critères PASS, avec deux réserves documentées —
RAM mesurée à 6,53 GiB contre un seuil fixé à 6,5 Go (écart de
0,46 %, accepté avec réserve, seuil non modifié rétroactivement) ;
une confusion récurrente entre le poids d'un pattern de détection et
un nombre de transactions ou d'occurrences, présente sur **4 fiches
sur 10** (F03, F05, F07, F08). **Correction du 13 octobre 2026** : elle
avait d'abord été documentée comme un cas unique (F05) ; la relecture
des sorties a montré qu'elle touchait 4 fiches dès la série native.
Un test complémentaire avec des faits étiquetés explicitement (4
fiches, un passage) ne la reproduit pas, ce qui indique qu'elle vient
largement de la présentation de nos fiches de test ; de petites
imprécisions persistent (unités, « même opération »). La décision du
7 octobre (« risque connu, non bloquant ») reposait sur le seul cas
F05 et est à reconfirmer par le fondateur. L'invariant déjà acté
(aucun chiffre produit par l'IA n'est une source de vérité autonome)
est renforcé. Fonctionnement sans connexion réseau confirmé
manuellement par le fondateur (WiFi physiquement coupé, génération
réussie).

**Étape 6a clôturée le 20 octobre 2026 (clôture simplifiée). Prête
pour l'analyse de l'Étape 6b (intégration) dès demande explicite du
fondateur.**

Reste à faire au début de la 6b (détail dans `VERDICT_ETAPE_6A.md`,
section « Décision de clôture ») :
1. mettre le modèle dans le volume du compose et vérifier son digest
   (`1922accd5827`) ;
2. mesurer la RAM du conteneur ;
3. rédiger l'ADR-006 (exécution conteneurisée) ;
4. désactiver puis, après vérification, désinstaller l'Ollama natif
   (même port 11434) ;
5. réparer ou documenter le réseau des conteneurs (téléchargements) ;
6. faire reconfirmer par le fondateur le caractère « non bloquant » du
   défaut de fidélité.

Mises en cohérence documentaires faites le 20 octobre 2026 :
`docs/architecture/decisions.md` §8 reflète la décision (conteneur) ; la
roadmap cite désormais `ADR-004-changement-modele-llm.md` (elle citait
`ADR-00X`) ; `.env.example` propose le modèle Ministral 3 8B (en
commentaire).

## Détail — Étape 6b : prérequis — grille de fidélité des explications IA

**Statut : grille VALIDÉE EN PRINCIPE par le fondateur le 22 octobre 2026,
avec réserves. Étape 6b NON COMMENCÉE, bloquée (ADR-006, §6) tant que le
contrôle n'est pas démontré sur les erreurs connues et que le lot de
validation n'est pas réussi.**

Document : `docs/ETAPE_6B_GRILLE_FIDELITE.md` (renvoi depuis
`docs/adr/ADR-006-deploiement-ollama-docker.md`, §7).

Contenu retenu :
- 5 critères bloquants (exactitude numérique avec signification,
  non-confusion des grandeurs, aucun verdict ni injonction, aucune entité
  étrangère à la fiche, repli sur les faits structurés) ; 2 critères suivis
  (imprécisions mineures, forme : 120 mots / 6 phrases, repli au-delà de 200).
- Seuil provisoire : zéro échec bloquant sur 48 sorties (16 fiches × 3
  passages, soit 16 cas indépendants) — critère de validation du lot, pas une
  garantie générale de fiabilité.
- Historique des décisions humaines exclu de la fiche de faits ; journaux sans
  texte généré.

Réserves du fondateur :
- timeout Ollama (120 s par tentative, 180 s au total) provisoire jusqu'à
  mesure sur la machine ;
- les 10 cas de la 6a sont conservés et reformulés au format de production ;
  F03, F05, F07 et F08 gardent aussi leurs sorties originales comme témoins ;
- le contrôle de fidélité doit être testé sur les erreurs connues avant toute
  intégration.

Reste à faire avant la 6b : versionner les 10 fiches de la 6a (absentes du
dépôt), figer le lot, prototyper et tester le contrôle, mesurer durée et
mémoire. Réserve mémoire (6,618 Gio contre 6,5 Gio) toujours ouverte. Aucun
fichier de B4, B5 ou B6 modifié.

## Campagne fonctionnelle (parcours analyste, 6 scénarios de fraude synthétique)

**Statut : ABANDONNÉE le 28 septembre 2026, par décision explicite du
fondateur (Seydou Dangande Abdoul Aziz).**

Cette tentative de campagne (tenant `tenant_test_fonctionnel`,
`tenant_id=916da41b-9b5b-44ea-8a95-2b92ac42592b`), restée bloquée à
mi-parcours (scénario 1 jamais confirmé, scénarios 2 à 6 jamais
exécutés — voir historique ci-dessus), est abandonnée sans reprise.
Tenant, registre et schéma physique supprimés. Aucune donnée réelle
perdue : la table `transactions` de ce tenant était déjà vide au
moment de la décision.

Une campagne fonctionnelle finale, plus complète, sera conçue après
la finalisation du projet — couvrant ingestion, détection, scoring,
graphe, alertes, investigation, audit/HITL et assistance IA locale.
Non planifiée à ce jour dans l'ordre numéroté.

## Correction post-validation — Brique 8 : provisionnement de l'audit (17 octobre 2026)

**Statut : VALIDÉE le 17 octobre 2026, par le fondateur (Seydou Dangande Abdoul Aziz), sur ThinkPad X1 Carbon Gen 6, avec trois réserves documentées (voir « Limites et points non traités » et le rappel en fin de section). Contrôles : Ruff propre, 44 tests B8 et 205 tests du workspace verts (PostgreSQL/TimescaleDB et Neo4j réels). La Brique 8 était déjà VALIDÉE (4 septembre 2026) ; sa correction post-validation l'est désormais aussi.**

Défaut (relevé le 29-30 septembre) : sur un tenant créé après la migration B8, la page de détail d'une alerte renvoyait un HTTP 500. **Cause confirmée sur la pile réelle** : `create_tenant()` ne provisionne rien pour le rôle `souverain_brique8_audit` (ni `USAGE` sur le schéma, ni `audit_log`) ; PostgreSQL lève `InsufficientPrivilegeError` (42501), que ni la lecture ni l'écriture n'interceptaient (seul 42P01 l'était). La fixture de test accordait `USAGE` à la main, ce qui masquait le défaut.

Décision : ADR-005 (provisionnement par commande explicite, réparation défensive à l'écriture, lecture sans DDL). Statut de l'ADR : Acceptée le 17 octobre 2026.

Livré (Brique 8 uniquement ; migration `0001`, B1, B2, B7, CSRF et RBAC inchangés) :
- `diagnostic.py` : diagnostic en lecture seule (transaction `READ ONLY`), seul accès du chemin de lecture au pool admin.
- `persistence.py` : `provisionner_audit()` (idempotent, verrou advisory par schéma, contrôle final : jamais `UPDATE`/`DELETE` sur `audit_log`) ; réparation à l'écriture selon la cause constatée, un seul nouvel essai.
- `lecture.py`, `routes.py`, `modeles.py` : `AuditNonProvisionne` → HTTP 503 générique ; `[]` seulement si `audit_log` est légitimement absente.
- `cli.py` : `uv run souverain-audit-provisionner --tenant … | --tous` (codes de sortie 0 à 3).
- Tests : `test_tenant_neuf.py` (R1 à R5 de régression, A/D/C d'acceptation, H5/H7), `test_diagnostic.py`, `test_garanties_statiques.py`.

Défaut propre au correctif, trouvé avant validation : sur un tenant neuf sans table `alertes`, la fermeture réparait l'audit puis remontait une erreur brute (500) au lieu d'`AlerteNonFermable` (409). Corrigé et couvert par le test A5.

Constaté sur la base réelle : `souverain-audit-provisionner --tous` a réparé `tenant_sn_test` (`audit_log`, `usage_schema`, `audit_log_privileges`) ; `tenant_ne` était déjà conforme ; deuxième exécution : 2 conformes, code 0. `INSERT`/`SELECT` accordés, `UPDATE`/`DELETE`/`TRUNCATE` refusés sur `tenant_sn_test.audit_log`.

Limites et points non traités (signalés, pas oubliés) :
- Procédure de reproduction : le tenant de test `tenant_repro_b8` (code `ZZ`) est entré en collision avec les constantes de `test_tenant_governance.py` ; ligne de registre retirée, suite repassée au vert.
- Affichage : avec HTMX, le 503 du fragment d'historique n'est pas inséré dans la page (comportement par défaut pour les 5xx) ; correction côté Brique 7, non faite.
- Migration `0001` de B8 : son `GRANT … ON alertes` n'est pas gardé et pourrait échouer pour un tenant sans table `alertes`. Défaut suspecté (lu dans le SQL), **non reproduit, non évalué**, non corrigé ; à traiter séparément par une migration corrective distincte.
- `create_tenant()` n'appelle pas le provisionnement de B8 : l'étape reste manuelle (automatisation à réexaminer en Phase 2).
- Traçabilité de la commande dans une table d'audit : non faite (le pool admin n'est pas le rôle de gouvernance).

Réserves actées par le fondateur lors de la validation (inchangées, détaillées ci-dessus) : (1) migration `0001` de B8 à examiner séparément ; (2) affichage HTMX du 503 côté Brique 7 ; (3) provisionnement des nouveaux tenants toujours manuel.

**Correction post-validation de la Brique 8 (provisionnement de l'audit) VALIDÉE le 17 octobre 2026, par le fondateur (Seydou Dangande Abdoul Aziz), sur ThinkPad X1 Carbon Gen 6.**

## Règle

Ne pas marquer une brique comme terminée uniquement parce que son code existe. La validation doit inclure tests, vérification manuelle et validation explicite du fondateur.
