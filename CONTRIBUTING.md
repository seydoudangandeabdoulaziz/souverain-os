# Contribuer à SOUVERAIN-OS

Les règles destinées aux agents IA et la hiérarchie documentaire sont dans [`AGENTS.md`](./AGENTS.md). Les décisions d'architecture faisant autorité restent dans les décisions verrouillées et les ADR approuvés.

## Principe général

Une seule brique ou un seul chantier transverse autorisé à la fois. Séquence de travail :

```text
COMPRENDRE → ARCHITECTURER → VALIDER → IMPLÉMENTER → TESTER → DOCUMENTER → VALIDER → BRIQUE SUIVANTE
```

Aucune brique ou étape suivante n'est commencée sans validation explicite du fondateur lorsque le processus du projet l'exige.

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
- Chaque brique ou paquet transverse déclare ses dépendances dans son propre `pyproject.toml` ; l'unique `uv.lock` à la racine centralise la résolution et le verrouillage (workspace `uv`, Option A).
- Tests requis avant livraison d'une brique ou d'un paquet transverse, selon le plan de validation approuvé.
- Secure by Design, EBIOS Risk Manager, zero-trust entre microservices.

## Qualité avant commit

Ces commandes décrivent les contrôles habituels des contributeurs. Les agents IA ne les exécutent que si la mission l'autorise et sur le périmètre concerné. `ruff format` modifie les fichiers.

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

Une branche par brique ou par chantier transverse autorisé. Exemple : `brique-01-postgresql`.
