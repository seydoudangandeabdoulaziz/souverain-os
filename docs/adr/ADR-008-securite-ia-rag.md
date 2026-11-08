# ADR-008 — Sécurité IA/RAG : cadre de conception de l'étape 7

**Statut de conception : validée par le fondateur le 4 novembre 2026 pour le périmètre du MVP RAG ; protocole V8 approuvé comme référence expérimentale.**
**État ultérieur : le socle technique de l'étape 8 a été validé par le fondateur le 8 novembre 2026 sur données synthétiques ; voir l'addendum de clôture. Les propositions historiques ci-dessous sont conservées avec leur statut d'origine, sous réserve des décisions ultérieures explicitées dans l'addendum.**
**Décideur : Seydou Dangande Abdoul Aziz (fondateur).**
**Emplacement : `docs/adr/ADR-008-securite-ia-rag.md`** (les ADR du dépôt vivent dans `docs/adr/`, de ADR-000 à ADR-007).
**Contexte : Étape 7, conception uniquement.** Complète ADR-004 (modèle), ADR-006 (déploiement) et ADR-007 (explication des alertes). S'appuie sur ADR-005 (provisionnement) et ADR-003 (intégrité).
**Document détaillé : `docs/ETAPE_7_CONCEPTION.md`.**

---

## Contexte

La 6b a livré une explication IA des alertes sûre par construction (ADR-007) : le modèle ne reçoit aucun fait, il ordonne des identifiants et le serveur écrit les phrases. L'étape 8 prévoit un RAG. Un RAG introduit du texte documentaire externe dans le contexte du modèle : injection indirecte, empoisonnement du corpus, fuite entre tenants, fausse autorité.

La 6b a laissé quatre réserves distinctes : limite de fréquence et de concurrence, traçabilité de l'utilisateur, déclenchement par un site tiers (GET, cookie `SameSite=lax`), stockage et consultation des explications par l'auditeur.

Cet ADR fixe le cadre de sécurité avant toute implémentation.

## Statut des décisions dans la version initiale (4 novembre 2026)

Cette section et le tableau de décisions ci-dessous conservent l'état de proposition consigné à cette date. Les décisions ultérieures du fondateur sont consignées dans l'addendum de clôture en fin de document.

- **D1 et D3 :** seul le périmètre borné par la section 10 des décisions verrouillées est approuvé : MVP sans LLM et corpus public commun sans collections privées par tenant. Les propositions historiques détaillées ci-dessous sur le classement par modèle et les collections privées restent hors MVP et non autorisées.
- **D6 :** orientation POST + CSRF validée pour les actions concernées ; ses détails d'application restent soumis aux critères de conception et d'implémentation applicables.
- **D2 :** le principe fonctionnel de requête serveur construite depuis une liste fermée est approuvé par la section 10 ; la correspondance canonique reste à détailler techniquement. **D4, D5, D7 et D10 : propositions techniques non approuvées. D8 et D9 : propositions historiques conservées, hors MVP et non autorisées.**
- Les précisions techniques de cet ADR restent des propositions sauf lorsqu'elles reprennent explicitement une décision bornée du fondateur.

## Décision

| # | Décision | Statut |
|---|---|---|
| **D1** | **Périmètre approuvé du MVP : recherche seule, sans LLM**, conformément aux décisions verrouillées §10. **Proposition historique hors MVP et non autorisée :** sélection d'identifiants permettant à un modèle d'ordonner les k passages par permutation exacte, avec contrat JSON strict, aucune rédaction ni omission, et repli déterministe en cas d'échec. Cette évolution exige une décision distincte du fondateur ; les précisions de sécurité associées ne sont pas une autorisation d'implémentation. | Approuvé uniquement dans le périmètre §10 ; proposition LLM non autorisée |
| **D2** | **Principe approuvé par la section 10 :** requête construite par le serveur depuis la liste fermée des types de patterns ; pas de question libre en MVP. La table détaillée de correspondance entre types et requêtes canoniques reste une précision technique à définir. | Principe approuvé ; correspondance technique à préciser |
| **D3** | **Périmètre approuvé du MVP :** collection documentaire publique commune ; aucune collection privée par tenant, conformément aux décisions verrouillées §10. **Proposition historique hors MVP et non autorisée :** collection distincte par tenant pour un éventuel corpus privé. Les constats sur les limites de l'isolation Chroma embarquée et les propositions de contrôle du magasin public restent des éléments techniques à évaluer, pas des décisions définitives. | Approuvé uniquement dans le périmètre §10 ; collections privées non autorisées |
| **D4** | **Embeddings dans l'application**, modèle local multilingue (français inclus), version figée, **mesuré avant d'être retenu**. Pas dans Ollama (`MAX_LOADED_MODELS=1`). | Proposée |
| **D5** | **Ingestion par commande d'opérateur** uniquement ; manifeste de provenance obligatoire ; journal d'ingestion en insertion seule distinguant l'**acteur déclaré** (non authentifié) de l'**utilisateur système observé** ; option : refus d'un manifeste dont le dernier commit n'est pas signé. L'authentification forte de l'opérateur n'est pas fournie (même limite que la gouvernance CLI). | Proposée |
| **D6** | **Génération en POST avec CSRF double-submit** (motif de la Brique 8) ; le fragment du bouton reste un GET sans effet. | Validée |
| **D7** | **Proposition non approuvée :** refus rapide, quotas et cache sans Redis ; sémaphore en mémoire limité au mono-processus actuel ; option de verrou consultatif PostgreSQL pour la concurrence. La proposition historique de compter les quotas sur le journal durable D8 est exclue du MVP : le lot 8a ne dépend d'aucune table d'audit durable ni de snapshot. Toute stratégie de quotas/concurrence reste à arbitrer sans rendre D8/D9 prérequis. | Proposée ; dépendance à D8 exclue du MVP |
| **D8** | **Proposition historique hors MVP et non autorisée :** journal opérationnel dédié plus table d'audit par tenant en insertion seule, identifiant pseudonyme, sans contenu ni IP ; durée de conservation non définie. La section 10 exclut toute nouvelle table d'audit durable du MVP ; la journalisation MVP est minimisée. Toute reprise nécessite une décision distincte du fondateur. | Hors MVP ; non autorisée |
| **D9** | **Proposition historique hors MVP et non autorisée :** snapshot en insertion seule comprenant faits, ordre, versions, texte rendu et empreinte, consultable par `auditor` et `admin`. La section 10 exclut snapshots et conservation durable supplémentaire du MVP. Toute reprise nécessite une décision distincte du fondateur et ne modifie pas ADR-007 rétroactivement. | Hors MVP ; non autorisée |
| **D10** | **Visibilité du dépôt** à confirmer par le fondateur ; aucune intention déduite. | Proposée |

## Options considérées

- **D1 — options historiques, hors MVP et non autorisées :** (a) recherche seule ; (c) rédaction libre contrôlée, écartée dans la proposition historique car elle expose à l'injection et à la fausse autorité. Le MVP approuvé reste sans aucun LLM.
- **D3 — options historiques pour une évolution future, non autorisées dans le MVP :** (A) collection globale + filtre `tenant_id` ; (C) un store par tenant ; (D) pgvector par schéma de tenant. Aucune option de collection privée n'est approuvée ; toute reprise exigerait une décision explicite.
- **D6.** (b) rester en GET avec contrôle `Sec-Fetch-Site` : dépend du navigateur. (c) accepter le risque : écartée.
- **D7.** Option 1 (sémaphore en mémoire) vs option 2 (verrou consultatif PostgreSQL), voir ci-dessus.
- **D9 — options historiques, hors MVP et non autorisées :** ne rien stocker ; stocker le texte seul sans instantané ; stocker l'instantané **sans** le texte (proposition de la révision 1, **abandonnée**). Aucun de ces choix n'autorise une conservation dans le MVP.

## Justification

- **D1 — justification de la proposition historique, non applicable au MVP :** le confinement par contrat de sortie visait à limiter les capacités d'un éventuel modèle ordonnateur. Cette proposition reste non autorisée ; aucun texte documentaire n'est transmis à un LLM dans le MVP.
- **D3 — constat et proposition technique à évaluer :** la documentation de ChromaDB présente le `PersistentClient` comme destiné au développement et aux tests ; un mode serveur authentifié est requis avant toute exploitation opérationnelle le nécessitant, conformément à la section 10.
- **D6.** Ferme le risque du site tiers et empêche que la traçabilité attribue à un utilisateur une action qu'il n'a pas faite.
- **D9 — justification historique non adoptée :** l'argument en faveur d'un snapshot était que l'alerte est mise à jour en place. Cette motivation ne lève pas l'interdiction du MVP ; tout stockage futur nécessite une décision distincte.

## Compatibilité vérifiée avec les décisions antérieures

Vérification faite sur lecture des ADR-000, 002, 006 et 007 **en entier**, et des sections « Décision » des ADR-001, 003, 004, 005. Détail dans `docs/ETAPE_7_CONCEPTION.md` §5.

**Compatibilité et périmètre approuvé :**

1. La **section 10 des décisions verrouillées** approuve le MVP RAG documentaire dans un périmètre précis. Elle ne modifie pas rétroactivement ADR-006, ADR-007 ni les sections 8 et 9 des décisions verrouillées, qui conservent leur portée historique 6a/6b.
2. **ADR-007** et les décisions verrouillées §9 ne sont pas modifiés : D8 et D9 restent des propositions historiques hors MVP et non autorisées ; aucune table d'audit durable ni aucun snapshot n'est introduit par le lot 8a.
3. La cible de performance concerne la **recherche seule** : le protocole V8 de `docs/ETAPE_7_CONCEPTION.md` §2 fixe dix échauffements exclus, puis cent mesures par chacun des cinq types de patterns ; le p95 est calculé séparément par type avec la méthode du rang le plus proche (rang 95 sur 100). Les résultats incluent l'environnement matériel et logiciel, la version du corpus et les conditions d'exécution. La mesure réelle est réalisée au lot 8a ; l'objectif est un p95 strictement inférieur à deux secondes pour chacun des cinq types. Aucune mesure réelle n'est exigée pour valider l'étape 7.
4. **Document fondateur, Bloc 8** (« Loi 2019-33 — protection des données ») : la loi 2019-33 porte sur la cybercriminalité (voir points à vérifier).

**Compatible sous condition :** ADR-000 (paquet transverse `rag/` avec son `pyproject.toml`, intégré au workspace dont l'unique `uv.lock` est à la racine ; arbitrages techniques n°1 et n°2) ; ADR-002 (moteur de traduction futur non budgété en mémoire) ; **ADR-003** (le mécanisme d'intégrité n'est **pas réutilisable** sans modifier la Brique 1 : l'event trigger de la migration `0004` limite les noms de table à `alertes` et `detections`) ; ADR-005 (leçon appliquée : provisionnement, pas seulement migration) ; ADR-007 (journal des replis gelé inchangé ; aucune table D8 ni snapshot D9 n'est autorisé dans le MVP) ; document fondateur Bloc 5 règle 3 (`tenant_id`, `country_code`, `data_classification` dans chaque nouvelle table, si une évolution future est autorisée) ; Bloc 6, précisé par l'amendement approuvé de la section 10 : LlamaIndex n'est pas une dépendance obligatoire du MVP ; le pipeline autonome sans framework RAG généraliste est privilégié et toute dépendance doit démontrer sa valeur.

**Compatibles :** ADR-001, ADR-004, décisions verrouillées §1 à §7 et §10 dans son périmètre approuvé.

## Conséquences

- **Aucun fichier gelé n'est modifié** : `explication_ia.py`, `traductions/fr.py`, prompt système, options, `lot_v2.json`, `termes_interdits_v1.json`. Nouveaux textes dans un **catalogue propre au RAG**. Aucun journal durable D8 ni snapshot D9 dans le MVP. `tests/test_gel_lot_v2.py` doit continuer à passer.
- **Correction post-validation de la 6b** (D6) : `explication_routes.py` (non gelé), le fragment du bouton et les tests de la route seront modifiés à l'étape 8. À tracer comme telle.
- **Briques 4, 5 et 6 intouchées.** Aucune donnée opérationnelle n'est indexée.
- **Un lot de validation RAG v1**, distinct du lot v2, sera construit à l'étape 8.
- Toute nouvelle table ou tout nouveau rôle ne pourrait être créé, pour une évolution future explicitement autorisée, que par un provisionnement diagnostiqué et idempotent (ADR-005), avec les champs requis (`tenant_id`, `country_code`, `data_classification`) lorsqu'applicables. Aucune table D8/D9 n'est créée par le MVP.
- **Mémoire.** Les **mesures** disponibles (Ministral 6,284 à 6,618 Gio selon la mesure ; PostgreSQL, Neo4j, Prometheus, Grafana) sont distinguées des **hypothèses** (application, magasin vectoriel, embeddings), qui n'ont **jamais été mesurées**. La projection de ~9,6 à ~11,1 Gio est **indicative, pas une mesure** ; une mesure réelle est requise avant l'étape 8. Les trois mesures de Ministral ne sont pas réconciliées (ADR-006 §8).
- **Corpus.** Aucun document n'est ingéré avant vérification de sa licence : FATF et GIABA exigent une **autorisation écrite préalable** (mentions constatées sur des publications types) ; UNODC autorise un usage non commercial avec attribution (usage commercial à clarifier) ; BCEAO : aucune condition trouvée.

## Points non couverts

- Version de ChromaDB et modèle d'embeddings (étape 8, après vérification et mesure). Le rôle de LlamaIndex n'est pas requis pour le MVP ; toute introduction ultérieure reste soumise à l'arbitrage explicite prévu par la section 10.
- Valeurs numériques des quotas ; toute durée de conservation future pour des journaux ou snapshots, qui restent hors MVP et non autorisés.
- Mode serveur authentifié de ChromaDB, chiffrement au repos, séparation des utilisateurs système, authentification forte de l'opérateur d'ingestion : **Vision**.
- Écoute de l'application sur toutes les interfaces (`0.0.0.0`) et sauvegardes non chiffrées : hors périmètre, signalés.
- Positionnement du sous-lot de snapshots (8c).

## Points à vérifier avant acceptation

1. **Référence juridique nigérienne : probablement erronée dans le document fondateur ; reste à vérifier sur texte officiel.** Recoupement web du 4 novembre 2026 : la **loi 2019-33** du 3 juillet 2019 porte **répression de la cybercriminalité** (modifiée ; ordonnance 2024-28 du 7 juin 2024 selon la presse) ; la protection des données relevait de la **loi 2017-28** (modifiée par la loi 2019-71) ; la page « Législation nationale » du site de la HAPDP liste la **loi 2022-59 du 16 décembre 2022 consolidée** (modifiée par la loi 2023-31 et les ordonnances 2024-16 et 2024-29), et un entretien du président de la HAPDP indique que les textes antérieurs sont abrogés. **Non lus :** les dispositions abrogatoires, le Journal officiel, le décret d'application de la loi 2022-59. Rien n'est indexé ni fixé (durées de conservation) avant cette vérification.
2. **Visibilité du dépôt : à confirmer par le fondateur.** Aucune intention n'est déduite d'un clonage anonyme. Les textes du dépôt ne concordent pas entre eux (`LICENSE` : « confidentiel et propriétaire » ; `SECURITY.md` : « non encore déployé publiquement » ; document fondateur : « 100 % open source ») : voir la liste des paramètres GitHub à vérifier dans `docs/ETAPE_7_CONCEPTION.md` D10.
3. **Licences du corpus**, document par document (V3).
4. **ChromaDB** : comportement exact en mode embarqué sur la version figée (mode lecture seule, sérialisation).
5. **Nombre de processus** : un seul aujourd'hui (`uvicorn.run` sans `workers`) ; non garanti pour un déploiement futur.
6. **ADR-001, 003, 004, 005** : relecture complète non faite (sections « Décision » relues).

## Arbitrages demandés

A1 (traité dans le périmètre de la section 10 approuvée ; aucune modification historique) ; A2 (D4, D5, D7, D10 et leurs options ; D2 fonctionnel approuvé, détail technique à préciser ; D8/D9 explicitement hors MVP et non autorisés) ; A3 (arbitrage technique n°3 validé : pipeline RAG Python autonome privilégié, LlamaIndex non obligatoire pour le MVP) ; A4 (licences) ; A5 (référence juridique) ; A6 (arbitrage technique n°2 validé : paquet transverse `rag/` et frontières avec `souverain_app`, les Briques 7 et 8) ; A7 (protection des nouvelles tables si une évolution future est autorisée) ; A8 (écoute `0.0.0.0`) ; A9 (protocole V8 approuvé comme référence expérimentale ; mesure réelle au lot 8a, objectif p95 < 2 s par type) ; A10 (chiffrement du disque, sauvegardes) ; A11 (ChromaDB embarqué puis serveur). Détail dans `docs/ETAPE_7_CONCEPTION.md` §18.

## Références

- `docs/ETAPE_7_CONCEPTION.md` (menaces T1–T14, exigences S1–S15, corpus, mémoire, dépendances, arbitrages).
- ADR-000 à ADR-007.
- `docs/ETAPE_6B_BILAN.md` §6 ; `docs/etape_6b_donnees/gel_v2.json`.
- `docs/00_DECISIONS_VERROUILLEES.md`, sections 1 à 10 ; les sections 8 et 9 restent historiques et inchangées.

## Addendum — décisions et clôture technique (8 novembre 2026)

Le fondateur a approuvé D5 et D7 dans le principe suivant, désormais appliqué au MVP :

- **D5 :** ingestion locale exclusivement par CLI ; manifeste de provenance obligatoire ; vérification SHA-256 ; vérification des droits avant ingestion ; aucun journal durable supplémentaire.
- **D7 :** contrôle de concurrence en mémoire, un seul traitement simultané et refus rapide ; déploiement MVP mono-processus.
- **D10 :** aucune modification de la visibilité ou de la licence du dépôt pour le moment. L'audit de la contradiction entre document fondateur, `LICENSE` et `SECURITY.md` reste séparé. Les droits du code et ceux des documents du corpus sont distincts.

Le modèle approuvé est `intfloat/multilingual-e5-small`, révision `614241f622f53c4eeff9890bdc4f31cfecc418b3`. Les résultats déjà obtenus (tests ciblés RAG/Chroma, Ruff, mypy sur 12 modules, démarrage authentifié Chroma et V8 synthétique) soutiennent la validation du socle technique sur données synthétiques. Le p95 V8 synthétique observé était de 20 à 22 ms selon le type, avec environ 793 Mio de RSS côté client. Aucun contrôle n'a été relancé pour cet addendum.

La validation ne couvre pas la qualité de recherche sur corpus réel. Chaque preuve de droits doit être examinée et approuvée humainement ; SHA-256 en garantit l'intégrité après référence, pas l'authenticité juridique. Les publications FATF restent exclues jusqu'à vérification de leurs autorisations originales. En cas d'interruption, une collection Chroma partielle est refusée et sa récupération reste manuelle ; elle n'est jamais supprimée automatiquement.
