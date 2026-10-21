# Journal des décisions d'architecture (résumé)

Ce fichier résume les décisions actées. Le détail argumenté de chaque décision se trouve dans `docs/adr/`.

| Décision | Résumé | ADR | Statut |
|---|---|---|---|
| Reconstruction Greenfield | Repartir de zéro sur tout le socle technique | ADR-000 | Acceptée |
| Gestion des dépendances | Workspace `uv`, Option A (pyproject par brique + lockfile racine unique) | ADR-000 | Acceptée |
| Ordre de reconstruction | Fondations → données → identité → ingestion → détection → scoring/alertes → graphe → investigation → audit | ADR-000 | Acceptée |
| Multilinguisme produit | FR + langues locales par pays (haoussa/zarma pour le Niger) — objectif acté, implémentation différée à la Brique 7 et à une future brique notifications | ADR-001 | Acceptée |
| Moteur de traduction | NLLB-200-distilled-600M (Transformers/CTranslate2), distinct d'Ollama ; M2M100 en repli identifié pour le zarma si besoin | ADR-002 | Acceptée |
| Déploiement Ollama dans Docker | Environnement cible, avec réserve mémoire et tests de fidélité | ADR-006 | Acceptée en principe — réserves ouvertes |

## 8. Modèle LLM local — Ministral 3 8B (remplace la mention Mistral 7B)

**Ajouté le 7 octobre 2026, corrigé le 13 octobre 2026, complété le 20
octobre 2026, suite à l'analyse et
au test de faisabilité de l'Étape 6a (détail complet : `docs/VERDICT_ETAPE_6A.md`,
`docs/adr/ADR-004-changement-modele-llm.md`).**

- Le document fondateur (`01_DOCUMENT_REFERENCE_FONDATEUR.md`, Bloc 6)
  mentionne littéralement « Ollama + Mistral 7B Q4_K_M ». Cette mention
  **n'est pas modifiée** — elle reste la source historique. Le cahier des
  charges (`03_CAHIER_DES_CHARGES.md`) prévoit explicitement la possibilité
  d'un changement de stack sur décision explicite — c'est cette clause qui
  s'applique ici, pas une modification silencieuse.
- **Modèle retenu : Ministral 3 8B Instruct, quantification Q4_K_M**
  (tag Ollama : `ministral-3:8b-instruct-2512-q4_K_M`, digest `1922accd5827`,
  licence Apache 2.0 vérifiée directement depuis le modèle installé).
- Mistral 7B conservé uniquement comme référence historique dans l'ADR
  correspondant — jamais installé ni benchmarké dans le cadre de cette
  décision.
- **Aucun benchmark comparatif multi-modèles effectué**, par décision
  explicite du fondateur avant toute exécution — un test de faisabilité
  ciblé sur ce candidat unique a été jugé suffisant pour une fonction
  d'assistance à la demande, hors chemin critique de détection
  (B4/B5/B6 restent déterministes, inchangés).
- **Résultats du test de faisabilité** (machine réelle, ThinkPad X1 Carbon
  Gen 6, 10 fiches de faits synthétiques) : licence et version Ollama
  conformes, swap quasi nul, résistance à l'injection de prompt confirmée
  (signalement explicite par le modèle), fonctionnement confirmé sans
  connexion réseau (test manuel, WiFi coupé), zéro verdict ou injonction
  sur 10 sorties.
- **Deux réserves documentées** :
  - RAM mesurée à 6,53 GiB contre un seuil fixé à 6,5 Go (écart de
    0,46 %, accepté avec réserve, seuil non modifié rétroactivement) ;
  - une confusion récurrente entre le poids d'un pattern de détection
    et un nombre de transactions ou d'occurrences, présente sur 4 fiches
    sur 10 (F03, F05, F07, F08) — d'abord documentée à tort comme un cas
    unique, corrigée le 13 octobre 2026. Elle n'apparaît pas sur un test
    complémentaire avec des faits étiquetés explicitement (4 fiches, un
    passage), mais de petites imprécisions persistent. La décision
    « non bloquant » du 7 octobre, prise sur la base d'un seul cas, est à
    reconfirmer par le fondateur. Elle renforce, sans le modifier,
    l'invariant déjà acté : tout chiffre produit par l'IA doit être
    rattaché aux faits structurés de SOUVERAIN-OS et présenté comme à
    vérifier, jamais comme une source de vérité autonome.
- **Invariants inchangés** : IA explicative uniquement, locale, à la
  demande, sans impact sur B4/B5/B6, sans décision automatique, sans
  RAG, sans agent, sans génération de requête SQL/Cypher, sans partage
  de données inter-tenant. La décision humaine n'est jamais remplacée.
- **Exécution : conteneur Docker (décision du 20 octobre 2026, clôture de
  la 6a).** Le test de la 6a a été réalisé avec Ollama en **installation
  native** à cause d'un blocage réseau des conteneurs (le réseau WiFi
  utilisé réécrit à 1 le TTL des paquets entrants ; contournement temporaire
  par une règle `nft`, absente le 20 octobre). L'exécution cible est le
  service `ollama` du `docker-compose.yml` (profile `ollama`, image figée
  par digest, port lié à `127.0.0.1`, volume nommé). Une fois le modèle dans
  le volume, l'inférence fonctionne sans réseau ; le blocage ne gêne que les
  téléchargements. L'ADR-006 (`docs/adr/ADR-006-deploiement-ollama-docker.md`)
  formalise ce choix, accepté en principe avec réserves ouvertes.
  Le pic mémoire observé pendant le test du 21 octobre est de
  6,618 Gio, au-dessus du seuil historique de 6,5 Gio ; cette réserve reste
  ouverte. Aucun retrait d'Ollama natif n'est autorisé par cet ADR.
Toute nouvelle décision architecturale doit faire l'objet d'un nouvel ADR avant d'être appliquée.
