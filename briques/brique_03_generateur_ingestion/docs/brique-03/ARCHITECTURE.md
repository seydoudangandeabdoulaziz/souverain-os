# Architecture — Brique 3 : Générateur + ingestion de transactions synthétiques

## Position dans le pipeline

```text
[Brique 1: PostgreSQL/TimescaleDB]   [Brique 2: Auth/RBAC]
              │                              │
              └──────────────┬───────────────┘
                              ▼
              [Brique 3: Générateur + ingestion]
                              │
                    (transactions marquées
                     is_synthetic = true,
                     dans le schéma tenant réel)
                              ▼
              [Brique 4: Détection Hybrid-Stream]  ← consommateur futur
```

La Brique 3 ne dépend que de la Brique 1 (schéma, pool de connexions) et,
indirectement, de la Brique 2 pour l'usage futur si un endpoint API venait
à être ajouté (non retenu en MVP — voir décision "Déclenchement").

## Flux interne

```text
cli.py (point d'entrée)
    │
    ├─► generateur_legitime.generer_lot_legitime()
    │        → transactions "bruit de fond", pattern_label=None
    │
    ├─► patterns_suspects.generer_*()
    │        → transactions issues des 6 patterns du Bloc 7,
    │          pattern_label renseigné (usage tests uniquement,
    │          jamais stocké en base)
    │
    ├─► mélange + shuffle (seed) des deux lots
    │
    └─► ingestion.inserer_transactions(pool, tenant, transactions)
             → INSERT par lots de 500, dans une transaction SQL par lot
             → colonne is_synthetic = true systématique
```

## Pourquoi séparer génération et ingestion (deux modules distincts) ?

**Analogie :** c'est la différence entre écrire un scénario (génération) et
le jouer devant une caméra (ingestion). On veut pouvoir tester le scénario
seul — vérifier que la structure en étoile a bien 8 destinataires en 60
minutes — sans jamais toucher à une base de données. C'est pour ça que
`generateur_legitime.py` et `patterns_suspects.py` sont 100% purs (aucun
import réseau/DB), testables en quelques millisecondes, alors que
`ingestion.py` est le seul module qui touche à `asyncpg`.

Conséquence directe : 15 tests unitaires sur 100% de la logique métier
s'exécutent sans Docker, en moins de 50 ms — seuls les tests d'intégration
de `ingestion.py` nécessitent une vraie instance PostgreSQL.

## Reproductibilité (seed)

Chaque fonction de génération accepte un `random.Random` initialisé avec une
seed. Même seed + mêmes paramètres ⇒ mêmes transactions, au bit près. C'est
ce qui permettra, en Brique 4, d'écrire des tests du type : "avec la seed 42
et l'intensité forte, le détecteur doit repérer au moins 95% des transactions
marquées `structure_etoile`" — un test de non-régression sur la qualité de
détection, reproductible indéfiniment.

## Pourquoi `pattern_label` n'est jamais stocké en base

Si la colonne existait en base, la Brique 4 pourrait "tricher" en la lisant
directement au lieu de détecter réellement le pattern à partir du
comportement transactionnel — biaisant tout test de qualité de détection.
`pattern_label` reste donc uniquement en mémoire côté génération/tests
Python, jamais persistée.

## Fuseau horaire

Le Niger est en WAT (UTC+1, fixe, sans changement d'heure). Tous les
horodatages générés sont conscients du fuseau (`FUSEAU_NIGER`), cohérent
avec une colonne `occurred_at` probablement de type `timestamptz` côté
TimescaleDB (bonne pratique standard pour une hypertable).

## Sécurité — implications de cette brique

- **Injection SQL sur le nom de schéma** : `nom_schema_tenant` provient d'un
  argument CLI (`--tenant`), donc potentiellement d'une saisie humaine.
  `_valider_nom_schema()` rejette tout ce qui n'est pas alphanumérique/underscore
  avant de l'interpoler dans la requête SQL — même précaution que
  `provision_tenant_schema()` en Brique 1.
- **Aucune donnée personnelle réelle** : tous les identifiants (`cpt_XXXXXX`,
  `hub_XXXXXX`, `pivot_XXXXXX`) sont générés, sans lien avec des personnes
  physiques — pas d'enjeu RGPD/Loi 2019-33 Niger pour cette brique.
- **Traçabilité** : `is_synthetic = true` permet un audit ultérieur (Brique 8)
  distinguant clairement les données de test des données réelles, et une
  purge propre avant tout déploiement en production.

## Dépendances vers les briques futures

| Brique | Dépendance |
|---|---|
| 4 — Détection Hybrid-Stream | Consommera les transactions `is_synthetic=true` en mode batch pour ses premiers tests. Le passage à un flux continu réel sera porté par la Brique 4 elle-même (décision actée : pas de stream dans cette brique). |
| 5 — Scoring + alertes | Pourra utiliser `pattern_label` (côté tests Python uniquement) pour mesurer le taux de faux positifs/négatifs du scoring sur un jeu de données connu. |
| 6 — Neo4j | Les patterns `structure_etoile` et `compte_pivot` produisent des sous-graphes reconnaissables (1 hub → N destinataires ; N sources → pivot → M destinations), directement exploitables pour tester les requêtes Cypher. |
| 8 — Audit | `is_synthetic` est le point d'ancrage pour tout hook d'audit qui devrait distinguer données réelles et données de test. |

## Points explicitement hors périmètre (Vision)

- Calibrage statistique des patterns sur données réelles GIABA/UNODC
- Comportement adaptatif des acteurs simulés (réseau qui change de stratégie)
- Génération multi-tenant simultanée
- Mode stream continu (porté par la Brique 4)
- Endpoint API de déclenchement (RBAC) — pourra être ajouté en Brique 7/8 si
  un besoin réel apparaît (ex. génération à la demande depuis le dashboard)
