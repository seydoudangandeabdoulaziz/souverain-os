# Journal des décisions d'architecture (résumé)

Ce fichier résume les décisions actées. Le détail argumenté de chaque décision se trouve dans `docs/adr/`.

| Décision | Résumé | ADR | Statut |
|---|---|---|---|
| Reconstruction Greenfield | Repartir de zéro sur tout le socle technique | ADR-000 | Acceptée |
| Gestion des dépendances | Workspace `uv`, Option A (pyproject par brique + lockfile racine unique) | ADR-000 | Acceptée |
| Ordre de reconstruction | Fondations → données → identité → ingestion → détection → scoring/alertes → graphe → investigation → audit | ADR-000 | Acceptée |
| Multilinguisme produit | FR + langues locales par pays (haoussa/zarma pour le Niger) — objectif acté, implémentation différée à la Brique 7 et à une future brique notifications | ADR-001 | Acceptée |
| Moteur de traduction | NLLB-200-distilled-600M (Transformers/CTranslate2), distinct d'Ollama ; M2M100 en repli identifié pour le zarma si besoin | ADR-002 | Acceptée |

Toute nouvelle décision architecturale doit faire l'objet d'un nouvel ADR avant d'être appliquée.
