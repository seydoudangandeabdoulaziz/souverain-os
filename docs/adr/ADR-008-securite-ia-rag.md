# ADR-008 — Sécurité IA/RAG : cadre de conception de l'étape 7

**Statut : Proposé (4 novembre 2026). Non accepté tant que le fondateur n'a pas validé.**
**Date de la proposition : 4 novembre 2026.**
**Décideur : Seydou Dangande Abdoul Aziz (fondateur).**
**Contexte : Étape 7 (conception uniquement). Complète ADR-004 (modèle), ADR-006 (déploiement) et ADR-007 (explication des alertes). S'appuie sur les leçons de l'ADR-005 (provisionnement) et les limites de l'ADR-003 (intégrité).**
**Document détaillé : `docs/ETAPE_7_CONCEPTION.md`.**

---

## Contexte

L'étape 6b a livré une explication IA des alertes sûre par construction (ADR-007) : le modèle ne reçoit aucun fait, il ordonne des identifiants et le serveur écrit les phrases. L'étape 8 prévoit un RAG (recherche documentaire). Un RAG introduit du texte documentaire externe dans le contexte du modèle, ce qui crée des menaces absentes de la 6b : injection de prompt indirecte, empoisonnement du corpus, fuite entre tenants, fausse autorité.

La 6b a aussi laissé quatre réserves ouvertes (bilan §6, point 10 ; ADR-007) : limite de fréquence et de concurrence, traçabilité de l'utilisateur, déclenchement par un site tiers (route GET, cookie `SameSite=lax`), stockage et consultation des explications par l'auditeur.

Cet ADR fixe le cadre de sécurité avant toute implémentation, sans modifier aucune décision antérieure.

## Décision

Les décisions D1, D3 et D6 sont **validées par le fondateur (4 novembre 2026)**. Les décisions D2, D4, D5, D7, D8, D9 et D10 sont **proposées** et attendent sa validation.

| # | Décision | Statut |
|---|---|---|
| **D1** | **Rôle du RAG : sélection d'identifiants.** Le serveur affiche les passages **verbatim** avec leur source ; un modèle éventuel ne peut qu'**ordonner** les passages récupérés (permutation exacte), jamais en exclure ni en rédiger. Première livraison : **recherche seule, sans modèle**. Le modèle n'entre que si un lot de validation démontre un gain mesuré. | Validée |
| **D2** | **Requête construite par le serveur**, à partir des types de patterns (vocabulaire fermé). Pas de question libre en MVP. Aucune donnée de tenant n'atteint le moteur de recherche. | Proposée |
| **D3** | **Isolation : une collection publique (classe A, lecture seule) + une collection par tenant** pour tout corpus propre à un tenant (Vision). Point d'accès unique, tests adversariaux. | Validée |
| **D4** | **Embeddings calculés dans l'application**, modèle local multilingue (français inclus), version figée, mesuré avant d'être retenu. Pas dans Ollama (`MAX_LOADED_MODELS=1` déchargerait Ministral). | Proposée |
| **D5** | **Gouvernance du corpus** : ingestion par commande opérateur uniquement, manifeste de provenance obligatoire (empreinte SHA-256, licence, version, drapeau `synthetique`), validation du fondateur par source. | Proposée |
| **D6** | **Déclenchement en POST avec CSRF double-submit** (motif de la Brique 8) pour la génération. Le fragment qui affiche le bouton reste un GET sans effet. | Validée |
| **D7** | **Sémaphore global à 1** pour tout appel Ollama (refus rapide au lieu d'une file sans borne), quotas par utilisateur et par tenant (valeurs calibrées à l'étape 8), cache par empreinte. Pas de Redis. | Proposée |
| **D8** | **Journal de traçabilité dédié**, émis par la route : utilisateur pseudonyme, alerte, action, issue (refus compris), durée ; jamais de contenu. | Proposée |
| **D9** | **Stockage d'un instantané** (faits, ordre, versions, empreinte du texte) en insertion seule, par tenant, créé par provisionnement ; consultation par `auditor` et `admin`. Positionnement (sous-lot 8c) à décider. | Proposée |
| **D10** | **Visibilité du dépôt** à confirmer (le clone anonyme a réussi le 4 novembre 2026). | Proposée |

## Options considérées

- **D1.** (a) recherche seule : valable comme premier lot, valeur limitée. (c) rédaction libre contrôlée : écartée, expose aux menaces T1 (injection) et T4 (fausse autorité) et exige un contrôleur de fidélité : **Vision**.
- **D3.** (A) collection globale + filtre `tenant_id` : écartée, un filtre oublié fuit. (C) un store par tenant : écartée, lourde et contraire à « ajouter un pays = ajouter un tenant ». (D) pgvector par schéma de tenant : **réouvrable**, mais contredit la stack imposée (ChromaDB) et exigerait une décision explicite (cahier des charges §3).
- **D6.** (b) rester en GET avec contrôle `Sec-Fetch-Site` : dépend du navigateur. (c) accepter le risque : écartée.
- **D9.** Ne rien stocker : l'auditeur ne consulterait rien. Stocker le texte seul : insuffisant, l'alerte est mise à jour en place.

## Justification

- **D1.** Conserve l'esprit de l'ADR-007 : le modèle ne peut ni inventer ni modifier ce qui est affiché. Précision assumée : pour ordonner, le modèle lit du texte de corpus public (non sensible), contrairement à la 6b ; sa sortie reste contrainte et validée, et le serveur affiche **tous** les passages récupérés. Le gain du modèle n'étant pas démontré (réserve 2 de la 6b), il n'est introduit que sur preuve.
- **D3.** Reprend la discipline du point de passage unique de la Brique 6. En classe A, le risque principal est l'empoisonnement d'un corpus partagé : la provenance tient lieu d'isolation.
- **D6.** Ferme le risque de déclenchement par un site tiers et empêche que la future traçabilité attribue à un utilisateur une action qu'il n'a pas faite. Réutilise un mécanisme déjà validé.
- **D9.** L'instantané est nécessaire parce que `alertes` est mise à jour en place : sans lui, un audit relirait d'autres faits.

## Conséquences

- **Aucun fichier gelé n'est modifié** : `explication_ia.py`, `traductions/fr.py`, prompt système, options, `lot_v2.json`, `termes_interdits_v1.json`. Les nouveaux textes vont dans un **catalogue propre au RAG** (ADR-001). Le journal D8 est **distinct** du journal des replis (qui vit dans `explication_ia.py`, gelé). Le garde-fou `tests/test_gel_lot_v2.py` doit continuer à passer.
- **Correction post-validation de la 6b** (D6) : `explication_routes.py` (non gelé), le fragment du bouton et les tests de la route seront modifiés à l'étape 8. À tracer comme telle.
- **Briques 4, 5 et 6 intouchées.** Aucune donnée opérationnelle n'est indexée.
- **Un lot de validation RAG v1**, distinct du lot 6b v2, sera construit à l'étape 8.
- **Toute nouvelle table par tenant** (D9) et tout nouveau rôle sont créés par un provisionnement diagnostiqué et idempotent (leçon de l'ADR-005). L'event trigger de l'ADR-003 ne couvre que `alertes` et `detections` : la protection d'intégrité des nouvelles tables doit être explicite.
- **Section 10 des décisions verrouillées** à proposer au fondateur (« sans RAG » des sections 8 et 9 vise l'explication 6b, pas le RAG).
- **Mémoire** : estimation 9,6 à 11,1 Gio sur un budget de 13 Gio, dont plusieurs postes **non mesurés** (application, magasin vectoriel, embeddings). Faisabilité à confirmer par mesure.
- **Baseline « RAG < 2 s »** du document fondateur : tenable pour la recherche seule, pas pour une génération. À acter explicitement.

## Points non couverts par cet ADR

- Choix final de la version de ChromaDB et du modèle d'embeddings (étape 8, après vérification et mesure).
- Valeurs numériques des quotas (à calibrer sur mesures).
- Durée de conservation des instantanés (dépend du texte légal en vigueur).
- Corpus de tenant (classe B), question libre, rédaction libre, signature du manifeste, chiffrement au repos, haoussa et zarma : **Vision**.
- Positionnement du sous-lot de stockage (8c), non décidé (ADR-007 : « place non décidée »).

## Points à vérifier avant acceptation

1. **Référence juridique nigérienne.** Le document fondateur cite « Loi 2019-33 (protection des données) ». Le recoupement web du 4 novembre 2026 (sources secondaires, non officielles) indique que la loi 2019-33 porte sur la **répression de la cybercriminalité**, que la protection des données relevait de la loi **2017-28** (modifiée par la loi 2019-71), et que celle-ci aurait été **remplacée par la loi 2022-59** du 16 décembre 2022 (modifiée en 2023 et 2024). À confirmer sur le texte officiel avant toute indexation ou rédaction de durée de conservation.
2. **Visibilité du dépôt** : le clone anonyme a réussi ; la visibilité voulue est à confirmer.
3. **Licences** du corpus (GIABA, UNODC, GAFI, BCEAO).
4. **ChromaDB** : modèle d'isolation réel en mode embarqué, sérialisation, version.
5. **Application mono-processus** (validité du sémaphore en mémoire).
6. **ADR-000, ADR-002 et ADR-006** : relus partiellement ; contradiction éventuelle à signaler.

## Références

- `docs/ETAPE_7_CONCEPTION.md` (détail, menaces T1–T13, exigences S1–S14, corpus, mémoire, dépendances).
- ADR-001, ADR-003, ADR-004, ADR-005, ADR-006, ADR-007.
- `docs/ETAPE_6B_BILAN.md` §6 (réserves) ; `docs/etape_6b_donnees/gel_v2.json` (gel).
- `00_DECISIONS_VERROUILLEES.md`, sections 8 et 9.
