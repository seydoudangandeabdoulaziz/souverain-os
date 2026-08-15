# Architecture — Brique 4 : Moteur de détection Hybrid-Stream

## Position dans le pipeline

```text
[Brique 3: Générateur + ingestion]
    │  (transactions is_synthetic=true dans {tenant}.transactions)
    ▼
[Brique 4: Détection Hybrid-Stream]
    ├── lecture.py         → SELECT ... ORDER BY occurred_at (source batch)
    ├── moteur.py           → orchestration séquentielle, sans état propre
    ├── regles/*.py         → 5 règles à état (fenêtres glissantes)
    └── persistence.py      → écriture dans {tenant}.detections
                              │
                              ▼
              [Brique 5: Scoring + alertes]  ← consommateur futur
```

## Le principe "Hybrid" en détail

**Analogie :** imagine un contrôleur de sécurité à un poste-frontière. Qu'il
regarde une caméra en direct (vrai flux) ou qu'il visionne l'enregistrement
de la nuit dernière accéléré (batch), sa façon de repérer un comportement
suspect ne change pas : il observe les passages un par un, dans l'ordre, et
garde en tête "ce véhicule est déjà passé 3 fois cette heure-ci". C'est
exactement la séparation ici : `lecture.py` est la caméra (source), `regles/`
est le contrôleur (logique), et le contrôleur ne sait pas s'il regarde du
direct ou de l'enregistré.

Concrètement :
- `TransactionObservee` (modeles.py) est indépendant de tout mécanisme de
  source — pas de champ `is_synthetic`, pas de référence à la Brique 3.
- `RegleDetection.traiter(transaction)` reçoit **une** transaction à la
  fois et retourne 0 ou 1 événement — jamais une liste complète à traiter
  d'un coup.
- `moteur.py` ne fait qu'itérer et distribuer — il n'a aucun état propre,
  tout l'état vit dans les règles.

Conséquence directe : brancher un vrai flux Kafka/Redis en phase transverse
ne touchera que `lecture.py` (remplacer le `SELECT` par un consommateur de
messages qui appelle `moteur.py` sur chaque message reçu). `regles/` et
`moteur.py` resteront identiques.

## Fenêtre glissante — le mécanisme d'état

`FenetreGlissante` (regles/base.py) est le seul mécanisme d'état partagé
entre les règles. Elle :
- conserve les entrées des N dernières minutes, purgées **par rapport à
  l'horodatage de la transaction courante** (pas l'heure système) — c'est
  ce qui rend le traitement rejouable et déterministe, peu importe quand
  le CLI est réellement exécuté.
- expose `deja_signale`, un booléen qui empêche de re-déclencher un
  événement à chaque nouvelle transaction tant que l'épisode suspect reste
  actif. Il se réinitialise automatiquement dès que la fenêtre se vide
  complètement (l'épisode est "terminé"), permettant un nouveau
  déclenchement pour un futur épisode sur le même compte.

## Pourquoi `is_synthetic` n'est jamais lu

Répété volontairement à plusieurs endroits (lecture.py, ce document,
README) : si le moteur pouvait lire cette colonne, un test de détection
"réussi" ne prouverait rien — il suffirait de renvoyer `is_synthetic` comme
résultat. Le découplage strict entre génération labellisée (Brique 3, tests
uniquement) et moteur de détection (aucune connaissance du label) est ce
qui rend la mesure de rappel/précision crédible.

## Limite MVP assumée — `flux_frontalier`

Voir le docstring de `regles/flux_frontalier.py` et le README. Cette règle
est un cas particulier : elle ne peut fonctionner qu'avec les conventions
de nommage du générateur synthétique. Documentée ici pour qu'elle ne soit
jamais confondue avec une vraie capacité de détection géographique en
production — un vrai référentiel compte→région est nécessaire en Vision.

## Dépendances

| Brique | Nature | Usage |
|---|---|---|
| 1 — PostgreSQL | Runtime | `create_pool`, `close_pool`, `validate_schema_name` |
| 3 — Générateur | Test uniquement (`dev` group) | `patterns_suspects.py`, pour générer des données labellisées en mémoire dans les tests |

La dépendance vers la Brique 3 en test uniquement est une décision
délibérée : elle garantit que le code runtime de la Brique 4 ne pourrait
techniquement pas accéder à `pattern_label` même par erreur d'import — la
séparation est structurelle, pas seulement une convention de style.

## Sécurité

- `validate_schema_name` (Brique 1) réutilisée en lecture et en écriture.
- `{tenant}.detections` suit la même convention de gouvernance que
  `{tenant}.transactions` (tenant_id/country_code/data_classification).
- Aucune donnée personnelle nouvelle introduite — les détections
  référencent des `transaction_id` déjà présents dans `transactions`.

## Dépendances vers les briques futures

| Brique | Dépendance |
|---|---|
| 5 — Scoring + alertes | Lira `{tenant}.detections` pour attribuer un score et déclencher les alertes. Aucune notion de gravité n'existe encore dans les événements de détection eux-mêmes (volontairement — c'est le rôle de la Brique 5). |
| 6 — Neo4j | `compte_pivot` (le champ, pas seulement le pattern) identifie un nœud central directement exploitable pour l'analyse de graphe. |
| Vision | Composante statistique/calibrée en complément des règles fixes ; vrai référentiel géographique ; vrai flux temps réel (remplace `lecture.py` uniquement). |

## Points explicitement hors périmètre (Vision)

- Composante statistique/ML de détection d'anomalie
- Référentiel géographique réel pour `flux_frontalier`
- Idempotence des détections (éviter les doublons entre exécutions successives)
- Vrai flux temps réel (Kafka/Redis)
- Utilisation de la saisonnalité comme facteur de réduction des faux positifs
