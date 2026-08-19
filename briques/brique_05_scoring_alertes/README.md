# Brique 5 — Scoring + Alertes

## Rôle

Agrège les détections indépendantes produites par la Brique 4
(`{tenant}.detections`) par `compte_pivot`, sur une fenêtre glissante
de 7 jours (configurable), en un score de risque (0-100). Si le score
franchit un seuil configurable, crée ou met à jour une alerte
`{tenant}.alertes`.

## Limites explicites (hors périmètre)

- Aucun envoi réel vers CENTIF (aucun canal n'existe) — une alerte MVP
  est une ligne en base avec statut `'ouverte'`, exposable plus tard
  par la Brique 7 (dashboard).
- Pas d'enrichissement graphe (Brique 6, pas encore construite).
- Pas de composante statistique/calibrée (Vision).
- Fermeture/traitement d'une alerte : Brique 8 (Human-in-the-loop).
- `is_synthetic` n'est jamais un critère de score, uniquement une
  métadonnée calculée après coup (cf. plus bas).

## Décisions d'architecture validées (résumé)

| Question | Décision |
|---|---|
| Granularité (Q1) | Score agrégé par `compte_pivot`, fenêtre glissante 7j |
| Consommation (Q2) | Lecture indépendante, table de suivi `detections_traitees` comme déclencheur de recalcul — jamais un filtre de calcul |
| Formule (Q3) | Somme des poids des `pattern_type` **distincts** présents dans la fenêtre (30/25/20/15/10), plafonnée à 100, pas de décroissance ni de bonus de combinaison |
| Seuil (Q4) | Fixe, `50` par défaut, explicitement provisoire |
| Anti-doublon (Q5) | Une alerte `'ouverte'` par `(tenant_id, compte_pivot)` — mise à jour, jamais dupliquée |
| Schéma (Q6) | Table `alertes` + table de jonction `alertes_detections` (traçabilité), plutôt qu'une colonne tableau |

## Gaps réels découverts (vérifiés contre le vrai code Brique 4)

1. **Aucun flag "traité" sur `detections`** — remplacé par une table
   de suivi séparée `detections_traitees (detection_id)`, cohérente
   avec le choix `alertes_detections` (table plutôt que colonne).
2. **Clé de regroupement = `detections.compte_pivot`** (pas
   `account_id`), nullable en théorie — une détection avec
   `compte_pivot IS NULL` est exclue du scoring et journalisée en
   warning (`detection_id`), jamais silencieusement ignorée.
3. **`is_synthetic` n'existe pas sur `detections`** — calculé par
   jointure `detections.transaction_ids` (UUID[]) →
   `transactions.is_synthetic`. Règle : `true` seulement si 100% des
   transactions liées à toutes les détections contributrices sont
   synthétiques, sinon `false` (en cas de doute, traité comme réel).

## Structure des fichiers

```text
briques/brique_05_scoring_alertes/
├── pyproject.toml              # nom : brique-05-scoring-alertes
├── migrations/
│   └── 0001_create_alertes_table.sql
├── src/souverain_scoring/
│   ├── config.py                # poids, fenêtre, seuil (provisoires)
│   ├── modeles.py                # DetectionAgregee, ScoreCompte, DecisionAlerte, Alerte
│   ├── lecture.py                # quels compte_pivot recalculer (déclencheur)
│   ├── agregation.py             # TOUTES les détections du compte, fenêtre 7j
│   ├── scoring.py                # calcul pur du score (testable sans DB)
│   ├── seuils.py                 # comparaison au seuil
│   ├── alertes.py                # anti-doublon + calcul is_synthetic
│   ├── persistence.py            # upsert alertes + jonction + detections_traitees
│   └── cli.py                    # uv run souverain-scorer
└── tests/
    ├── unit/                     # 17 tests, aucune DB requise
    └── integration/              # squelette, à connecter à l'infra réelle
```

## Commandes

```bash
# Depuis la racine du workspace
uv sync --all-packages

# Appliquer la migration (adapter à ton mécanisme d'application de migrations)
psql -d souverain_os -f briques/brique_05_scoring_alertes/migrations/0001_create_alertes_table.sql \
    --set search_path=tenant_ne

# Lancer les tests unitaires (aucune DB requise)
cd briques/brique_05_scoring_alertes
uv run pytest tests/unit -v

# Lint / typage
uv run ruff check briques/brique_05_scoring_alertes
uv run mypy src --strict   # depuis le dossier de la brique

# Cycle de scoring (une fois le pool Brique 1 branché, cf. TODO dans cli.py)
uv run souverain-scorer --tenant tenant_ne --tenant-id niger_001 --country-code NE
```

## Vérifié dans cette session (sandbox, sans DB)

- `ruff check src tests` → **All checks passed**.
- `mypy src --strict` → **Success, no issues found** (10 fichiers).
- `pytest tests/unit` → **17/17 tests passés** (scoring, seuils, is_synthetic).

## Points à vérifier sur ta machine avant la validation finale

1. **`cli.py`** importe `from souverain_postgresql.pool import create_pool` —
   nom de module non confirmé contre le vrai code de la Brique 1, à
   corriger si différent.
2. **`tests/integration/conftest.py`** est un squelette — à connecter
   à la fixture réelle de tenant éphémère déjà utilisée en Briques 1/3/4,
   plutôt que réinventée.
3. **`pyproject.toml`** — vérifier le chemin relatif exact de
   `[tool.uv.sources] brique-04-detection = { workspace = true }`
   contre la structure réelle du workspace racine.
4. La migration n'a **jamais été exécutée contre une vraie instance**
   PostgreSQL/TimescaleDB dans cette session (pas d'accès Docker en
   sandbox) — comme pour les Briques 1, 3 et 4, des bugs réels peuvent
   apparaître uniquement au moment de l'exécution locale.

## Erreurs fréquentes attendues (par analogie avec les briques précédentes)

- Si `uv sync --all-packages` échoue sur la dépendance dev vers la
  Brique 4 : vérifier que `tool.uv.sources` pointe vers le bon chemin
  workspace (même classe de bug que Brique 4 → Brique 3).
- Si `souverain-scorer` échoue avec une erreur sur `alertes` ou
  `alertes_detections` introuvable : la migration
  `0001_create_alertes_table.sql` n'a pas été appliquée dans le schéma
  tenant ciblé — `verifier_schema()` doit lever une erreur explicite
  dans ce cas plutôt qu'une erreur SQL opaque.
