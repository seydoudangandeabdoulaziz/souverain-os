# ADR-003 — Event Trigger PostgreSQL pour l'intégrité des données métier

**Statut : Acceptée**
**Date : 8 septembre 2026**
**Décideur : Seydou Dangande Abdoul Aziz (fondateur)**

## Contexte

Revue d'architecture précédant la Phase transverse (Étape 2 — Intégrité
des données métier) : `{tenant}.audit_log` (Brique 8) et
`shared.gouvernance_audit_log` (Brique 1 V2) protègent les **actions**
humaines (fermeture d'alerte, gestion de compte) par privilège
PostgreSQL réel. Elles ne protègent pas les **données** elles-mêmes —
`{tenant}.alertes` et `{tenant}.detections` ne sont accessibles en
écriture que par `souverain_admin` (propriétaire de toutes les tables),
sans aucune restriction, sans aucune trace en cas de modification
directe.

Constat vérifié avant toute conception : `souverain_admin` est
**superutilisateur** (`rolsuper = true`), et propriétaire de chaque
table du dépôt. Un propriétaire de table PostgreSQL a toujours tous les
droits sur ses propres objets, indépendamment de tout `GRANT`/`REVOKE`
— aucune protection technique ne peut empêcher `souverain_admin`
lui-même de contourner un mécanisme d'intégrité. Cette limite est
documentée explicitement, pas dissimulée : cette décision protège
contre une **modification directe non accompagnée d'une désactivation
délibérée de la protection**, pas contre un compte admin compromis.

## Problème d'implémentation découvert en cours de conception

`{tenant}.alertes` et `{tenant}.detections` n'existent pas au moment de
la création d'un tenant (`create_tenant()`, Brique 1 V2) — elles sont
créées paresseusement par Brique 4/5 (`CREATE TABLE IF NOT EXISTS`) au
premier cycle de détection/scoring. Une première approche envisagée
(créer ces tables par anticipation dans `schema_tenant_template.sql`,
Brique 1) a été écartée : elle aurait fait porter à la Brique 1 la
responsabilité de la structure exacte de tables appartenant
fonctionnellement à Brique 4/5, avec un risque réel de dérive si ces
briques font évoluer leur schéma sans que le template ne soit mis à
jour en parallèle — rompant le principe de séparation des
responsabilités déjà appliqué partout ailleurs dans le projet.

## Décision

**Event Trigger PostgreSQL** (`ddl_command_end`, filtré sur
`CREATE TABLE`) plutôt qu'une création anticipée des tables. Réagit à
la véritable création de `alertes`/`detections` par Brique 4/5, quel
que soit le moment, sans dépendre de leur structure interne (seule la
colonne de clé primaire est connue — `to_jsonb(OLD)`/`to_jsonb(NEW)`
capturent la ligne entière génériquement).

- **Portée** : tout `CREATE TABLE` du cluster déclenche l'évaluation du
  handler, mais celui-ci ne fait quelque chose que si (a) le schéma est
  enregistré dans `shared.tenants_registry`, (b) le nom de la table est
  exactement `alertes` ou `detections`.
- **Fonction transverse réutilisable** (`shared.assurer_protection_integrite()`)
  : crée la table `{schema}.integrite_donnees_log`, la fonction de
  trigger de ligne (propre à chaque schéma, jamais partagée entre
  tenants — même principe d'isolation que `garde_isolation.py`,
  Brique 6), et attache le trigger. Appelée à la fois par le handler
  de l'event trigger (futurs tenants) et par un rattrapage explicite,
  une fois, pour les tenants déjà existants au moment de cette
  migration.
- **Détection, jamais blocage** : `AFTER UPDATE OR DELETE` uniquement
  — un `INSERT` normal (fonctionnement courant de ces tables) n'est
  jamais journalisé.
- **Durcissement** : `SECURITY DEFINER` + `search_path = pg_catalog, pg_temp`
  sur toutes les fonctions concernées ; `session_user` (pas
  `current_user`, qui refléterait le propriétaire de la fonction sous
  `SECURITY DEFINER`) pour capturer le rôle réellement à l'origine de
  la modification.
- **Défensif par construction** : toute erreur interne au handler est
  journalisée (`RAISE WARNING`) et jamais propagée — un bug dans ce
  mécanisme ne doit jamais faire échouer le `CREATE TABLE` d'origine de
  Brique 4/5.
- **Anti-récursion** : le filtre sur le nom de table (`alertes`/
  `detections` uniquement) empêche par construction toute boucle — la
  création de `integrite_donnees_log` elle-même, bien que capturée par
  le même event trigger, ne correspond à aucun des deux noms filtrés.

**Aucune modification d'aucun fichier de Brique 4, 5 ou 8** — la
Brique 1 ne connaît que deux noms de table et un nom de colonne de clé
primaire chacune, jamais leur structure complète.

## Conséquences

- Premier Event Trigger du projet — mécanisme PostgreSQL jamais utilisé
  auparavant dans ce dépôt, portée cluster entier (contrainte du
  moteur, pas un choix : les event triggers n'existent qu'à ce niveau).
- **Compromis de découvrabilité assumé** : rien dans `persistence.py`
  de Brique 4/5 ne signale l'existence de cette protection — un
  lecteur de ce code n'en verra aucune trace. Compensé uniquement par
  cet ADR et `avancement.md`, jamais par un commentaire dans les
  fichiers de Brique 4/5 eux-mêmes (respect strict de la consigne
  "aucune modification de Brique 4/5/8", y compris pour un simple
  commentaire).
- Nécessite `souverain_admin` superutilisateur pour la création de
  l'event trigger — vérifié réel avant cette décision, pas supposé.
- `souverain_admin` reste techniquement capable de désactiver
  (`ALTER EVENT TRIGGER ... DISABLE`) ou supprimer ce mécanisme —
  limite structurelle documentée, pas résolue par cette étape.

## Alternatives envisagées

- **Option B — Réparation différée via CLI dédié** : écartée, pas
  automatique, dépend d'une étape manuelle après le premier cycle
  Brique 4/5, facilement oubliée.
- **Option C — Création anticipée de `alertes`/`detections` dans
  `schema_tenant_template.sql`** (Brique 1) : envisagée sérieusement,
  d'abord choisie provisoirement, puis écartée après analyse détaillée
  du risque de dérive de schéma entre le template et Brique 4/5 (voir
  section "Problème d'implémentation découvert" ci-dessus) — rompt la
  séparation des responsabilités que ce projet a systématiquement
  préservée ailleurs.
- **Row-Level Security** : écartée dès l'analyse initiale, mauvais
  outil pour un besoin de détection plutôt que de filtrage par ligne.
