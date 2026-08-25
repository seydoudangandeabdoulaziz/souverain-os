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

## Règle

Ne pas marquer une brique comme terminée uniquement parce que son code existe. La validation doit inclure tests, vérification manuelle et validation explicite du fondateur.
