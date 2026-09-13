# Modélisation opérationnelle de SOUVERAIN-OS

**Statut : document de conception, en attente de relecture et validation
explicite du fondateur avant toute implémentation supplémentaire.**

**Date de rédaction : 4 septembre 2026.**

**Méthode** : chaque affirmation de ce document distingue explicitement
son statut, selon le code réellement présent dans le dépôt au moment de
la rédaction (Briques 0 à 8, toutes validées) — jamais une supposition
de ce qui serait logique ou souhaitable.

## Légende des statuts utilisés dans ce document

- **[VERROUILLÉ]** — décision déjà actée dans `00_DECISIONS_VERROUILLEES.md` avant cette analyse.
- **[DÉCIDÉ ICI]** — décision prise au cours de cette session de modélisation, pas encore reportée dans `00_DECISIONS_VERROUILLEES.md`.
- **[IMPLÉMENTÉ]** — présent et vérifié dans le code/les tests du dépôt.
- **[PARTIEL]** — une partie existe, une partie manque.
- **[À CONCEVOIR]** — besoin réel identifié, analyse à faire avant tout code.
- **[FUTUR]** — explicitement reporté, hors périmètre actuel.
- **[OUVERT]** — question non tranchée, nécessite une décision du fondateur.

---

## 1. Objectif

Ce document décrit comment SOUVERAIN-OS fonctionne **réellement**
aujourd'hui (Briques 0 à 8 validées) du point de vue d'une institution
utilisatrice — qui fait quoi, qui voit quoi, qui décide, qui contrôle —
et distingue précisément cet état réel de ce qui reste à concevoir ou
à reporter. Il ne remplace aucun document existant
(`01_DOCUMENT_REFERENCE_FONDATEUR.md`, `00_DECISIONS_VERROUILLEES.md`,
`avancement.md`) — il les complète avec une lecture opérationnelle
transversale.

## 2. Principes opérationnels

- **[VERROUILLÉ]** Toute donnée métier est isolée par tenant (schema-per-tenant PostgreSQL), jamais par filtrage applicatif seul.
- **[VERROUILLÉ]** Aucune modification silencieuse d'une décision d'architecture déjà validée.
- **[DÉCIDÉ ICI]** SOUVERAIN-OS est un outil d'aide à la décision et d'investigation — jamais un système qui conclut seul à une culpabilité. Voir section 10.
- **[IMPLÉMENTÉ]** Toute action humaine sensible (fermeture d'alerte) est tracée de façon immuable (privilège PostgreSQL réel, pas seulement applicatif).

## 3. Acteurs

Trois rôles réellement implémentés (`briques/brique_02_auth_rbac/.../rbac.py`,
`Role(StrEnum)` ; contrainte identique sur `shared.users.role`) :

- `admin`
- `analyst`
- `auditor`

**[IMPLÉMENTÉ]** Chaque utilisateur appartient à **exactement un
tenant** (`shared.users.tenant_id NOT NULL`, FK vers
`shared.tenants_registry`). Il n'existe **aucun** rôle ou compte
transverse à plusieurs tenants dans le modèle actuel — voir section 7
pour l'implication sur la gouvernance des tenants eux-mêmes.

Aucun autre acteur (superviseur, responsable conformité, enquêteur
spécialisé, administrateur système) n'est implémenté. Voir section 19
pour les profils potentiels à étudier, qui ne sont pas des rôles
officiels.

## 4. Rôles — responsabilités réelles

### `admin`
- Données accessibles : toutes les données de **son** tenant (aucun accès inter-tenant).
- Actions autorisées : identiques à `analyst` sur tout le dashboard actuel, y compris la fermeture d'alerte.
- Actions interdites : aucune différence codée avec `analyst` à ce jour.
- **[DÉCIDÉ ICI]** Cette absence de différenciation est un choix explicite, pas un oubli — voir section 17.

### `analyst`
- Données accessibles : toutes les alertes, détections, fragments graphe de son tenant.
- Actions autorisées : consulter, fermer une alerte avec motif structuré + commentaire optionnel.
- Actions interdites : modifier ou supprimer une entrée d'audit (impossible pour tous les rôles, protection par privilège PostgreSQL, pas une règle de rôle).

### `auditor`
- Données accessibles : identiques à `analyst` en lecture (alertes, détections, graphe, historique d'audit complet).
- Actions autorisées : consultation uniquement.
- Actions interdites : fermer une alerte — **[IMPLÉMENTÉ]**, vérifié par un test HTTP réel (`test_fermeture_refusee_pour_un_auditor`), refus `403` même sur une requête POST forgée directement, indépendamment de ce que l'interface affiche.

## 5. Matrice des permissions

| Fonction | Admin | Analyst | Auditor |
|---|---|---|---|
| Se connecter | IMPLÉMENTÉ | IMPLÉMENTÉ | IMPLÉMENTÉ |
| Consulter les alertes | IMPLÉMENTÉ | IMPLÉMENTÉ | IMPLÉMENTÉ |
| Consulter les transactions brutes | NON DÉFINI DANS LE PROJET ACTUEL | NON DÉFINI DANS LE PROJET ACTUEL | NON DÉFINI DANS LE PROJET ACTUEL |
| Consulter le graphe (Neo4j) | IMPLÉMENTÉ | IMPLÉMENTÉ | IMPLÉMENTÉ |
| Fermer une alerte | IMPLÉMENTÉ | IMPLÉMENTÉ | INTERDIT (testé) |
| Consulter l'audit | IMPLÉMENTÉ | IMPLÉMENTÉ | IMPLÉMENTÉ |
| Modifier/supprimer l'audit | IMPOSSIBLE (tous rôles — privilège PostgreSQL) | IMPOSSIBLE | IMPOSSIBLE |
| Gérer les utilisateurs | NON DÉFINI DANS LE PROJET ACTUEL | — | — |
| Créer/activer/désactiver un tenant | NON DÉFINI DANS LE PROJET ACTUEL — voir section 7 | — | — |
| Modifier la configuration | NON DÉFINI DANS LE PROJET ACTUEL | — | — |

## 6. Visibilité des données

**Admin / Analyst** : écran d'accueil = liste des alertes du tenant
(`/alertes`). Détail d'alerte : score, motifs impliqués, fenêtre
d'observation, détections liées, fragment graphe (chaînes de
redistribution, comptes pont, chemins entre comptes alertés — 3
requêtes Brique 6), fragment fermeture avec formulaire (motif + commentaire).

**Auditor** : mêmes écrans, à l'exception du formulaire de fermeture
(absent du HTML — vérifié par test, pas seulement masqué en CSS).

Aucun rôle n'a d'écran utilisateurs, tenant ou configuration —
**NON IMPLÉMENTÉ**, ces écrans n'existent pas, pas seulement cachés.

## 7. Architecture multi-tenant

- **[VERROUILLÉ]** Un tenant = un pays = un schéma PostgreSQL physique dédié (`{tenant}`), enregistré dans `shared.tenants_registry` (métadonnées de gouvernance uniquement, aucune donnée métier).
- **[IMPLÉMENTÉ]** Isolation : schema-per-tenant — **pas de Row-Level Security PostgreSQL**. `validate_schema_name()` protège contre l'injection SQL sur le nom de schéma dynamique.
- **[IMPLÉMENTÉ]** Un utilisateur est associé à un tenant via `shared.users.tenant_id` (FK, `ON DELETE RESTRICT`).
- **[IMPLÉMENTÉ]** Revalidation défensive à chaque requête dashboard (`tenant_valide()`) : le JWT est revérifié contre `shared.tenants_registry.is_active` — un jeton signé ne suffit pas si le tenant a été désactivé entre-temps.
- **[IMPLÉMENTÉ]** Neo4j (Community, une seule base) : isolation logique par `tenant_id` sur chaque nœud/relation, contrainte composite `(tenant_id, compte_id)`, un seul point d'exécution Cypher (`garde_isolation.py`).
- Ce que l'utilisateur d'un tenant peut voir : uniquement les données de son propre schéma. Ce qu'il ne peut jamais voir : toute donnée d'un autre tenant — isolation physique, pas un filtre applicatif contournable.

### 7bis. Gouvernance des tenants — qui peut créer/activer/désactiver un tenant [À CONCEVOIR]

Point explicitement demandé avant toute implémentation. Constat
architectural central : **les trois rôles existants sont tous
scopés à un tenant unique** (`shared.users.tenant_id NOT NULL`). Un
`admin` d'aujourd'hui est un administrateur *de son tenant*, pas de la
plateforme — il n'a, par construction, aucune vue sur les autres
tenants et ne peut donc pas être le rôle qui crée un nouveau tenant
(ce serait une opération transverse, hors du modèle d'isolation actuel).

**Conséquence** : créer un nouveau tenant (un nouveau pays) est une
opération **structurellement différente** d'une action `admin`
classique — elle ne peut pas être portée par un rôle actuel sans
introduire un concept nouveau (un opérateur "plateforme", hors du
modèle par-tenant).

**Recommandation, non actée comme décision** : au stade MVP (un seul
tenant actif, `tenant_ne`), garder la création/activation/désactivation
de tenant **CLI-only**, réservée à qui a un accès direct au serveur —
même principe déjà appliqué à l'ingestion, la détection et le scoring
(Briques 3/4/5), qui sont elles aussi CLI-only et non exposées en HTTP.
Aucune route web de gestion des tenants ne devrait exister tant qu'un
véritable concept d'opérateur plateforme (distinct des trois rôles
par-tenant) n'a pas été conçu explicitement — ce n'est pas un ajustement
mineur de RBAC, c'est une nouvelle dimension du modèle de rôles.

**[OUVERT]** Faut-il concevoir ce concept d'opérateur plateforme
maintenant, ou rester en CLI-only tant qu'un seul tenant est actif
(pas d'urgence avant la Phase 2 / premier export UEMOA) ?

## 8. Cycle de vie d'une alerte

| Transition | Brique | Déclencheur | Donnée | État |
|---|---|---|---|---|
| Transaction → ingérée | 3 | CLI (`souverain-generer`) | `transactions` | IMPLÉMENTÉ (synthétique uniquement) |
| Ingérée → détection | 4 | CLI (`souverain-detecter`) | `detections` | IMPLÉMENTÉ |
| Détection → score → alerte `ouverte` | 5 | CLI (`souverain-scorer`) | `alertes` | IMPLÉMENTÉ |
| `ouverte` → `fermee` | 8 | Humain authentifié (`analyst`/`admin`), POST | `alertes.statut` + `audit_log` (1 transaction atomique) | IMPLÉMENTÉ |
| `fermee` → `ouverte` | — | — | — | **NON IMPLÉMENTÉ, exclu par décision verrouillée** |

**[IMPLÉMENTÉ]** `alertes.statut` a exactement deux valeurs
(`ouverte`, `fermee` — contrainte `CHECK` en base). Le motif de
fermeture (`faux_positif`, `confirme`, `en_cours_investigation`) est
un **attribut de l'action de fermeture**, jamais un état intermédiaire
de l'alerte elle-même — `en_cours_investigation` ferme l'alerte tout
autant que les deux autres motifs.

Aucune étape d'ingestion/détection/scoring n'est exposée en HTTP —
uniquement la fermeture (Brique 8) est un vrai workflow web.

## 9. Workflow d'investigation

Déjà implémenté : consulter l'alerte, les motifs, les détections
liées, le fragment graphe (3 requêtes), fermer avec motif structuré,
trace d'audit automatique et atomique.

**[PARTIEL / À CONCEVOIR]** :
- Consulter les transactions brutes individuelles depuis le dashboard — aucune route n'existe.
- "Poursuivre/escalader" au sens d'un état intermédiaire distinct — n'existe pas, seul `fermee` existe (voir section 8).
- Assignation d'une alerte à un analyste nommé — voir section 17.

## 10. Décision humaine — invariant architectural

**[DÉCIDÉ ICI, à élever en décision verrouillée]** SOUVERAIN-OS est un
**outil d'aide à la décision et d'investigation**. Aucune fermeture,
conclusion, ou qualification (faux positif / confirmé) n'est jamais
produite automatiquement par le système. Le Rule Engine (Brique 4) et
le scoring (Brique 5) **détectent et priorisent** — ils ne concluent
jamais. Seule une action HTTP authentifiée et explicitement autorisée
(`analyst`/`admin`) peut fermer une alerte, avec un motif que
**l'humain choisit**, jamais que le système suggère ou pré-sélectionne.

Ce principe est traité comme un **invariant**, pas comme une simple
description de l'état actuel : toute évolution future (y compris une
"auto-fermeture des cas à score très faible" qui pourrait sembler un
gain de productivité) devrait être explicitement mise en tension avec
cet invariant avant d'être envisagée, jamais ajoutée comme un détail
d'optimisation.

Comment la décision humaine est enregistrée : `audit_log`
(`user_id`, `motif`, `commentaire`, `created_at`), immuable par
privilège PostgreSQL réel (voir section 11).

## 11. Workflow d'audit

- **[IMPLÉMENTÉ]** Qui peut créer une trace : uniquement le système lui-même, au moment exact d'une fermeture d'alerte réussie (une seule transaction atomique avec le changement de statut).
- **[IMPLÉMENTÉ]** Qui peut consulter : `admin`, `analyst`, `auditor` — tous, en lecture.
- **[IMPLÉMENTÉ]** Qui peut modifier/supprimer : **personne** — rôle PostgreSQL dédié (`souverain_brique8_audit`) avec privilèges strictement limités à `INSERT`/`SELECT` sur `audit_log`, aucun `UPDATE`/`DELETE` possible même en cas de bug applicatif. Vérifié par test réel contre une vraie base (`test_role_restreint_ne_peut_pas_modifier_l_audit_log`), pas une simple discipline de code.
- **[IMPLÉMENTÉ]** Immutabilité **applicative** : garantie réelle aujourd'hui.
- **[FUTUR]** Immutabilité **cryptographique/tamper-evident** (hash-chaînage, signature Dilithium-5) : **non implémentée**. Ne pas présenter la protection actuelle comme équivalente à une preuve cryptographique face à un tiers (régulateur, investisseur) — c'est une protection par privilège d'accès, pas un tamper-evidence au sens fort.

## 12. Institution cliente / CENTIF

**[OUVERT dans le code, DÉCIDÉ ICI comme principe]** Aucune table,
route ou modèle ne référence CENTIF, BCEAO ou un acteur institutionnel
externe — ces mentions existent uniquement dans les documents de
vision, jamais dans le code. Le positionnement institutionnel
(section 10) — outil d'aide à la décision, jamais un remplacement du
jugement humain — est acté comme principe, mais son intégration
concrète avec un système externe (CENTIF, BCEAO) reste entièrement à
concevoir : aucun format d'export, aucune API, aucun protocole
d'échange n'existe à ce jour.

## 13. Parcours transaction → décision

| Étape | Brique | Acteur | Donnée | Action | État |
|---|---|---|---|---|---|
| Transaction | 3 | Système (CLI) | `transactions` | Génération/ingestion | IMPLÉMENTÉ (synthétique) |
| Ingestion | 3 | Système (CLI) | `transactions` | Insertion par lots | IMPLÉMENTÉ |
| Détection | 4 | Système (CLI) | `detections` | 5 règles à état | IMPLÉMENTÉ |
| Score | 5 | Système (CLI) | `alertes` (ouverte) | Agrégation pondérée | IMPLÉMENTÉ |
| Alerte | 5→7 | Système → Humain | `alertes` | Affichage dashboard | IMPLÉMENTÉ |
| Analyste | 7 | `analyst`/`admin`/`auditor` | lecture | Consultation | IMPLÉMENTÉ |
| Investigation | 7 | `analyst`/`admin`/`auditor` | lecture | Motifs, graphe | IMPLÉMENTÉ |
| Décision humaine | 8 | `analyst`/`admin` | `audit_log` | Fermeture + motif | IMPLÉMENTÉ |
| Fermeture / suite | 8 | `analyst`/`admin` | `alertes.statut` | `ouverte→fermee` | IMPLÉMENTÉ (pas de réouverture) |
| Audit | 8 | Système | `audit_log` | Trace immuable | IMPLÉMENTÉ |
| Contrôle | — | `auditor` | lecture | Consultation historique | IMPLÉMENTÉ (lecture seule) |

## 14. Matrice métier ↔ briques 0–8

| Fonction métier | Brique | Implémentation | Preuve | Manque |
|---|---|---|---|---|
| Authentification | 2 | Oui | `test_api.py`, JWT+cookie | Pas de MFA (hors périmètre MVP) |
| RBAC | 2 | Oui (3 rôles) | `test_rbac.py`, `require_role` | Différenciation admin/analyst quasi nulle (choix assumé, section 17) |
| Isolation multi-tenant | 1 | Oui (schema-per-tenant) | `test_connection.py`, `validate_schema_name` | Pas de RLS ; gouvernance de création de tenant absente (section 7bis) |
| Ingestion | 3 | Oui (synthétique) | `test_ingestion.py` | Aucune ingestion de données réelles (hors périmètre MVP) |
| Détection | 4 | Oui (5 règles) | `test_regle_*.py` | Composante statistique/calibrée = Vision |
| Scoring | 5 | Oui | `test_agregation.py`, `test_integration.py` | Seuils provisoires, non recalibrés sur données réelles |
| Graphe | 6 | Oui (3 requêtes) | `test_requetes.py` | Pas de distinction absence de données / panne Neo4j (section 17) |
| Dashboard | 7 | Oui (lecture seule) | `test_routes_alertes.py` | Pas de vue transactions brutes |
| Fermeture humaine | 8 | Oui | `test_routes.py` | Pas de réouverture, pas d'assignation (section 17) |
| Audit | 8 | Oui (immuable, privilège réel) | `test_persistence.py` | Pas de tamper-evidence cryptographique |
| Gestion utilisateurs/tenants | — | Non (scripts ponctuels non versionnés) | — | Section 7bis, 17 |

## 15. Fonctionnalités déjà implémentées

Auth JWT + cookie httpOnly ; RBAC 3 rôles (partiellement différencié) ;
isolation multi-tenant schema-per-tenant + revalidation défensive ;
pipeline détection → scoring CLI ; dashboard lecture seule ; graphe
Neo4j isolé par tenant ; fermeture d'alerte + audit atomique et
immuable par privilège PostgreSQL réel ; multilinguisme posé (mécanisme
`t()`, français seul livré).

## 16. Fonctionnalités partielles

- RBAC : rôles définis, quasi non différenciés hors fermeture d'alerte.
- Audit : immuabilité applicative + privilège réelle, pas de tamper-evidence cryptographique.
- Multilinguisme : mécanisme posé, `ADR-001` référencé mais absent du dépôt (section 20).

## 17. Fonctionnalités manquantes

- Gestion des utilisateurs et des tenants via interface — actuellement scripts ponctuels non committés (section 7bis).
- Consultation des transactions brutes depuis le dashboard.
- Distinction entre absence réelle de résultats Neo4j et indisponibilité du service — un fragment vide aujourd'hui ne dit pas lequel des deux cas s'est produit ; risque de confiance pour un analyste qui interpréterait un silence de panne comme un silence d'absence de réseau.
- Politique de rétention et gouvernance des données (transactions, alertes, audit) — durée de vie, purge, responsable — totalement absente du modèle actuel.
- Assignation d'une alerte à un analyste nommé — non implémenté ; sans risque tant qu'un seul analyste existe, devient un risque de double traitement invisible dès qu'il y en a plusieurs.
- Différenciation fonctionnelle admin/analyst (différée par choix, section 4).

## 18. Futures capacités [FUTUR]

RAG (LlamaIndex/ChromaDB), Ollama/Mistral, PQC (Kyber/Dilithium — dont
la tamper-evidence de l'audit), Redis/Celery, mémoire criminelle
collective inter-États, notifications citoyens, SOUVERAIN-ID complet,
différenciation avancée des rôles.

**Prometheus/Grafana** : traité séparément — capacité transverse
**indépendante** des autres (aucune dépendance vers la gestion des
utilisateurs ou l'identité), potentiellement réalisable avant le reste
du transverse, mais sans en faire une priorité immédiate.

## 19. Candidats potentiels pour futures briques

Aucune décision de création n'est prise ici.

- **Gestion des utilisateurs et tenants** : analyse ci-dessus (section 7bis) conclut à une extension des Briques 1 et 2, pas une nouvelle brique — mentionné ici seulement pour mémoire du raisonnement, pas comme candidat retenu.
- **Opérateur plateforme (cross-tenant)** : si la gouvernance de création de tenant devait un jour dépasser le CLI, ce serait un concept réellement nouveau (aucun rôle actuel n'est cross-tenant) — candidat sérieux à une conception dédiée, pas une brique immédiate.

### Profils potentiels à étudier ultérieurement (pas des rôles officiels)
- *Superviseur* : pertinent si la différenciation admin/analyst devient un jour réelle.
- *Responsable conformité* : pertinent si un export de rapport signé (Dilithium) devient nécessaire pour CENTIF.

## 20. Questions à décider [OUVERT]

1. Faut-il concevoir le concept d'"opérateur plateforme" maintenant, ou rester en CLI-only pour la gouvernance des tenants tant qu'un seul tenant est actif ?
2. `ADR-001` : validé pour reconstruction rétroactive (voir section 21) — reste à l'écrire réellement, action non exécutée par ce document.
3. Faut-il un état intermédiaire d'alerte distinct (au-delà du simple motif de fermeture `en_cours_investigation`) si le besoin de "poursuivre sans fermer" devient concret ?
4. Politique de rétention des données : à qui revient cette décision (le fondateur seul, ou une contrainte réglementaire externe à consulter d'abord — BCEAO, loi 2019-33 Niger) ?

## 21. Décisions actées lors de cette session de modélisation

- **ADR-001** : à recréer rétroactivement, en indiquant honnêtement qu'il s'agit d'une reconstruction d'une décision déjà appliquée (non encore exécuté — action de suivi, hors périmètre de ce document).
- **Admin/Analyst** : non différenciés pour l'instant ; différenciation explicitement reportée jusqu'à l'apparition d'un besoin métier concret (pas un oubli).
- **Gestion des tenants/utilisateurs** : provisioning de tenant = extension de la Brique 1 ; gestion des utilisateurs/rôles = extension de la Brique 2 ; pas de nouvelle brique dédiée. Gouvernance de création de tenant à analyser avant toute implémentation (section 7bis).
- **Positionnement institutionnel** : SOUVERAIN-OS formalisé comme outil d'aide à la décision et d'investigation, décision humaine finale obligatoire, aucune conclusion automatique — traité comme invariant architectural (section 10), pas comme simple description.
- **Trois manques ajoutés au modèle** : distinction silence Neo4j (panne vs absence réelle), politique de rétention/gouvernance des données, future gestion de l'assignation des alertes.
- **Reportés explicitement** : PQC, RAG/Ollama, mémoire criminelle inter-États, notifications citoyens, différenciation avancée des rôles.
- **Prometheus/Grafana** : capacité transverse indépendante, réalisable avant le reste du transverse si utile, sans urgence.

---

## Avis architectural

### Ce qui est déjà solide
La mécanique RBAC + authentification, l'isolation multi-tenant
(schema-per-tenant + revalidation défensive du JWT contre l'état actif
du tenant), l'immuabilité de l'audit par privilège PostgreSQL réel
(pas une simple discipline de code), et la fermeture atomique
d'alerte. Au-delà du code lui-même, la discipline de test du projet
est elle-même une force réelle : chaque brique a révélé de vrais bugs
en conditions réelles (fuite de pool, cache de requêtes préparées
invalidé, confusion entre deux causes d'erreur identique) — c'est le
signe d'une rigueur qui tient, pas d'une couverture cosmétique.

### Risques architecturaux actuels
1. **Ambiguïté du silence Neo4j** — le risque le plus concret à court terme. Un analyste qui lit "Aucun résultat" ne peut pas distinguer une vraie absence de réseau d'une panne du service. Pour un outil d'investigation, cette ambiguïté a un coût de confiance direct.
2. **Provisioning de tenant informel** — écart entre le principe fondateur ("ajouter un pays = ajouter un tenant, zéro ligne de code") et la réalité actuelle (script SQL manuel, `bootstrap_tenant_ne.sql`). Pas un bug, mais un écart entre narratif et code qu'un audit technique externe relèverait.
3. **Risque de sur-vente du niveau de garantie de l'audit** — l'immuabilité actuelle est réelle mais applicative/par privilège, pas cryptographique. Vigilance sur le vocabulaire employé face à un tiers (régulateur, investisseur) tant que la PQC n'existe pas.
4. **Absence totale de modèle de rétention** — non bloquant au volume actuel, mais c'est typiquement le genre de question qu'un régulateur (BCEAO) posera un jour, et qui est plus coûteuse à retrofitter qu'à anticiper.

### Ordre recommandé des prochaines étapes, et pourquoi

1. **Validation de ce document** par le fondateur — préalable à tout le reste.
2. **Gestion des utilisateurs et tenants** (extensions Briques 1 et 2), en priorité haute — pas pour une raison architecturale abstraite, mais parce que c'est concrètement la seule chose qui empêche aujourd'hui un usage réel par quelqu'un d'autre que le fondateur (un compte se crée aujourd'hui par script ponctuel non versionné). Inclut la résolution de la question de gouvernance de tenant (section 7bis) avant tout code.
3. **Résolution des trois manques identifiés** (section 17) qui sont peu coûteux et réduisent un risque réel : distinction silence Neo4j, ébauche de politique de rétention (même minimale), réflexion sur l'assignation d'alerte — aucun des trois ne nécessite d'attendre les capacités transverses.
4. **Capacités transverses**, avec une nuance sur leur ordre interne plutôt qu'un bloc unique : Prometheus/Grafana n'a aucune dépendance vers l'identité ou la gestion des utilisateurs et pourrait avancer en parallèle du reste sans coût particulier ; PQC dépend réellement de SOUVERAIN-ID et a une bonne raison structurelle d'attendre après les extensions ; RAG, mémoire criminelle inter-États et notifications citoyens n'ont pas de dépendance technique bloquante mais représentent un effort de conception substantiel, cohérent avec un report complet.

Cet ordre n'est pas une compétition entre briques mais une lecture de
dépendances réelles et de risques concrets — la seule urgence
opérationnelle véritable est la gestion des comptes, tout le reste
peut attendre sans coût caché.
