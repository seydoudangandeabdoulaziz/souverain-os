# Brique 0 — Fondations : documentation détaillée

## Rôle

Fournir le socle de développement du projet : structure du dépôt, configuration Python (`uv`), outillage qualité (Ruff, mypy, pytest, pre-commit), Docker Compose socle, documentation initiale. Aucune logique métier.

## Responsabilités

- Initialiser le repository Git et sa structure de dossiers cible.
- Configurer le workspace `uv` (racine + Brique 0).
- Fournir un healthcheck minimal de l'environnement (Python, dépendances, structure de dossiers).
- Poser les bases de qualité de code (lint, typage, tests, hooks).

## Limites explicites

Cette brique **n'inclut pas** : PostgreSQL/TimescaleDB, Neo4j, Auth/RBAC, SOUVERAIN-ID, RAG, Ollama/Mistral, PQC, Redis/Celery, monitoring métier. Ces éléments sont explicitement hors périmètre (cf. `00_DECISIONS_VERROUILLEES.md`, point 5).

## Fichiers livrés

```text
briques/brique_00_fondations/
├── README.md
├── pyproject.toml
├── src/
│   └── brique_00_fondations/
│       ├── __init__.py
│       └── healthcheck.py
├── tests/
│   └── test_sanity.py
└── scripts/
    └── healthcheck_env.py
```

## Commandes de vérification

```bash
cd briques/brique_00_fondations
uv sync
uv run pytest -v
uv run python scripts/healthcheck_env.py
uv run ruff check .
uv run mypy src/
```

## Estimation RAM

< 300 Mo en pic (Python + venv + pytest). Marge > 15,7 Go sur la machine de référence (16 Go DDR4). Pas de distinction MVP/Vision pertinente pour cette brique — socle identique dans les deux cas.
