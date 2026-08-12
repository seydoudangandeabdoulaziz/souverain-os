# SOUVERAIN-OS — Architecture

## Principe

Architecture multi-tenant conçue pour démarrer au Niger, puis s'étendre à l'UEMOA, puis au continent — sans jamais réécrire le code métier, uniquement en ajoutant des tenants.

## Vue macro (cible finale)

```text
Ingestion API
    ↓
Normalisation FastAPI
    ↓
PostgreSQL + TimescaleDB
    ├── transactions
    ├── scores
    ├── données tenant-aware
    └── audit / gouvernance
    ↓
Redis / Celery
    ↓
Neo4j
    ↓
RAG : LlamaIndex + ChromaDB
    ↓
Ollama + Mistral 7B
    ↓
Couche PQC
    ↓
Dashboard / alertes
```

**Important** : ce schéma décrit la **cible finale**, pas l'état actuel. Voir `avancement.md` pour ce qui existe réellement aujourd'hui.

## État actuel (reconstruction Greenfield)

Seule la **Brique 0 (Fondations)** est implémentée. Aucun service métier (PostgreSQL, Neo4j, Ollama, etc.) n'est encore actif.

## Ordre de construction opérationnel

```text
Fondations → données → identité → ingestion → détection →
scoring/alertes → graphe → investigation → audit
```

Puis, en phase transverse, une fois le flux principal fonctionnel :
RAG, IA locale (Ollama/Mistral), PQC, Redis/Celery, monitoring (Prometheus/Grafana), SOUVERAIN-ID complet.

## Principes transverses

- **tenant-aware** : chaque table/service connaît son tenant.
- **country-aware** : chaque tenant est rattaché à un pays.
- **data-classification-aware** : chaque donnée est classifiée.
- **traitement local** : aucune inférence IA hors du territoire.
- **open source** : aucune dépendance propriétaire fermée.
- **fallback** : mode dégradé défini pour chaque composant critique.
- **sécurité par conception (Secure by Design)**.

## Gestion des dépendances (uv workspace)

```text
souverain-os/
├── pyproject.toml          ← workspace uv racine
├── uv.lock                 ← lockfile unique, résout tout le graphe
└── briques/
    ├── brique_00_fondations/pyproject.toml   ← dépendances isolées
    ├── brique_01_postgresql/pyproject.toml   ← dépendances isolées
    └── ...
```

Chaque brique reste installable et testable indépendamment (`uv sync --package <nom>`), tout en bénéficiant d'une résolution de dépendances cohérente au niveau du workspace.

## Règle de gouvernance architecture

Ce document ne remplace pas les ADR (`docs/adr/`). Toute décision architecturale nouvelle doit être documentée sous forme d'ADR avant d'être appliquée silencieusement.
