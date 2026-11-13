# SOUVERAIN-OS — Roadmap de reconstruction

## Briques

| Brique | État |
|---|---|
| 0 — Fondations | **Reconstruite et validée** |
| 1 — PostgreSQL / TimescaleDB | **Reconstruite et validée** |
| 2 — Auth / RBAC | **Reconstruite et validée** |
| 3 — Générateur + ingestion | **Reconstruite et validée** |
| 4 — Détection Hybrid-Stream | **Reconstruite et validée** |
| 5 — Scoring + alertes | **Reconstruite et validée** |
| 6 — Neo4j | **Reconstruite et validée** |
| 7 — Dashboard / investigation | **Reconstruite et validée** |
| 8 — Audit + Human-in-the-loop | **Reconstruite et validée** (4 septembre 2026) |

Le flux fonctionnel principal (ingestion → détection → scoring/alertes
→ graphe → dashboard → audit) est désormais complet de bout en bout.

## Extensions V2 (après le flux principal 0–8)

| Extension | État |
|---|---|
| Brique 1 V2 — gouvernance des tenants (CLI : `create_tenant()`, activer, désactiver) | **Reconstruite et validée** (6 septembre 2026) |
| Brique 2 V2 — gouvernance des utilisateurs (routes web, réservées à `admin`) | **Reconstruite et validée** (6 septembre 2026) |

## Note structurelle — module d'assemblage `souverain_app/`

Introduit à l'analyse de la Brique 8, validé explicitement par le
fondateur : un nouveau répertoire racine `souverain_app/` (sibling de
`briques/` et `shared/`, pas une brique fonctionnelle) assemble
l'application FastAPI complète — `creer_application()` de la Brique 7
+ le routeur de la Brique 8, sans qu'aucune des deux briques ne
dépende de l'autre. Point d'entrée réel du dashboard complet :
`uv run souverain-app`. Détail complet dans
`00_DECISIONS_VERROUILLEES.md`, section 7.

## Phase transverse

Ordre consolidé après la revue d'architecture des 6 et 7 septembre 2026.
État détaillé dans `avancement.md`, qui fait foi.

| Étape | Nom | État |
|---|---|---|
| 1 | Hygiène de socle (backup/restore, `/health`, logs structurés) | **Validée** (7 septembre 2026) |
| 2 | Intégrité des données métier | **Validée** (8 septembre 2026) |
| 3 | UX/UI (fondations) | **Validée** (14 septembre 2026) |
| 4 | Prometheus/Grafana | **Validée** (4a et 4b, 19 septembre 2026) |
| 5 | Test de charge du pipeline actuel | **Validée** (19 septembre 2026) |
| 6 | Ollama/Mistral (→ Ministral 3 8B) | 6a **validée** (20 octobre 2026), 6b **validée** (30 octobre 2026) |
| 7 | Sécurité IA/RAG (conception du MVP RAG) | Validée par le fondateur — conception et périmètre uniquement ; réserves conservées |
| 8 | RAG | **Socle technique validé sur données synthétiques** (8 novembre 2026) ; aucune validation de pertinence sur corpus réel autorisé |
| 9 | Redis/Celery (conditionnel à l'étape 5) | Non commencée |
| 10 | SOUVERAIN-ID complet | Non commencée |
| 11 | PQC (ML-KEM + ML-DSA) | Non commencée |
| 12 | Résilience inter-États (conception) | Non commencée |

**Prérequis transversal avant l'étape 9 :** le correctif P0 d'identités PostgreSQL dédiées par tenant est appliqué à la base principale et validé techniquement le 13 novembre 2026. La migration 0008, le provisionnement des rôles, les connexions dédiées aux trois tenants et le retrait des privilèges de `souverain_app` sur leurs schémas ont été vérifiés. Les tests ciblés donnent 3 réussis et 4 ignorés. La validation fonctionnelle complète de tous les parcours applicatifs reste distincte.

Aucune étape 6C n'existe. Le fondateur a validé la conception de l'étape 7
dans le seul périmètre du MVP RAG et sous réserve des sujets reportés aux étapes
correspondantes. Le pilote expérimental du lot 8a.1 a été autorisé et exécuté ;
ses évaluations restent provisoires et assistées par IA, sans validation humaine
indépendante. Le fondateur a ensuite approuvé `intfloat/multilingual-e5-small`,
révision `614241f622f53c4eeff9890bdc4f31cfecc418b3`, et autorisé
l'implémentation de l'étape 8. Le socle technique est désormais validé sur
données synthétiques ; les publications FATF restent exclues jusqu'à vérification
des autorisations originales. Voir `avancement.md` pour les preuves et réserves.

La traçabilité disponible est partielle : le résumé V8 est conservé dans
`avancement.md`, mais pas sa sortie JSON détaillée ; le test des routes RAG est
présent, sans compte rendu d'exécution dédié retrouvé. Aucun test ni benchmark
n'a été relancé pour cette clôture documentaire. Voir aussi les errata datés du
rapport 8a.1 et de `docs/ETAPE_7_CONCEPTION.md`.

Pour le RAG, l'objectif approuvé est un p95 de recherche strictement inférieur
à deux secondes pour chacun des cinq types de patterns, indépendamment de toute
génération par LLM. L'étape 7 définit et valide le protocole reproductible ; la
mesure V8 synthétique a été réalisée au lot 8a ; les mesures déjà obtenues sont
consignées dans `avancement.md`. Elles ne constituent pas une validation de la
qualité de recherche sur un corpus documentaire réel autorisé.

**Note — changement de modèle LLM (7 octobre 2026)** : le libellé
« Ollama/Mistral » (étape 6) désigne désormais **Ministral 3 8B
Instruct Q4_K_M**, pas Mistral 7B Q4_K_M du document fondateur.
Décision actée après test de faisabilité (Étape 6a), détaillée dans
`00_DECISIONS_VERROUILLEES.md` section 8 et
`docs/adr/ADR-004-changement-modele-llm.md`. Mistral 7B reste cité ici
et dans le document fondateur comme référence historique uniquement.

L'explication IA des alertes (étape 6b, validée le 30 octobre 2026) suit le
design de sélection d'identifiants de
`docs/adr/ADR-007-explication-ia-selection-identifiants.md`
(`00_DECISIONS_VERROUILLEES.md`, section 9). Ses réserves ouvertes sont
consignées dans `docs/ETAPE_6B_BILAN.md`.

## Points en suspens — hors de cet ordre numéroté

Une brique "notifications citoyens" (alertes SMS multilingues aux
victimes de fraude, distincte du dashboard CENTIF de la Brique 7) a été
identifiée comme besoin réel (voir ADR-001, `docs/adr/`), mais **n'est
pas encore positionnée dans cet ordre** — sa place exacte (après la
Brique 7 ? en parallèle de la Brique 8 ?) reste à trancher explicitement
le moment venu, pas anticipée ici.

**Gouvernance multi-tenant / `create_tenant()`** : la « vraie gouvernance »
qu'attendait le contournement provisoire de la Brique 3
(`scripts/bootstrap_tenant_ne.sql`) existe désormais sous la forme de
l'extension **Brique 1 V2** (gouvernance des tenants par CLI), validée le
6 septembre 2026, après que le périmètre de la Brique 8 a été confirmé
strictement limité à Audit + Human-in-the-loop. Restent **hors périmètre et
non positionnés** : un rôle « Platform Operator » et la création de tenant
par interface web, différés jusqu'à un besoin réel (approche de la Phase 2,
premier export UEMOA). Leur place exacte reste à trancher explicitement le
moment venu, pas anticipée ici.

**Décision pendante non actée** : le marqueur `py.typed` manquant sur
la Brique 2 (découvert lors de la Brique 7, contourné localement par les
Briques 7 et 8 et par `souverain_app`) — toujours absent du dépôt à la date du
30 octobre 2026, non corrigé sans décision explicite du fondateur.

## Méthode

Une brique = architecture → implémentation → tests → documentation → validation.

Aucune brique suivante n'est commencée sans validation explicite.
