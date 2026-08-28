# Brique 7 — Dashboard / investigation

**Statut : implémentée, en attente de validation par le fondateur.**

## Rôle

Interface FastAPI + HTMX pour consulter les alertes (Brique 5) et explorer
les motifs de réseau (Brique 6) — sans écrire de SQL ni de Cypher à la
main. **Strictement lecture seule** : aucun déclenchement de calcul
(pas de bouton "relancer la détection/le scoring/le graphe"), aucun
changement d'état d'alerte.

**Hors périmètre, documenté explicitement (pas un oubli) :**
- Audit trail immuable (Brique 8).
- Changement d'état `'ouverte' → 'fermee'` d'une alerte — appartient
  entièrement à la Brique 8 (Human-in-the-loop).
- RAG / IA locale (phase transverse).
- Notifications citoyens (ADR-001, position non tranchée).
- **Export de rapport, signé ou non, avant l'existence de la Brique
  PQC (Dilithium-5).** Le document fondateur ne demande que des
  rapports SIGNÉS comme livrable — jamais un export intermédiaire non
  signé comme fonctionnalité séparée. Construire un export non signé
  maintenant reviendrait à reconstruire deux fois la même
  fonctionnalité une fois la PQC prête.

## Multilinguisme — posé dès cette brique, pas un ajout futur

Conforme à l'ADR-001 et au point 6 de `00_DECISIONS_VERROUILLEES.md`.
`traductions/__init__.py` expose `t(cle, langue)`, enregistrée comme
fonction globale Jinja2 (`{{ t('cle') }}` dans chaque template) — **aucun
texte français écrit en dur**, même règle de rigueur que "aucun Cypher
hors `garde_isolation.py`" (Brique 6). Seul `fr.py` est livré maintenant ;
ajouter le haoussa/zarma signifie ajouter un fichier `{langue}.py`,
jamais toucher aux templates. Langue résolue depuis `country_code` du
tenant (déjà présent depuis la Brique 1, aucune migration nécessaire).

## Authentification — Option A validée à l'analyse

`brique_02_auth_rbac.session.get_current_user` attend un header
`Authorization: Bearer <token>` (`HTTPBearer`) — adapté à une API JSON,
pas à un dashboard HTMX (le navigateur n'attache pas ce header sur une
navigation normale). **Option A retenue** : `auth_cookie.py` lit le JWT
depuis un cookie `httpOnly`, en réutilisant directement les **primitives**
de la Brique 2 (`decode_token()`, `get_user_by_id()`) — jamais le wrapper
`HTTPBearer`. **Aucune modification de `brique_02_auth_rbac`, déjà
validée.**

`/login` réutilise `verify_password`/`get_user_by_email`/
`create_access_token` de la Brique 2 tels quels — la logique de
vérification elle-même n'est jamais dupliquée, seule la source du jeton
change. Protection anti-énumération : un hash factice est systématiquement
vérifié même si l'email n'existe pas, pour ne jamais laisser un
attaquant distinguer "email inconnu" de "mauvais mot de passe" par la
durée de réponse.

## Revalidation défensive du tenant — exigence explicite de l'analyse

`tenant_garde.py` : un JWT signé prouve qu'il n'a pas été modifié depuis
son émission — **pas** que le tenant qu'il désigne est toujours actif
maintenant. `tenant_valide()` revérifie `tenant_id` contre
`shared.tenants_registry` (`is_active = true`) à **chaque requête**, même
discipline défensive que `validate_schema_name()` (Brique 1). Testé
explicitement : un tenant désactivé après l'émission du jeton doit être
rejeté immédiatement (`test_tenant_garde.py`).

## Requêtes du graphe — exclusivement via `garde_isolation.py`

Aucune ligne de Cypher dans cette brique. Les routes appellent
`brique_06_neo4j.requetes` (la couche de présentation), jamais
`garde_isolation.py` directement — extension de la règle du point de
passage unique posée à l'analyse de la Brique 6 à tout futur consommateur.

## ⚠️ Point de vigilance documenté — latence du fragment graphe

Les 3 fonctions de `requetes.py` retournent leurs résultats pour **tout
le tenant**, pas filtrés par compte. **Option A validée à l'analyse** :
filtrage côté Python dans `routes/alertes.py`, aucune modification de la
Brique 6 (déjà figée). Cohérent avec deux précédents déjà actés dans ce
projet (import complet des transactions en Brique 6, recalcul complet en
Brique 4/5) : documenter la limite d'échelle plutôt qu'optimiser
prématurément sans données réelles pour le justifier.

**Différence avec les précédents, à ne pas minimiser** : Brique 4/5/6
sont des traitements **batch CLI**, où la latence importe peu. Ici, cette
même limite touche directement le **temps de réponse d'une page web
consultée par un humain qui attend**. Pas un problème au volume actuel
(quelques dizaines de résultats), mais un point à surveiller si le volume
grossit, avant de passer à l'Option B (fonctions Cypher paramétrées par
compte, modification de la Brique 6 à valider explicitement le moment
venu).

Atténuation déjà en place : la page de détail (`GET /alertes/{id}`) se
charge indépendamment du fragment graphe (`GET /alertes/{id}/graphe`,
chargé après coup via `hx-trigger="load"`) — l'utilisateur voit l'alerte
et ses détections immédiatement, avec un état de chargement
(`chargement_graphe`) pendant que le graphe retraverse.

## HTMX vendorisé localement — pas de CDN

Conforme au Bloc 5 (*"aucune donnée ne quitte le territoire national"*,
*"jamais de solution cloud étrangère"*) : `static/htmx.min.js` (v2.0.10,
~50 Ko) récupéré via le registre npm (domaine déjà autorisé) et servi
directement par FastAPI, jamais chargé depuis un CDN étranger à chaque
session.

## Dépendances — deux exceptions documentées à la convention "dupliquer plutôt que dépendre"

- **Runtime** : `brique-01-postgresql` (lecture), `brique-02-auth-rbac`
  (l'authentification ne doit jamais avoir deux sources de vérité — seule
  exception légitime à la duplication), `brique-06-neo4j` (`requetes.py`
  appelé réellement en production, pas seulement en test — différent du
  pattern Brique 5→Brique 4 qui était une dépendance de confort de test
  uniquement).
- **Tests uniquement** (dev-group) : `brique-04-detection`,
  `brique-05-scoring-alertes` — génèrent une vraie alerte via les
  fonctions déjà validées (`enregistrer_detections`, `enregistrer_scores`)
  plutôt que d'insérer des lignes SQL à la main dans les fixtures.

## ⚠️ Manque découvert, non corrigé silencieusement

La Brique 2 est la **seule** brique du projet sans `py.typed` — jamais
nécessaire jusqu'ici, personne n'en dépendait pour son typage. La
Brique 7 est la première. Corriger proprement demande de toucher **deux**
points de la Brique 2 déjà validée (fichier `py.typed` + son
enregistrement dans `artifacts` du `pyproject.toml`, même traitement que
la Brique 1 en son temps). **Non fait ici** — contournement local et
autonome dans `pyproject.toml` de la Brique 7
(`ignore_missing_imports` ciblé sur `brique_02_auth_rbac.*`), en attendant
une décision explicite du fondateur sur la vraie correction.

## Commandes

```bash
# Depuis la racine du workspace
uv sync --all-packages

# Démarrer les dépendances (PostgreSQL + Neo4j)
docker compose --profile postgres --profile neo4j up -d
docker compose ps   # attendre "healthy" sur les deux

# Tests
uv run pytest briques/brique_07_dashboard/tests/ -v

# Qualité
uv run ruff check briques/brique_07_dashboard
cd briques/brique_07_dashboard && uv run mypy src && cd ../..

# Démarrer le dashboard
uv run souverain-dashboard
# → http://localhost:8080
```

## Vérification manuelle

1. Créer un utilisateur de test via la Brique 2 (`POST /auth/...` ou
   directement en base), avec un `tenant_id` pointant vers `tenant_ne`.
2. `http://localhost:8080/login` → se connecter.
3. `/alertes` → liste (vide actuellement sur `tenant_ne`, comportement
   attendu — voir README Brique 5).
4. Ouvrir le détail d'une alerte une fois qu'il en existe une réelle
   (après recalibrage du seuil, ou données réelles en Vision) → vérifier
   que le fragment graphe se charge après la page, sans bloquer
   l'affichage.

## Erreurs fréquentes

| Symptôme | Cause probable | Diagnostic |
|---|---|---|
| Redirection immédiate vers `/login` | Cookie absent/expiré, ou tenant désactivé (voir `tenant_garde.py`) | Vérifier `shared.tenants_registry.is_active` pour ce tenant |
| `401` au login avec les bons identifiants | `is_active = false` sur l'utilisateur | Vérifier `shared.users` |
| Fragment graphe qui ne charge jamais | Neo4j non démarré | `docker compose --profile neo4j up -d` |
| Détail d'alerte lent | Volume de transactions/détections élevé — voir le point de vigilance ci-dessus | Normal au-delà d'un certain volume, pas un bug |

## Dépendances avec les briques futures

- **Brique 8 (Audit)** : portera le changement d'état des alertes,
  absent de cette brique par construction.
- **Vision** : Option B (Cypher paramétré par compte) si la latence du
  fragment graphe devient un problème réel ; py.typed pour la Brique 2 ;
  export de rapport signé une fois la PQC prête.
