# SOUVERAIN-OS — Architecture

## Principe

Architecture multi-tenant conçue pour démarrer au Niger, puis s'étendre à l'UEMOA, puis au continent — sans jamais réécrire le code métier, uniquement en ajoutant des tenants.

## Architecture réellement implémentée

L'état des briques et des étapes est tenu dans [`avancement.md`](./avancement.md), source de vérité opérationnelle. Une validation de brique ne signifie pas que ses services sont démarrés en permanence. Cette page ne doit pas être utilisée pour déduire un état d'exécution.

À la date de la dernière mise à jour d'`avancement.md`, les briques 0 à 8 et les étapes transverses 1 à 7 sont validées dans leurs périmètres respectifs. L'étape 7 valide uniquement la conception du MVP RAG. **Le RAG n'est pas implémenté : l'étape 8 n'a pas commencé et n'est pas autorisée.**

## Architecture cible du RAG — non implémentée

Le schéma suivant représente uniquement la cible approuvée. Aucun composant RAG ci-dessous n'est présenté comme opérationnel.

```text
INGESTION HORS LIGNE (cible de l'étape 8)
Opérateur → paquet transverse rag/ → extraction et découpage déterministes
          → embeddings locaux → index documentaire public et autorisé

RECHERCHE (cible de l'étape 8)
Analyste → interface existante → souverain_app
                                  ├── authentification, rôle et contexte tenant
                                  └── validation du type de pattern fermé
                                           ↓ type de pattern uniquement
                           paquet rag/ → requête canonique et recherche locale
                                      → vérification des sources
Analyste ← passages documentaires sourcés, sans génération par LLM
```

Le paquet `rag/` ne reçoit aucun identifiant de tenant, n'accède à aucune base métier et n'accepte aucune question libre. `souverain_app` assemble l'application et porte l'adaptateur de contrôle d'accès ; les Briques 7 et 8 conservent leurs responsabilités propres. L'intégration est prévue dans le workspace `uv` avec un `pyproject.toml` dédié et l'unique `uv.lock` racine, puis dans l'environnement Docker de SOUVERAIN-OS. Ces éléments restent à implémenter après autorisation distincte.

## Ordre de reconstruction de référence

```text
Fondations → données → identité → ingestion → détection →
scoring/alertes → graphe → investigation → audit
```

La phase transverse et son état réel sont suivis dans [`06_ROADMAP_ET_BRIQUES.md`](./06_ROADMAP_ET_BRIQUES.md) et [`avancement.md`](./avancement.md). Cet ordre de référence ne vaut pas autorisation de commencer une étape.

## Principes transverses

- **tenant-aware** : les accès métier sont limités au tenant autorisé. Exception bornée du MVP RAG : le paquet documentaire public ne reçoit aucun identifiant de tenant et n'accède à aucune donnée métier ; `souverain_app` valide le contexte d'accès avant de transmettre le seul type de pattern fermé.
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

Le paquet transverse `rag/` et son `pyproject.toml` appartiennent à la cible, pas à l'état implémenté actuel.

Chaque brique reste installable et testable indépendamment (`uv sync --package <nom>`), tout en bénéficiant d'une résolution de dépendances cohérente au niveau du workspace.

## Règle de gouvernance architecture

Ce document ne remplace pas les ADR (`docs/adr/`). Toute décision architecturale nouvelle doit être documentée sous forme d'ADR avant d'être appliquée silencieusement.
