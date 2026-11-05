# SOUVERAIN-OS — Étape 7 : Sécurité IA/RAG (conception) — révision 6

**Statut : CONCEPTION VALIDÉE par le fondateur le 4 novembre 2026**, exclusivement pour la conception et le périmètre fonctionnel et sécuritaire du MVP RAG. Les réserves restent applicables ; cette validation n'autorise pas l'étape 8.
**Nature : conception documentaire uniquement. Aucun code applicatif, test, migration, dépendance ou configuration RAG n'est implémenté.**
**Révision 6 du 4 novembre 2026**, après enregistrement de la validation du fondateur et approbation du protocole V8 comme référence expérimentale.
**ADR associé : `docs/adr/ADR-008-securite-ia-rag.md` (les propositions techniques non approuvées restent distinctes de la validation de la conception).**

> Emplacement des ADR : le dépôt les range dans **`docs/adr/`** (ADR-000 à ADR-007). Il n'existe pas de dossier `docs/architecture/decisions/` ; `docs/architecture/decisions.md` est un fichier unique distinct. L'ADR-008 conserve donc l'emplacement réel `docs/adr/`.

La validation finale de l'étape 7 appartient exclusivement au fondateur. Elle a été prononcée le 4 novembre 2026 pour la conception du MVP RAG et son périmètre fonctionnel et sécuritaire approuvé ; elle ne vaut pas autorisation d'implémenter l'étape 8.

**Statuts des décisions :**
- **D1 : MVP sans LLM** et **D3 : corpus public commun, sans collection privée par tenant dans le MVP** sont bornés par la section 10 des décisions verrouillées. **D6 : POST + CSRF** reste l'orientation validée pour les actions concernées.
- **D2 :** le principe de requête construite par le serveur depuis la liste fermée des types de patterns est approuvé par la section 10 ; le détail de la table de correspondance canonique reste technique et à préciser.
- **D4, D5, D7 et D10 : propositions soumises à arbitrage.**
- **D8 et D9 : propositions historiques conservées pour traçabilité, hors MVP et non autorisées.** Toute évolution future exige une décision distincte du fondateur.
- Les précisions techniques de D1 et D3 relatives aux évolutions futures, ainsi que celles de D6, ne sont pas toutes validées par la décision de périmètre ; leur statut est indiqué dans les sections concernées.

---

## 1. Objet et périmètre

Définir, **avant toute implémentation de l'étape 8 (RAG)**, le cadre de sécurité de l'IA locale étendue à une recherche documentaire : menaces, exigences, corpus et provenance, isolation multi-tenant, décisions, mémoire, dépendances, distinction MVP / Vision.

Intègre les quatre réserves distinctes laissées ouvertes par la 6b (bilan §6, point 10 ; ADR-007) :

| Réserve 6b | Traitée par |
|---|---|
| (a) limite de fréquence et de concurrence | D7 |
| (b) traçabilité de l'utilisateur | D8 |
| (c) déclenchement par un site tiers (GET, `SameSite=lax`) | D6 |
| (d) stockage et consultation des explications par l'auditeur | D9 |

**Hors périmètre :** toute implémentation ; le choix final de version de ChromaDB et du modèle d'embeddings ; toute modification des Briques 4, 5 et 6 ; toute modification des fichiers couverts par le gel du lot v2.

---

## 2. Registre des vérifications

| # | Point | État au 4 novembre 2026 |
|---|---|---|
| **V1** | Référence juridique nigérienne (protection des données) | **Partiellement confirmée, reste à vérifier sur texte officiel.** Voir §9.1. |
| **V2** | Visibilité du dépôt GitHub | **À confirmer par le fondateur.** Voir D10. Aucune intention n'est déduite. |
| **V3** | Licences et provenance des sources du corpus | **Vérifiées en partie** (§9.2). FATF et GIABA : autorisation écrite requise ; UNODC : usage non commercial avec attribution, usage commercial à clarifier ; BCEAO : **non vérifiée**. |
| **V4** | ChromaDB : isolation en mode embarqué | **Partiellement vérifié** (documentation officielle consultée, §11.D3). Version à figer et comportement exact à tester à l'étape 8. |
| **V5** | Modèle d'embeddings : licence, RAM, qualité en français | Non mesuré, non choisi. |
| **V6** | Nombre de processus de l'application | **Vérifié dans le code** : un seul processus aujourd'hui (§11.D7). Non garanti pour un déploiement futur. |
| **V7** | Mémoire de l'application, du magasin vectoriel, des embeddings | **Jamais mesurée** (§12). |
| **V8** | Baseline de performance du document fondateur | La cible approuvée est un p95 strictement inférieur à deux secondes pour la recherche seule. L'étape 7 valide le protocole ; la mesure réelle reproductible est effectuée au lot 8a de l'étape 8. |
| **V9** | Documentation en retard sur le code (`d96d7c6`, 2 novembre) | Constatée ; mise à jour à décider (§17). |
| **V10** | Lecture des ADR | **ADR-000, 002, 006 et 007 relus intégralement** ; ADR-001, 003, 004, 005 : sections « Décision » relues, relecture complète non faite. |
| **V11** | Écoute réseau de l'application | `uvicorn.run(host="0.0.0.0", …)` : l'application écoute sur **toutes les interfaces** (commentaire du code : « dev local uniquement, à restreindre en déploiement réel »). Voir §6.4 et A8. |
| **V12** | Ollama natif résiduel (ADR-006 §2 point 4) | Non vérifié : ni désinstallé ni vérifié (ADR-006 §8). Impact mémoire et port 11434 non mesurés. |

**Protocole de performance V8 — spécification de mesure du critère 9 :** mesurer sans LLM le temps entre la réception par le composant RAG du type de pattern fermé et la remise au service appelant des passages sourcés. La mesure inclut construction de la requête, calcul local de l'embedding, recherche vectorielle et vérification des références ; elle exclut l'aller-retour HTTP, l'affichage navigateur et toute génération LLM.

**Jeu et corpus :** exécuter exhaustivement les cinq types de patterns canoniques définis par le service, avec une requête canonique par type. Figer le corpus par identifiant de version et empreinte du manifeste ; consigner le nombre de documents et de passages, ainsi que les versions des outils d'ingestion et de recherche.

**Environnement et exécution :** accompagner les résultats de l'environnement matériel et logiciel : processeur, mémoire disponible, système d'exploitation, versions de l'application, du moteur vectoriel, des bibliothèques et du modèle d'embedding avec son empreinte ; consigner également la version et l'empreinte du corpus, l'état de charge de la machine, la date et les conditions d'exécution. Utiliser un seul processus et une requête à la fois ; aucune concurrence artificielle dans la mesure principale. D7 pourra définir une campagne de concurrence distincte. Pour chacun des cinq types, effectuer dix échauffements puis cent mesures ; les dix échauffements sont exclus des cent mesures et de toutes les statistiques. Réaliser les mesures dans un ordre entrelacé et reproductible. Utiliser une horloge monotone aux bornes du composant RAG. Le processus, le modèle et l'index sont préchauffés ; le cache de résultats de requête est désactivé. Une mesure à froid peut être rapportée séparément, sans être mélangée à la mesure principale.

**Statistiques et cible :** publier les cent mesures par type ainsi que la médiane, le p95 et le maximum **séparément pour chacun des cinq types**. Calculer le p95 par la méthode du rang le plus proche : trier les 100 durées de chaque type par ordre croissant et retenir l'observation de rang `ceil(0,95 × 100) = 95` (rang compté à partir de 1). La cible approuvée par le fondateur est un p95 strictement inférieur à 2 000 ms **pour chacun des cinq types**. Publier également les 500 mesures et les statistiques globales à titre descriptif, sans les substituer aux p95 par type. La méthode, les mesures et les résultats doivent être documentés et reproductibles ; la mesure réelle est effectuée au lot 8a selon ce protocole. L'absence de mesure réelle à l'étape 7 ne constitue pas un échec de cette étape.

---

## 3. État de référence (preuves)

- `git fetch` : `HEAD = origin/main = 69ce508`. Historique 6b présent (validation `2028668`, autorisations `312e51a`, gel `0ab1001`, résultats `1006e30`, indicateur de chargement `d96d7c6`).
- Prochain ADR disponible : **ADR-008** (`docs/adr/` : ADR-000 à ADR-007).
- Gel du lot v2 : `docs/etape_6b_donnees/gel_v2.json` ; garde-fou `tests/test_gel_lot_v2.py`.
- Dans le code : aucun CORS, aucun contrôle `Origin` / `Sec-Fetch-Site` ; cookie de session `samesite="lax"` (Brique 7) ; cookies CSRF de B8 et de la gouvernance en `strict` ; `/alertes/{id}/expliquer` est un **GET** ; Ollama lié à `127.0.0.1`, `OLLAMA_NUM_PARALLEL=1`, `OLLAMA_MAX_LOADED_MODELS=1` (`docker-compose.yml`).
- Historique Git : aucun fichier `.env`, clé ou certificat commité (seul `.env.example`) ; des mots de passe de test/développement en clair figurent dans l'historique ; pas de répertoire `.github` (pas de CI).
- Aucun code RAG dans le dépôt.
- **Non prouvé :** l'exécution des tests (aucun Docker disponible dans l'environnement de travail).

---

## 4. Invariants conservés et ce qui change

**Conservés :** IA locale (Ollama), à la demande, hors chemin critique ; Briques 4, 5, 6 déterministes et intouchées ; aucune décision automatique ; aucun SQL ni Cypher généré ; aucun partage entre tenants ; la décision humaine n'est jamais remplacée ; tout chiffre affiché est rattaché à des faits structurés ; aucun texte utilisateur en dur (ADR-001).

**Ce qui change :** la section 10 des décisions verrouillées autorise la conception d'un MVP documentaire borné, sans LLM. Les garanties historiques de la 6a/6b et leurs décisions restent inchangées. Tout passage documentaire reste une donnée non fiable ; aucun LLM n'est autorisé dans le MVP.

**A1 — traité dans son périmètre :** le fondateur a approuvé la section 10 des décisions verrouillées pour le MVP RAG documentaire. Cette décision ne modifie pas rétroactivement les décisions historiques des étapes 6a/6b ni les sections 8 et 9 ; elle n'autorise pas l'étape 8.

---

## 5. Compatibilité avec les décisions antérieures

Verdicts : **C** = compatible ; **CC** = compatible sous condition ; **⚠** = contradiction apparente, arbitrage requis.

| Référence | Section | Verdict | Détail |
|---|---|---|---|
| ADR-000 | Décision (workspace `uv`, méthode, dépendances signalées) | **CC** | Toute nouvelle dépendance (magasin vectoriel, embeddings) va dans le `pyproject.toml` du paquet concerné, avec lockfile racine. **L'emplacement du code RAG (nouvelle brique ou module transverse) n'est défini nulle part** : arbitrage A6. |
| ADR-001 | Décision, Conséquences | **C** | Catalogue propre, aucun texte en dur. Aucune traduction automatique en temps réel : les passages sont affichés **dans leur langue d'origine** (une partie du corpus GAFI/GIABA est en anglais). Langues locales : Vision. |
| ADR-002 | Décision | **CC** | Moteur de traduction futur (NLLB-200 600M) **non inclus dans le budget mémoire** de ce document. La dépendance `transformers` pourrait être partagée avec les embeddings : à évaluer à l'étape 8. Aucune interaction fonctionnelle (composant distinct d'Ollama). |
| ADR-003 | Décision | **CC** | **Le mécanisme n'est pas réutilisable tel quel** : l'event trigger de la migration `0004` limite les noms de table à `alertes` et `detections`, et `shared.assurer_protection_integrite(p_schema, p_table)` branche sur ces noms. Protéger les nouvelles tables (D8, D9) exige soit une migration **dans la Brique 1 (verrouillée)**, soit une protection propre au nouveau module : arbitrage A7. |
| ADR-004 | Décision | **C** | Modèle inchangé. Le RAG reste « explicatif », sans décision. |
| ADR-005 | Décision | **CC** | Leçon appliquée (S10). Point d'implémentation : HTMX n'insère pas une réponse 4xx/5xx ; les refus visibles doivent suivre le motif déjà adopté (fragment en 200, ADR-007), à décider à l'étape 8. |
| **ADR-006** | **§3 « Invariants » : « Aucun agent autonome, RAG ou génération de requêtes SQL/Cypher n'est introduit. »** | **CC** | L'invariant historique des étapes 6a/6b est préservé. La section 10 des décisions verrouillées autorise séparément un MVP RAG documentaire sans LLM ; aucun amendement de l'ADR-006 n'est effectué ici. |
| ADR-006 | §1 (mesures), §8 (réserve mémoire ouverte) | **CC** | Trois mesures non réconciliées (§12) ; la réserve mémoire reste ouverte. Les estimations de ce document en dépendent. |
| **ADR-007** | « Variantes écartées » et décision du 29 octobre : « aucune migration ni stockage d'explications » | **C pour le MVP** | D9 est conservée comme proposition historique, mais les snapshots sont exclus et non autorisés dans le MVP par la section 10. Toute évolution de stockage reste un chantier distinct nécessitant une décision explicite ; l'ADR-007 demeure inchangé. |
| ADR-007 | « Journalisation : aucun identifiant de compte dans les journaux » | **CC** | Le journal des replis (dans `explication_ia.py`, **gelé**) reste inchangé. La proposition historique D8 de journal distinct et durable est hors MVP, non autorisée et nécessite un arbitrage ultérieur ; aucun identifiant utilisateur n'est ajouté à un journal durable dans le MVP. |
| ADR-007 | Approbation du 25 octobre (Brique 7 : une `<div>` sans texte) | **CC** | L'affichage du RAG ne doit **pas** modifier de nouveau `alerte_detail.html` (Brique 7) : il se compose dans les fragments servis par `souverain_app`. |
| ADR-007 | Gel du lot v2 | **C** | Aucun fichier gelé modifié (§11.D6, §11.D8, S13). |
| Décisions verrouillées | §1 machine 16 Go ; §2 workspace ; §3 greenfield ; §4 méthode | **C** | — |
| Décisions verrouillées | §6 multilinguisme | **C** | Pas de traduction en temps réel sans validation (cohérent avec l'affichage verbatim). |
| Décisions verrouillées | §7 (B8 : `require_role` paramétré, `souverain_app`, immuabilité par privilège) | **C** | Mécanismes réutilisés. |
| **Décisions verrouillées** | **§8 et §9 : « sans RAG »** | **CC** | Les sections 8 et 9 restent intactes et décrivent les décisions historiques 6a/6b. La section 10 autorise uniquement le MVP documentaire sans LLM ; elle ne change pas les décisions historiques ni ne valide l'étape 7. |
| Document fondateur | Bloc 5, règle 3 : `tenant_id`, `country_code`, `data_classification` dans **chaque** table | **CC** | S'appliquerait à toute table D8/D9 seulement si une évolution future était approuvée ; aucune table de ce type n'est autorisée dans le MVP. |
| Document fondateur | Bloc 5, règle 2 : aucune donnée ne quitte le territoire | **C** | Embeddings et recherche locaux. |
| Document fondateur | Bloc 5, règle 6 : fallback pour chaque composant | **C** | RAG indisponible = mode dégradé sans recherche (D3, D5). |
| Document fondateur | Bloc 6 : stack **LlamaIndex + ChromaDB** | **CC** | LlamaIndex est conservé dans la stack conformément à la section 10. Son rôle technique (proposition : couche locale d'intégration ingestion/retrieval avec ChromaDB, sans autorité sur accès, tenant ou requêtes) reste à évaluer ; aucune dépendance nouvelle n'est autorisée par cette formulation. |
| Document fondateur | Bloc 11 : « RAG < 2 s » ; Bloc 8 : « Loi 2019-33 (protection des données) » | **⚠** | V8 et V1. |
| Cahier des charges | §3 stack obligatoire sauf décision explicite ; §7 ne pas inventer d'exigences | **CC** | Les exigences S1–S15 sont des **exigences de conception proposées**, rattachées aux principes de `05_SECURITE_ET_GOUVERNANCE.md` (Secure by Design, zero trust, audit, pseudonymisation, chiffrement, fallback), pas des exigences du fondateur. |
| `05_SECURITE_ET_GOUVERNANCE.md` / `SECURITY.md` | Chiffrement au repos ; « projet non encore déployé publiquement » | **CC / ⚠** | Le chiffrement au repos est un principe **non encore réalisé** (étape 11) : il resterait à traiter avant toute évolution future approuvée qui stockerait des snapshots. `SECURITY.md` et le fichier `LICENSE` (« confidentiel et propriétaire ») décrivent un dépôt non public : à rapprocher de l'état observé (V2, D10). |

---

## 6. Modèle de menaces

### 6.1 Actifs
Faits d'alerte et données de tenant ; corpus et manifeste ; capacité de calcul locale (une génération à la fois, CPU seul) ; piste d'audit ; confiance de l'analyste (un indice d'investigation n'est pas une preuve).

### 6.2 Acteurs
Insider (CENTIF, banque, opérateur) ; compte `analyst`/`admin` compromis ; site tiers ciblant un utilisateur connecté ; source documentaire falsifiée ; acteur étatique hostile ; machine du réseau local (voir V11) ; erreur humaine.

### 6.3 Menaces

| # | Menace | Gravité | Parade principale |
|---|---|---|---|
| T1 | Injection de prompt indirecte (passage contenant des instructions) | Haute | Confinement par contrat de sortie, affichage verbatim (D1) |
| T2 | Fuite inter-tenant par la recherche | Haute | Collections séparées, module d'accès unique (D3) |
| T3 | Empoisonnement du corpus, partagé par **tous** les tenants | Haute | Manifeste, empreintes, ingestion contrôlée (D5) |
| T4 | Fausse autorité (citation inventée, périmée ou mal attribuée) | Haute | Aucune affirmation sans passage identifiable (S2, S9) |
| T5 | Synthétique pris pour réel | Moyenne | Drapeau `synthetique` affiché (S1) |
| T6 | Épuisement de ressources | Moyenne | Concurrence et quotas (D7) |
| T7 | Déclenchement par un site tiers ; attribution erronée dans une éventuelle traçabilité future | Faible aujourd'hui, à réévaluer si D8 est un jour approuvée | POST + CSRF pour les actions concernées (D6) |
| T8 | Absence de traçabilité durable | Hors MVP | D8 reste une proposition historique non autorisée |
| T9 | Explication stockée : faits modifiés depuis, relecture hors contexte | Hors MVP | D9 reste une proposition historique de snapshots non autorisée |
| T10 | Chaîne d'approvisionnement (bibliothèques, poids de modèles, sérialisation) | Moyenne | Versions et empreintes figées (S11) |
| T11 | Magasin vectoriel et snapshots lisibles sur disque ou dans une sauvegarde | Moyenne | Droits système, sauvegardes protégées ; chiffrement au repos en Vision |
| T12 | Le RAG devient canal de partage inter-États | Haute (Vision) | Corpus public uniquement (étape 12) |
| T13 | Modèle influencé qui enterre un passage utile ou remonte un passage trompeur | Moyenne | Tous les passages affichés ; gain du modèle prouvé avant usage (D1, S14) |
| T14 | Application joignable depuis le réseau local (écoute `0.0.0.0`) | Moyenne | Hors périmètre de cette étape ; arbitrage A8 |

### 6.4 Risques résiduels hors périmètre
`/health` et `/metrics` sans authentification ; superutilisateur PostgreSQL non contraint (ADR-003) ; **écoute sur toutes les interfaces** : restreindre à `127.0.0.1` n'est pas trivial, car Prometheus (en conteneur) interroge l'application via `host.docker.internal` ; la correction doit donc être pensée avec le monitoring (A8).

---

## 7. Exigences de conception proposées

| ID | Exigence |
|---|---|
| S1 | Aucun document n'entre dans le corpus sans entrée complète du **manifeste** (§9.3), y compris licence et drapeau `synthetique`. |
| S2 | Toute affirmation issue du RAG pointe vers un passage identifiable (source, version, page). |
| S3 | Un passage est une **donnée**, jamais une instruction. |
| S4 | Toute recherche passe par **un seul point d'accès** imposant le périmètre. |
| S5 | **Aucune donnée opérationnelle** (transactions, alertes, détections, décisions) n'est indexée ni envoyée au moteur de recherche. La requête ne contient que le vocabulaire fermé des types de patterns. |
| S6 | L'ingestion est une **commande d'opérateur** ; aucune route web ne la déclenche. |
| S7 | Toute action coûteuse est un POST protégé par CSRF, réservé aux rôles autorisés, avec limites de fréquence et de concurrence. |
| S8 | Les journaux opérationnels sont minimisés conformément à la section 10 des décisions verrouillées. Aucun journal d'audit durable supplémentaire, aucune requête ni aucun passage n'est conservé dans le MVP. |
| S9 | Le texte affiché est écrit par le serveur ou cité **tel quel** avec sa référence. |
| S10 | Toute table par tenant et tout rôle nouveaux ne sont envisagés que dans une évolution future explicitement approuvée ; si autorisés, ils exigent un **provisionnement** diagnostiqué et idempotent (ADR-005). Aucune table nouvelle dans le MVP. |
| S11 | Versions des bibliothèques et du modèle d'embeddings figées ; aucune désérialisation de contenu non fiable ; index reconstruisible depuis corpus et manifeste. |
| S12 | Aucun texte juridique n'est indexé tant que sa **référence en vigueur** n'est pas vérifiée (V1) et son droit de réutilisation établi. |
| S13 | Aucun texte en dur ; nouveaux textes dans un **catalogue propre au RAG** ; `traductions/fr.py` jamais modifié sans lot v3. |
| S14 | Le MVP n'utilise aucun LLM. Toute évolution future vers un LLM exige une décision distincte du fondateur et une justification mesurée avec un lot dédié. |
| S15 | Toute table éventuellement autorisée dans une évolution future porte `tenant_id`, `country_code`, `data_classification` (document fondateur, Bloc 5 règle 3). Cette exigence ne constitue pas une autorisation de créer une table dans le MVP. |

---

## 8. Architecture conceptuelle (MVP)

```text
Alerte (déjà en base, lecture seule)
   │  types de patterns (vocabulaire fermé) ← seule information transmise (S5)
   ▼
Requête canonique construite par le SERVEUR (D2)
   ▼
Module d'accès unique (S4) ── collection publique (classe A)
   ▼
k passages + références (S2)
   ▼
[MVP / lot 8a : affichage verbatim, SANS modèle]               ← périmètre autorisé
   ▼
Fragment affiché (composé dans souverain_app, sans nouvelle modification de la Brique 7)
   ▼
Journaux opérationnels minimisés ; aucun journal d'audit durable supplémentaire
```

Le lot 8b et tout classement par LLM sont des évolutions futures non autorisées par le MVP ; ils nécessitent une décision distincte du fondateur.

Avec cinq types de patterns fermés, l'ensemble des requêtes canoniques est **fini** : la qualité de la recherche peut être évaluée de façon exhaustive.

---

## 9. Corpus RAG : sources, licences, provenance

### 9.1 Référence juridique nigérienne (V1)

| Élément | Résultat de la vérification (recherche web du 4 novembre 2026) | Niveau de preuve |
|---|---|---|
| « Loi 2019-33 (protection des données) » du document fondateur | **Incorrect pour la protection des données.** La loi n°2019-33 du 3 juillet 2019 porte **répression de la cybercriminalité**. | Plusieurs sources secondaires et copies de texte ; **Journal officiel non consulté** |
| Loi 2017-28 du 3 mai 2017 (protection des données), modifiée par la loi 2019-71 du 24 décembre 2019 | Existait ; décret d'application 2020-309. | Sources secondaires |
| **Loi 2022-59 du 16 décembre 2022** relative à la protection des données, modifiée par la loi 2023-31 du 4 juillet 2023 et les ordonnances 2024-16 (26 avril 2024) et 2024-29 (24 juin 2024) | Le **site de la HAPDP** (page « Législation nationale », consultée via l'extrait de recherche ; le chargement direct est bloqué par le site) liste la loi 2022-59 **consolidée** avec ses textes modificatifs, et présente la HAPDP comme créée par la loi 2022-59. Un entretien du président de la HAPDP (quotidien *Le Sahel*) indique que les textes antérieurs ont été **abrogés**. | Source officielle partielle (extrait) + presse nationale. **Texte des dispositions abrogatoires non lu.** |
| Loi 2019-33, modifications | Modifiée en 2022 (adoption de l'Assemblée nationale du 21 juin 2022, selon la presse), puis par l'**ordonnance n°2024-28 du 7 juin 2024** (communiqué du ministère de la Justice relayé par la presse). | Presse ; **texte consolidé et Journal officiel non consultés** |

**Conclusion :** le texte de protection des données apparemment en vigueur est la **loi 2022-59 consolidée**. Ce point **reste à vérifier** sur le texte officiel (site HAPDP, Journal officiel) avant : toute correction du document fondateur (décision du fondateur, non faite ici), toute indexation de texte juridique, toute durée de conservation (D8, D9). Le décret d'application de la loi 2022-59 n'a pas été identifié.

### 9.2 Classes et licences des sources envisagées (V3)

| Classe | Source | Mention de droits constatée | Conséquence |
|---|---|---|---|
| A | **FATF/GAFI** | « © FATF/OECD. All rights reserved. **No reproduction or translation of this publication may be made without prior written permission.** » (publications de 2018 et 2025, consultées via des copies tierces) | **Autorisation écrite préalable** du Secrétariat du GAFI avant toute ingestion ; l'indexation et l'affichage verbatim sont des reproductions. Sans autorisation : exclure, ou ne conserver que des références et des synthèses écrites par le fondateur (statut d'œuvre dérivée à faire qualifier). |
| A | **GIABA** (typologies, rapports) | « © GIABA. All rights reserved. No reproduction or translation … without prior written permission » ; rapport conjoint 2013 : © FATF/OECD et © GIABA | Même régime ; demande au Secrétariat du GIABA (et au GAFI pour les rapports conjoints). |
| A | **UNODC** | Publications types (World Drug Report 2024, rapport annuel 2015) : reproduction « for educational or non-profit purposes without special permission, provided acknowledgement of the source is made » ; autre édition : usage commercial interdit sans autorisation écrite | Usage non commercial avec attribution ; **le caractère commercial du projet (B2G, licences) rend l'usage ambigu** : à demander ; à vérifier **par publication**. |
| A | **BCEAO** (directives, instructions) | **Aucune condition d'utilisation trouvée** (recherche infructueuse) | **Non vérifiée.** |
| A | **Textes légaux nigériens et UEMOA** | Régime de réutilisation non vérifié ; sources officielles à privilégier (HAPDP, Journal officiel) | À vérifier ; S12. |
| A, `synthetique` | Données synthétiques du projet | `LICENSE` : « Tous droits réservés » | Propriété du projet ; toujours marquées (T5). |

**Limites de cette vérification :** les mentions ont été lues sur des **publications types** ou des copies tierces, pas sur les documents précis que le fondateur compte ingérer ; la qualification juridique (reproduction, citation, exception) n'est pas établie ici. **Aucun document ne doit être ingéré avant vérification document par document.**

**Tension documentaire à clarifier (hors arbitrage de ce document) :** le document fondateur impose « 100 % open source et auditable » ; le fichier `LICENSE` actuel déclare le dépôt « confidentiel et propriétaire ».

### 9.3 Manifeste de provenance (une entrée par source)
Identifiant ; titre ; éditeur et URL d'origine ; date de publication ; date d'acquisition ; **SHA-256 du fichier brut** ; version ; **licence et preuve de l'autorisation** (référence de la demande ou de la mention) ; langue ; classe ; drapeau `synthetique` ; validé par ; date de validation. Versionné dans Git. Chaque passage porte l'identifiant de source et la page. Signature : Vision (ML-DSA, étape 11).

---

## 10. Isolation multi-tenant : cadre général

- **Classe A** : une collection **publique** unique, lecture seule pour tous les tenants. Le risque principal est l'**empoisonnement partagé** (T3).
- **Classe B (évolution future non autorisée)** : **une collection par tenant**, séparée de la publique, fusion côté serveur, uniquement après décision distincte du fondateur.
- Détail des limites et protections : D3 (§11).

---

## 11. Décisions

**Légende :** ✅ orientation validée · 🟡 proposée, à valider · 🔎 *précision ajoutée en révision 2, à relire*.

### D1 ✅ — MVP sans LLM : recherche documentaire et affichage verbatim

**Orientation approuvée dans le périmètre de la section 10 :** le serveur affiche les passages **verbatim** avec leur source. Le MVP ne transmet aucun passage à un LLM et n'utilise aucun modèle pour rédiger, résumer, sélectionner ou classer les résultats.

**Proposition historique conservée, hors MVP et non autorisée :** un LLM pourrait éventuellement ordonner les k passages selon une permutation de jetons. Cette évolution nécessite une décision distincte du fondateur après mesures et tests ; elle n'est pas engagée par la présente conception.

**Statut de D1.1–D1.7 ci-dessous :** exigences proposées pour cette éventuelle évolution future avec LLM ; elles ne font pas partie du MVP et n'autorisent pas son implémentation.

**🔎 D1.1 — Séparation des passages et des instructions.**
Trois canaux distincts :
1. une **consigne système fixe**, jamais construite avec du contenu documentaire ;
2. les k passages transmis comme **données structurées** : une liste `[{"id": "P1", "texte": "…"}, …]` où `id` est un **jeton opaque généré à chaque requête** (P1…Pk), **distinct de l'identifiant de source** ; le texte est une valeur de chaîne JSON échappée, **jamais concaténée à la consigne** ;
3. un **format de sortie contraint** (schéma JSON imposé côté Ollama, comme en 6b).

**Limite assumée :** aucune séparation par délimiteurs ou structure n'empêche un modèle de « suivre » du texte qu'il lit. La protection réelle est le **confinement** : quoi que dise un passage, la sortie du modèle ne peut être qu'un ordre de jetons connus, et tout ce qui est affiché vient du serveur.

**🔎 D1.2 — Prétraitement à l'ingestion (mesure complémentaire, non une barrière).**
Normalisation Unicode (NFKC) ; suppression des caractères de contrôle, de direction (bidi) et de largeur nulle ; retrait du balisage ; longueur maximale par passage ; détection heuristique de motifs d'instruction → **quarantaine et revue humaine** du fondateur. Une heuristique ne garantit rien ; elle réduit le bruit.

**🔎 D1.3 — Validation de la permutation exacte.**
La sortie doit être **un unique objet JSON** à **une seule clé** (nom fixé), dont la valeur est une liste de chaînes, avec : exactement k éléments ; chacun égal (casse comprise) à un jeton fourni ; **aucun doublon** ; **aucun élément en trop ni manquant** ; aucun autre champ ; **aucun texte hors JSON** ; taille maximale bornée. Mêmes règles que la validation de la 6b (clé unique, chaque identifiant exactement une fois), mais **réécrites et testées pour le RAG** : on n'importe pas une fonction privée du module gelé.

**🔎 D1.4 — Comportement en cas de sortie invalide.**
- **Aucune relance** (cohérent avec l'ADR-007 : à `temperature 0` et `seed 42`, un second essai redonnerait la même sortie).
- **Repli déterministe** : ordre de pertinence de la recherche.
- La sortie brute du modèle n'est **jamais affichée ni journalisée**.
- Cause journalisée dans une liste fermée : `modele_indisponible`, `delai_depasse` (120 s, comme en 6b), `reponse_invalide` (pas un JSON conforme), `ordre_invalide` (JSON conforme mais pas une permutation exacte).
- L'utilisateur voit les passages dans l'ordre de pertinence, avec une mention neutre (catalogue propre).

**🔎 D1.5 — Affichage.** Les k passages sont **toujours tous affichés** ; texte échappé, **pas de rendu Markdown/HTML**, aucun lien actif créé à partir du texte ; source et page issues du **manifeste**, jamais du passage ; marque `synthetique` ; mention « indice d'investigation, pas une preuve ».

**🔎 D1.6 — Effet résiduel d'un éventuel modèle futur (T13).** Il pourrait faire remonter un passage trompeur ou enterrer un passage utile en changeant l'ordre. Cette hypothèse ne concerne pas le MVP sans LLM ; tout lot correspondant exige une décision distincte.

**🔎 D1.7 — Cas adversariaux d'une éventuelle évolution LLM :** passages contenant des instructions en français et en anglais ; faux jetons (`P2` dans un passage) ; JSON imbriqué ; demande d'omission ; sorties invalides (doublon, manquant, excédent, clé en plus, texte avant ou après le JSON). Ces tests ne font partie d'aucun lot autorisé tant qu'une décision distincte n'a pas été prise.

**Note historique sur l'ADR-007 :** la proposition d'ordonnancement ci-dessus ferait lire au modèle du texte de corpus public. Elle est hors MVP, non autorisée et ne modifie pas l'ADR-007 ni les décisions de la 6b.

### D2 ✅ — Principe approuvé : requête serveur construite depuis une liste fermée
La section 10 approuve le principe fonctionnel : aucune question libre en MVP ; le serveur construit la requête à partir des types de patterns autorisés. La table précise de correspondance entre chaque type et sa requête canonique reste un choix technique de conception à détailler. Les requêtes sont finies et testables exhaustivement ; aucune donnée de tenant ou opérationnelle n'est transmise au moteur de recherche. La question libre reste hors MVP.

### D3 ✅ — Isolation MVP : collection publique unique, aucune collection privée par tenant

**Décision bornée par la section 10 :** le MVP utilise une collection documentaire publique unique en lecture seule. Il ne crée ni n'alimente de collection privée par tenant ; le composant RAG ne reçoit pas de données opérationnelles ou de tenant et ne choisit pas de collection à partir d'une entrée d'appelant.

**Proposition historique conservée, hors MVP et non autorisée :** une collection par tenant, séparée de la collection publique, avec fusion côté serveur. Elle ne pourra être réexaminée qu'après décision distincte du fondateur.

**Statut des précisions D3.1–D3.3 :** les constats sur les limites de Chroma et les propositions de défense en profondeur sont conservés pour traçabilité. Toute partie concernant des collections privées par tenant est une évolution future, non autorisée pour le MVP.

**🔎 D3.1 — Limites de l'isolation logique (ce que la documentation de ChromaDB permet de dire).**
- Chroma expose des notions de **tenant**, de **base** et de **collection**, présentées comme moyen de **cadrer** les données. En mode **`PersistentClient`** (embarqué), ces valeurs sont **des paramètres fournis par le code appelant** ; je n'ai pas trouvé, dans les pages consultées, de mécanisme d'authentification ou d'identité qui les impose en mode embarqué. L'isolation y est donc **une discipline du code**, pas une barrière : tout code exécuté dans le processus avec accès au répertoire peut ouvrir toutes les collections.
- La documentation et le code de Chroma indiquent que le `PersistentClient` est **destiné au développement local et aux tests** et que, **pour la production, un serveur Chroma est préférable**. C'est compatible avec le MVP mais **pas avec une cible de production** : mode serveur (écoute `127.0.0.1`, authentification) à décider avant tout déploiement réel.
- À **vérifier à l'étape 8 sur la version figée** (V4) : existence d'un mode lecture seule, format de sérialisation sur disque, comportement à l'ouverture concurrente.

**🔎 D3.2 — Protections au niveau du système de fichiers (précisions proposées, à relire).**
- **Répertoire du magasin hors du dépôt Git** (et ajouté au `.gitignore`, qui ne contient aujourd'hui aucun motif pour un magasin vectoriel).
- **Magasin public dans un répertoire séparé**, **construit hors ligne** par l'ingestion et **immuable** une fois publié : il est nommé par l'empreinte du manifeste ; l'application ne l'ouvre qu'en **lecture seule si le mode existe** (V4), sinon avec des droits minimaux.
- **Vérification au démarrage** : l'empreinte du répertoire d'index est comparée à celle enregistrée par l'ingestion ; **en cas d'écart, la fonction RAG est indisponible** (mode dégradé, fail-closed), sans bloquer le reste de l'application.
- **Classe B (évolution future non autorisée)** : un répertoire par tenant, droits distincts, uniquement après décision distincte.
- **Limite honnête en développement :** l'application et l'ingestion s'exécutent sous **le même utilisateur du système** sur la machine du fondateur ; les droits de fichiers ne protègent donc pas contre un processus compromis. La séparation d'utilisateurs système (ingestion en écriture, application en lecture) est une mesure de **déploiement**, pas de développement.
- **Chiffrement au repos : non réalisé** (principe de `05_SECURITE_ET_GOUVERNANCE.md`, cible étape 11). Le chiffrement du disque de la machine n'est pas connu : question au fondateur (A10).

**🔎 D3.3 — Rôle du module central d'accès.**
Il est la **seule** porte de lecture de la collection publique. Il doit :
1. recevoir du service applicatif uniquement les types de patterns autorisés ; l'identité du tenant est validée en amont et n'est pas transmise au composant RAG ;
2. être le seul à connaître le nom de l'unique collection publique ; aucune fonction n'accepte un nom de collection ou un filtre fournis par l'appelant ;
3. imposer un **k maximal** ;
4. **revérifier chaque passage retourné** (la source et les métadonnées doivent correspondre au manifeste public attendu, sinon le passage est écarté et seul un événement minimal non sensible est consigné) — même double vérification défensive que `ALL(...)` en Brique 6 ;
5. retourner des **objets typés** (identifiant, texte, source, page, `synthetique`), jamais des structures brutes du magasin ;
6. **échouer fermé** si le service applicatif ne fournit pas un contexte d'accès autorisé ;
7. rester testable de façon adversariale en vérifiant qu'aucune donnée propre à un tenant n'est accessible au composant RAG ni exposée à un autre tenant.

### D4 🟡 — Modèle d'embeddings : dans l'application, mesuré avant de figer
Avec `OLLAMA_MAX_LOADED_MODELS=1`, un modèle d'embeddings servi par Ollama ferait décharger Ministral ; le rechargement à froid mesuré dure de **47,6 s** (campagne 6b) à **72,7 s** (test ADR-006). Proposition : embeddings **dans l'application**, modèle local multilingue incluant le français, version et licence figées. À mesurer (V5). L'ingestion (calcul massif) ne s'exécute pas pendant que le modèle de génération sert. Qualité en haoussa et zarma : Vision.

### D5 🟡 — Ingestion : opérateur identifié et ingestion non autorisée empêchée

**État réel de l'existant (lu dans le code) :** le CLI de gouvernance des tenants **n'authentifie pas l'humain**. Il se connecte à PostgreSQL avec un **rôle dédié** (`souverain_gouvernance_cli`) dont le mot de passe vient du `.env`, et l'argument `--acteur` est une **déclaration libre, non authentifiée** (le fichier le dit explicitement). La protection réelle est donc : **posséder l'accès au serveur et aux identifiants du rôle**. Le mot de passe par défaut du code est un placeholder de développement.

**🔎 Proposition pour l'ingestion — quatre couches, de la plus faible à la plus forte :**
1. **Pas de route web** (S6) : la seule voie est une commande exécutée sur la machine.
2. **Droits système** : seul l'utilisateur propriétaire du répertoire d'index peut écrire ; le `.env` est lisible par ce seul utilisateur (permissions à vérifier).
3. **Journal d'ingestion en insertion seule**, sous **rôle PostgreSQL dédié** (motif de `gouvernance_audit_log`) : acteur **déclaré** (`--acteur`), **utilisateur système observé** (non falsifiable par l'argument), nom de machine, **empreinte du manifeste**, **hash du commit Git** du manifeste, nombre de passages, empreinte de l'index produit. L'acteur déclaré reste étiqueté comme **déclaration non authentifiée**, distincte de l'identité observée.
4. **Option de durcissement (à arbitrer, A2) :** l'ingestion **refuse** un manifeste dont le dernier commit n'est pas **signé** (clé SSH ou GPG) par une clé autorisée par le fondateur ; elle refuse aussi toute source sans entrée validée ou dont l'empreinte diffère.

**Ce que cette proposition ne fait pas :** elle n'authentifie pas une personne de façon forte ; un compte système compromis reste un compte autorisé. C'est la même limite que celle de la gouvernance CLI, assumée. L'authentification forte de l'opérateur reste un chantier futur.

### D6 ✅ — Déclenchement : POST + CSRF double-submit
**Orientation validée.** La génération devient un POST protégé par le motif de la Brique 8 (cookie `SameSite=strict` + champ caché) ; le fragment qui affiche le bouton reste un GET **sans effet**.

**🔎 Précisions :**
- **Fichiers touchés (étape 8, non faits ici) :** `explication_routes.py` (non gelé), le fragment du bouton, les tests de la route (au moins `test_explication_routes.py`, `test_explication_roles.py`, `test_explication_indicateur.py`). **Aucun fichier gelé.** À tracer comme **correction post-validation de la 6b**.
- Un refus CSRF ne doit **pas** laisser l'indicateur de chargement affiché indéfiniment (HTMX n'insère pas une réponse 4xx) : motif « fragment en 200 » de l'ADR-007 à étudier.
- La réutilisation du CSRF de la Brique 8 par `souverain_app` doit être confirmée **sans créer de dépendance entre briques** (la Brique 2 l'a dupliqué pour ne pas inverser son graphe).
- Un nouveau message de refus passe par le **catalogue propre** (S13), pas par `fr.py`.

### D7 🟡 — Limite de fréquence et de concurrence

**Vérification du nombre réel de processus (V6).**
- Le point d'entrée `uv run souverain-app` appelle `uvicorn.run("souverain_app.main:app", host="0.0.0.0", port=…, reload=False)` **sans argument `workers`** : **un seul processus** et **une seule boucle d'événements** (idem pour le point d'entrée de la Brique 7).
- Il n'existe dans le dépôt **ni Dockerfile, ni unité de service, ni configuration Gunicorn** : le déploiement n'est pas défini.
- **Non garanti :** si quelqu'un lance `uvicorn … --workers N` à la main, ou si un déploiement futur utilise plusieurs processus. La version d'uvicorn figée est `0.52.4` ; son éventuelle lecture d'une variable d'environnement de nombre de workers est **à vérifier**.

**Conséquence : un sémaphore `asyncio` en mémoire fonctionnerait réellement pour toute l'application aujourd'hui** (une seule boucle), mais **seulement tant qu'il n'y a qu'un processus**. Avec plusieurs processus, chacun aurait son propre sémaphore : jusqu'à N générations simultanées sur un Ollama réglé à `NUM_PARALLEL=1`, donc une file d'attente et des délais dépassés.

**Deux options, sans Redis :**
- **Option 1 — sémaphore en mémoire.** Simple ; valable en mono-processus ; compteurs de quotas perdus au redémarrage.
- **Option 2 — verrou consultatif PostgreSQL (recommandée).** La concurrence globale est portée par un **verrou consultatif de session** (`pg_try_advisory_lock`, non bloquant) tenu pendant la durée de l'appel à Ollama (≤ 120 s) : **valable quel que soit le nombre de processus**, libéré automatiquement si la connexion tombe. Les **quotas** se calculent par **comptage sur la table de journal de D8** dans une fenêtre glissante (durable, multi-processus, sans composant nouveau). Coûts : une connexion du pool tenue par génération (une seule autorisée) ; si PostgreSQL est indisponible, la fonction IA l'est aussi (échec fermé, l'application dépend déjà de la base).
- **Réserve pour le MVP :** l'usage de la table D8 par cette option n'est pas autorisé ; aucun journal d'audit durable supplémentaire n'est créé. Toute option de quota nécessitant un stockage durable reste à arbitrer séparément. La recherche seule du MVP n'appelle pas Ollama.
- Dans les deux options : **refus rapide** avec `Retry-After` plutôt qu'une file sans borne ; **cache** par empreinte (faits + versions) ; la **recherche seule (lot 8a)** n'appelle pas Ollama et n'a donc pas besoin du verrou global (elle reste soumise aux quotas).
- **Point d'implémentation :** un sémaphore au niveau module est un singleton lié à une boucle ; les tests par fonction du projet ont déjà révélé ce type de fuite (driver Neo4j en Brique 7, pools en Brique 8) : la fixture devra le réinitialiser.
- Valeurs des quotas : à calibrer à l'étape 8 d'après les mesures ; aucune valeur n'est figée ici. Redis/Celery (étape 9, conditionnelle) n'est **pas** une dépendance.

### D8 🟡 — Journalisation et traçabilité

**Statut : proposition historique conservée, hors MVP et non autorisée.** La section 10 interdit toute nouvelle table d'audit durable dans le MVP. Les journaux opérationnels restent minimisés et ne contiennent ni requête, ni passage récupéré, ni contenu sensible. La proposition détaillée ci-dessous n'est pas une décision et ne peut être incluse dans le lot 8a ; toute évolution future requiert un arbitrage distinct du fondateur.

**État réel de l'existant (lu dans le code) :** les journaux actuels (`souverain_app.requetes`, `souverain_app.explication`) sont des lignes JSON écrites sur la **sortie d'erreur du processus** (`StreamHandler`), **sans fichier, sans rotation, sans contrôle d'accès, sans durée de conservation**. Ce ne sont pas des pistes d'audit.

**🔎 Proposition à deux couches :**
1. **Ligne opérationnelle** sur un logger dédié (`souverain_app.ia_acces`), **distinct** du logger gelé de la 6b : éphémère, comme l'existant.
2. **Table d'audit par tenant, en insertion seule** (la piste d'audit réelle), créée par **provisionnement** (S10, S15).

**Données exactement enregistrées (table) :** identifiant de ligne ; horodatage serveur ; `tenant_id`, `country_code`, `data_classification` ; **identifiant utilisateur pseudonyme** (UUID, jamais l'e-mail) ; identifiant d'alerte (nul pour une action sans alerte) ; **action** (liste fermée : `explication`, `recherche_documentaire`, `consultation_snapshot`) ; **issue** (liste fermée : `ok`, `repli`, `refus_role`, `refus_csrf`, `refus_quota`, `refus_concurrence`) ; **cause** éventuelle (liste fermée, §D1.4) ; durée en ms ; version du schéma du journal.
**Jamais enregistrés :** texte généré, e-mail ou nom, **adresse IP** (aucun contrôle ne la fiabilise derrière l'absence de proxy ; décision à reprendre si un proxy est introduit), contenu ou identifiants de passages, valeur de requête, jetons de session ou de CSRF, `compte_pivot`.

**Droits de lecture :** la lecture applicative est réservée à `auditor` et `admin` du **même tenant** ; la lecture technique (comptage des quotas) par le rôle dédié ; pas de lecture entre tenants (schéma par tenant). Aucune route de lecture en MVP si le fondateur le préfère : lecture par requête SQL de l'opérateur.

**Protection contre la modification et la suppression :** **rôle PostgreSQL dédié** avec `INSERT` et `SELECT` seulement (jamais `UPDATE`, `DELETE`, `TRUNCATE`), et aucune route de modification (même motif que la Brique 8). **Limite reconnue :** le propriétaire des tables (`souverain_admin`, superutilisateur) peut contourner ; le mécanisme de l'ADR-003 **n'est pas réutilisable sans modifier la Brique 1** (§5) : soit migration B1 (A7), soit **détection propre** au nouveau module. **Option (A2) :** chaînage d'empreintes (chaque ligne contient l'empreinte de la précédente), qui rend une modification ou une suppression **au milieu** détectable, sans empêcher la troncature de la fin.

**Durée de conservation : non fixée.** Aucune durée n'est inventée : elle dépend du texte légal en vigueur (V1) et d'une décision du fondateur. Proposition provisoire : **aucune purge automatique** ; une purge n'est possible que par une **procédure d'opérateur explicite, validée et elle-même journalisée**. Volume attendu : une ligne par action, négligeable.

### D9 🟡 — Historisation des explications (snapshots)

**Statut : proposition historique conservée, snapshots hors MVP et non autorisés.** La section 10 exclut les snapshots et toute conservation durable supplémentaire. La proposition détaillée ci-dessous n'est pas une décision ; aucune table, donnée d'alerte, donnée de compte, passage ou explication ne peut être persisté au titre du MVP. Toute évolution future requiert une décision distincte du fondateur.

**⚠ Révision d'une proposition précédente.** La version 1 proposait de **ne pas stocker le texte** et de le reconstruire par le code. Cette révision **renonce à cette proposition**, pour la raison suivante.

**Pourquoi la reconstruction par le code n'est pas fidèle dans la durée.** Le texte est produit par le code gelé à partir des faits, de l'ordre et des gabarits de `traductions/fr.py`. Aujourd'hui le gel garantit un texte identique. Mais si un **lot v3** modifie un gabarit ou le contrôleur, **rejouer un ancien snapshot produirait un autre texte** : la fidélité n'est garantie que tant que le code n'a pas changé. Conserver tous les anciens catalogues par empreinte serait possible mais lourd et fragile.

**🔎 Proposition : stocker le texte rendu avec l'instantané.**
Contenu d'une ligne : identifiants et colonnes de périmètre (S15) ; alerte ; utilisateur pseudonyme ; horodatage ; **faits au moment de la génération** (compte, score, seuil, statut, motifs, nombre de transactions, fenêtre) ; **ordre retenu** ; origine (modèle ou repli) et cause ; langue ; **texte rendu tel qu'affiché** ; **SHA-256 du texte** ; **versions** (digest du modèle, empreintes du prompt, du contrôleur, des traductions, version du lot, image Ollama) ; version du schéma.
Conséquences : une consultation **lit** le texte stocké, **sans jamais régénérer** ; l'affichage indique « état au moment de la génération » et le **distingue de l'état courant** de l'alerte (statut et score peuvent avoir changé, l'alerte étant mise à jour en place). Les phrases de ces mentions viennent du catalogue propre (S13).

**Protection des snapshots sensibles.**
- **Sensibilité :** équivalente à la ligne d'alerte (identifiant de compte, score, motifs). Classification héritée du tenant (`data_classification`).
- **Isolation par tenant :** table dans le **schéma du tenant** (comme `audit_log` de la Brique 8). **Honnêteté sur la limite :** le pool de connexions est partagé et le rôle dédié reçoit des droits sur chaque schéma de tenant provisionné ; le choix du schéma repose donc sur le tenant de la session validée et sur la validation stricte du nom de schéma — la même limite que l'existant. Ce que PostgreSQL impose réellement : l'**absence** de `UPDATE`/`DELETE`.
- **Pas de modification :** rôle en insertion seule ; aucune route de modification ; détection de contournement (A7) ; chaînage optionnel (A2).
- **Lecture :** `auditor` et `admin` du tenant ; `analyst` voit ce qu'il a déclenché.
- **Au repos :** **non chiffré aujourd'hui** (étape 11). Les **sauvegardes** (`pg_dump` en clair, Étape 1) contiennent ces données : leurs droits d'accès sont à protéger (A10).
- **Ordre des écritures :** provisionnement diagnostiqué et idempotent (S10) ; leçon de l'ADR-005.

**Positionnement : hors MVP et non autorisé.** L'ADR-007 qualifie le stockage de chantier distinct dont la place n'est pas décidée. Un éventuel sous-lot 8c reste une proposition future, soumise à une décision distincte du fondateur ; il ne fait pas partie du plan d'implémentation autorisé. Aucune étape 6C n'est créée.

### D10 🟡 — Visibilité du dépôt (aucune intention déduite)

**Constats factuels, sans interprétation :**
- Le clone et le `fetch` anonymes ont réussi (4 novembre 2026) ; l'API GitHub n'a pas pu confirmer l'indicateur (limite de débit).
- Le fichier `LICENSE` déclare : « Tous droits réservés. Ce dépôt est actuellement confidentiel et propriétaire. »
- `SECURITY.md` indique : « projet … non encore déployé publiquement ».
- Le document fondateur impose : « 100 % open source et auditable ».
- Ces textes ne disent pas tous la même chose ; **laquelle reflète votre intention est votre décision**.

**À confirmer dans les paramètres GitHub :**
1. **Visibilité actuelle** : bandeau « Public » ou « Private » sous le nom du dépôt, et *Settings → General → Danger Zone → Change repository visibility*.
2. **Visibilité voulue**, aujourd'hui puis à chaque phase (si elle diffère de l'état actuel).
3. **Accès** : *Settings → Collaborators and teams* (qui peut lire, écrire, administrer).
4. **Forks** : un dépôt resté public a pu être forké ou copié ; repasser en privé **ne supprime pas** les copies existantes ni les caches.
5. **Sécurité du dépôt** : *Settings → Code security* (détection de secrets, protection au push, signalement privé des vulnérabilités).
6. **Autres surfaces** : wiki, Pages, Releases, Actions (aucun workflow dans le dépôt).
7. **Cohérence documentaire** : mettre `LICENSE`, `SECURITY.md` et la visibilité réelle d'accord.

**Constats de l'historique, à connaître quelle que soit la décision :** aucun `.env`, clé ou certificat n'a été commité ; des **mots de passe de test et de démonstration en clair** figurent dans l'historique (valeurs de développement). **Si l'un d'eux a été réutilisé ailleurs, le changer** : le retirer du code actuel ne le retire pas de l'historique.

Tant que la visibilité n'est pas confirmée, traiter ce document et son modèle de menaces comme **potentiellement lisibles par tous**.

---

## 12. Mémoire sur 16 Go (budget de travail : 13 Go)

**Le budget de 13 Go (étape 4a) et les 14,87 Go « disponibles pour Docker » (Brique 6) sont deux chiffres du fondateur non réconciliés.**

### 12.1 Mesures réellement effectuées (sources du dépôt)

| Composant | Valeur mesurée | Source et conditions |
|---|---|---|
| Ministral 3 8B, conteneur | **6,284 Gio** (pic) | Campagne 6b du 28 octobre ; `docker stats`, 2 s entre relevés (période réelle supérieure) |
| Ministral 3 8B, conteneur | **6,618 Gio** (pic) | ADR-006 §1, 21 octobre, inférence de test à froid |
| Ministral 3 8B, processus natif | **6,53 GiB** (RSS) | Étape 6a (installation native) |
| PostgreSQL | **141 MiB** au repos ; **160,8 à 193,7 MiB** pendant la campagne de charge | Étapes 4a et 5 |
| Neo4j | **136,5 MiB** au repos ; **998,1 MiB**, **1,312 GiB**, **1,51 GiB** (paliers 5 000 / 20 000 / 50 000) ; **931 Mo** (validation Brique 6) | Étapes 4a, 5, Brique 6 |
| Prometheus / Grafana | **88,6 MiB** / **425,3 MiB** | Étape 4a |
| Somme mesurée des quatre services (hors Ollama), au repos | **~791 MiB** | Étape 4a |

Les trois mesures de Ministral **ne sont pas réconciliées** (méthodes et dates différentes) ; l'unité du seuil de 6,5 n'a jamais été précisée (ADR-006 §8).

### 12.2 Jamais mesuré

Application FastAPI ; magasin vectoriel ; modèle d'embeddings ; moteur de traduction futur (ADR-002) ; **Ollama natif résiduel** (V12) ; système, éditeur et navigateur de la machine.

### 12.3 Calcul arithmétique et hypothèses (ce ne sont pas des mesures)

- **Calcul :** 10 000 à 100 000 passages × 1 024 dimensions × 4 octets = **41 à 410 Mo** de vecteurs, **hors index et métadonnées**. L'hypothèse « 1 024 dimensions » n'est **pas figée** (elle dépend du modèle choisi).
- **Hypothèses sans mesure :** application ~0,3 Gio ; magasin vectoriel 0,3 à 0,8 Gio ; embeddings 0,5 à 1,2 Gio.

### 12.4 Projection indicative (mélange de mesures et d'hypothèses)

Bornes basse et haute obtenues en additionnant les valeurs mesurées maximales ci-dessus (Ministral 6,284 à 6,618 ; PostgreSQL ≤ 0,19 ; Neo4j ≤ 1,51 ; monitoring ~0,51) et les hypothèses du §12.3 : **~9,6 à ~11,1 Gio**. **Ce n'est pas une mesure** : trois postes sont des hypothèses, un poste (traduction) n'est pas estimé, et le système hôte n'est pas inclus. **Une mesure réelle est requise avant la première brique de l'étape 8** (V5, V7).

La concurrence ne multiplie pas la RAM (`NUM_PARALLEL=1`) ; elle multiplie l'attente.

---

## 13. Dépendances avec les étapes 8 à 12

| Étape | Dépendance |
|---|---|
| **8 — RAG** | Le lot **8a** couvre uniquement le MVP documentaire sans LLM défini par la section 10 : corpus autorisé, requêtes serveur fermées, collection publique, recherche et affichage sourcé, contrôles d'accès, CSRF applicable, journalisation minimale. Il effectue la mesure réelle reproductible selon le protocole validé à l'étape 7 ; l'objectif approuvé est un p95 strictement inférieur à deux secondes, hors génération LLM. D1.1–D1.7 (classement LLM), collections privées par tenant (D3), journal durable (D8) et snapshots (D9) sont hors MVP et non autorisés. Les options de concurrence et de quotas restent soumises à l'arbitrage D7 sans recours à une table D8. |
| 9 — Redis/Celery | Non requise (D7). Conditionnelle à l'étape 5. |
| 10 — SOUVERAIN-ID | Traçabilité sur l'identifiant utilisateur pseudonyme existant ; aucune attente. |
| 11 — PQC | Signature du manifeste et des exports ; chiffrement au repos (T11). |
| 12 — Résilience inter-États | Le corpus public partagé illustre ce qui peut circuler ; la mémoire criminelle ne transite jamais par le RAG (T12). |

---

## 14. MVP / Vision

| MVP (faisable seul) | Vision |
|---|---|
| Classe A, sources dont la licence est **établie**, requêtes serveur fermées, recherche seule sans LLM, passages sourcés, POST + CSRF pour les actions applicables, contrôles d'accès, journalisation minimale, manifeste + empreintes | Évolutions futures non autorisées : collections privées par tenant ; classement ou rédaction par LLM ; question libre ; génération asynchrone ; journal d'audit durable ; snapshots ; signature du manifeste ; chiffrement au repos ; utilisateurs système séparés ; haoussa / zarma ; évaluation élargie. **Condition d'un déploiement opérationnel ultérieur :** ChromaDB serveur authentifié si le magasin vectoriel doit être exploité en mode serveur. |

---

## 15. Critères de validation de l'étape 8 (à prévoir, non implémentés)

- **Lot de validation RAG v1**, distinct du lot 6b v2 ; le lot v2 n'est jamais modifié.
- Recherche : requêtes canoniques, passages attendus présents, aucune citation sans source.
- Tests adversariaux : absence d'accès aux données opérationnelles et de tenant, aucun mélange inter-tenant, rendu sûr de documents hostiles, CSRF applicable, quotas et concurrence selon les décisions retenues, rôles refusés avant accès aux données, manifeste corrompu (RAG indisponible), index modifié (refus au démarrage).
- Journaux : vérifier l'absence des requêtes, passages et contenus sensibles ; aucun journal d'audit durable supplémentaire ni snapshot dans le MVP.
- `tests/test_gel_lot_v2.py` : aucune empreinte gelée ne change.
- Mesure réelle de RAM (V7) et de latence de recherche selon le protocole V8 : inclure la construction de la requête, l'embedding local, la recherche et la vérification des sources ; exclure toute génération par LLM ; consigner jeu de requêtes, corpus et version, environnement matériel et logiciel, conditions de cache/concurrence, méthode statistique, nombre de répétitions et résultats pour permettre la reproduction. Cible approuvée : p95 strictement inférieur à deux secondes.
- Vérifications manuelles dans un navigateur réel pour `analyst`, `auditor`, `admin`.

---

## 16. Risques résiduels acceptés ou reportés

Gain du modèle non démontré ; variation d'ordre non expliquée (6b) ; mesures sur une seule machine, CPU seul ; corpus public partagé (parade humaine avant l'étape 11) ; isolation par discipline de code en mode embarqué ; superutilisateur PostgreSQL non contraint ; `/health` et `/metrics` non authentifiés ; écoute `0.0.0.0` ; sauvegardes non chiffrées ; droits de réutilisation du corpus non établis pour la plupart des sources.

---

## 17. Mises à jour documentaires et réserves restantes

La validation de l'étape 7 ne lève pas les réserves suivantes :

1. Vérifier les droits de chaque source et les références juridiques avant toute ingestion.
2. Évaluer puis sélectionner le modèle d'embedding avant son usage.
3. Arrêter les choix techniques encore ouverts (notamment le rôle concret de LlamaIndex, les quotas/concurrence et l'emplacement du composant) avant l'implémentation correspondante.
4. Protéger ChromaDB et les endpoints avant toute exploitation ou exposition réseau concernée.
5. Traiter la visibilité et la licence du dépôt selon l'arbitrage D10.
6. La mesure réelle V8 reste au lot 8a ; le protocole approuvé est sa référence expérimentale.

Les documents historiques de la 6a/6b et les sections 8 et 9 des décisions verrouillées restent préservés. Les éventuelles mises à jour rétrospectives de ces documents ne font pas partie de la validation de l'étape 7.

---

## 18. Arbitrages demandés au fondateur

| # | Arbitrage |
|---|---|
| **A1** | **Traité dans le périmètre approuvé** : la section 10 autorise le MVP RAG documentaire sans modifier les décisions historiques 6a/6b ni les sections 8 et 9. |
| **A2** | Arbitrer D4, D5 (dont le **durcissement par commit signé**), D7 (**option 1 ou 2**) et D10. Le principe fonctionnel D2 est approuvé par la section 10 ; son détail de correspondance canonique reste une tâche de conception technique. D8 (journal durable/chaînage) et D9 (snapshots) restent des propositions historiques hors MVP, non autorisées ; toute reprise future requiert une décision distincte. |
| **A3** | LlamaIndex reste dans la stack. Évaluer la proposition de le limiter à une couche locale d'intégration ingestion/retrieval avec ChromaDB, sans autorité sur l'accès, le tenant ou la construction des requêtes. |
| **A4** | Licences : demander l'**autorisation écrite** au GAFI et au GIABA, ou **exclure** ces sources ; clarifier l'usage **commercial** UNODC ; rechercher les conditions BCEAO. |
| **A5** | Corriger la **référence juridique** du document fondateur (après vérification sur texte officiel). |
| **A6** | **Emplacement du code RAG** (nouvelle brique, ou module transverse) et organisation du workspace. |
| **A7** | Protéger les nouvelles tables : **nouvelle migration dans la Brique 1** (verrouillée) ou protection propre au nouveau module. |
| **A8** | **Écoute `0.0.0.0`** : restreindre, en tenant compte du scraping Prometheus en conteneur ? |
| **A9** | **Séquencement approuvé :** le protocole est précisé au §2/V8, avec dix échauffements exclus puis cent mesures et un p95 calculé séparément par type ; effectuer au lot 8a la mesure réelle reproductible, avec un objectif p95 strictement inférieur à deux secondes pour chacun des cinq types. Aucune mesure réelle n'est exigée pour valider l'étape 7. |
| **A10** | Le **disque** de la machine est-il chiffré ? Comment protéger les sauvegardes de données sensibles si un stockage durable est autorisé ultérieurement ? |
| **A11** | ChromaDB : **mode embarqué** pour le MVP (assumé comme développement/test) et **mode serveur authentifié** avant tout déploiement réel ? |

---

## 19. Journal de la conception

| Date | Événement |
|---|---|
| 4 novembre 2026 | Ouverture de l'étape 7 sur demande explicite ; orientations **D1, D3, D6 validées** ; version 1 de ce document et de l'ADR-008. |
| 4 novembre 2026 | **Révision 2** : lecture intégrale des ADR-000, 002, 006, 007 ; vérification du code (processus, journaux, CLI de gouvernance, fonctions d'intégrité, historique Git) ; vérification web (documentation ChromaDB, textes juridiques nigériens, licences) ; correction de D9 ; ajout des arbitrages A1–A11. |
| 4 novembre 2026 | **Révision 3** : séquencement du critère de performance clarifié conformément à la décision du fondateur ; protocole à valider à l'étape 7, mesure reproductible avec objectif p95 < 2 s au lot 8a. |
| 4 novembre 2026 | **Révision 4** : statut de D2 harmonisé avec la section 10 ; protocole V8 complété selon les précisions du fondateur : échauffements exclus, cent mesures et p95 par type, rang le plus proche, résultats contextualisés par corpus, environnement et conditions d'exécution. |
| 4 novembre 2026 | **Révision 5** : le critère 9 et A9 sont précisés sur l'exclusion des échauffements, le calcul du p95 par type et la documentation des résultats ; aucun test ni mesure réelle n'est effectué. |
| 4 novembre 2026 | **Révision 6** : validation de la conception enregistrée selon la décision du fondateur ; protocole V8 approuvé comme référence expérimentale, mesure réelle reportée au lot 8a ; étape 8 non autorisée. |

**L'étape 8 n'est pas autorisée par la validation de cette conception et exige une autorisation distincte du fondateur.**
