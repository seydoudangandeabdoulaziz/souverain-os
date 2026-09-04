# Brique 8 — Audit trail + Human-in-the-loop

**Statut : implémentée, en attente de validation par le fondateur (tests
d'intégration non exécutés en environnement de génération — pas de
PostgreSQL disponible ici, à lancer sur la machine réelle).**

## Rôle

Permet à un humain (`analyst` ou `admin`) de **fermer une alerte**
(`{tenant}.alertes.statut : 'ouverte' → 'fermee'`) avec un motif
structuré, et enregistre cette action dans une **piste d'audit
immuable** (`{tenant}.audit_log`). Les deux seules routes d'écriture
de tout le dashboard.

**Hors périmètre, documenté explicitement (pas un oubli) :**
- `create_tenant()` / gouvernance multi-tenant complète — besoin réel
  identifié mais non positionné dans l'ordre numéroté (voir
  `06_ROADMAP_ET_BRIQUES.md`), **pas** dans cette brique malgré ce
  qu'indiquait un commentaire non corrigé de la Brique 1
  (`tenant_provisioning.py`) — voir section "Incohérence relevée"
  ci-dessous.
- Notifications citoyens — même statut.
- Réouverture d'une alerte fermée, modification du score, assignation
  d'une alerte à un analyste nommé — aucun de ces trois n'a été validé
  à l'analyse, aucun n'est implémenté.

## Décision d'architecture centrale : immuabilité par privilège PostgreSQL réel

Validé à l'analyse : la discipline applicative seule (« aucune route
ne permet de modifier `audit_log` ») ne suffisait pas. Un rôle
PostgreSQL **dédié**, `souverain_brique8_audit`, créé par
`migrations/0001_create_audit_log_table.sql`, reçoit :

| Table | Privilèges accordés | Jamais accordé |
|---|---|---|
| `{tenant}.alertes` | `SELECT`, `UPDATE` | `INSERT`, `DELETE` |
| `{tenant}.audit_log` | `INSERT`, `SELECT` | `UPDATE`, `DELETE` |
| `shared.users` | `SELECT` (affichage email) | — |

Ce rôle a besoin d'`UPDATE` sur `alertes` **et** d'`INSERT` sur
`audit_log` parce que la fermeture d'alerte et l'écriture de l'audit
sont **atomiques** (une seule transaction, une seule connexion — donc
un seul rôle). C'est l'absence d'`UPDATE`/`DELETE` sur `audit_log`
spécifiquement, et seulement là, qui constitue la garantie
d'immuabilité — testée directement
(`test_role_restreint_ne_peut_pas_modifier_l_audit_log`, attend une
`InsufficientPrivilegeError` de PostgreSQL lui-même, pas une
vérification côté application).

`souverain_admin` (Brique 1), propriétaire de toutes les tables,
contournerait n'importe quel `GRANT`/`REVOKE` sur ses propres objets —
c'est pour cette raison précise qu'un rôle séparé est nécessaire, pas
une préférence stylistique.

## Composition avec la Brique 7 — zéro fichier Brique 7 modifié en logique

Validé à l'analyse : la Brique 7 reste **fonctionnellement lecture
seule**. Cette brique ne s'y intègre pas en la rouvrant, mais via :

1. **`souverain_app/`** (nouveau module racine, validé à l'analyse) :
   assemble `creer_application()` (Brique 7, inchangée) et le routeur
   de cette brique via `include_router()`. Point d'entrée réel désormais
   : `uv run souverain-app` (remplace `souverain-dashboard` pour tout
   usage nécessitant la fermeture d'alerte — `souverain-dashboard`
   reste utilisable pour isoler un bug Brique 7 pure, sans le
   formulaire de fermeture).
2. **Un seul ajout dans `alerte_detail.html`** (Brique 7) : une div
   HTMX (`hx-get=".../fermeture"`, `hx-trigger="load"`), même pattern
   que la div `graphe-resultats` déjà en place. Aucune ligne existante
   modifiée, aucune clé de traduction Brique 7 requise (le texte du
   placeholder est un simple « … » neutre).
3. **Réutilisation directe** de `get_current_user_from_cookie` et
   `tenant_valide` (Brique 7) — jamais dupliqués une troisième fois.

## Retouche de la Brique 2 (déjà validée) — signalée et validée à l'analyse

`require_role()` était câblé en dur sur `Depends(get_current_user)`
(header `Authorization: Bearer`), inutilisable pour une route
cookie-based comme celle-ci. Ajout d'un paramètre `user_dependency`,
**valeur par défaut inchangée** (`get_current_user`) — rétrocompatible,
zéro régression (`test_rbac.py` de la Brique 2 : 3/3 passés, fichier de
test non modifié).

## RBAC — deux niveaux, pas un seul

- **Affichage du formulaire** (GET, informatif) : visible pour
  `analyst`/`admin`, masqué pour `auditor` (qui ne voit que
  l'historique).
- **Exécution de la fermeture** (POST, `require_role`) : la vraie
  barrière. Un `auditor` qui forge une requête POST directe reçoit un
  `403`, indépendamment de ce que l'UI affichait.

## CSRF — double-submit cookie

Première route d'écriture du dashboard (Brique 7 était 100% `GET`),
donc premier besoin de protection CSRF du projet. Jeton aléatoire posé
en cookie `httpOnly` à l'affichage du formulaire, revérifié
(comparaison à temps constant, `secrets.compare_digest`) à la
soumission — voir `csrf.py`.

## Anti-course réelle, pas une vérification préalable

`UPDATE {tenant}.alertes SET statut = 'fermee' ... WHERE statut =
'ouverte' RETURNING ...`, dans la même transaction que l'`INSERT`
d'audit. Si deux analystes ferment la même alerte au même instant, un
seul `UPDATE` renvoie une ligne — le second lève `AlerteNonFermable`
(traduit en `409` côté route), jamais un doublon d'audit. Testé
explicitement (`test_fermer_alerte_deja_fermee_leve_alerte_non_
fermable`, et côté HTTP `test_fermeture_deja_fermee_retourne_409`).

## Multilinguisme — mécanisme propre, pas un ajout aux clés Brique 7

Même règle non négociable que la Brique 7 (ADR-001) : aucun texte
français en dur dans un template. Plutôt que d'ajouter des clés au
dictionnaire `fr.py` de la Brique 7 (un fichier déjà validé), cette
brique porte son propre petit mécanisme isolé
(`traductions/__init__.py`, `traductions/fr.py`), et sa propre instance
`Jinja2Templates` (construite dans `routes.py`, pas partagée avec la
Brique 7 — celle-ci n'expose de toute façon pas la sienne hors de
`creer_application()`).

## Bug trouvé et corrigé avant tout run (pas une correction de validation locale)

En vérifiant l'assemblage de l'application, un `router = APIRouter()`
déclaré au niveau module (mon propre code) s'accumulait à chaque appel
de `construire_routes_audit()` dans le même process Python — chaque
test reconstruisant l'app aurait ré-enregistré les mêmes routes sur le
même routeur partagé. Corrigé en déplaçant la construction du routeur
**à l'intérieur** de la fonction (vérifié : deux appels successifs de
`creer_application_complete()` ne produisent plus aucun doublon de
route).

**Incohérence relevée dans le dépôt, signalée, pas corrigée
silencieusement** : `brique_01_postgresql/tenant_provisioning.py`
contient encore un commentaire affirmant que `create_tenant()`
« appartient à la Brique 8 » — cette affirmation date d'avant la
correction du 28 août 2026 (`06_ROADMAP_ET_BRIQUES.md`), qui a
explicitement retiré `create_tenant()` du périmètre de cette brique.
Le commentaire n'a jamais été mis à jour en conséquence. Aucune ligne
de `tenant_provisioning.py` n'a été modifiée par cette brique — la
dérive documentaire reste à corriger par une décision explicite du
fondateur, pas ici.

## Livré

- `config.py` (identifiants du rôle DB dédié), `connection.py` (pool
  restreint, distinct du pool admin Brique 1), `modeles.py`
  (`MotifFermeture`, `EntreeAudit`, `AlerteNonFermable`),
  `persistence.py` (fermeture + audit atomiques, auto-réparation via
  le pool admin), `lecture.py` (historique, jointure `shared.users`
  pour affichage email), `csrf.py`, `routes.py` (2 routes, instance
  Jinja2Templates propre), `traductions/` (`t()`, `fr.py`),
  `templates/fermeture_fragment.html`.
- `migrations/0001_create_audit_log_table.sql` — rôle dédié + table +
  grants par tenant déjà enregistré.
- `souverain_app/` (nouveau module racine) — assemblage FastAPI
  Brique 7 + Brique 8, `uv run souverain-app`.
- 15 tests : `test_csrf.py` (4, sans DB — **4/4 exécutés et passés en
  environnement de génération**), `test_persistence.py` (5, intégration
  — dont le test de privilège PostgreSQL réel), `test_routes.py` (6,
  HTTP de bout en bout via `httpx.AsyncClient` + `ASGITransport`, jamais
  `TestClient`).

## Vérifié en environnement de génération (dépôt réel cloné)

- `uv sync --all-packages` — Brique 8 et `souverain_app` ajoutés au
  workspace, résolution propre.
- Import de tous les modules + assemblage complet de l'application —
  sans erreur.
- `uv run ruff check briques/brique_08_audit_human_loop souverain_app` —
  All checks passed.
- `uv run mypy src` (Brique 8, `souverain_app`) — Success, no issues
  found.
- Non-régression **stricte** de `test_rbac.py` (Brique 2) après la
  retouche : **3/3 passés**, fichier de test inchangé.
- Non-régression mypy de la Brique 7 après l'ajout de la div HTMX dans
  `alerte_detail.html` : Success, no issues found (13 fichiers).
- `pytest --collect-only` sur la Brique 8 — 15 tests collectés sans
  erreur de câblage (fixtures, imports).
- `pytest tests/test_csrf.py` — **4/4 passés**.
- `pytest` sur l'ensemble du workspace (Briques 0 à 8) — **81 passed,
  9 skipped, 48 errors**, toutes les erreurs étant des
  `ConnectionRefusedError` sur `localhost:5432` (pas de conteneur
  Docker dans cet environnement) — même limite déjà documentée pour
  chaque brique précédente, rien d'imputable à la Brique 8.

## Reste à vérifier sur la machine réelle avant validation

1. `docker compose --profile postgres up -d`
2. Appliquer `migrations/0001_create_audit_log_table.sql`
3. Vérifier `AUDIT_DB_PASSWORD` dans le `.env` réel (défaut
   `change_me_audit` à changer, même règle que `NEO4J_PASSWORD`)
4. `uv run pytest` — 15/15 tests Brique 8 attendus, en particulier
   `test_role_restreint_ne_peut_pas_modifier_l_audit_log` (la preuve
   concrète du privilège PostgreSQL réel)
5. Vérification manuelle dans un vrai navigateur (`uv run
   souverain-app`) : fermeture d'une alerte de démo, historique
   affiché, tentative de double fermeture → 409, rôle `auditor` ne
   voit pas le formulaire.
