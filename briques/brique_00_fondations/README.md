# Brique 0 — Fondations

**Statut : VALIDÉE**

## Rôle

Fournir le socle de développement du projet SOUVERAIN-OS : structure de dossiers, environnement Python géré par `uv`, outillage qualité (Ruff, mypy, pytest), et un healthcheck qui vérifie que tout est en place.

Cette brique ne contient **aucune logique métier**. Elle ne parle à aucune base de données, aucun service externe, aucun réseau.

## Structure

```text
brique_00_fondations/
├── README.md                              ← ce fichier
├── pyproject.toml                         ← dépendances isolées de la brique
├── src/
│   └── brique_00_fondations/
│       ├── __init__.py
│       └── healthcheck.py                 ← logique de vérification
├── tests/
│   └── test_sanity.py                     ← tests de base
└── scripts/
    └── healthcheck_env.py                 ← CLI exécutable
```

## Installation

Depuis la racine du dépôt :

```bash
cd briques/brique_00_fondations
uv sync
```

`uv sync` lit le `pyproject.toml` de cette brique (dépendances isolées) tout en respectant le workspace `uv` racine (résolution cohérente du graphe global).

## Vérifier que tout fonctionne

```bash
# Lancer les tests
uv run pytest -v

# Lancer le healthcheck en ligne de commande
uv run python scripts/healthcheck_env.py

# Vérifier le style et le typage
uv run ruff check .
uv run mypy src/
```

## Ce que vérifie le healthcheck

1. **Version de Python** — doit être >= 3.12.
2. **Structure du dépôt** — les dossiers `briques/`, `docs/`, `shared/`, `scripts/`, `tests/`, `data/` doivent exister à la racine.
3. **Structure de la Brique 0 elle-même** — README, pyproject.toml, `src/`, `tests/`, `scripts/` doivent être présents.

## Erreurs fréquentes et diagnostic

| Symptôme | Cause probable | Diagnostic |
|---|---|---|
| `uv sync` échoue avec une erreur de version Python | Python 3.12+ non disponible sur la machine | Vérifier `python3 --version`, installer 3.12+ si nécessaire, ou laisser `uv` le télécharger automatiquement |
| `ModuleNotFoundError: brique_00_fondations` en lançant `scripts/healthcheck_env.py` directement (sans `uv run`) | Le package n'est pas sur le `PYTHONPATH` | Toujours utiliser `uv run python scripts/healthcheck_env.py`, qui active l'environnement virtuel correctement |
| `check_repo_structure` retourne `FAIL` | Le script est exécuté depuis un clone incomplet du dépôt | Vérifier que tous les dossiers racine (`briques/`, `docs/`, etc.) ont bien été clonés/committés |
| `pytest` ne trouve aucun test | Mauvais répertoire de travail | Se placer dans `briques/brique_00_fondations/` avant de lancer `uv run pytest` |

## Implications sécurité

- Aucun secret n'est manipulé par cette brique.
- Aucun service réseau n'est exposé.
- Le hook pre-commit `detect-private-key` protège contre un commit accidentel de clé privée dès cette étape.

## Dépendances avec les briques futures

La Brique 1 (PostgreSQL/TimescaleDB) réutilisera la même logique de workspace `uv` et le même pattern de healthcheck, étendu à la connectivité base de données.

## Estimation RAM

Voir `docs/brique-00/README.md` pour le détail. Résumé : **< 300 Mo en pic**, marge très large sur la machine de référence (16 Go DDR4). Pas de distinction MVP/Vision pertinente pour cette brique.

## Validation

Cette brique est **VALIDÉE** (12 août 2026, par le fondateur, testée en local sur ThinkPad X1 Carbon Gen 6 — tests, healthcheck, ruff, mypy tous passés).
