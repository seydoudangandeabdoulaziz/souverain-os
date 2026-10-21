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

Après le flux fonctionnel principal :

- RAG ingestion/retrieval ;
- Ollama/Mistral ;
- PQC ;
- Redis/Celery ;
- Prometheus/Grafana ;
- SOUVERAIN-ID complet ;
- autres composants nécessaires.

**Note — changement de modèle LLM (7 octobre 2026)** : le libellé
« Ollama/Mistral » ci-dessus désigne désormais **Ministral 3 8B
Instruct Q4_K_M**, pas Mistral 7B Q4_K_M du document fondateur.
Décision actée après test de faisabilité (Étape 6a), détaillée dans
`00_DECISIONS_VERROUILLEES.md` section 8 et
`docs/adr/ADR-004-changement-modele-llm.md`. Mistral 7B reste cité ici
et dans le document fondateur comme référence historique uniquement.

## Points en suspens — hors de cet ordre numéroté

Une brique "notifications citoyens" (alertes SMS multilingues aux
victimes de fraude, distincte du dashboard CENTIF de la Brique 7) a été
identifiée comme besoin réel (voir ADR-001, `docs/adr/`), mais **n'est
pas encore positionnée dans cet ordre** — sa place exacte (après la
Brique 7 ? en parallèle de la Brique 8 ?) reste à trancher explicitement
le moment venu, pas anticipée ici.

**Gouvernance multi-tenant / `create_tenant()`** (ajouté après
clarification du périmètre de la Brique 8, 28 août 2026) : la Brique 3
a laissé un contournement explicitement provisoire
(`scripts/bootstrap_tenant_ne.sql`) en attendant "la vraie gouvernance",
initialement supposée arriver en Brique 8. Le périmètre de la Brique 8 a
été confirmé strictement limité à Audit + Human-in-the-loop (voir
`00_DECISIONS_VERROUILLEES.md`), **confirmé de nouveau par
l'implémentation réelle de la Brique 8** (4 septembre 2026, désormais
validée sans `create_tenant()`) — `create_tenant()` reste donc, comme
les notifications citoyens, un besoin réel identifié mais **non
positionné** dans l'ordre numéroté. Aucune urgence MVP tant qu'un seul
tenant (`tenant_ne`) est actif ; redevient pertinent à l'approche de la
Phase 2 (premier export UEMOA). Sa place exacte reste à trancher
explicitement le moment venu, pas anticipée ici.

**Décision pendante non actée** : le marqueur `py.typed` manquant sur
la Brique 2 (découvert lors de la Brique 7, contourné localement une
seconde fois par la Brique 8) — toujours non corrigé sans décision
explicite du fondateur.

## Méthode

Une brique = architecture → implémentation → tests → documentation → validation.

Aucune brique suivante n'est commencée sans validation explicite.
