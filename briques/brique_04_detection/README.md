# Brique 4 — Moteur de détection Hybrid-Stream

## Rôle

Détecte les 5 patterns criminels sahéliens structurels (Bloc 7) sur les
transactions déjà ingérées par la Brique 3 : structure en étoile, compte
pivot, micro-fractionnement, transactions nocturnes, flux frontalier. Émet
des événements de détection, persistés dans `{tenant}.detections`. Ne
score rien, n'alerte personne — c'est le rôle de la Brique 5.

## Décisions actées

- **"Hybrid"** = traitement batch en source (lecture SQL triée par
  `occurred_at`), mais **séquentiel et état-plein** dans le moteur — chaque
  règle reçoit les transactions une par une et maintient sa propre mémoire
  courte (fenêtre glissante par compte). C'est ce qui permettra de brancher
  un vrai flux (Kafka/Redis, phase transverse) sans réécrire les règles :
  seul `lecture.py` change, `moteur.py` et `regles/` restent identiques.
  Une composante statistique/calibrée (`Vision`) est explicitement hors
  périmètre MVP.
- **Sortie** : table dédiée `{tenant}.detections`, migration portée par
  cette brique (`0001_create_detections_table.sql`), même mécanique que
  `is_synthetic` en Brique 3 — ne modifie aucun fichier des briques
  précédentes.
- **Seuils MVP** validés tels quels (voir tableau ci-dessous), à ajuster
  après observation des résultats réels sur les données de la Brique 3.
- **Saisonnalité** : pas une règle de détection en MVP (facteur de
  contexte réservé à la Vision).
- **`is_synthetic` jamais utilisé comme critère de détection** — même
  principe que `pattern_label` en Brique 3 : le moteur ne doit jamais
  pouvoir "tricher" en lisant une étiquette plutôt qu'en détectant un
  vrai comportement. `lecture.py` ne sélectionne d'ailleurs même pas
  cette colonne.

## Seuils MVP

| Règle | Seuil |
|---|---|
| Structure en étoile | ≥ 6 destinataires distincts en ≤ 90 min |
| Compte pivot | ≥ 3 réceptions puis ≥ 2 redistributions en ≤ 60 min |
| Micro-fractionnement | ≥ 10 transactions < 1000 XOF, même paire, ≤ 20 min |
| Transactions nocturnes | ≥ 4 transactions 22h-4h, même émetteur |
| Flux frontalier | pas de seuil — chaque transaction du motif est signalée |

## ⚠️ Limite MVP importante — flux frontalier

Cette règle ne détecte le motif Niamey→frontière **que via la convention
de nommage des comptes** du générateur synthétique (`niamey_*` /
`*frontiere*`). En production réelle, aucun identifiant de compte Mobile
Money ne contient d'information géographique — il faudrait un référentiel
compte→région (KYC/déclaratif), qui n'existe dans aucune brique actuelle.
C'est un **placeholder fonctionnel pour les données de test uniquement**,
documenté explicitement dans `regles/flux_frontalier.py` pour qu'aucun
développeur (humain ou IA) ne suppose par erreur qu'il s'agit d'une vraie
détection géographique.

## Dépendances

- **Runtime** : `brique-01-postgresql` (pool, `validate_schema_name`)
- **Tests uniquement** (`dev` group, jamais importée en runtime) :
  `brique-03-generateur-ingestion`, pour réutiliser `patterns_suspects.py`
  et générer des données labellisées en mémoire (jamais persistées avec
  leur label)

## Commandes

```bash
# Depuis la racine du workspace (ajoute "briques/brique_04_detection" à
# [tool.uv.workspace].members si ce n'est pas déjà fait)
uv sync --all-packages

# Tests unitaires purs (sans DB) :
uv run pytest briques/brique_04_detection/tests/test_regle_structure_etoile.py \
              briques/brique_04_detection/tests/test_regle_compte_pivot.py \
              briques/brique_04_detection/tests/test_regle_micro_fractionnement.py \
              briques/brique_04_detection/tests/test_regle_nocturne.py \
              briques/brique_04_detection/tests/test_regle_flux_frontalier.py \
              briques/brique_04_detection/tests/test_moteur.py -v
# → 13/13 attendus (déjà vérifié en environnement de génération)

# Tests d'intégration (contre vraie base, tenant éphémère + tenant_ne réel) :
uv run pytest briques/brique_04_detection/tests/test_integration.py -v -s

# Qualité :
uv run ruff check briques/brique_04_detection
cd briques/brique_04_detection && uv run mypy src && cd ../..

# Détection réelle sur tenant_ne (suppose que la Brique 3 a déjà tourné) :
uv run souverain-detecter --tenant tenant_ne
```

## Sortie attendue (exemple)

```text
5000 transactions lues pour le tenant tenant_ne
X événements de détection générés
  - compte_pivot : ...
  - flux_frontalier : ...
  - micro_fractionnement : ...
  - structure_etoile : ...
  - transactions_nocturnes : ...
✅ X détections enregistrées dans tenant_ne.detections
```

Le nombre exact d'événements dépend des 250 transactions suspectes
réellement injectées par la Brique 3 (répartition aléatoire entre les 5
patterns structurels, seed=42) — c'est normal et attendu, pas un chiffre
figé à l'avance.

## Vérification manuelle

```sql
SELECT pattern_type, count(*) FROM tenant_ne.detections GROUP BY pattern_type;
```

## Erreurs fréquentes

| Symptôme | Cause probable | Diagnostic |
|---|---|---|
| `ValueError: Aucun tenant actif trouvé` | Bootstrap non joué pour ce tenant | Voir README Brique 3 |
| 0 détection alors que la Brique 3 a bien tourné | Normal si les seuils MVP sont plus stricts que l'intensité "moyenne" générée — vérifier avec `test_detecte_sur_transactions_existantes_tenant_ne` | Ajuster les seuils dans `regles/*.py` |
| Détections en double à chaque exécution du CLI | Le CLI ne fait pas de déduplication — relancer `souverain-detecter` plusieurs fois sur les mêmes transactions insère de nouvelles lignes à chaque fois | Attendu en MVP : pas de mécanisme d'idempotence sur les détections (à ajouter en Brique 5/8 si besoin) |

## Sécurité

- Validation anti-injection réutilisée de la Brique 1 (`validate_schema_name`).
- `lecture.py` ne sélectionne jamais `is_synthetic` — le moteur ne peut pas
  s'appuyer sur cette colonne, volontairement.
- Table `detections` suit la même convention de gouvernance que
  `transactions` (tenant_id/country_code/data_classification dupliqués).

## Dépendances avec les briques futures

- **Brique 5 (Scoring + alertes)** : lira `{tenant}.detections` pour
  attribuer un score de risque et déclencher les alertes CENTIF.
- **Brique 6 (Neo4j)** : `compte_pivot` et `structure_etoile` produisent
  des `compte_pivot` identifiables, exploitables pour l'analyse de graphe.
- **Vision** : composante statistique/calibrée, vrai référentiel
  géographique pour `flux_frontalier`, vrai flux temps réel (remplace
  uniquement `lecture.py`).
