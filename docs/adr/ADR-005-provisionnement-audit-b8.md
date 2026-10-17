# ADR-005 — Provisionnement de l'audit B8 par commande explicite

**Statut : Proposée (Proposed) — critères techniques remplis le 17 octobre
2026 ; passe à « Acceptée » sur validation explicite du fondateur.**
Implémentation validée par 203/203 tests sur la machine du fondateur
(voir « Critère de passage » et « Annexe »).
**Date : 17 octobre 2026**
**Décideur : Seydou Dangande Abdoul Aziz (fondateur)**

## Contexte

La Brique 8 (audit trail + Human-in-the-loop, validée le 4 septembre
2026) repose sur un rôle PostgreSQL dédié, `souverain_brique8_audit`,
et sur une table `{tenant}.audit_log` dont l'immuabilité est garantie
par privilège réel : `INSERT` et `SELECT` uniquement, jamais `UPDATE`
ni `DELETE`.

Lors de la vérification manuelle du 29-30 septembre 2026, la page de
détail d'une alerte a renvoyé une erreur HTTP 500 sur un tenant créé
après l'application de la migration B8. Le défaut a été contourné
manuellement pour ce test, sans modification de code, et reste ouvert
(voir `avancement.md`).

## Constat vérifié dans le code (branche `main`, HEAD `6a08bf9`)

1. **Le provisionnement B8 n'existe que dans la migration 0001.** Elle
   boucle sur les tenants enregistrés *au moment de son exécution*
   (`shared.tenants_registry`) et leur accorde `USAGE` sur le schéma,
   `SELECT, UPDATE` sur `alertes` et `INSERT, SELECT` sur `audit_log`.
2. **`create_tenant()` (Brique 1) ne connaît pas B8.** Signature :
   `create_tenant(connexion, *, tenant_code, country_code, schema_name,
   data_classification, acteur_declare) -> UUID`. Elle enregistre le
   tenant, provisionne le schéma et écrit l'audit de gouvernance dans
   une seule transaction, via le pool `souverain_gouvernance_cli`. Un
   tenant ainsi créé n'a donc ni `audit_log`, ni aucun privilège pour le
   rôle B8.
3. **`alertes` n'existe pas à la création du tenant.** Elle est créée
   paresseusement par la Brique 5 (même constat que l'ADR-003). Aucun
   provisionnement à la création ne peut accorder de privilège sur une
   table qui n'existe pas encore.
4. **Lecture** (`lecture.py`) : seule `UndefinedTableError` est
   interceptée (et renvoie une liste vide). Sans `USAGE` sur le schéma,
   PostgreSQL lève `InsufficientPrivilegeError` avant même de vérifier
   l'existence de la table : l'erreur n'est pas interceptée.
5. **Écriture** (`persistence.py`) : `fermer_alerte_avec_audit()` ne
   déclenche la réparation (`_assurer_table_audit_log()`, pool admin)
   que sur `UndefinedTableError`, et en déduit que la table absente est
   « forcément » `audit_log` après avoir vérifié `alertes`
   (`_table_alertes_existe()`). Le même défaut de privilège y produit
   une erreur brute, sans réparation.
6. **La fixture de test masque le défaut** : `tenant_provisionne`
   (`tests/conftest.py`) accorde `USAGE` à la main, de sorte que la
   situation d'un tenant réellement neuf n'est jamais exercée.
7. **Défaut annexe suspecté dans la migration 0001** : son `GRANT ...
   ON {tenant}.alertes` n'est pas gardé et pourrait échouer si un
   tenant enregistré n'a pas encore de table `alertes`. *Lu dans le
   SQL, non reproduit, non évalué (impact sur les bases existantes
   inconnu).* Hors périmètre de cet ADR, voir plus bas.

## Hypothèses techniques à confirmer (H1 à H7)

Rien de ce qui suit n'est encore prouvé. Chaque hypothèse est reliée à
un test de caractérisation (section « Tests de caractérisation »).

| # | Hypothèse | Test |
|---|---|---|
| H1 | Sur un tenant neuf, l'accès par le rôle B8 lève `InsufficientPrivilegeError` (SQLSTATE 42501) avant toute vérification d'existence de table (constat 4). | C-P1 |
| H2 | Les champs structurés de l'exception asyncpg (`schema_name`, `table_name`, `column_name`, `constraint_name`) sont vides ou non fiables pour 42501 et 42P01 ; l'objet en cause ne peut donc pas être lu dans l'exception. | C-P1 à C-L |
| H3 | `audit_log` absente et `alertes` absente produisent la même classe d'exception et le même SQLSTATE (42P01) : l'exception seule ne permet pas de les distinguer, d'où le diagnostic par le catalogue. | C-A, C-L |
| H4 | Un privilège manquant au niveau du schéma et un privilège manquant au niveau d'une table produisent la même classe et le même SQLSTATE (42501). | C-P1, C-P2, C-P3 |
| H5 | Une transaction `READ ONLY` sur la connexion admin rejette `GRANT` et `CREATE TABLE` (SQLSTATE 25006), sans aucun effet. | C-RO |
| H6 | `lock_timeout` interrompt l'attente du verrou advisory (SQLSTATE 55P03) ; le `ROLLBACK` annule tout et le verrou est libéré, y compris après erreur. | C-LOCK |
| H7 | Dans une même transaction, `has_table_privilege` reflète les `GRANT` non encore validés ; les fonctions de catalogue s'exécutent sous `READ ONLY`. | C-TXN, C-RO |

## Options considérées

**A. Réparer à la lecture (GET).** Rejetée : DDL et `GRANT` dans une
route de lecture, y compris pour un `auditor` ; risque de course sur
`CREATE TABLE IF NOT EXISTS` concurrent.

**B. Event trigger PostgreSQL** (sur le modèle de l'ADR-003). Rejetée
pour le MVP :
- `alertes` est créée tardivement (constat 3) : un trigger sur
  `CREATE SCHEMA` ne suffirait pas, il faudrait un second trigger sur
  `CREATE TABLE alertes`, alors que le trigger de la Brique 1 est
  verrouillé ;
- un event trigger avale ses erreurs par construction (`RAISE
  WARNING`), ce qui est le contraire de ce qu'on veut pour un
  provisionnement de privilèges ;
- complexité disproportionnée pour un seul tenant actif.

**C. Commande explicite + réparation défensive à l'écriture + lecture
sans DDL.** Retenue.

## Décision

### D1. Contrat de provisionnement (deux fonctions séparées)

Portées par la Brique 8, exécutées **uniquement sous le pool
administrateur** (`create_pool_admin()`, Brique 1). Elles sont
**deux fonctions distinctes**, ce qui est la base des garanties de D2 :

- `diagnostiquer_audit(schéma) -> DiagnosticAudit` : lecture seule du
  catalogue, ne modifie rien ;
- `provisionner_audit(schéma) -> liste des éléments réparés` : appelle
  le diagnostic, puis répare.

Liste **fermée** de ce que B8 peut créer ou accorder, pour un schéma
donné :

| Élément du contrat | Condition |
|---|---|
| `{schéma}.audit_log` + son index | toujours |
| `USAGE` sur le schéma pour `souverain_brique8_audit` | toujours |
| `INSERT, SELECT` sur `audit_log` | toujours |
| `SELECT, UPDATE` sur `alertes` | **seulement si `alertes` existe** |

Rien d'autre n'est jamais créé ni accordé. En particulier : aucun
`UPDATE` ni `DELETE` sur `audit_log`, aucune création de `alertes`,
aucune création du rôle (relève de la migration), aucun privilège sur
`shared` (relève de la migration : leur absence est signalée, pas
réparée).

`provisionner_audit` procède en trois temps, **dans une seule
transaction** (le DDL et les `GRANT` PostgreSQL sont transactionnels) :

1. **Diagnostic** par le catalogue système : existence du rôle
   (`pg_roles`), du schéma, de `audit_log` et de `alertes`
   (`to_regclass`), puis `has_schema_privilege` / `has_table_privilege`
   pour chaque ligne du contrat ci-dessus.
2. **Réparation ciblée** : seuls les éléments *constatés manquants*
   sont créés ou accordés.
3. **Contrôle final dans la même transaction** : le rôle B8 ne doit
   avoir ni `UPDATE` ni `DELETE` sur `audit_log` (repose sur H7).
   Sinon la transaction est annulée et l'erreur remonte.

Résultat : liste des éléments réparés (vide = « déjà conforme »), ce
qui rend la fonction idempotente et observable.

Si le diagnostic détecte que le rôle B8 possède **déjà** `UPDATE` ou
`DELETE` sur `audit_log`, c'est une anomalie de sécurité : elle est
journalisée en CRITICAL et remontée, **sans correction automatique**.

### D2. Garanties du pool admin pendant un GET (diagnostic en lecture seule)

Le pool admin se connecte avec un rôle superutilisateur
(`souverain_admin`, ADR-003) : **aucun privilège PostgreSQL ne le
limite**. La garantie « pas de réparation, pas d'élévation de
privilèges pendant un GET » repose donc sur quatre couches
indépendantes, qu'il faut toutes maintenir :

1. **Séparation du code.** Le chemin de lecture (`lecture.py`,
   `routes.py`) n'importe que `diagnostiquer_audit`. Il n'a aucun accès
   à `provisionner_audit`, à `_assurer_table_audit_log`, aux constantes
   `GRANT`, ni au pool admin lui-même : il reçoit uniquement un
   `DiagnosticAudit` (objet immuable de booléens). Un test statique
   vérifie que `lecture.py` n'importe aucun de ces symboles.
2. **Transaction en lecture seule imposée par le serveur.**
   `diagnostiquer_audit` s'exécute dans
   `connexion.transaction(readonly=True)` (`SET TRANSACTION READ
   ONLY`). PostgreSQL rejette alors tout `CREATE`, `ALTER`, `DROP`,
   `GRANT`, `REVOKE` et toute écriture (H5), même sous un rôle
   superutilisateur. Un test vérifie ce rejet sur la connexion admin
   (C-RO).
3. **SQL constant et paramétré.** Les requêtes du diagnostic sont des
   constantes contenant uniquement des lectures de catalogue
   (`pg_roles`, `pg_namespace`, `to_regclass`, `has_*_privilege`). Le
   schéma est validé (`validate_schema_name()`) et transmis comme
   paramètre lié, avec `quote_ident` côté SQL ; jamais interpolé. La
   seule entrée est le nom de schéma issu de la session authentifiée
   (`tenant_valide()`), jamais une donnée libre de l'utilisateur. Un
   test statique vérifie l'absence de mots-clés DDL/DML dans ces
   constantes.
4. **Bornes.** `SET LOCAL statement_timeout = '2s'` dans cette
   transaction, et diagnostic appelé uniquement sur le **chemin
   d'erreur**, jamais sur le chemin nominal.

**Limite assumée.** Ce n'est pas une frontière de privilèges : un bug
qui utiliserait le pool admin directement dans un GET contournerait ces
couches. C'est la même limite que celle de l'ADR-003 (le superutilisateur
reste hors de portée de toute restriction). **Alternative écartée pour
le MVP** : un rôle dédié de diagnostic en lecture seule. Elle
nécessiterait un nouveau rôle, un secret et une migration, et
probablement `USAGE` sur chaque schéma tenant pour résoudre les noms
(*à vérifier*). À réexaminer en Phase 2.

### D3. Verrou advisory : déroulement complet

- Verrou de transaction, `pg_advisory_xact_lock(
  hashtextextended('souverain:b8_audit:' || schéma, 0))` : clé 64 bits
  propre au schéma (une collision ne ferait que sérialiser à tort,
  jamais produire un résultat incorrect). Aucun verrou de session
  (risque de fuite quand la connexion retourne au pool).
- **Une seule connexion du pool admin** par réparation, et une seule
  `connexion.transaction()`. Elle est rendue au pool **avant** le
  nouvel essai : on ne détient jamais deux connexions à la fois (pas
  d'attente croisée entre pools).
- La commande CLI (D6) utilise la même fonction, donc le même verrou :
  CLI et réparation à l'écriture sont mutuellement sérialisés.

**Déroulement (chemin d'écriture)**

1. *Essai 1* (pool restreint, transaction T1) : échec. T1 est annulée
   par le gestionnaire de contexte ; la connexion restreinte retourne au
   pool. L'alerte reste `ouverte`, aucune ligne d'audit n'est écrite.
2. *Réparation* (pool admin, transaction T2) :
   a. `BEGIN`, puis `SET LOCAL lock_timeout = '5s'` et
      `SET LOCAL statement_timeout = '15s'` ;
   b. prise du verrou advisory (attente bornée par `lock_timeout`) ;
   c. diagnostic sous verrou ;
   d. si rien à réparer ou cause autre (tableaux D4) : `COMMIT` (rien à
      valider), verrou libéré, puis traitement selon D4 sans nouvel
      essai ;
   e. sinon réparation, puis contrôle final (D1, étape 3) ;
   f. `COMMIT` : les changements deviennent visibles pour toutes les
      sessions et le verrou est libéré à cet instant ;
   g. la connexion admin retourne au pool.
3. *Essai 2* (pool restreint, nouvelle transaction T3), **unique** :
   succès, ou l'échec remonte tel quel (chaîné à l'erreur d'origine).
   Jamais de troisième essai. Cet essai n'est pas sous le verrou : il
   utilise un autre rôle et une autre connexion, et n'en a pas besoin
   (la réparation est déjà validée et idempotente).

**Cas d'échec**

| Situation | Effet | Résultat |
|---|---|---|
| Timeout du verrou (`lock_timeout`, 55P03, H6) ou d'un verrou de table pris par le DDL | `ROLLBACK` de T2, rien de modifié, verrou libéré | exception `AuditNonProvisionne` (raison `VERROU_TIMEOUT`), chaînée à l'erreur d'origine ; HTTP 503 ; aucun nouvel essai ; l'utilisateur peut réessayer |
| `statement_timeout` (57014), perte de connexion, interblocage | `ROLLBACK` de T2 (ou fin de session côté serveur), verrou libéré | exception `AuditNonProvisionne` (raison `REPARATION_ECHOUEE`) ; HTTP 503 |
| Contrôle final en échec (`UPDATE`/`DELETE` détecté) | `ROLLBACK` de T2 : le DDL et les `GRANT` de cette réparation sont annulés | CRITICAL, l'erreur remonte, pas de nouvel essai |
| Arrêt du processus après le `COMMIT` de T2 et avant T3 | réparation faite, alerte toujours `ouverte` | la tentative suivante réussit directement (idempotence) |
| Appelant concurrent | attend à l'étape b ; après le `COMMIT` du premier, diagnostic « conforme », rien à faire | passe directement à son essai 2 |
| Échec de l'essai 2 | pas de nouvelle réparation | l'erreur remonte, journalisée |

Le verrou advisory, pris en premier, sérialise les réparateurs entre
eux ; le risque résiduel (attente derrière des transactions de
fermeture en cours) est borné par `lock_timeout`, jamais une attente
infinie. Dans tous les cas d'échec, l'état de la base reste cohérent :
la fermeture d'alerte et son audit restent atomiques (une seule
transaction restreinte, inchangée).

### D4. Décider selon la cause, pas la classe d'erreur

**Écriture.** `fermer_alerte_avec_audit()` ne lance **aucun `GRANT` sur
la seule base du type d'exception** et n'analyse pas le texte du
message (dépendant de `lc_messages`). Toute erreur déclenche d'abord le
diagnostic de D1 :

| Erreur observée | Diagnostic | Action |
|---|---|---|
| `UndefinedTableError` | `alertes` absente | `AlerteNonFermable`, aucune réparation (comportement actuel inchangé) |
| `UndefinedTableError` | `alertes` présente, `audit_log` absente | réparer, **un** nouvel essai |
| `UndefinedTableError` | `alertes` et `audit_log` présentes | anormal : l'erreur remonte brute, aucun DDL |
| `InsufficientPrivilegeError` | un élément du contrat D1 manque | réparer cet élément, **un** nouvel essai |
| `InsufficientPrivilegeError` | contrat complet, rien à réparer | la cause est autre : l'erreur remonte brute |
| `InsufficientPrivilegeError` | rôle B8 absent | `AuditNonProvisionne` (raison `ROLE_ABSENT`), aucune création de rôle |
| toute autre erreur | — | remonte brute |

**Lecture** (sans DDL ni `GRANT` ; diagnostic en lecture seule, D2) :

| Erreur observée | Diagnostic (catalogue, lecture seule) | Résultat |
|---|---|---|
| aucune | — | historique |
| `UndefinedTableError` | schéma et rôle présents, `audit_log` absente | **liste vide** (absence légitime : aucune fermeture n'a eu lieu, `audit_log` étant aussi créée à la première écriture) |
| `UndefinedTableError` | autre cause (schéma absent, objet partagé absent…) | l'erreur remonte, jamais `[]` |
| `InsufficientPrivilegeError` | un élément du contrat D1 manque | `AuditNonProvisionne` (raison `NON_PROVISIONNE`) : log ERROR, HTTP 503 sans détail interne |
| `InsufficientPrivilegeError` | contrat complet | cause inconnue : l'erreur remonte brute (500 journalisé) |

Choix assumé : ce classement lit le catalogue via le pool admin déjà
utilisé par `_table_alertes_existe()`. Alternative écartée : analyser
le texte des messages d'erreur (fragile, dépend de la langue du
serveur).

### D5. Journalisation sans divulgation de données sensibles

Principe : le diagnostic utile est porté par des **champs structurés à
liste blanche**, jamais par le texte brut des exceptions.

- **Journalisés** : code d'événement (`b8.diagnostic`,
  `b8.reparation`, `b8.reparation_echec`, `b8.verrou_timeout`,
  `b8.anomalie_audit_log_privilege`), `schema_name` (identifiant
  technique issu du registre), `tenant_id`, identifiant de requête
  (`X-Request-ID`, déjà posé par le middleware de `souverain_app`),
  classe de l'exception, SQLSTATE, code `raison`
  (`NON_PROVISIONNE`, `ROLE_ABSENT`, `VERROU_TIMEOUT`,
  `REPARATION_ECHOUEE`, `ANOMALIE_PRIVILEGE`), éléments manquants ou
  réparés (valeurs de la liste fermée de D1), durée, numéro d'essai.
- **Jamais journalisés** : le texte brut de l'exception (`message`,
  `detail`, `hint` : ils peuvent contenir noms de rôles, d'objets ou
  valeurs de lignes), les requêtes SQL avec leurs paramètres,
  `alerte_id`, `user_id`, e-mails, `commentaire` (texte libre
  d'analyste), `compte_pivot`, scores, mots de passe, DSN, JWT, cookies
  et jetons CSRF, contenu d'`audit_log`.
- **Exceptions** : la classe, le SQLSTATE et la chaîne des classes de
  `__cause__` sont journalisés ; pas de trace d'appel complète avec le
  message d'exception aux niveaux ERROR et CRITICAL. Une trace complète
  éventuelle n'est permise qu'à un niveau DEBUG désactivé par défaut.
  Le booléen de diagnostic de D1 apporte l'information que le message
  brut aurait donnée.
- **Réponses HTTP** : texte 503 générique via `t()` ; aucun nom de
  schéma, de rôle, de table ni SQLSTATE. Le `X-Request-ID` de la
  réponse permet de retrouver l'entrée de journal.
- **Sortie de la CLI** : codes d'état et noms de schéma uniquement (le
  contexte opérateur) ; les messages d'erreur bruts restent hors de la
  sortie.
- **Vérification** : un test d'acceptation capture les journaux et
  les réponses avec des valeurs « sentinelles » (faux e-mail, faux
  commentaire, `alerte_id` connu, faux mot de passe) et vérifie leur
  absence, ainsi que celle du texte brut de l'exception.

### D6. Contrat de la commande `souverain-audit-provisionner`

- **Arguments** : exactement un parmi `--tenant <schema_name>` et
  `--tous`. Convention existante du projet : l'identifiant est le
  `schema_name` (comme `--tenant tenant_ne` dans les autres commandes),
  pas le `tenant_code`.
- **Validation par le registre** : `validate_schema_name()`, puis
  recherche exacte dans `shared.tenants_registry`. Le schéma traité est
  toujours celui lu dans le registre, jamais une chaîne libre. Présent
  au registre mais schéma absent de la base (`pg_namespace`) : échec
  explicite (incohérence), jamais de création de schéma.
- **Tenant désactivé** : `--tenant` sur un tenant inactif est refusé
  (code 3) ; `--tous` l'ignore et le liste comme « ignoré (inactif) ».
  Pour provisionner un tenant inactif, le réactiver d'abord
  (`souverain-tenant-activer`). Aucune option de contournement en MVP.
- **`--tous`** : tenants actifs, ordre alphabétique de `schema_name`,
  **une transaction et un verrou par tenant**.

**Codes de sortie**

| Code | Signification | Cas |
|---|---|---|
| 0 | Succès complet | tous les tenants visés sont conformes ou réparés ; en `--tous`, les tenants inactifs ignorés et l'absence de tenant actif (message d'information) ne changent pas le code |
| 1 | Échec d'exécution | au moins un tenant en échec : erreur SQL, timeout de verrou, schéma absent, contrôle final en échec, anomalie de privilège, rôle B8 absent, ou impossibilité de se connecter à la base |
| 2 | Erreur d'usage ou d'identification | aucun argument ou les deux, nom de schéma invalide, tenant inconnu du registre ; aucune modification (c'est aussi le code d'`argparse` pour un usage invalide) |
| 3 | Refus de politique | `--tenant` visant un tenant inactif ; aucune modification |

En `--tous`, seuls 0 et 1 sont possibles (hors erreur d'usage, 2).

**Échecs partiels de `--tous`**

- L'échec d'un tenant **n'interrompt pas** les suivants et **n'annule
  pas** les tenants déjà traités : chaque tenant a sa propre
  transaction, validée ou annulée indépendamment. Il n'y a pas de
  transaction globale.
- Un résumé final liste, pour chaque tenant : conforme / réparé
  (éléments) / ignoré (inactif) / échec (code `raison`, jamais le
  message brut), avec les totaux. Résumé sur la sortie standard, erreurs
  sur la sortie d'erreur, détails dans les journaux (D5).
- S'il y a au moins un échec, le code de sortie est 1 même si d'autres
  tenants ont réussi.
- Relancer la commande est sûr (idempotence) : les tenants déjà
  réparés sont rapportés « conformes », seuls les échecs sont retraités.
- Interruption (Ctrl+C) : la transaction du tenant en cours est
  annulée, les tenants précédents restent validés ; code par défaut du
  shell (130), non spécifié davantage. Relancer.
- Pas d'option « arrêter au premier échec » en MVP.

### D7. Inchangé

`csrf.py`, le RBAC des routes, la transaction de fermeture,
`connection.py`, et B1/B2/B7.

## Tests de caractérisation

Objectif : **confirmer ou réfuter H1 à H7 avant toute implémentation.**
Ce sont des tests qui *décrivent le comportement réel* de PostgreSQL et
d'asyncpg ; un test qui échoue signifie une hypothèse réfutée, donc
l'ADR est révisé avant d'écrire du code. Ils ne vérifient pas encore la
correction (voir « Tests d'acceptation »).

Fichier prévu : `briques/brique_08_audit_human_loop/tests/
test_caracterisation_provisioning.py` (nouveau). Règles communes :
- tenant **éphémère** créé par le vrai `create_tenant()` (pool
  `souverain_gouvernance_cli`), jamais `tenant_ne`, sans `GRANT`
  manuel ; mise en place dans le `try`, nettoyage dans le `finally` ;
- chaque test commence par des **assertions de garde** sur l'état
  initial (via le catalogue), pour qu'une fixture mal posée ne puisse
  pas confirmer une hypothèse à tort ;
- chaque test enregistre : classe de l'exception, `sqlstate`, valeurs
  de `schema_name`, `table_name`, `column_name`, `constraint_name`, et
  si le message contient ou non le nom de l'objet. Le texte du message
  n'est pas copié dans l'annexe ;
- exécution sur la machine du fondateur (PostgreSQL requis) ; le
  `lc_messages` du serveur est consigné.

| Test | Situation de départ | Appel | Confirme |
|---|---|---|---|
| C-P1 | tenant neuf : schéma, aucun `USAGE` pour le rôle B8 ; `alertes` et `audit_log` existent (créées par l'admin) | lecture d'historique, puis `_tenter_fermeture` | H1, H2, H4 : 42501 de niveau schéma |
| C-P2 | `USAGE` accordé, aucun droit sur `alertes` | `_tenter_fermeture` | H4 : 42501 de niveau table, même classe que C-P1 |
| C-P3 | `USAGE` et droits sur `alertes`, aucun droit sur `audit_log` | `_tenter_fermeture` | H4 : 42501 sur `audit_log` |
| C-A | `USAGE` et droits sur `alertes` ; `audit_log` absente | lecture, puis `_tenter_fermeture` | H3 : 42P01 « `audit_log` absente » |
| C-L | `USAGE` accordé ; `alertes` absente (B5 jamais exécutée), avec puis sans `audit_log` | `_tenter_fermeture` | H3 : 42P01 « `alertes` absente » ; comparaison champ par champ avec C-A : si identiques, l'exception ne distingue pas les deux cas |
| C-RO | connexion admin, transaction `readonly=True`, schéma éphémère | tenter `GRANT` puis `CREATE TABLE`, puis lire le catalogue | H5 : rejet 25006 de l'écriture, aucun effet ; H7 (catalogue lisible) |
| C-LOCK | deux connexions admin ; la première détient le verrou advisory | seconde avec `lock_timeout` court | H6 : 55P03, `ROLLBACK`, verrou libéré ensuite |
| C-TXN | transaction admin : `GRANT`, puis `has_table_privilege` avant `COMMIT` | contrôle de visibilité | H7 : le contrôle final voit les `GRANT` non validés |

Les trois cas à distinguer sont couverts ainsi : **privilèges
manquants** (C-P1 à C-P3), **`audit_log` absente** (C-A), **`alertes`
absente** (C-L). Les cas « autre cause » des tableaux D4 (objet
partagé absent, etc.) ne sont **pas** caractérisés sur PostgreSQL (cela
imposerait de modifier un privilège global) : ils seront couverts à
l'acceptation par un diagnostic simulé.

## Tests d'acceptation (après correction)

- Chaque ligne des tableaux D4 (avec diagnostic simulé pour les cas
  « autre cause »).
- Verrou et reprise (D3) : réparations concurrentes, timeout du
  verrou, échec injecté en cours de réparation (aucune réparation
  partielle visible), reprise après `COMMIT` sans essai 2.
- Garanties D2 : test statique des imports de `lecture.py`, test
  statique des constantes SQL du diagnostic, rejet `READ ONLY`.
- CLI (D6) : chaque code de sortie 0, 1, 2 et 3 ; `--tous` avec un
  échec au milieu (les autres tenants traités, code 1, relance sûre) ;
  tenant inconnu ; tenant inactif ; idempotence.
- Journaux et réponses (D5) : valeurs sentinelles absentes.
- Lecture sur tenant non provisionné = 503, jamais liste vide ;
  fermeture réussie sans `GRANT` manuel avec `alertes` créée après
  coup ; `REVOKE USAGE` fait toujours remonter l'erreur ; absence
  d'`UPDATE` et de `DELETE` sur `audit_log`.
- Non-régression : suite complète du workspace.

## Invariants de sécurité

- `souverain_brique8_audit` n'a jamais `UPDATE` ni `DELETE` sur
  `audit_log` (contrôle dans la transaction de réparation, puis
  `has_table_privilege` dans les tests).
- DDL et `GRANT` uniquement dans `provisionner_audit`, sous le pool
  admin ; le chemin de lecture n'y a aucun accès (D2) ; le rôle
  restreint n'obtient aucun privilège DDL.
- Liste fermée de privilèges (D1) : constantes, jamais déduites d'une
  entrée utilisateur ; schéma issu de la session authentifiée ou du
  registre.
- Aucune réparation sans diagnostic confirmant l'objet manquant ;
  jamais de `GRANT` déclenché par la seule classe d'exception.
- Aucune erreur de permission convertie en historique vide.
- Aucune donnée sensible ni texte brut d'exception dans les journaux
  ni dans les réponses (D5).
- Isolation multi-tenant : chaque appel et chaque verrou ne concernent
  qu'un schéma.

## Conséquences

- **Positives** : le défaut disparaît sans magie cachée ; les échecs de
  permission restent visibles ; la réparation reste bornée par une liste
  fermée et par des délais ; les journaux restent exploitables sans
  fuite.
- **Négatives** : un nouveau tenant exige une étape manuelle ; l'oubli
  est rattrapé à l'écriture mais se voit à la lecture comme un 503
  explicite. Le diagnostic ajoute quelques requêtes de catalogue sur le
  chemin d'erreur uniquement.
- **Limite connue** : `souverain_admin` (superutilisateur) reste hors
  de portée de toute restriction (ADR-003) ; D2 est une défense en
  profondeur, pas une frontière de privilèges.
- **À réexaminer en Phase 2** (premier export UEMOA) : automatiser le
  provisionnement si la création de tenants devient fréquente ; rôle
  de diagnostic dédié.

## Hors périmètre

- **Migration `0001` : conservée telle quelle.** Le défaut annexe
  (constat 7) doit d'abord être **reproduit** sur une base réelle, puis
  **évalué** (impact sur les bases existantes, compatibilité d'un
  éventuel correctif). Seulement après, une migration corrective
  distincte pourra être proposée, séparément. Rien dans cet ADR ne
  dépend de ce défaut : D1 gère l'absence d'`alertes` elle-même.
- Étape 6A / 6B, et toute modification de B1 (`create_tenant()`).
- Le commentaire obsolète de `tenant_provisioning.py` (« appartient à
  la Brique 8 ») : signalé, non corrigé ici.

## Critère de passage à « Acceptée » (état au 17 octobre 2026)

1. **Hypothèses H1 à H7 confirmées** : oui, voir l'annexe. Écart de
   méthode assumé : le fichier `test_caracterisation_provisioning.py`
   prévu plus haut n'a **pas** été écrit. La confirmation s'est faite par
   un script ponctuel sur la pile réelle (H1, H2), un PostgreSQL 16 de
   test (H3 à H7) et les tests d'acceptation permanents de
   `test_tenant_neuf.py` (dont `test_h5_*` et `test_h7_*`).
2. **Résultats consignés** : oui, annexe ci-dessous.
3. **Validation du fondateur** : en attente.

## Points ouverts

- Traçabilité de la commande dans une table d'audit (le rôle admin n'a
  pas le droit d'écrire dans `shared.gouvernance_audit_log`).
- Valeurs exactes des délais (`lock_timeout` 5 s, `statement_timeout`
  15 s pour la réparation et 2 s pour le diagnostic) : à ajuster selon
  les mesures.

## Annexe — Confirmation des hypothèses

| # | Vérifiée par | Résultat |
|---|---|---|
| H1 | Script de reproduction sur la pile réelle (TimescaleDB 2.17.2 / PG 16, vrai code B8) ; tests R1 et R3 | `InsufficientPrivilegeError`, SQLSTATE 42501, avant toute vérification d'existence ✔ |
| H2 | Même script ; PostgreSQL 16.15 de test pour 42P01 | `schema_name`, `table_name`, `column_name`, `constraint_name` tous `None` ✔ |
| H3 | PostgreSQL 16.15 de test ; tests A5, D1, D2 sur la pile réelle | `audit_log` absente et `alertes` absente : même classe, même SQLSTATE 42P01, champs vides ; la distinction passe par le catalogue ✔ |
| H4 | PostgreSQL 16.15 de test (états S1 et S3) ; tests R5 et D3 sur la pile réelle | Privilège de schéma ou de table manquant : même classe 42501 ✔ |
| H5 | PostgreSQL 16.15 de test ; `test_h5_*` | `GRANT` et `CREATE TABLE` rejetés en transaction `READ ONLY` (25006), même pour le superutilisateur, sans effet ✔ (test réel à confirmer à la prochaine exécution) |
| H6 | Test A1 sur la pile réelle ; PostgreSQL 16.15 de test | Verrou déjà tenu : `lock_timeout` (55P03), rien créé, verrou libre ensuite ✔ |
| H7 | PostgreSQL 16.15 de test ; `test_h7_*` | Un `GRANT` non validé est visible dans la même transaction, annulé par le `ROLLBACK` ✔ (test réel à confirmer à la prochaine exécution) |

`lc_messages` du serveur : non consigné. Aucune décision du code ne
repose sur le texte des messages d'erreur.
