# ADR-008 — Sécurité IA/RAG : cadre de conception de l'étape 7

**Statut : Proposé (4 novembre 2026, révision 2). Non accepté tant que le fondateur n'a pas validé.**
**Décideur : Seydou Dangande Abdoul Aziz (fondateur).**
**Emplacement : `docs/adr/ADR-008-securite-ia-rag.md`** (les ADR du dépôt vivent dans `docs/adr/`, de ADR-000 à ADR-007).
**Contexte : Étape 7, conception uniquement.** Complète ADR-004 (modèle), ADR-006 (déploiement) et ADR-007 (explication des alertes). S'appuie sur ADR-005 (provisionnement) et ADR-003 (intégrité).
**Document détaillé : `docs/ETAPE_7_CONCEPTION.md`.**

---

## Contexte

La 6b a livré une explication IA des alertes sûre par construction (ADR-007) : le modèle ne reçoit aucun fait, il ordonne des identifiants et le serveur écrit les phrases. L'étape 8 prévoit un RAG. Un RAG introduit du texte documentaire externe dans le contexte du modèle : injection indirecte, empoisonnement du corpus, fuite entre tenants, fausse autorité.

La 6b a laissé quatre réserves distinctes : limite de fréquence et de concurrence, traçabilité de l'utilisateur, déclenchement par un site tiers (GET, cookie `SameSite=lax`), stockage et consultation des explications par l'auditeur.

Cet ADR fixe le cadre de sécurité avant toute implémentation.

## Statut des décisions

- **D1, D3, D6 : orientations déjà validées** par le fondateur (4 novembre 2026).
- **D2, D4, D5, D7, D8, D9, D10 : propositions soumises à sa validation.**
- Les précisions techniques de la révision 2 détaillent les orientations validées ; elles restent à relire.

## Décision

| # | Décision | Statut |
|---|---|---|
| **D1** | **Sélection d'identifiants.** Le serveur affiche les passages **verbatim** avec leur source ; un modèle éventuel ne peut qu'**ordonner** les k passages récupérés (permutation exacte), jamais en exclure ni en rédiger. Livraison initiale : **recherche seule, sans modèle** ; le modèle n'entre que sur gain mesuré. *Précisions :* passages transmis comme **données structurées** avec **jetons opaques par requête**, jamais concaténés à la consigne ; confinement par **contrat de sortie** (objet JSON à une clé, exactement k jetons connus, sans doublon, sans ajout ni omission, aucun texte hors JSON) ; **sortie invalide = aucune relance, repli sur l'ordre de pertinence**, sortie brute jamais affichée ni journalisée. | Validée |
| **D2** | **Requête construite par le serveur** à partir des types de patterns (vocabulaire fermé). Pas de question libre en MVP. | Proposée |
| **D3** | **Une collection publique (classe A, lecture seule) + une collection par tenant** pour tout corpus de tenant (Vision). Module d'accès unique. *Précisions :* l'isolation en mode embarqué de ChromaDB est **une discipline du code, pas une barrière** ; magasin public **immuable**, vérifié au démarrage (**échec = RAG indisponible**) ; limites du système de fichiers assumées en développement. | Validée |
| **D4** | **Embeddings dans l'application**, modèle local multilingue (français inclus), version figée, **mesuré avant d'être retenu**. Pas dans Ollama (`MAX_LOADED_MODELS=1`). | Proposée |
| **D5** | **Ingestion par commande d'opérateur** uniquement ; manifeste de provenance obligatoire ; journal d'ingestion en insertion seule distinguant l'**acteur déclaré** (non authentifié) de l'**utilisateur système observé** ; option : refus d'un manifeste dont le dernier commit n'est pas signé. L'authentification forte de l'opérateur n'est pas fournie (même limite que la gouvernance CLI). | Proposée |
| **D6** | **Génération en POST avec CSRF double-submit** (motif de la Brique 8) ; le fragment du bouton reste un GET sans effet. | Validée |
| **D7** | **Refus rapide au lieu d'une file sans borne**, quotas, cache par empreinte, sans Redis. **Le sémaphore en mémoire ne vaut que pour un seul processus** (cas actuel). Recommandé : **verrou consultatif PostgreSQL** (valable multi-processus) et quotas comptés sur le journal de D8. | Proposée |
| **D8** | **Journal en deux couches** : ligne opérationnelle (logger dédié) + **table d'audit par tenant en insertion seule** (rôle dédié), identifiant utilisateur **pseudonyme**, jamais de contenu ni d'IP. Durée de conservation **non fixée** (dépend du texte légal en vigueur). | Proposée |
| **D9** | **Snapshot en insertion seule** : faits, ordre, versions, **texte rendu** et son empreinte ; consultation par `auditor` et `admin`. **Le texte est stocké** (la reconstruction par le code n'est pas fidèle si les gabarits évoluent) ; l'état au moment de la génération est distingué de l'état courant. Positionnement (8c) à décider. | Proposée |
| **D10** | **Visibilité du dépôt** à confirmer par le fondateur ; aucune intention déduite. | Proposée |

## Options considérées

- **D1.** (a) recherche seule : premier lot. (c) rédaction libre contrôlée : écartée, expose à l'injection et à la fausse autorité : **Vision**.
- **D3.** (A) collection globale + filtre `tenant_id` : écartée. (C) un store par tenant : écartée. (D) pgvector par schéma de tenant : **réouvrable**, mais contredit la stack imposée et exigerait une décision explicite (cahier des charges §3).
- **D6.** (b) rester en GET avec contrôle `Sec-Fetch-Site` : dépend du navigateur. (c) accepter le risque : écartée.
- **D7.** Option 1 (sémaphore en mémoire) vs option 2 (verrou consultatif PostgreSQL), voir ci-dessus.
- **D9.** Ne rien stocker ; stocker le texte seul sans instantané ; stocker l'instantané **sans** le texte (proposition de la révision 1, **abandonnée**).

## Justification

- **D1.** Conserve l'esprit de l'ADR-007 : le modèle ne peut ni inventer ni modifier ce qui est affiché. La séparation par structure ne garantit pas que le modèle ignore un texte injecté ; la protection est le **confinement** par le contrat de sortie. Précision assumée : le modèle lit du texte de corpus public (non sensible), contrairement à la 6b.
- **D3.** Reprend la discipline du point de passage unique de la Brique 6. La documentation de ChromaDB présente le `PersistentClient` comme destiné au développement et aux tests ; un mode serveur authentifié est à décider avant toute mise en production.
- **D6.** Ferme le risque du site tiers et empêche que la traçabilité attribue à un utilisateur une action qu'il n'a pas faite.
- **D9.** L'alerte est mise à jour en place ; sans instantané, un audit relirait d'autres faits. Le texte est stocké parce que le gel garantit l'identité du texte **seulement tant que le code ne change pas**.

## Compatibilité vérifiée avec les décisions antérieures

Vérification faite sur lecture des ADR-000, 002, 006 et 007 **en entier**, et des sections « Décision » des ADR-001, 003, 004, 005. Détail dans `docs/ETAPE_7_CONCEPTION.md` §5.

**Contradictions apparentes, arbitrage requis :**

1. **ADR-006 §3** (« Aucun agent autonome, RAG ou génération de requêtes SQL/Cypher n'est introduit »), **décisions verrouillées §8 et §9** (« sans RAG »), ADR-007 : introduire un RAG contredit la lettre de ces invariants, rédigés pour la 6a/6b. **Proposition :** une nouvelle section 10 des décisions verrouillées dédiée au RAG, sans modifier les sections 8 et 9 (modification réservée au fondateur).
2. **ADR-007, décision du 29 octobre** (« aucune migration ni stockage d'explications ») : D9 introduit un stockage. L'ADR-007 le qualifie de « chantier distinct, place non décidée » : c'est une **nouvelle décision**, à valider explicitement.
3. **Document fondateur, Bloc 11** (« RAG < 2 s ») : incompatible avec une génération (8 à 12 s à chaud) ; tenable pour la recherche seule.
4. **Document fondateur, Bloc 8** (« Loi 2019-33 — protection des données ») : la loi 2019-33 porte sur la cybercriminalité (voir points à vérifier).

**Compatible sous condition :** ADR-000 (emplacement du code RAG non défini ; dépendances dans le `pyproject.toml` du paquet concerné) ; ADR-002 (moteur de traduction futur non budgété en mémoire) ; **ADR-003** (le mécanisme d'intégrité n'est **pas réutilisable** sans modifier la Brique 1 : l'event trigger de la migration `0004` limite les noms de table à `alertes` et `detections`) ; ADR-005 (leçon appliquée : provisionnement, pas seulement migration) ; ADR-007 (journal des replis gelé inchangé, journal distinct pour D8 ; la Brique 7 n'est pas modifiée de nouveau) ; document fondateur Bloc 5 règle 3 (`tenant_id`, `country_code`, `data_classification` dans chaque nouvelle table) ; Bloc 6 (rôle de **LlamaIndex** non tranché).

**Compatibles :** ADR-001, ADR-004, décisions verrouillées §1 à §7.

## Conséquences

- **Aucun fichier gelé n'est modifié** : `explication_ia.py`, `traductions/fr.py`, prompt système, options, `lot_v2.json`, `termes_interdits_v1.json`. Nouveaux textes dans un **catalogue propre au RAG**. Journal D8 **distinct** du journal des replis. `tests/test_gel_lot_v2.py` doit continuer à passer.
- **Correction post-validation de la 6b** (D6) : `explication_routes.py` (non gelé), le fragment du bouton et les tests de la route seront modifiés à l'étape 8. À tracer comme telle.
- **Briques 4, 5 et 6 intouchées.** Aucune donnée opérationnelle n'est indexée.
- **Un lot de validation RAG v1**, distinct du lot v2, sera construit à l'étape 8.
- **Toute nouvelle table par tenant et tout nouveau rôle** sont créés par un provisionnement diagnostiqué et idempotent (ADR-005), et portent `tenant_id`, `country_code`, `data_classification`.
- **Mémoire.** Les **mesures** disponibles (Ministral 6,284 à 6,618 Gio selon la mesure ; PostgreSQL, Neo4j, Prometheus, Grafana) sont distinguées des **hypothèses** (application, magasin vectoriel, embeddings), qui n'ont **jamais été mesurées**. La projection de ~9,6 à ~11,1 Gio est **indicative, pas une mesure** ; une mesure réelle est requise avant l'étape 8. Les trois mesures de Ministral ne sont pas réconciliées (ADR-006 §8).
- **Corpus.** Aucun document n'est ingéré avant vérification de sa licence : FATF et GIABA exigent une **autorisation écrite préalable** (mentions constatées sur des publications types) ; UNODC autorise un usage non commercial avec attribution (usage commercial à clarifier) ; BCEAO : aucune condition trouvée.

## Points non couverts

- Version de ChromaDB et modèle d'embeddings (étape 8, après vérification et mesure) ; rôle de LlamaIndex.
- Valeurs numériques des quotas ; durée de conservation des journaux et snapshots.
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

A1 (portée du « sans RAG ») ; A2 (D2, D4, D5, D7, D8, D9, D10 et leurs options) ; A3 (LlamaIndex) ; A4 (licences) ; A5 (référence juridique) ; A6 (emplacement du code RAG) ; A7 (protection des nouvelles tables : migration Brique 1 ou protection propre) ; A8 (écoute `0.0.0.0`) ; A9 (baseline RAG) ; A10 (chiffrement du disque, sauvegardes) ; A11 (ChromaDB embarqué puis serveur). Détail dans `docs/ETAPE_7_CONCEPTION.md` §18.

## Références

- `docs/ETAPE_7_CONCEPTION.md` (menaces T1–T14, exigences S1–S15, corpus, mémoire, dépendances, arbitrages).
- ADR-000 à ADR-007.
- `docs/ETAPE_6B_BILAN.md` §6 ; `docs/etape_6b_donnees/gel_v2.json`.
- `00_DECISIONS_VERROUILLEES.md`, sections 1 à 9.
