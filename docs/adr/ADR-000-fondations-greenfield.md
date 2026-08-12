# ADR-000 — Reconstruction Greenfield des fondations

**Statut : Acceptée**
**Date : 11 août 2026**
**Décideur : Seydou Dangande Abdoul Aziz (fondateur)**

## Contexte

Le projet SOUVERAIN-OS dispose d'un document fondateur (juin 2026) définissant vision, fonctions, stack et roadmap. Une première tentative de construction existait, mais il a été décidé de repartir de zéro sur l'ensemble du socle technique (code, environnement, bases de données, migrations, configurations, conteneurs, tests, pipelines), conformément à `00_DECISIONS_VERROUILLEES.md`.

## Décision

- Reconstruction complète : aucun ancien code, ancienne base ou ancien état d'avancement ne constitue le socle actuel.
- L'ancien code peut être consulté ponctuellement comme référence, jamais comme fondation.
- La vision, les exigences fonctionnelles et les décisions explicitement conservées du document fondateur restent valables et ne sont pas réinventées.
- Gestion des dépendances : **Option A — workspace `uv`** (un `pyproject.toml` racine + un `pyproject.toml` par brique, lockfile unique racine résolvant l'ensemble du graphe).
- Ordre de reconstruction : Fondations → PostgreSQL/TimescaleDB → Auth/RBAC → Générateur/ingestion → Détection → Scoring/alertes → Neo4j → Dashboard → Audit. Puis phase transverse (RAG, Ollama/Mistral, PQC, Redis/Celery, Prometheus/Grafana, SOUVERAIN-ID complet).
- Méthode : une seule brique à la fois, séquence COMPRENDRE → ARCHITECTURER → VALIDER → IMPLÉMENTER → TESTER → DOCUMENTER → VALIDER → BRIQUE SUIVANTE.

## Conséquences

- La structure complète du dépôt est posée dès la Brique 0, mais seule la Brique 0 est réellement implémentée (règle `STRUCTURE ≠ IMPLÉMENTATION`).
- Toute dépendance technique imposant un changement d'ordre ou de périmètre doit être signalée, expliquée et validée avant application — aucune modification silencieuse.
- Ce document complète mais ne remplace pas `01_DOCUMENT_REFERENCE_FONDATEUR.md`, `03_CAHIER_DES_CHARGES.md`, `04_ARCHITECTURE_REFERENCE.md`, `05_SECURITE_ET_GOUVERNANCE.md`, `06_ROADMAP_ET_BRIQUES.md`, `07_GUIDE_DEVELOPPEMENT.md`, `08_AVANCEMENT.md`.

## Alternatives envisagées

- Projets `uv` totalement indépendants par brique (lockfiles séparés, sans workspace) : écartée car elle complique la cohérence globale des versions de dépendances partagées entre briques (ex. `pydantic`, `fastapi`) sans bénéfice réel à l'échelle de ce projet.
