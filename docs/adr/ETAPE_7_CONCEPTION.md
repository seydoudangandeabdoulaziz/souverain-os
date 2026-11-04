# SOUVERAIN-OS — Étape 7 : Sécurité IA/RAG (conception)

**Statut : PROPOSÉ — en attente de relecture et de validation par le fondateur.**
**Nature : conception uniquement. Aucun code, aucun test, aucune migration, aucune modification de fichier du dépôt.**
**Rédigé le : 4 novembre 2026, à la demande explicite du fondateur (Seydou Dangande Abdoul Aziz).**
**ADR associé : `docs/adr/ADR-008-securite-ia-rag.md` (statut Proposé).**

Ce document ne passe **jamais** l'étape 7 à VALIDÉE. La validation finale appartient exclusivement au fondateur (`avancement.md`).

---

## 1. Objet et périmètre

Définir, **avant toute implémentation de l'étape 8 (RAG)**, le cadre de sécurité de l'IA locale étendue à une recherche documentaire : menaces, exigences, corpus et provenance, isolation multi-tenant, décisions structurantes, mémoire, dépendances, distinction MVP / Vision.

Intègre aussi les quatre réserves distinctes laissées ouvertes par la 6b (`docs/ETAPE_6B_BILAN.md` §6, point 10 ; ADR-007) :

| Réserve 6b | Traitée par |
|---|---|
| (a) limite de fréquence et de concurrence | D7 |
| (b) traçabilité de l'utilisateur | D8 |
| (c) déclenchement par un site tiers (GET, `SameSite=lax`) | D6 |
| (d) stockage et consultation des explications par l'auditeur | D9 |

**Hors périmètre de ce document :** toute implémentation, tout test, tout choix final de bibliothèque ou de modèle d'embeddings (D4 fixe la méthode, pas la référence), toute modification des Briques 4, 5 et 6, toute modification des fichiers couverts par le gel du lot v2.

---

## 2. Points à vérifier AVANT validation

Ces points n'ont pas pu être établis avec certitude. Aucune décision de ce document ne doit être considérée comme figée tant qu'ils ne sont pas levés.

| # | Point | État | Action attendue |
|---|---|---|---|
| **V1** | **Référence juridique nigérienne.** Le document fondateur cite « Loi 2019-33 Niger (protection données) ». | **Probablement erronée pour la protection des données.** Recoupement web du 4 novembre 2026 (sources secondaires, **non officielles**) : la loi 2019-33 du 3 juillet 2019 est la loi **portant répression de la cybercriminalité**. La protection des données relevait de la loi **2017-28 du 3 mai 2017** (modifiée par la loi 2019-71 du 24 décembre 2019). Plusieurs sources secondaires indiquent qu'elle a été **abrogée et remplacée par la loi 2022-59 du 16 décembre 2022** (modifiée par la loi 2023-31 du 4 juillet 2023 et par des ordonnances de 2024) ; ce point reste à confirmer sur le texte officiel. | Vérifier sur le Journal officiel ou le site de la HAPDP quel texte est en vigueur, puis corriger la source de référence **par décision explicite du fondateur** (`01_DOCUMENT_REFERENCE_FONDATEUR.md` n'est pas modifié ici). Aucun texte juridique n'est indexé avant cette vérification (S1, S12). |
| **V2** | **Visibilité publique du dépôt.** | **Non résolu.** Le clone et le `fetch` de `https://github.com/seydoudangandeabdoulaziz/souverain-os` ont réussi **sans aucune authentification** depuis l'environnement de travail de l'IA, le 4 novembre 2026. Les notes de projet indiquaient un dépôt privé. L'API GitHub n'a pas pu confirmer l'indicateur de visibilité (limite de débit atteinte). | Confirmer dans les paramètres GitHub (ou par une session de navigateur non connectée) si la visibilité publique est **voulue**. Si oui, noter que ce document (modèle de menaces compris) est lisible publiquement ; si non, passer le dépôt en privé. Décision D10. |
| **V3** | Licences et droits de redistribution des rapports du corpus (GIABA, UNODC, GAFI/FATF, BCEAO). | Non vérifié. | Vérifier source par source avant ingestion (champ `licence` du manifeste, §6). |
| **V4** | ChromaDB en mode embarqué : modèle d'isolation réel (la notion de tenant de Chroma ne constitue pas, à ma connaissance, une barrière d'authentification en mode embarqué), mode de sérialisation sur disque, version à figer. | Non vérifié dans la documentation de la version qui sera retenue. | Vérification en début d'étape 8, avant toute décision de version. |
| **V5** | Modèle d'embeddings : licence, taille mémoire, qualité sur le français. | Non mesuré. | Mesure en étape 8, avant de figer (D4). |
| **V6** | L'application tourne-t-elle dans **un seul processus** ? Condition de validité d'un sémaphore en mémoire (D7). | Non vérifié (appel `uvicorn.run` dans `souverain_app/cli.py` lu, nombre de processus non confirmé). | Confirmer ; sinon D7 bascule sur un compteur partagé en base. |
| **V7** | Mémoire de l'application FastAPI et de la recherche vectorielle. | **Jamais mesurée** (§12 : estimations). | Mesurer avant la première brique de l'étape 8. |
| **V8** | Baseline du document fondateur « latence RAG < 2 s ». | **Incompatible avec une génération** (explication 6b : 8 à 12 s à chaud, ~50 s à froid). Tenable pour la **recherche seule**. | À acter par le fondateur : la baseline porte sur la recherche, pas sur une génération. |
| **V9** | Documentation en retard sur le code. | Le commit `d96d7c6` (2 novembre 2026 : indicateur de chargement, mot de passe de démo aléatoire, garde-fou du gel) n'est pas reflété dans `docs/ETAPE_6B_BILAN.md` §6 (points 8 et 11 encore listés ouverts) ni dans `avancement.md`. | Mise à jour documentaire à décider séparément (§17). |
| **V10** | Lecture des ADR. | Les sections « Décision » des ADR-001, 003, 004, 005 et 007 ont été relues. **ADR-000, 002 et 006 n'ont pas été relus intégralement.** | Le fondateur signale toute contradiction avec ces trois ADR. |

---

## 3. État de référence (preuves)

- `git log` : `HEAD = origin/main = 69ce508` (« docs: roadmap a jour… étape 6b validée »). Historique 6b présent : validation `2028668`, autorisations `312e51a`, gel du lot v2 `0ab1001`, résultats `1006e30`, indicateur de chargement `d96d7c6`.
- Prochain numéro d'ADR disponible : **ADR-008** (`docs/adr/` contient ADR-000 à ADR-007, vérifié sur `origin/main`).
- Gel du lot v2 : `docs/etape_6b_donnees/gel_v2.json` (contrôleur, traductions `fr.py`, empreinte du prompt système, options, format, `lot_v2.json`, `termes_interdits_v1.json`). Le garde-fou `tests/test_gel_lot_v2.py` existe.
- Dans le code lu : aucun CORS, aucun contrôle `Origin` / `Sec-Fetch-Site` ; cookie de session `samesite="lax"` (Brique 7) ; cookies CSRF de la Brique 8 et de la gouvernance en `samesite="strict"` ; `/alertes/{id}/expliquer` est un **GET** protégé par `require_role` ; l'identité est lue pour le RBAC puis **non conservée** ; Ollama lié à `127.0.0.1`, `OLLAMA_NUM_PARALLEL=1`, `OLLAMA_MAX_LOADED_MODELS=1`.
- Aucun code RAG dans le dépôt (seules des mentions documentaires).
- **Non prouvé par cette conception :** l'exécution des tests (aucun Docker disponible). Les chiffres de la suite (486 réussis) restent ceux annoncés par le fondateur.

---

## 4. Invariants conservés et ce qui change

**Conservés (6b, sections 8 et 9 des décisions verrouillées) :**
IA locale uniquement (Ollama), à la demande, hors chemin critique de détection ; Briques 4, 5 et 6 déterministes et **intouchées** ; aucune décision automatique ; aucun SQL ni Cypher généré ; aucun partage de données entre tenants ; la décision humaine n'est jamais remplacée ; tout chiffre affiché est rattaché à des faits structurés ; aucun texte utilisateur en dur (ADR-001).

**Ce qui change :** la 6b est sûre par construction parce que le modèle ne voit **aucun fait**. Avec un RAG, du **texte documentaire externe** peut entrer dans le contexte du modèle. La conception vise à conserver l'esprit de l'ADR-007 : le modèle ne rédige rien, il ne peut ni inventer ni modifier ce qui est affiché.

**Conséquence documentaire :** les sections 8 et 9 des décisions verrouillées affirment « sans RAG » pour l'explication des alertes. Le RAG est une **fonction nouvelle et distincte** ; il ne modifie pas l'explication 6b. Une nouvelle section 10 des décisions verrouillées devra être proposée à la validation du fondateur (modification réservée au fondateur ; non faite ici).

---

## 5. Compatibilité avec les ADR existants et avec le gel du lot v2

| Référence | Compatibilité | Remarque |
|---|---|---|
| **ADR-001** (multilinguisme) | Compatible | Aucun texte en dur ; langue dérivée de `country_code`. Le français seul est livré. Traduction haoussa / zarma : Vision. |
| **ADR-003** (event trigger d'intégrité) | Compatible, **portée limitée** | Le trigger ne protège que `alertes` et `detections`. Une nouvelle table (D9) n'est pas couverte automatiquement : sa protection repose sur un rôle à privilèges restreints (insertion seule), motif de la Brique 8. |
| **ADR-004** (modèle LLM) | Compatible | Ministral 3 8B inchangé. |
| **ADR-005** (provisionnement audit B8) | Compatible, **leçon appliquée (S10)** | Toute nouvelle table par tenant et tout nouveau rôle sont créés par un provisionnement diagnostiqué et idempotent, **pas seulement par une migration** : un tenant créé après coup n'avait rien. |
| **ADR-006** (déploiement Ollama) | Compatible (relecture partielle, V10) | Image figée par digest, `127.0.0.1`, `NUM_PARALLEL=1` inchangés. |
| **ADR-007** (explication 6b) | Compatible | Les deux fonctions coexistent. Le RAG n'appelle pas `explication_ia.py` pour autre chose qu'un éventuel **import en lecture** ; il ne le modifie pas. |
| **Gel du lot v2** | **Respecté** | Aucun fichier gelé n'est modifié : `explication_ia.py`, `traductions/fr.py`, prompt système, options, `lot_v2.json`, `termes_interdits_v1.json`. Les **nouveaux textes** (refus, messages RAG) vont dans un **nouveau catalogue** propre au RAG (même mécanisme `t()` isolé que la Brique 8, ADR-001), jamais dans `fr.py`. Le **journal de traçabilité** (D8) est un journal **distinct**, émis par la route : le journal des replis vit dans `explication_ia.py` (gelé). |
| **Briques 4, 5, 6** | Intouchées | Le RAG ne lit ni leurs sorties internes ni leurs tables en MVP (S5). |
| **Suite de tests existante** | **Impact identifié** | D6 (GET → POST) obligera à adapter les tests de la route d'explication (`tests/test_explication_routes.py`, `test_explication_roles.py`, `test_explication_indicateur.py` notamment) lors de l'étape 8. Ce n'est pas une modification du lot gelé (le gel n'empreinte pas ces tests), mais c'est une **correction post-validation de la 6b** à tracer comme telle (à la manière de l'ADR-005 pour la Brique 8). |

---

## 6. Modèle de menaces

### 6.1 Actifs

1. Faits d'alerte et données tenant (comptes, scores, décisions humaines).
2. Corpus documentaire et son manifeste de provenance.
3. Capacité de calcul locale (une génération à la fois, CPU seul).
4. Piste d'audit (journaux, explications éventuellement stockées).
5. Confiance de l'analyste dans ce qui s'affiche (invariant : un indice d'investigation n'est pas une preuve).

### 6.2 Acteurs

Insider corrompu (CENTIF, banque, opérateur), compte `analyst`/`admin` compromis, site tiers malveillant ciblant un utilisateur connecté, source documentaire falsifiée ou compromise, acteur étatique hostile (espionnage, empoisonnement), erreur humaine (filtre oublié, corpus mal étiqueté).

### 6.3 Menaces

| # | Menace | Gravité | Surface | Parade principale |
|---|---|---|---|---|
| **T1** | Injection de prompt indirecte : un passage du corpus contient des instructions. | Haute | Nouvelle avec le RAG | Contrat de sortie strict (permutation exacte d'identifiants), affichage verbatim par le serveur, le modèle n'exclut jamais un passage (D1, S3) |
| **T2** | Fuite inter-tenant par la recherche (filtre oublié, collection partagée). | Haute | Nouvelle si du contenu de tenant est indexé | Collections séparées, point d'accès unique, tests adversariaux (D3, S4) |
| **T3** | Empoisonnement du corpus (document falsifié, source douteuse). Un corpus public partagé empoisonne **tous** les tenants. | Haute | Nouvelle | Manifeste, empreintes, validation humaine par source, ingestion par commande opérateur (D5, S1, S6) |
| **T4** | Fausse autorité : loi ou typologie inventée, mal attribuée ou périmée, prise pour une preuve. | Haute | Nouvelle | Aucune affirmation sans passage identifiable ; affichage verbatim avec source ; mention « indice, pas preuve » (S2, S9) |
| **T5** | Contenu synthétique pris pour un cas réel. | Moyenne | Propre au projet (Bloc 8 du fondateur) | Drapeau `synthetique` obligatoire et affiché (S1) |
| **T6** | Épuisement de ressources : une requête à la fois, ~8–12 s à chaud, ~50 s à froid, file sans borne. | Moyenne | Réelle aujourd'hui | Sémaphore global, quotas, cache (D7) |
| **T7** | Déclenchement par un site tiers : `SameSite=lax` envoie le cookie sur une navigation de haut niveau en GET. | Faible aujourd'hui ; **élevée dès que la traçabilité existe** (une génération non voulue serait attribuée à la victime) | Réelle, non testée | POST + CSRF double-submit (D6) |
| **T8** | Absence de traçabilité : on ignore qui a demandé quoi. | Moyenne | Réelle | Journal dédié, refus compris (D8) |
| **T9** | Explications stockées : faits modifiés depuis (l'alerte est mise à jour en place), relecture hors contexte. | Moyenne | Si stockage décidé | Instantané des faits + versions + empreinte du texte (D9) |
| **T10** | Chaîne d'approvisionnement : poids de modèles, bibliothèques, sérialisation. | Moyenne | Partiellement couverte (images Ollama figées par digest) | Versions et empreintes figées ; aucune désérialisation de données non fiables (S11) |
| **T11** | Store vectoriel lisible sur disque par un insider. | Moyenne | Nouvelle | Droits système restreints ; chiffrement au repos en Vision (étape 11) |
| **T12** | Le RAG devient un canal de partage inter-États. | Haute (Vision) | Étape 12 | Le RAG ne transporte jamais de mémoire criminelle ; corpus public partagé seulement |
| **T13** | Suppression de contenu pertinent par un modèle influencé (le modèle « oublie » un passage). | Moyenne | Spécifique à D1(b) | Le serveur impose l'affichage de **tous** les passages récupérés ; le modèle ne fait qu'ordonner |

### 6.4 Risques résiduels connus, hors périmètre de cette étape

- `/health` et `/metrics` ne sont pas authentifiés (décision antérieure, documentée dans `main.py`) ; `/metrics` révèle des volumes.
- Un compte `souverain_admin` (superutilisateur) peut contourner les mécanismes de détection (limite déjà reconnue par l'ADR-003).

---

## 7. Exigences de sécurité

| ID | Exigence |
|---|---|
| **S1** | Aucun document n'entre dans le corpus sans entrée complète dans le **manifeste de provenance** (§8), y compris le drapeau `synthetique`. |
| **S2** | Toute affirmation issue du RAG pointe vers un passage identifiable (source, version, page). Pas de passage, pas d'affirmation. |
| **S3** | Un passage est une **donnée**, jamais une instruction : encadré, échappé à l'affichage, jamais concaténé à une consigne. |
| **S4** | Toute recherche passe par **un seul point d'accès** qui impose le périmètre (corpus public, puis éventuellement corpus du tenant). |
| **S5** | **Aucune donnée opérationnelle** (transactions, alertes, détections, décisions humaines) n'est indexée ni envoyée au moteur de recherche en MVP. La requête ne contient que le vocabulaire fermé des types de patterns. |
| **S6** | L'**ingestion** est une commande explicite d'opérateur (CLI). Aucune route web ne déclenche l'ingestion. |
| **S7** | Toute action coûteuse est un **POST** protégé par CSRF, réservée aux rôles autorisés, soumise à limite de fréquence et de concurrence. |
| **S8** | Chaque déclenchement, **refus compris**, est journalisé avec l'identifiant pseudonyme de l'utilisateur. Jamais de texte généré, d'adresse e-mail, de contenu de passage, ni de valeur de requête dans les journaux. |
| **S9** | Le texte affiché est écrit par le serveur ou cité **tel quel** avec sa référence. Le modèle n'écrit aucune phrase. |
| **S10** | Toute nouvelle table par tenant et tout nouveau rôle sont créés par un **provisionnement** diagnostiqué et idempotent (ADR-005), pas seulement par une migration. |
| **S11** | Versions des bibliothèques et du modèle d'embeddings **figées** ; aucune désérialisation de contenu non fiable ; données du store reconstruisibles depuis le corpus et le manifeste. |
| **S12** | Aucun texte juridique n'est indexé tant que sa **référence en vigueur** n'est pas vérifiée (V1). |
| **S13** | Aucun texte utilisateur en dur ; nouveaux textes dans un **catalogue propre au RAG** (ADR-001) ; `traductions/fr.py` du lot v2 n'est jamais modifié sans lot v3. |
| **S14** | Le modèle n'est introduit dans le RAG que si un **lot de validation dédié** démontre un gain mesuré (leçon de la réserve 2 de la 6b). |

---

## 8. Corpus RAG : sources et provenance

### 8.1 Trois classes

| Classe | Contenu | Statut |
|---|---|---|
| **A — Référentiel public** | Rapports et typologies (GIABA, UNODC, GAFI/FATF), directives BCEAO, textes légaux. Partagé entre tenants, lecture seule, non sensible. | **MVP** |
| **B — Corpus propre à un tenant** | Procédures internes, notes d'investigation. | **Vision** (isolation décrite au §10) |
| **C — Données opérationnelles** | Transactions, alertes, détections, décisions. | **Exclue** (S5) |

### 8.2 Sources initiales candidates (issues du Bloc 8 du document fondateur)

| Source | Classe | État de vérification |
|---|---|---|
| Rapports GIABA (typologies régionales) | A | Licence et version à vérifier (V3) |
| Rapports UNODC (criminalité financière, Afrique subsaharienne) | A | Licence et version à vérifier (V3) |
| Typologies GAFI/FATF, Afrique de l'Ouest, Mobile Money | A | Licence et version à vérifier (V3) |
| Directives BCEAO sur la surveillance des transactions Mobile Money | A | Existence, version, licence à vérifier |
| Texte nigérien de protection des données | A | **Référence à corriger : V1 (2022-59 vs 2017-28 vs « 2019-33 »)** |
| Loi 2019-33 (cybercriminalité), modifiée | A | Candidate **sous son vrai intitulé** ; version consolidée à vérifier |
| Cadres UEMOA membres (ex. loi uniforme 2008-48 sur les instruments électroniques de paiement, citée dans le préambule de la loi 2019-33) | A | Candidate, à vérifier |
| Données synthétiques (patterns hawala simulés) | A, **drapeau `synthetique`** | Toujours marquées, affichées comme telles (T5) |

### 8.3 Manifeste de provenance (une entrée par source)

Identifiant de source ; titre ; éditeur et URL d'origine ; date de publication ; date d'acquisition ; **empreinte SHA-256 du fichier brut** ; version ; **licence ou droit de réutilisation** ; langue ; classe ; drapeau `synthetique` ; validé par ; date de validation.

- Le manifeste est **versionné dans Git** ; toute modification est un commit relisible.
- Chaque passage indexé porte l'identifiant de source et la page.
- **MVP** : empreinte + validation humaine par source. **Vision** : signature du manifeste (ML-DSA, étape 11).
- Le magasin vectoriel est **reconstruisible** depuis le corpus et le manifeste (S11) : on ne sauvegarde pas l'index comme une vérité.

---

## 9. Architecture conceptuelle (MVP)

```text
Alerte (déjà en base, lecture seule)
   │  types de patterns (vocabulaire fermé)  ← seule information transmise
   ▼
Requête canonique construite par le SERVEUR (D2)
   ▼
Point d'accès unique à la recherche (S4)  ── collection publique (classe A)
   ▼
k passages + références (S2)
   ▼
[Lot 8a : affichage verbatim, sans modèle]                    ← première livraison
[Lot 8b, seulement si gain mesuré (S14) : le modèle ordonne les k identifiants ;
 contrat = permutation exacte, tout écart → repli sur l'ordre de pertinence]
   ▼
Affichage : passages verbatim + source + mention « indice, pas preuve »
   ▼
Journal de traçabilité (D8) : utilisateur, alerte, issue — sans contenu
```

Points de passage uniques (analogie : un seul guichet, pas dix portes) : un module d'accès à la recherche (S4), une commande d'ingestion (S6), un contrôleur de déclenchement (rôle + CSRF + quota + concurrence).

Avec cinq types de patterns fermés, l'ensemble des requêtes canoniques est **fini** : la qualité de la recherche peut être évaluée de façon exhaustive, ce qui rend le lot de validation du RAG nettement plus simple que celui d'une question libre.

---

## 10. Isolation multi-tenant du RAG (D3)

- **Classe A** : une collection **publique** unique, en lecture seule pour tous les tenants. Le risque principal n'est pas la fuite entre tenants mais l'**empoisonnement partagé** (T3) : la provenance tient lieu d'isolation.
- **Classe B (Vision)** : **une collection par tenant**, séparée de la collection publique, fusion **côté serveur**. Pas de filtre `tenant_id` dans une collection commune : un filtre oublié ne peut pas fuiter.
- Un **module d'accès unique** impose le périmètre ; il est le seul à connaître les noms de collections (même discipline que `garde_isolation.py` de la Brique 6).
- **Tests adversariaux requis à l'étape 8** (à la manière de `test_isolation_tenant.py`) : deux tenants avec des contenus et identifiants identiques ; aucune recherche d'un tenant ne retourne un passage de l'autre ; ajout d'un tenant = création de collection, sans modification de code.
- Le nommage reste la seule barrière en mode embarqué (V4) : d'où le point d'accès unique, les droits système restreints sur le répertoire du store et, en Vision, le chiffrement au repos.

---

## 11. Décisions

**Légende :** ✅ validée par le fondateur (4 novembre 2026) · 🟡 proposée, à valider.

### D1 ✅ — Rôle du RAG : sélection d'identifiants (option b), livraison initiale en recherche seule (option a)

- **Retenu :** le serveur affiche les passages **verbatim** avec leur source. Un modèle éventuel ne peut qu'**ordonner** les k passages déjà récupérés (permutation exacte des identifiants), jamais en exclure ni en rédiger.
- **Précision importante :** pour ordonner, le modèle doit **lire** le texte des passages (corpus public, non sensible), contrairement à la 6b où il ne voyait que des identifiants. C'est un assouplissement **assumé et borné** : le modèle ne reçoit jamais de fait de tenant (S5), et sa sortie est contrainte et validée (T1, T13).
- **Livraison :** lot 8a = recherche seule, **sans modèle**. Le modèle n'entre qu'au lot 8b si un lot de validation prouve un gain mesuré (S14).
- **Écartées :** (a) seule définitivement — valeur limitée mais valable comme premier lot ; (c) rédaction libre contrôlée — exige un contrôleur de fidélité et expose à T1/T4 : **Vision**.
- **Risques résiduels :** gain de lisibilité non démontré (même limite que la 6b) ; variation d'ordre non expliquée (réserve 1 de la 6b) susceptible de réapparaître.

### D2 🟡 — Origine de la requête : construite par le serveur

- Requête dérivée des **types de patterns** de l'alerte, via une table de requêtes canoniques. Aucune question libre de l'utilisateur en MVP.
- **Avantages :** surface d'injection directe nulle ; requêtes finies, donc testables exhaustivement ; aucune donnée de tenant n'atteint le moteur de recherche (S5).
- **Risque :** utilité limitée aux alertes existantes. **Question libre : Vision**, avec filtrage d'entrée, quotas renforcés et journalisation.

### D3 ✅ — Isolation : une collection par tenant + une collection publique

Voir §10. **Écartées :** (A) collection globale + filtre `tenant_id` (isolation purement applicative) ; (C) un store par tenant (lourd, contraire à « ajouter un pays = ajouter un tenant ») ; (D) pgvector dans PostgreSQL par schéma de tenant — conserve l'isolation déjà prouvée mais **contredit la stack imposée (ChromaDB)** et exigerait une décision explicite de changement (cahier des charges §3). D reste **réouvrable** si le fondateur préfère un seul moteur de stockage.

### D4 🟡 — Modèle d'embeddings : dans l'application, mesuré avant de figer

- **Pourquoi pas dans Ollama :** avec `OLLAMA_MAX_LOADED_MODELS=1`, chaque embedding déchargerait Ministral, soit jusqu'à ~50 s de rechargement à froid. Avec `MAX_LOADED_MODELS=2`, de la RAM est consommée en permanence.
- **Retenu (proposition) :** embeddings calculés **dans l'application**, modèle **local** et **multilingue incluant le français**, version et licence figées (S11).
- **À mesurer (V5) :** RAM, latence CPU, qualité de recherche sur les 5 requêtes canoniques. La qualité en haoussa et en zarma n'est pas garantie : **Vision**.
- **Règle opérationnelle :** l'ingestion (calcul massif d'embeddings) ne s'exécute pas pendant que le modèle de génération sert, pour éviter la contention CPU.

### D5 🟡 — Gouvernance du corpus : ingestion par commande opérateur

- Commande CLI (S6), manifeste obligatoire (S1), **validation du fondateur par source**, empreinte vérifiée à l'ingestion, rejet de toute source sans licence documentée (V3).
- Réingestion complète possible depuis le manifeste (S11). Journal d'ingestion (source, empreinte, nombre de passages, date, opérateur déclaré — même distinction acteur déclaré / acteur authentifié que la gouvernance CLI).

### D6 ✅ — Déclenchement : POST + CSRF double-submit

- **Retenu :** la génération (et, plus tard, toute action coûteuse du RAG) devient un **POST** protégé par le motif déjà éprouvé en Brique 8 (cookie `SameSite=strict` + champ caché). Le fragment qui affiche le bouton reste un GET **sans effet**.
- **Pourquoi :** ferme T7 et garantit que la traçabilité (D8) ne peut pas attribuer à un utilisateur une action qu'il n'a pas faite.
- **Périmètre de changement (étape 8, non fait ici) :** `explication_routes.py` (non gelé), le fragment du bouton, les tests de la route. **Aucun fichier gelé.** À tracer comme **correction post-validation de la 6b**.
- **Point d'implémentation à examiner :** `souverain_app` importe déjà plusieurs briques ; la réutilisation du mécanisme CSRF de la Brique 8 par l'assemblage doit être confirmée sans créer de dépendance entre briques (la Brique 2 a, elle, **dupliqué** ce mécanisme pour ne pas inverser son graphe de dépendances).
- **Écartées :** (b) rester en GET avec contrôle `Sec-Fetch-Site` (dépend du navigateur) ; (c) accepter le risque.

### D7 🟡 — Limite de fréquence et de concurrence

- **Sémaphore applicatif global à 1** pour tout appel à Ollama (explication 6b et éventuel lot 8b), aligné sur `NUM_PARALLEL=1` : les requêtes en excès reçoivent un **refus rapide** (avec `Retry-After`) au lieu d'attendre dans une file sans borne.
- **Quota** par utilisateur et par tenant. **Valeurs à calibrer à l'étape 8 sur les mesures** (8–12 s à chaud) ; aucune valeur n'est figée ici.
- **Cache** par empreinte (faits + versions) : à `temperature 0` et `seed 42`, une même entrée donne la même sortie ; le cache réduit fortement la charge. L'invalidation suit l'empreinte des versions.
- **Stockage des compteurs :** en mémoire si l'application est mono-processus (V6) ; sinon table PostgreSQL. **Redis/Celery (étape 9, conditionnelle) n'est pas une dépendance.**
- **Limite connue :** un sémaphore en mémoire est perdu au redémarrage ; acceptable pour un plafond de ressources.
- Refus et messages : catalogue propre (S13).

### D8 🟡 — Traçabilité de l'utilisateur

- **Journal JSON dédié**, émis par la **route** (pas par `explication_ia.py`, gelé) : horodatage ; tenant ; **identifiant utilisateur pseudonyme** (UUID) ; identifiant d'alerte ; action ; issue (`ok`, `repli` + cause, `refus_role`, `refus_csrf`, `refus_quota`, `refus_concurrence`) ; durée.
- **Jamais :** texte généré, adresse e-mail, contenu de passage, valeur de requête. Le critère C5 de la 6b interdit déjà l'identifiant de **compte** (compte surveillé) dans le journal des replis ; l'identifiant **utilisateur** est une notion distincte, ici explicitement autorisée.
- **Refus journalisés**, y compris les tentatives d'un `auditor`.
- **Évolution :** table par tenant en insertion seule (rôle dédié, motif B8) si D9 est retenue.

### D9 🟡 — Stockage et consultation des explications par l'auditeur

- **Proposition :** stocker un **instantané** — faits (au moment de la génération), ordre retenu, origine (modèle ou repli) et cause éventuelle, versions (digest du modèle, empreinte du prompt, du contrôleur, des traductions, version du lot), **empreinte SHA-256 du texte rendu**, utilisateur pseudonyme, horodatage. Le **texte n'est pas stocké** : il est reconstruit de façon déterministe par le code gelé, et l'empreinte permet de vérifier la fidélité.
- **Pourquoi un instantané :** l'alerte est mise à jour **en place** (UPSERT). Sans instantané, une relecture ultérieure montrerait d'autres faits : trompeur pour un audit (T9).
- **Contraintes :** table par tenant **en insertion seule**, rôle PostgreSQL dédié, **provisionnement diagnostiqué et idempotent** (S10, ADR-005) ; protection d'intégrité explicite (l'ADR-003 ne couvre pas cette table) ; durée de conservation à définir **après vérification du texte légal en vigueur (V1)**.
- **Repli si la reconstruction se révèle fragile** (gabarits modifiés par un futur lot v3) : stocker aussi le texte rendu. À arbitrer par le fondateur.
- **Lecture :** `auditor` et `admin` ; `analyst` voit ce qu'il a déclenché. Les droits exacts sont à confirmer à l'étape 8.
- **Positionnement : à décider.** L'ADR-007 indique que le stockage est « un chantier distinct, place non décidée ». Proposition : **sous-lot 8c**, après le RAG minimal. Aucune étape 6C n'est créée.
- **Écartées :** ne rien stocker (l'auditeur ne consulte pas) ; stocker le texte seul sans instantané (insuffisant, T9).

### D10 🟡 — Visibilité du dépôt

À trancher par le fondateur (V2). Recommandation de prudence : tant que la visibilité n'est pas confirmée comme voulue, traiter ce document et le modèle de menaces comme potentiellement **publics**.

---

## 12. Estimation mémoire sur 16 Go (budget de travail : 13 Go)

Mesures issues des campagnes du fondateur ; le reste est une **estimation à mesurer** avant toute brique (V5, V7).

| Composant | RAM | Origine |
|---|---|---|
| Ministral 3 8B (conteneur Ollama) | 6,3 à 6,6 Gio | **Mesuré** (pic campagne 6b : 6,284 Gio ; ADR-006 : 6,618 Gio ; écart non tranché) |
| PostgreSQL | ~0,15 Gio | **Mesuré** (étape 4a) |
| Neo4j | ~0,14 Gio au repos ; ~1,5 Gio sous charge (palier 50 000) | **Mesuré** (étapes 4a et 5) |
| Prometheus + Grafana | ~0,5 Gio | **Mesuré** (étape 4a) |
| Application FastAPI | ~0,3 Gio | **Estimation, jamais mesurée** |
| Magasin vectoriel (ChromaDB embarqué) | 0,3 à 0,8 Gio | **Estimation** : 10 000 à 100 000 passages × 1 024 dimensions × 4 octets = 40 à 410 Mo de vecteurs, plus l'index |
| Modèle d'embeddings dans l'application | 0,5 à 1,2 Gio | **Estimation** |

**Total estimé : ~9,6 à 11,1 Gio** sur 13, marge de 2 à 3,4 Gio. **Faisable en MVP**, plus serré qu'aujourd'hui. Mesures sur CPU seul. La concurrence ne multiplie pas la RAM (`NUM_PARALLEL=1`), elle multiplie l'attente. La mémoire de l'ingestion (pic temporaire) n'est pas incluse : elle s'exécute hors service (D4).

---

## 13. Dépendances avec les étapes 8 à 12

| Étape | Dépendance |
|---|---|
| **8 — RAG** | Consomme D1 à D9 et S1 à S14. Rien n'est implémenté avant validation. Lots proposés : **8a** recherche seule + corpus + isolation + POST/CSRF + quotas + journal ; **8b** (conditionnel, S14) ordonnancement par le modèle ; **8c** (à décider) stockage des instantanés. |
| **9 — Redis/Celery** | Non requise (D7). Pourrait apporter une génération asynchrone contre l'attente de ~50 s à froid ; reste conditionnelle à l'étape 5. |
| **10 — SOUVERAIN-ID complet** | La traçabilité utilise l'identifiant utilisateur pseudonyme existant ; aucune attente. |
| **11 — PQC** | Signature du manifeste et des exports (ML-DSA), chiffrement au repos du magasin vectoriel (T11). |
| **12 — Résilience inter-États** | Le corpus public partagé illustre ce qui peut circuler ; la mémoire criminelle ne transite jamais par le RAG (T12). |

---

## 14. MVP / Vision

| MVP (faisable seul) | Vision (équipe, long terme) |
|---|---|
| Classe A uniquement ; requêtes canoniques serveur ; recherche seule puis ordonnancement conditionnel ; POST + CSRF ; sémaphore + quotas + cache ; journal de traçabilité ; manifeste + empreintes ; instantané d'explication (8c, à décider) | Classe B (corpus de tenant) ; question libre avec filtrage ; rédaction libre contrôlée ; génération asynchrone ; signature du manifeste ; chiffrement au repos ; haoussa / zarma ; évaluation de la recherche sur un jeu étiqueté élargi ; bascule éventuelle vers un moteur unique (option D) |

---

## 15. Critères de validation de l'étape 8 (à prévoir, non implémentés ici)

- **Lot de validation RAG v1, distinct du lot 6b v2** : jamais de modification du lot v2 gelé.
- Évaluation de la recherche sur les requêtes canoniques (finies) ; passages attendus présents ; aucune citation sans source.
- Tests adversariaux d'isolation (deux tenants, mêmes identifiants), d'injection (passage contenant des instructions), de CSRF (POST sans jeton refusé), de quotas et de concurrence, de rôle (`auditor` refusé avant tout accès base ou modèle).
- Vérification que le journal ne contient aucun contenu interdit (S8).
- Rejeu du garde-fou `tests/test_gel_lot_v2.py` : aucune empreinte gelée ne change.
- Mesure de la RAM réelle (V7) et de la latence de recherche contre la baseline reformulée (V8).
- Vérifications manuelles dans un vrai navigateur pour `analyst`, `auditor` et `admin`.

---

## 16. Risques résiduels acceptés ou reportés

- Gain du modèle non démontré (S14) ; variation d'ordre non expliquée (6b).
- Mesures sur une seule machine, CPU seul.
- Corpus public partagé : un document empoisonné non détecté affecte tous les tenants ; la parade est humaine (validation par source), pas cryptographique, avant l'étape 11.
- Isolation par nommage en mode embarqué (V4).
- Superutilisateur PostgreSQL non contraint (ADR-003).
- `/health` et `/metrics` non authentifiés.

---

## 17. Mises à jour documentaires à prévoir (NON faites ici)

À décider séparément par le fondateur, après validation :

1. `avancement.md` : section Étape 7 ; reflet du commit `d96d7c6`.
2. `docs/ETAPE_6B_BILAN.md` §6 : points 8 et 11 (indicateur, mot de passe de démo) et réserves 10b, 10c, 10a en cours de traitement.
3. `06_ROADMAP_ET_BRIQUES.md` : ligne Étape 7.
4. `00_DECISIONS_VERROUILLEES.md` : **nouvelle section 10** (RAG et sécurité IA), modification réservée au fondateur ; correction éventuelle de la référence juridique (V1).
5. `docs/securite/README.md` : implications sécurité de l'étape 7.
6. `docs/adr/ADR-008-securite-ia-rag.md` : passage de « Proposé » à « Accepté » à la validation.
7. Trace de la **correction post-validation de la 6b** (D6) quand elle sera réalisée.

---

## 18. Journal de la conception

| Date | Événement |
|---|---|
| 4 novembre 2026 | Ouverture de l'étape 7 sur demande explicite. Vérification de l'état du dépôt (`69ce508`), lecture des documents de référence et des sections « Décision » des ADR. Orientations **D1, D3, D6 validées** par le fondateur. Rédaction de ce document et de l'ADR-008 (statut Proposé). |

**Aucune implémentation n'est autorisée avant la validation explicite de ce document par le fondateur.**
