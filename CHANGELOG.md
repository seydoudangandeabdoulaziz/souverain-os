# Changelog

Ce projet suit le [Semantic Versioning](https://semver.org/lang/fr/) (`MAJOR.MINOR.PATCH`).
Le projet reste en `0.x` tant que le MVP n'est pas considéré comme stable.

## [Non publié]

### Ajouté
- Structure complète du repository (cible finale).
- Brique 0 — Fondations : socle Python/uv, Docker Compose socle, qualité de code (Ruff/mypy/pytest/pre-commit), documentation initiale.
- ADR-000 : décision de reconstruction Greenfield.

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
