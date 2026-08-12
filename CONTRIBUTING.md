# Contribuer à SOUVERAIN-OS

## Principe général

Une seule brique à la fois. Séquence obligatoire :

```text
COMPRENDRE → ARCHITECTURER → VALIDER → IMPLÉMENTER → TESTER → DOCUMENTER → VALIDER → BRIQUE SUIVANTE
```

Aucune brique suivante n'est commencée sans validation explicite du fondateur sur la brique précédente.

## Conventions de commit

Ce projet utilise [Conventional Commits](https://www.conventionalcommits.org/fr/).

```text
feat(fondations): initialiser le socle
feat(postgresql): ajouter le schema multi-tenant
fix(fondations): corriger le healthcheck
docs(architecture): documenter la decision ADR
test(brique-01): ajouter les tests de persistence
```

## Conventions de code

- Python 3.12+ strict, type hints obligatoires, async partout où pertinent.
- Commentaires en français, uniquement lorsqu'ils apportent une vraie valeur pédagogique (pas de commentaires redondants avec le code).
- Nommage des variables/fonctions en anglais, `snake_case`.
- Chaque brique a son propre `pyproject.toml` et son lockfile (workspace `uv`, Option A).
- Tests obligatoires pour toute brique livrée.
- Secure by Design, EBIOS Risk Manager, zero-trust entre microservices.

## Qualité avant commit

```bash
uv run ruff check .
uv run ruff format .
uv run mypy .
uv run pytest
```

Les hooks `pre-commit` automatisent ces vérifications.

## Structure d'une brique

```text
brique_XX_nom/
├── README.md
├── pyproject.toml
├── src/
│   └── package_name/
├── tests/
├── migrations/    (si applicable)
├── scripts/
└── docs/
```

Ne pas créer de fichiers ou dossiers dont la nécessité n'est pas démontrée.

## Branches

Une branche par brique. Exemple : `brique-01-postgresql`.
