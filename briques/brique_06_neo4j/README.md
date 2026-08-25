# Brique 6 — Graphe criminel Neo4j

**Statut : implémentée, en attente de validation par le fondateur.**

## Rôle

Projette le flux transactionnel (`{tenant}.transactions`, Brique 1) dans
un graphe Neo4j, pour révéler des motifs de réseau **invisibles** aux
règles séquentielles de la Brique 4 et au scoring par compte isolé de la
Brique 5 : chaînes de redistribution multi-sauts, comptes pont entre deux
comptes déjà alertés, connexions cachées entre investigations distinctes.

**Hors périmètre** : pas de dashboard/investigation (Brique 7), pas
d'audit trail (Brique 8). CLI uniquement (`uv run souverain-grapher`),
cohérent avec toutes les briques précédentes.

## ⚠️ Contradiction actée à l'analyse — isolation multi-tenant

**Neo4j Community Edition ne supporte qu'une seule base de données** —
le multi-base (l'équivalent du schema-per-tenant PostgreSQL) est une
fonctionnalité Enterprise. Vérifié explicitement pendant l'analyse
(document Neo4j officiel + communauté), pas supposé.

**Décision actée : Option A — isolation logique par `tenant_id`**, une
seule base Neo4j, `tenant_id` posé sur **chaque** nœud et **chaque**
relation. Rejetée : une instance Neo4j par tenant (isolation physique),
qui contredit le principe fondateur *"ajouter un pays = ajouter un
tenant, pas réécrire le système"* — provisionner un conteneur/JVM par
pays n'est pas un ajout léger.

**Conséquence assumée** : le niveau d'isolation de cette brique est
**plus faible** que celui de PostgreSQL (schema-per-tenant, isolation
physique). C'est une garantie logique, appliquée par discipline de code
et par contrainte de schéma — voir `garde_isolation.py`.

## Point de passage unique — `garde_isolation.py`

**Décision actée, non négociable** : `garde_isolation.py` est le **seul**
fichier du projet autorisé à contenir du texte Cypher — générique
(synchronisation) et métier (les 3 requêtes) confondus. `requetes.py` ne
fait que traduire ses résultats bruts (`dict`) en objets Python typés
(`Chemin`, `ComptePont`) ; `cli.py` n'appelle jamais Neo4j directement.

Discipline appliquée dans **toute** requête de ce fichier :
- Chaque motif de nœud dans un `MATCH` porte `{tenant_id: $tenant_id}` —
  y compris les nœuds atteints après plusieurs sauts.
- Pour les traversées à longueur variable (nœuds intermédiaires non liés
  individuellement) : double vérification défensive
  `ALL(n IN nodes(path) WHERE n.tenant_id = $tenant_id)` **et**
  `ALL(r IN relationships(path) WHERE r.tenant_id = $tenant_id)` —
  jamais laissé à la seule garantie implicite que les relations ne
  peuvent physiquement pas exister entre deux tenants.
- Contrainte de schéma en renfort : unicité composite `(tenant_id,
  compte_id)` sur `:Compte` (`assurer_contraintes()`) — empêche la
  fusion silencieuse de deux comptes de tenants différents partageant
  le même `compte_id` (réutilisation des préfixes du générateur Brique 3
  à l'export UEMOA). Vérifié à l'analyse : disponible en Community
  Edition (contrainte d'unicité simple, à la différence des "node key
  constraints" existence+unicité, réservées à Enterprise).

**Testé en premier, avant tout autre test de cette brique** :
`tests/test_isolation_tenant.py` — scénario délibérément défavorable, deux
tenants avec les **mêmes** `compte_id`, vérifie qu'aucune requête ne
fuit d'un tenant à l'autre, y compris via une traversée à plusieurs sauts.

## Modèle de nœuds/relations

```
(:Compte {tenant_id, compte_id})
    -[:ENVOIE {tenant_id, transaction_id, amount, currency, channel, occurred_at, is_synthetic}]->
(:Compte {tenant_id, compte_id})
```

Pas de nœud `Transaction` séparé — chaque transaction est une relation.
`transaction_id` comme clé de la relation dans le `MERGE` : repose sur
son **unicité garantie** (UUID généré par PostgreSQL, `gen_random_uuid()`,
Brique 1) — vérifié dans le schéma réel avant de faire ce choix, pas une
supposition implicite.

## Double dépendance de lecture — jamais vers la Brique 4 directement

`lecture.py` lit deux sources en amont, jamais la Brique 4 :
- **Brique 1** (`{tenant}.transactions`) : source à projeter dans le graphe.
- **Brique 5** (`{tenant}.alertes`, statut `'ouverte'`) : comptes déjà
  alertés, nécessaires aux requêtes b) et c).

Dupliquées en lecture directe via `brique-01-postgresql`, sans importer
`brique_05_scoring_alertes` en runtime — même principe que la Brique 5
vis-à-vis de la Brique 4. **Une future conversation ne doit pas supposer
une dépendance directe vers la Brique 4** : cette brique n'en a aucune.

`lire_comptes_alertes()` retourne une liste vide si `{tenant}.alertes`
n'a pas encore d'alerte ouverte (cas réel actuel de `tenant_ne`) — jamais
une erreur. Si la table n'existe pas du tout (Brique 5 jamais exécutée
pour ce tenant), l'erreur PostgreSQL est laissée remonter telle quelle
(signal clair d'un problème de séquencement des briques, pas masqué).

## Les 3 requêtes métier

| # | Requête | Ce qu'elle révèle, invisible aux briques précédentes |
|---|---|---|
| a) | `detecter_chaines_redistribution` | Chaîne A→B→C→...→N (3 à 6 sauts) — invisible aux règles séquentielles de la Brique 4, qui regardent une fenêtre courte autour d'un seul compte. |
| b) | `detecter_comptes_pont` | Compte reliant deux comptes déjà alertés, lui-même jamais alerté — invisible au scoring par compte isolé de la Brique 5. |
| c) | `chemin_le_plus_court_entre_alertes` | Connexion cachée entre deux comptes flaggés indépendamment — `shortestPath` non dirigé. |

(c) remplace la proposition initiale "cluster dense de comptes" — écartée
à l'analyse : nécessitait le plugin Neo4j Graph Data Science (non
installé, dépendance non signalée) et recouvrait ce que la règle
`structure_etoile` de la Brique 4 détecte déjà.

## Portée du graphe — limite MVP documentée

Import de **l'intégralité** de `{tenant}.transactions`, pas seulement les
comptes déjà détectés — le graphe doit pouvoir révéler des motifs
invisibles à la Brique 4, se limiter aux comptes déjà flaggés viderait
sa raison d'être.

**Limite MVP assumée** : `synchroniser()` retraverse l'intégralité des
transactions à chaque exécution, même si `MERGE` évite toute duplication
— cohérent avec le principe déjà appliqué en Brique 4/5 (recalcul complet
plutôt qu'un mécanisme de "traité" fragile, cf. le bug corrigé en
Brique 5). Pas une régression, mais même limite d'échelle : à l'échelle
UEMOA (millions de transactions potentielles), un import complet à
chaque exécution deviendra coûteux. **Import incrémental = Vision.**

## Dépendances

- **Runtime** : `brique-01-postgresql` (lecture transactions + alertes),
  driver `neo4j` officiel.
- Aucune dépendance vers `brique_04_detection` ni `brique_05_scoring_alertes`
  en runtime (voir section double dépendance ci-dessus).

## Commandes

```bash
# Depuis la racine du workspace
uv sync --all-packages

# Démarrer Neo4j (emplacement réservé depuis la Brique 0, activé ici)
docker compose --profile neo4j up -d
docker compose ps   # vérifier "healthy"

# Tests d'isolation — EN PREMIER, avant tout autre test
uv run pytest briques/brique_06_neo4j/tests/test_isolation_tenant.py -v

# Reste des tests
uv run pytest briques/brique_06_neo4j/tests/ -v

# Qualité
uv run ruff check briques/brique_06_neo4j
cd briques/brique_06_neo4j && uv run mypy src && cd ../..

# Synchronisation + requêtes réelles sur tenant_ne
uv run souverain-grapher --tenant tenant_ne
```

## Vérification manuelle

Via Neo4j Browser (`http://localhost:7474`) ou `cypher-shell` :

```cypher
MATCH (n:Compte) RETURN count(n);
MATCH ()-[r:ENVOIE]->() RETURN count(r);
// Vérifier qu'aucun compte_id n'existe en double pour un même tenant :
MATCH (n:Compte) RETURN n.tenant_id, n.compte_id, count(*) AS n
  ORDER BY n DESC LIMIT 5;
```

## Estimation RAM (Bloc 5, validée à l'analyse)

Configuration JVM explicite posée dans `docker-compose.yml` (jamais les
valeurs par défaut de l'image) :

```
heap.initial_size = 512m
heap.max_size = 1G
pagecache.size = 512m
```

Empreinte totale attendue : **~1,5 à 2 Go** sur 16 Go disponibles, en
cohabitation avec PostgreSQL (quelques centaines de Mo en usage léger).
À confirmer par `docker stats` au premier démarrage réel.

## Erreurs fréquentes

| Symptôme | Cause probable | Diagnostic |
|---|---|---|
| `ConnectionRefusedError` au démarrage de `souverain-grapher` | Neo4j pas démarré | `docker compose --profile neo4j up -d`, attendre `healthy` |
| `ValueError: Aucun tenant actif trouvé` | Bootstrap non joué pour ce tenant | Voir README Brique 3 |
| Deux comptes identiques mais `count(n) > 1` inattendu | Vérifier que `assurer_contraintes()` a bien tourné (`SHOW CONSTRAINTS` dans `cypher-shell`) | La contrainte composite doit exister avant tout import |
| `detecter_comptes_pont`/`chemin_le_plus_court_entre_alertes` toujours vides sur `tenant_ne` | Normal — 0 alerte ouverte actuellement (voir README Brique 5, limite du générateur) | Pas un bug, testé explicitement (`test_comptes_alertes_vide_retourne_liste_vide_sans_erreur`) |

## Dépendances avec les briques futures

- **Brique 7 (Dashboard)** : consommera les résultats des 3 requêtes
  métier via `requetes.py`, jamais directement `garde_isolation.py`.
- **Brique 8 (Audit)** : aucune dépendance identifiée à ce stade.
- **Vision** : import incrémental (voir limite MVP ci-dessus), migration
  éventuelle vers Enterprise ou instances séparées si le multi-tenant
  logique s'avère insuffisant à l'échelle UEMOA — `tenant_id` déjà posé
  partout facilite cette transition sans réécriture du modèle.
