# Changelog

Ce projet suit le [Semantic Versioning](https://semver.org/lang/fr/) (`MAJOR.MINOR.PATCH`).
Le projet reste en `0.x` tant que le MVP n'est pas considéré comme stable.

## [Non publié]

### Ajouté
- Structure complète du repository (cible finale).
- Brique 0 — Fondations : socle Python/uv, Docker Compose socle, qualité de code (Ruff/mypy/pytest/pre-commit), documentation initiale.
- ADR-000 : décision de reconstruction Greenfield.

## [0.4.0] — 2026-08-15

### Ajouté
- Brique 3 — Générateur + ingestion de transactions synthétiques : génération de transactions Mobile Money légitimes et des 6 patterns criminels sahéliens (Bloc 7), insertion par lots dans le schéma tenant réel, CLI `souverain-generer`.
- `scripts/bootstrap_tenant_ne.sql` : enregistrement MVP provisoire du tenant Niger dans `shared.tenants_registry`, en attendant `create_tenant()` (Brique 8).
- Colonne `is_synthetic` sur `{tenant}.transactions`, avec auto-réparation idempotente à l'insertion.

### Corrigé
- `pyproject.toml` racine : ajout de `[tool.uv]` / `package = false`, corrigeant l'échec de `uv sync` (le projet racine n'a pas de code propre à construire, seulement un point d'ancrage de workspace).
- Documentation de la commande correcte pour synchroniser tout le workspace : `uv sync --all-packages` (et non `uv sync` seul).

### Validé
- Brique 3 : validée par le fondateur après tests réels contre une instance PostgreSQL (21/21 tests) et génération réelle de 5000 transactions.

## [0.3.0] — 2026-08-13

### Ajouté
- Brique 2 — Auth / RBAC minimal + fondations SOUVERAIN-ID : hachage Argon2id, JWT HMAC-SHA256, révocation via `token_version`, RBAC 3 rôles, routeur `/auth/login` et `/auth/me`.

### Corrigé
- `verify_password()` : capture de `InvalidHashError` (hérite de `ValueError`, pas de `Argon2Error`).
- Tests d'intégration : remplacement de `TestClient` (thread séparé, boucle asyncio incompatible avec le pool `asyncpg`) par `httpx.AsyncClient` + `ASGITransport`.
- Ajout du marqueur `py.typed` à la Brique 1 pour exposer son typage aux packages dépendants.

### Validé
- Brique 2 : validée par le fondateur après tests réels contre une instance PostgreSQL (24/24 tests).

## [0.2.0] — 2026-08-13

### Ajouté
- Brique 1 — PostgreSQL / TimescaleDB multi-tenant : schéma partagé, template schema-per-tenant, provisioning technique, healthcheck DB, service Docker Compose (profile `postgres`).

### Corrigé
- Résolution du fichier `.env` indépendante du répertoire d'exécution.
- Healthcheck Docker `pg_isready` ciblant explicitement la bonne base de données.

### Validé
- Brique 1 : validée par le fondateur après tests réels contre une instance PostgreSQL/TimescaleDB (15/15 tests, healthcheck SAIN).

## [0.1.0] — 2026-08-12

### Validé
- Brique 0 — Fondations : validée par le fondateur après vérification locale complète (tests, healthcheck, ruff, mypy).
