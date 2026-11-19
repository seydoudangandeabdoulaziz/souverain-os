# API d'ingestion/scoring — périmètre d'implémentation (v2)

**Statut : EN IMPLÉMENTATION — périmètre validé par le fondateur (décisions D1 à D3, option 2 pour D3b, conditions du 14 novembre 2026). Cycle incrémental NON VALIDÉ** tant que les tests différentiels et les mesures sur la machine du fondateur ne sont pas concluants. Version v3, établie sur le code réel (HEAD `dac6589`). Chantier transverse **hors de l'ordre numéroté**.

Contraintes confirmées : aucune modification des Briques 1 à 8, décisions historiques intactes, étapes 10 à 12 non commencées, aucun commit ni push sans autorisation.

## 1. Objectif

Permettre à une **identité technique** liée à un tenant d'envoyer des transactions par HTTP puis de déclencher détection et scoring sur ses données, sans passer par les CLI de développement. Les alertes alimentent le dashboard (B7) et la fermeture humaine (B8), inchangés.

## 2. Contradictions et limites à connaître

1. **« CLI uniquement » (B3, B4, B5)** : cette API en est l'inversion assumée ; elle **réutilise** ces briques sans les modifier.
2. **Document fondateur, Bloc 10 (`POST /score/transaction`, < 5 s)** : non livré. Le moteur B4 est séquentiel à fenêtres glissantes : on ingère un lot, puis on lance un cycle. Le verdict par transaction reste une **Vision**.
3. **Aucune alerte réelle garantie** : limite du générateur B3 (Brique 5), traitée par un chantier distinct d'évaluation de la détection.
4. **Rôles PostgreSQL du P0 : ensemble fermé.** `role_name_for_tenant()` n'accepte que `data` et `audit`, et `shared.tenant_login_map.purpose` porte un `CHECK (purpose IN ('data','audit'))`. Un rôle PostgreSQL dédié à l'API par tenant **exige donc d'étendre B1** — voir D3b, décision réservée au fondateur.
5. **Le rôle `data` existant est large** : `CREATE` sur son schéma, `SELECT/INSERT/UPDATE` sur toutes ses tables et sur `shared.users` (limité à son tenant par RLS). Le réutiliser tel quel pour l'API est possible mais pas « minimal » au niveau base de données.
6. **Transport** : ni TLS ni PQC dans le dépôt (étape 11). L'API vise `127.0.0.1` / réseau privé derrière un terminateur TLS ; exposition réseau hors de ce chantier.
7. **`py.typed` de la Brique 2** : décision pendante inchangée (contournement mypy local).

## 3. Mesures (réponse à la réserve sur le recalcul complet)

Banc d'essai : `bench_cycle_b4.py` (fourni, à rejouer sur ta machine). Il exécute le **vrai moteur B4** et les générateurs de patterns B3 sans les modifier. **Pas de base de données** : le coût SQL/réseau n'est pas mesuré ici. Environnement : bac à sable à 1 vCPU, pas le ThinkPad : valeurs **indicatives**, à confirmer sur ta machine.

**Recalcul complet de l'historique (tri + moteur B4), un cycle :**

| Transactions | Durée | RSS max (harnais inclus, borne haute) |
|---|---|---|
| 52 150 | 0,74 s | 147 Mo |
| 208 600 | 3,96 s | 514 Mo |
| 521 500 | 10,82 s | 1 123 Mo |
| 1 043 000 | 24,23 s | 1 873 Mo |

Le coût est linéaire : **recalculer tout à chaque cycle est donc écarté** (24 s et près de 2 Go de pic par cycle à 1 M de transactions, avant toute lecture SQL).

**Cycle incrémental par compte** (lots de 1 000 transactions, cycles successifs, résultat comparé au recalcul complet sur le même jeu) :

| Jeu | Cycles | Cycle moyen / p95 / max | Transactions relues par cycle (moy.) | Résultat vs recalcul complet |
|---|---|---|---|---|
| 52 k, ordre chronologique | 53 | 28 / 75 / 101 ms | 2 256 | **identique** (0 manquant, 0 en trop) |
| 209 k, ordre chronologique | 209 | 18 / 20 / 208 ms | 1 383 | **identique** |
| 522 k, ordre chronologique | 522 | 18 / 21 / 485 ms | 1 194 | **identique** (4 802 détections) |
| 52 k, 5 % d'arrivées en retard | 53 | 27 / 65 / 96 ms | 2 275 | 0 manquant ; 34 clés exactes en trop (7 %) |
| 209 k, 5 % d'arrivées en retard | 209 | 20 / 21 / 245 ms | 1 397 | 0 manquant ; 114 clés exactes en trop (6 %) |

- Le coût d'un cycle **ne dépend pas du volume stocké** (≈ 18 ms pour 1 000 transactions à 209 k comme à 522 k) : environ 590 fois moins de calcul que le recalcul complet à 522 k.
- Avec des arrivées en retard, **aucune détection n'est perdue**. Les clés en trop sont des détections émises sur un historique partiel dont la fenêtre diffère ensuite de celle du recalcul complet. Avec la politique de dédoublonnage par **chevauchement** (§4, D2), le résultat sur ces deux jeux est : 0 épisode manquant, 0 ligne sans épisode correspondant, autant de lignes que le recalcul complet (492 et 1 925).
- **Limite mesurée** : pour des comptes très actifs (jeu de 31 k transactions sur 300 comptes), un cycle relit en moyenne 51 % de l'historique (15 881 sur 31 290) et dure 145 ms en moyenne : l'avantage disparaît quand l'activité est continue. Un essai plus gros (100 k transactions, 300 comptes) n'a pas abouti dans le bac à sable : **non mesuré**. Les comptes réels de type agent ou marchand pourraient se comporter ainsi : à mesurer sur données réalistes avant toute mise en production.

## 4. Décisions

### D1 — Idempotence (validée, précisée)

- `external_id` obligatoire (texte ≤ 128) et **`source` d'ingestion**. Unicité **`(source, external_id)` par tenant** : `{tenant}.ingestion_keys(source, external_id, transaction_id, seq BIGINT IDENTITY, ingested_at)`, clé primaire `(source, external_id)`.
- `source` n'est **jamais** fournie par le corps : elle est liée à l'identité technique (§D3), donc un client ne peut pas se faire passer pour une autre source.
- Insertion `ON CONFLICT DO NOTHING` **dans la même transaction SQL** que les transactions. Un rejeu ne crée aucun doublon ; la réponse distingue `insérées` et `doublons_ignorés`.
- Un même `external_id` rejoué avec un contenu différent est signalé (`conflit`, 409 pour ce lot) et non écrasé : la table conserve une empreinte du contenu.

### D2 — Détection sans doublon ni recalcul global (corrigée)

Principe, vérifié sur le code de B4 : chaque règle garde son état **par compte pivot** (étoile et nocturne par émetteur ; pivot par réception/redistribution du compte ; micro-fractionnement par paire dont l'émetteur est le pivot ; flux frontalier sans état). Un événement pour un compte X ne dépend donc que des transactions où X est émetteur ou destinataire.

Cycle, par compte touché :
1. **Curseur** : `{tenant}.pipeline_cursor` (une ligne : dernier `seq` traité). Le cycle lit les nouvelles lignes d'`ingestion_keys` au-dessus du curseur.
2. **Comptes touchés** = émetteurs et destinataires de ces transactions.
3. **Relecture par épisode** : pour chaque compte touché, lecture de son historique depuis le début de son épisode d'activité (remontée tant que l'écart entre deux transactions consécutives du compte est ≤ 6 h, la plus grande fenêtre des règles). Au-delà d'un trou de 6 h, toutes les fenêtres sont vides : l'état de départ est exactement celui du recalcul complet. Si l'épisode remonte trop loin (plus de 500 transactions), repli **explicite et compté** : le compte est relu en entier (exactitude conservée, coût plus élevé).
4. **Moteur B4 inchangé** sur ce sous-ensemble trié, puis **filtre** : seuls les événements dont `compte_pivot` est un compte touché sont gardés (les autres reposent sur un historique partiel).
5. **Dédoublonnage par chevauchement** : un événement est nouveau s'il n'existe pas déjà une détection de même `(pattern_type, compte_pivot)` dont l'intervalle `[fenetre_debut, fenetre_fin]` le chevauche. Cette règle remplace une clé exacte, qui produit des doublons dès qu'une transaction arrive en retard (§3).
6. **Atomicité** : détections nouvelles et avance du curseur dans **la même transaction SQL** ; un cycle interrompu puis rejoué ne duplique rien.
7. Le scoring **B5 est appelé tel quel** après la détection (idempotent par UPSERT ; 0,59 s à 50 000 transactions à l'étape 5).

Conséquences assumées : une détection déjà stockée garde ses bornes de fenêtre d'origine même si une arrivée tardive les aurait légèrement décalées (donnée informative, le score déduplique par type de pattern et par compte) ; une transaction arrivée très en retard est traitée au prochain cycle sans perte.

**Critères d'acceptation mesurés sur PostgreSQL réel** (seuils proposés, à confirmer par la mesure et à valider) :
- **Test différentiel** : sur des jeux synthétiques (ordre chronologique, 5 % de retards, comptes très actifs), le cycle incrémental redonne **0 détection manquante** et **0 ligne sans épisode correspondant** face au recalcul complet.
- Cycle d'un lot de 1 000 transactions, tenant à 50 k puis 500 k transactions : p95 ≤ 2 s, **sans croissance notable avec le volume**.
- Pic mémoire du cycle ≤ 300 Mo ; ingestion d'un lot de 1 000 : p95 ≤ 1 s.
- Index composites `(sender_account, occurred_at)` et `(receiver_account, occurred_at)` ajoutés par la migration de la nouvelle brique (B1 ne les fournit pas), leur effet mesuré.

### D3 — Identité technique dédiée (corrigée)

**D3a — Identité applicative (retenue d'office).**
- Table `shared.api_clients` (migration de la nouvelle brique) : `client_id`, `tenant_id` (FK registre, `ON DELETE RESTRICT`), `source_code` (unique par tenant), `secret_hash` (Argon2id, primitives B2 réutilisées sans modification), `scopes` (liste fermée : `ingest`, `cycle`), `is_active`, `expires_at`, `secret_version`, dates de création/rotation. **Absente de `shared.users`** : aucun rôle humain, pas de connexion au dashboard, aucun accès aux routes B7/B8/gouvernance.
- Authentification : `POST /api/v1/auth/token` avec `tenant_code`, `client_id`, `client_secret` (même schéma que le login B2) → jeton court (15 min) portant `typ=service`, `scope`, `tenant_id`, `sub=client_id`, `aud` dédié, signé avec **une clé distincte** de celle des jetons humains. Un jeton humain est refusé par l'API et un jeton technique par B2/B7/B8 (test dédié).
- Permissions minimales : `ingest` autorise uniquement `POST /transactions` ; `cycle` uniquement `POST /pipeline/cycle`. Aucune lecture d'utilisateurs, d'alertes ni d'audit, aucune écriture hors de ses tables.
- Cycle de vie : création, rotation (le secret n'est affiché qu'une fois, jamais journalisé) et révocation par **CLI opérateur** (`souverain-api-client-*`), pas par interface web en MVP. Révocation immédiate : `secret_version` et `is_active` revérifiés à chaque requête ; tenant désactivé ⇒ refus.
- Protection du point d'entrée : limitation des échecs d'authentification par client et par adresse, réponse identique pour client inconnu / secret faux.
- Journal d'événements insert-only (`shared.api_client_events`) : création, rotation, révocation (opérations de l'opérateur). **Écart par rapport à la v2 :** les échecs d'authentification ne sont pas écrits en base (le rôle `pipeline` n'a volontairement aucun droit d'écriture sur cette table) ; ils sont journalisés en JSON applicatif, sans secret, compte ni corps de requête.

**D3b — Niveau base de données : option 2 retenue par le fondateur (14 novembre 2026) et implémentée.** Rappel des options :
- **Option 1 (par défaut, sans toucher B1)** : l'API utilise le pool du rôle `data` du tenant (compatible P0 : isolation par rôle et ACL de schéma). Limite : ce rôle est plus large que nécessaire (voir §2 point 5) ; la minimalité est portée par le code et les scopes seulement.
- **Option 2 (recommandée comme cible)** : étendre B1 de façon **additive** (nouvelle migration `0009` + `purpose='pipeline'` dans `role_name_for_tenant` et le `CHECK`), pour un rôle `sov_p_<tenant>` limité à `INSERT/SELECT` sur `transactions`, `ingestion_keys`, `detections`, `SELECT/INSERT/UPDATE` sur `pipeline_cursor` et `SELECT/INSERT/UPDATE` sur `alertes` (nécessaire au scoring B5) — sans `CREATE`, sans accès à `shared.users`, `NOLOGIN` jusqu'au provisionnement explicite comme le P0. Cela **modifie B1** : réservé à ton accord explicite.

## 5. Périmètre MVP

**Nouveau paquet** `briques/brique_09_api_pipeline/` (membre du workspace uv, lockfile propre, `py.typed`). *« Brique 9 » désigne le prochain paquet fonctionnel, sans rapport avec l'« étape 9 » (Redis/Celery, non requise).* Branchement dans `souverain_app/main.py` par un `include_router()` additif.

| Méthode | Route | Scope | Effet |
|---|---|---|---|
| POST | `/api/v1/auth/token` | — | Échange `tenant_code` + `client_id` + `client_secret` contre un jeton court. |
| POST | `/api/v1/transactions` | `ingest` | Ingère un lot (≤ 1 000). Réponse : `reçues / insérées / doublons_ignorés / conflits`. |
| POST | `/api/v1/pipeline/cycle` | `cycle` | Cycle incrémental D2 puis B5. Réponse : comptes touchés, transactions relues, détections nouvelles, comptes scorés, alertes créées/mises à jour, replis d'épisode. |

**Schéma d'une transaction** (Pydantic v2, `extra="forbid"`) : `external_id`, `amount` (> 0, plafond configurable), `currency` (`XOF`), `sender_account`, `receiver_account` (formats bornés, différents), `channel` (liste fermée), `occurred_at` (avec fuseau, pas dans le futur au-delà d'une tolérance). Jamais dans le corps : `tenant_id`, `country_code`, `data_classification`, `is_synthetic`, `source`.

**Sécurité** : tenant uniquement issu du jeton et revérifié actif ; aucun cookie accepté (pas de surface CSRF) ; un cycle à la fois par tenant (409, mono-processus, comme D7) ; corps et lots bornés ; journal JSON sans compte, montant ni corps ; erreurs génériques ; textes via `t()` (ADR-001).

**Hors périmètre** : verdict synchrone par transaction ; administration des identités par interface web ; multi-tenant par jeton ; flux continu ; file de tâches (étape 9 non requise) ; journal d'audit durable des lots ; TLS/PQC ; lecture des alertes par API ; modification de B3 à B8 (et de B1 sauf D3b option 2, sur accord).

## 6. Tests prévus

- **Unitaires** : schéma, bornes, formats, empreinte de contenu.
- **Intégration PostgreSQL réel (tenants éphémères)** :
  - isolation : un jeton du tenant A n'écrit rien chez B ; un `tenant_id` ou `source` dans le corps est refusé ;
  - identité technique : jeton humain refusé par l'API, jeton technique refusé par B2/B7/B8 ; scope `ingest` ne peut pas lancer un cycle et inversement ; secret révoqué, expiré, ancienne `secret_version`, tenant désactivé : refus immédiat ; aucun secret dans les journaux ; limitation des échecs ;
  - idempotence : lot rejoué → 0 insertion ; même `external_id` avec contenu différent → conflit signalé ; même `external_id` pour deux `source` : accepté ;
  - cycle : test différentiel face au recalcul complet (ordre chronologique, retards, comptes très actifs) ; cycle rejoué ou interrompu après détection mais avant curseur → aucun doublon ;
  - concurrence : deux cycles simultanés → un seul passe (409) ;
  - privilèges : l'identité d'accès base ne peut ni `DELETE` ni créer d'objet (option 2), ou limites documentées (option 1).
- **Non-régression** : suite complète B0–B8, RAG, `souverain_app` ; Ruff, mypy.
- **Mesures** : critères du §4 D2 sur PostgreSQL réel, consignés dans `avancement.md`.

## 7. Structure de fichiers proposée

```text
briques/brique_09_api_pipeline/
├── pyproject.toml  README.md
├── migrations/
│   ├── 0001_create_ingestion_keys_and_cursor.sql    (par tenant)
│   ├── 0002_create_api_clients.sql                  (shared)
│   └── 0003_transactions_account_time_indexes.sql   (par tenant)
├── src/brique_09_api_pipeline/
│   ├── schemas.py  identites.py  jetons.py  auth.py
│   ├── ingestion.py  cycle.py  episodes.py  verrou.py
│   ├── cli.py  routes.py  traductions/
│   └── py.typed
└── tests/
```

## 8. Ordre d'implémentation après validation

1. Décision D3b ; migrations et tests de privilèges.
2. `schemas.py`, `ingestion.py` + tests d'idempotence et d'isolation.
3. `episodes.py`, `cycle.py` + test différentiel et mesures sur PostgreSQL.
4. `identites.py`, `jetons.py`, `auth.py`, CLI + tests de l'identité technique.
5. `verrou.py`, `routes.py` + tests HTTP (`httpx.AsyncClient` + `ASGITransport`).
6. Branchement dans `souverain_app`, documentation (`README`, `ARCHITECTURE`, `avancement.md`).

Aucune migration sur la base principale sans autorisation explicite du fondateur.

## 9. État d'implémentation et résultats (bac à sable, PostgreSQL 16 + TimescaleDB 2.17.2 réels)

**Livré (local, non commité)** : extension additive de B1 (rôle `pipeline`, migration `0009`, option `--with-pipeline`) ; paquet `briques/brique_09_api_pipeline/` ; câblage additif dans `souverain_app` (un `include_router`) ; `tests/` et `benchmarks/bench_pg.py`. Aucune migration appliquée sur la base principale.

**Tests exécutés** : B1 `test_pipeline_role.py` 14/14 + `test_tenant_isolation.py` (P0, inchangé) 4/4 ; B9 58/58 (unitaires, ingestion, cycle différentiel, API/identité technique) ; Ruff et mypy propres sur B1 (src) et B9. **Non exécutés ici** : les autres tests de B1 à B8, RAG et `souverain_app` (leurs dépendances ou bases ne sont pas disponibles dans ce bac à sable) et toute exécution sur la base principale.

**Validité des tests (mutations volontaires)** : portée ignorée, version de secret ignorée, hash de conflit ignoré, écart d'épisode réduit, dédoublonnage désactivé → tous détectés. Une première version de la comparaison masquait les doublons (comparaison par ensembles) ; corrigée. **Une mutation survit** : retirer le filtre « comptes touchés » ne change aucun résultat testé (garde de cohérence, non prouvée utile par les jeux actuels).

**Défaut trouvé par la mesure, corrigé** : la relecture d'historique parcourait tous les chunks de l'hypertable ; le coût du cycle croissait avec l'étendue des données (1,28 s à 576 k transactions pour ~1 300 relues). Une borne basse globale constante rend l'exclusion de chunks possible : 0,22 s sur la même base.

**Mesures (sandbox 1 vCPU, bruit de mesure d'environ ±50 % entre deux passages ; à rejouer sur le ThinkPad)** — lot de 1 000, 20 itérations en régime établi, seuils : cycle p95 ≤ 2 s, ingestion p95 ≤ 1 s, pic mémoire Python d'un cycle ≤ 300 Mo :

| Scénario | Stocké | Cycle p50 / p95 / max | Relues (moy.) | Ingestion p95 | Mémoire cycle | Seuils |
|---|---|---|---|---|---|---|
| 5 000 comptes, activité dense | 77 k | 0,95 / 1,32 / 2,81 s | 24 619 | 0,12 s | 25 Mo | atteints |
| 20 000 comptes | 244 k | 0,35 / 0,53 / 0,77 s | 2 160 | 0,14 s | 6 Mo | atteints |
| 50 000 comptes | 576 k | 0,24 / 0,67 / 1,01 s | 1 399 | 0,10 s | 12 Mo | atteints |
| **300 comptes très actifs, exact** | 77 k | 2,82 / **3,39** / 10,3 s | 61 807 | 0,13 s | 63 Mo | **cycle p95 NON atteint** |
| 300 comptes, plafond 24 h | 77 k | 1,58 / 2,02 / 5,36 s | 35 975 | 0,17 s | 33 Mo | cycle p95 NON atteint (2,016 s) |
| 300 comptes, plafond 12 h | 77 k | 0,74 / 0,82 / 2,79 s | 9 665 | 0,13 s | 11 Mo | atteints |

(Le scénario « 300 comptes » correspond à une transaction toutes les ~17 minutes par compte, en continu : volontairement extrême.)

**Qualité du plafond d'épisode** (6 000 transactions, 40 comptes, comparaison au recalcul complet) :

| Retards | Plafond | Lignes référence | Lignes stockées | Épisodes manquants | Doublons | Lignes sans épisode |
|---|---|---|---|---|---|---|
| 0 % | exact | 939 | 939 (identique) | 0 | 0 | 0 |
| 0 % | 24 h | 940 | 1 130 | 0 | 0 | 0 |
| 0 % | 12 h | 940 | 1 225 | 0 | 0 | 0 |
| 5 % | exact | 940 | 1 052 | 0 | 0 | 0 |
| 5 % | 12 h | 939 | 1 191 | 0 | 0 | 0 |

Aucun épisode n'est jamais perdu et aucune ligne n'est orpheline. En revanche, dans ce scénario extrême, les « lignes en trop » (épisodes de la référence réenregistrés avec d'autres bornes) atteignent environ 12 % en mode exact avec 5 % de retards, et 20 à 30 % avec un plafond de 24 h ou 12 h. Elles n'altèrent pas le score (B5 compte un type de pattern une fois par compte).

**Conclusion honnête.**
- Atteint dans les scénarios « raisonnables » : coût de cycle indépendant du volume stocké après correction, ingestion et mémoire très en deçà des seuils.
- **Non atteint** : cycle p95 ≤ 2 s en mode exact pour des comptes à activité continue (3,4 s). Avec B4 inchangé, un état d'épisode ne peut pas être reconstitué sans rejouer l'épisode.
- **Décision à prendre par le fondateur** (le plafond est désactivé par défaut = mode exact, variable `SOUVERAIN_API_EPISODE_MAX_HEURES`) : accepter le plafond (coût borné, jusqu'à ~30 % de lignes de détection supplémentaires dans le cas extrême) ; ou garder le mode exact et accepter un cycle plus long pour ces comptes ; ou autoriser plus tard une évolution de B4 exposant l'état des fenêtres.
- **Le cycle incrémental n'est pas déclaré validé** : mesures à rejouer sur la machine du fondateur avec les volumes 50 k, 200 k, 500 k et le scénario de comptes très actifs (`benchmarks/bench_pg.py`), puis décision.

### 9 bis. Mesures sur la machine du fondateur (ThinkPad X1 Carbon, base jetable en conteneur, 16 novembre 2026)

Version optimisée de `cycle.py` (lecture par tranches), 60 tests réussis sur cette machine. Lot de 1 000, 20 itérations en régime établi, mêmes seuils (cycle p95 ≤ 2 s, ingestion p95 ≤ 1 s, mémoire ≤ 300 Mo).

| Scénario | Stocké | Cycle p50 / p95 / max | Relues (moy.) | Ingestion p95 | Seuils |
|---|---|---|---|---|---|
| 5 000 comptes, dense (passage 1) | 77 k | 0,93 / 1,09 / 2,86 s | 24 619 | 0,36 s | atteints |
| idem (passage 2) | 77 k | 1,02 / 1,33 / 3,41 s | 24 619 | 0,41 s | atteints |
| idem (passage 3) | 77 k | 1,03 / 1,31 / 3,26 s | 24 619 | 0,43 s | atteints |
| 20 000 comptes | 244 k | 0,23 / 0,66 / 0,94 s | 2 160 | 0,40 s | atteints |
| 50 000 comptes | 576 k | 0,26 / 0,80 / 1,67 s | 1 399 | 0,34 s | atteints |
| **Mixte : 30 agents (15 % des tx) + 20 000 comptes, exact** | 77 k | 0,76 / 0,82 / 2,49 s | 11 704 | 0,46 s | atteints |
| **300 comptes très actifs, exact** | 77 k | 4,78 / **5,41** / 14,25 s | 61 807 | 0,41 s | **cycle NON atteint** |
| 300 comptes, plafond 12 h | 77 k | 3,02 / **3,44** / 5,05 s | 9 665 | 0,47 s | **cycle NON atteint** |

- **Répétabilité** : trois passages du scénario dense donnent un cycle p95 entre 1,09 et 1,33 s. Une première mesure à 3,76 s, prise avec un load average de 3,2 et un gouverneur `powersave`, est donc attribuable à l'état de la machine et non au code.
- **Disque** : 200 validations séparées en 533 ms (≈ 2,7 ms chacune).
- **Scénario « 300 comptes » : ventilation du cycle exact** : chargement de l'historique 1,65 s, moteur B4 0,83 s, **scoring B5 2,42 s**. B5 (inchangé) ouvre une transaction par alerte et réécrit chaque alerte ouverte à chaque cycle (fenêtre glissante, `updated_at`), soit environ 8 ms par alerte sur cette machine (1 ms dans le bac à sable : écart attribué aux validations disque et au processeur, non démontré). Ce coût dépend du **nombre d'alertes ouvertes**, pas du volume de transactions ; il n'a jamais été éprouvé à grande échelle (le générateur ne produit presque aucune alerte).
- **Plafond d'épisode** : il règle le chargement et le moteur (0,33 s) mais pas le scoring, et il multiplie les lignes de détection : 10 957 contre 4 661 en mode exact dans ce scénario (+135 %), sans épisode perdu.
- **Scénario mixte** : 30 agents très actifs portant 15 % des transactions parmi 20 000 comptes ordinaires. Sur la machine du fondateur, en mode exact : cycle p95 0,82 s (seuil 2 s), mémoire 13 Mo, 1 844 détections (identique au bac à sable : jeu déterministe). Dans le bac à sable, le plafond 12 h donnait p95 0,35 s mais 2 713 détections (+47 %).

**Lecture.** Les seuils sont atteints pour tous les volumes testés (77 k à 576 k), pour le scénario dense et pour le scénario mixte (agents très actifs parmi des comptes ordinaires). Ils ne le sont pas lorsque **tous** les comptes sont à activité continue, scénario volontairement extrême. Le mode exact est conservé par défaut ; le plafond coûte entre +47 % et +135 % de lignes de détection et ne règle pas le scoring.

**Statut : PRÊT POUR LA VALIDATION DU FONDATEUR, AVEC RÉSERVES — non validé.** Tests différentiels concluants (aucun épisode manquant, aucune ligne orpheline, aucun doublon ; lignes supplémentaires dues aux arrivées tardives, jusqu'à environ 12 % dans le scénario le plus défavorable) ; mesures PostgreSQL concluantes sauf scénario « tous comptes très actifs ». Réserves à lever ou à accepter explicitement :
1. scénario « tous comptes très actifs » hors seuil (cycle p95 5,41 s) : limite documentée du mode exact, B4 inchangé ;
2. coût du scoring B5 proportionnel au nombre d'alertes ouvertes (≈ 8 ms par alerte sur la machine du fondateur), non éprouvé à grande échelle : toute solution modifie B5 ;
3. lignes de détection supplémentaires lorsqu'une arrivée tardive relie deux salves d'activité (preuves immuables, score inchangé) ;
4. ne pas mélanger la CLI B4 et l'API sur un même tenant ;
5. garde « comptes touchés » du cycle non prouvée utile par les jeux de test (mutation survivante) ;
6. suites B1 à B8, RAG et démarrage de `souverain_app` avec le nouveau routeur non rejoués sur la machine du fondateur ;
7. aucune migration appliquée sur la base principale (sauvegarde vérifiée, inventaire des rôles et autorisation requis) ; TLS et exposition réseau hors périmètre.
