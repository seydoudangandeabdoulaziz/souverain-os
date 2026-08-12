# Journal des décisions d'architecture (résumé)

Ce fichier résume les décisions actées. Le détail argumenté de chaque décision se trouve dans `docs/adr/`.

| Décision | Résumé | ADR | Statut |
|---|---|---|---|
| Reconstruction Greenfield | Repartir de zéro sur tout le socle technique | ADR-000 | Acceptée |
| Gestion des dépendances | Workspace `uv`, Option A (pyproject par brique + lockfile racine unique) | ADR-000 | Acceptée |
| Ordre de reconstruction | Fondations → données → identité → ingestion → détection → scoring/alertes → graphe → investigation → audit | ADR-000 | Acceptée |

Toute nouvelle décision architecturale doit faire l'objet d'un nouvel ADR avant d'être appliquée.
