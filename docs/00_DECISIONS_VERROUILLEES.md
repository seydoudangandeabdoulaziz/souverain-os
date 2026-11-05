SOUVERAIN-OS — Décisions verrouillées

Statut : figées et validées explicitement par le fondateur. Date de verrouillage : 11 août 2026. Dernière mise à jour : 4 novembre 2026 (section 10 approuvée — périmètre du MVP RAG)

Ce document a valeur de source de vérité écrite. Il complète les documents existants (01_DOCUMENT_REFERENCE_FONDATEUR.md, 03_CAHIER_DES_CHARGES.md, 04_ARCHITECTURE_REFERENCE.md, 05_SECURITE_ET_GOUVERNANCE.md, 06_ROADMAP_ET_BRIQUES.md, 07_GUIDE_DEVELOPPEMENT.md, 08_AVANCEMENT.md, SOUVERAIN-OS_Prompt_Definitif.docx) et ne les remplace pas.

Toute nouvelle conversation du projet doit considérer ces points comme acquis, sans les rediscuter.

1. Machine de développement MVP
ThinkPad X1 Carbon Gen 6
Intel i7-8650U, 4 cœurs / 8 threads
16 Go RAM DDR4
512 Go SSD
Ubuntu 26.04 LTS

Toute estimation mémoire de brique doit être évaluée par rapport à ces 16 Go, et non par rapport à une ancienne référence de 8 Go/4 Go mentionnée dans du contenu antérieur au greenfield.

2. Gestion des dépendances — Option A : workspace uv
Un pyproject.toml à la racine du repository.
Un pyproject.toml propre à chaque brique, sous briques/brique_XX_nom/.
Dépendances isolées par brique, versions verrouillées (lockfile par brique).
Aucune dépendance inutile installée globalement au niveau racine.
Cette option respecte l'exigence du document fondateur (Bloc 14) : « chaque brique a son propre requirements.txt fixé », adaptée à l'écosystème uv.
3. Reconstruction Greenfield
Reconstruction complète : code, environnement, bases de données, migrations, configurations, conteneurs, tests, pipelines.
Aucun ancien code, ancienne base ou ancien état d'avancement ne constitue le socle technique actuel.
L'ancien code peut être consulté ponctuellement comme référence, jamais comme fondation.
La vision, les exigences fonctionnelles et les décisions explicitement conservées du document fondateur restent valables et ne doivent pas être réinventées.
4. Méthode de travail
Une seule brique à la fois.
Séquence obligatoire : COMPRENDRE → ARCHITECTURER → VALIDER → IMPLÉMENTER → TESTER → DOCUMENTER → VALIDER → BRIQUE SUIVANTE.
Analyse complète présentée et validée explicitement par le fondateur avant tout code.
Validation explicite requise après chaque brique avant de passer à la suivante.
Aucune modification silencieuse d'une décision d'architecture. Toute dépendance technique imposant un changement d'ordre ou de périmètre doit être signalée, expliquée, et validée avant d'être appliquée.
5. Périmètre de la Brique 0 — Fondations

La Brique 0 constitue uniquement le socle technique du projet.

Inclus :

Initialisation du repository Git
Structure des dossiers (briques/, docs/adr/, shared/)
Configuration Python via uv (workspace, cf. point 2)
Ruff, mypy, pytest, pre-commit
Docker Compose socle (sans service métier)
.env.example, .gitignore
Documentation initiale (README.md, ARCHITECTURE.md, avancement.md)
Tests de base et healthcheck minimal de l'environnement
Conventions de développement

Explicitement exclu de la Brique 0 :

PostgreSQL / TimescaleDB
Neo4j
Auth / RBAC
SOUVERAIN-ID
RAG (LlamaIndex / ChromaDB)
Ollama / Mistral
PQC (Kyber / Dilithium)
Redis / Celery
Monitoring métier (Prometheus / Grafana)
6. Multilinguisme (FR + langues locales par pays)

Ajouté le 15 août 2026, suite aux ADR-001 et ADR-002 (docs/adr/ du dépôt).

Objectif produit acté : français + langues locales selon le pays (haoussa et zarma pour le Niger ; fulfulde et autres à l'expansion UEMOA). Détail argumenté dans ADR-001 (décision produit) et ADR-002 (choix technique du moteur de traduction).
Implémentation différée à la Brique 7 (dashboard) et à une future brique notifications citoyens (non planifiée à ce jour dans l'ordre de reconstruction). Aucune des Briques 0 à 4 validées n'affiche de texte à un utilisateur humain — rien à traduire pour l'instant.
Règle contraignante pour la Brique 7, dès son premier jour d'analyse : aucun texte utilisateur écrit en dur dans le code — externalisation systématique dans des fichiers de traduction, même si seul le français est livré initialement.
Langue déterminée par préférence explicite de l'utilisateur/citoyen quand elle existe, sinon valeur par défaut dérivée de country_code (déjà présent dans le schéma tenant depuis la Brique 1 — aucune modification de schéma nécessaire pour ce mécanisme).
Moteur technique retenu : NLLB-200-distilled-600M (Hugging Face Transformers, éventuellement CTranslate2 pour l'inférence CPU optimisée) — composant technique distinct d'Ollama, pas d'intégration à la stack Mistral existante.
Cas particulier du zarma (langue à très faibles ressources) : qualité à évaluer concrètement au moment de l'implémentation ; M2M100 identifié comme repli, avec le corpus de recherche "Feriji" (français-zarma) comme ressource prioritaire à investiguer.
Traduction assistée par IA autorisée uniquement pour un premier jet, relecture humaine par un locuteur natif obligatoire avant toute mise en production. Aucune traduction en temps réel sans validation préalable, en particulier pour les messages citoyens (SMS d'alerte fraude) — les templates sont traduits et validés une fois, jamais générés à la volée.
7. Brique 8 — Extensions validées (audit trail + human-in-the-loop)

Ajouté le 4 septembre 2026, suite à l'analyse et l'implémentation de la Brique 8 (validée le même jour).

require_role() (Brique 2) paramétré. Ajout d'un paramètre user_dependency (défaut get_current_user, rétrocompatible), permettant de vérifier un rôle contre une résolution de session différente du header Authorization: Bearer — en particulier get_current_user_from_cookie (Brique 7), nécessaire pour toute route du dashboard combinant RBAC et session cookie. Zéro régression vérifiée sur test_rbac.py (fichier de test inchangé).
souverain_app/ — module d'assemblage neutre. Nouveau répertoire racine (sibling de briques/ et shared/, pas une brique fonctionnelle du document fondateur) qui assemble l'application FastAPI complète : creer_application() de la Brique 7 + include_router() du routeur de la Brique 8, sans qu'aucune des deux briques ne dépende de l'autre. Introduit pour respecter la contrainte "zéro fichier Brique 7 modifié en logique" tout en exposant les routes d'écriture de la Brique 8 sur la même instance FastAPI que le dashboard. Point d'entrée réel du dashboard complet désormais : uv run souverain-app (souverain-dashboard reste disponible pour isoler un bug Brique 7 pure, sans les routes d'écriture de la Brique 8).
Immuabilité de audit_log par privilège PostgreSQL réel. Rôle PostgreSQL dédié souverain_brique8_audit (créé par la migration de la Brique 8), privilèges strictement limités à INSERT/SELECT sur {tenant}.audit_log (+ SELECT/UPDATE sur {tenant}.alertes, nécessaire à l'atomicité de la fermeture d'alerte — une seule transaction, un seul rôle). Jamais UPDATE ni DELETE sur audit_log — protection contre une modification ou suppression même en cas de bug applicatif, en complément (pas en remplacement) de la discipline applicative (aucune route de modification n'existe). Validé comme "défense en profondeur", pas comme discipline applicative seule.
Confirmation : le périmètre de la Brique 8 reste strictement limité à la fermeture d'alerte (motif structuré + commentaire optionnel) et son audit — create_tenant() et les notifications citoyens restent hors périmètre, non positionnés dans l'ordre numéroté (voir 06_ROADMAP_ET_BRIQUES.md).
8. Modèle LLM local — Ministral 3 8B (remplace la mention Mistral 7B)

**Ajouté le 7 octobre 2026, complété le 20 octobre 2026, suite à l'analyse et au test de faisabilité de
l'Étape 6a (détail complet : `VERDICT_ETAPE_6A.md`, `docs/adr/ADR-004-
changement-modele-llm.md`).**

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
  téléchargements. L'ADR-006 formalisera ce choix au début de la 6b, avec la
  vérification du digest du modèle, la mesure de RAM du conteneur et le
  retrait de l'Ollama natif (voir `VERDICT_ETAPE_6A.md`, section « Décision
  de clôture »).

9. Explication IA des alertes — sélection d'identifiants (ADR-007)

**Ajouté le 30 octobre 2026, suite à la validation de l'étape 6b (détail :
`docs/adr/ADR-007-explication-ia-selection-identifiants.md`,
`docs/ETAPE_6B_BILAN.md`).**

- **Design retenu : sélection d'identifiants.** Le modèle ne reçoit aucun fait.
  Il reçoit uniquement la liste des identifiants d'affirmations autorisés et
  retourne leur ordre en JSON. Le serveur contrôle strictement la réponse, puis
  écrit lui-même les phrases à partir des faits structurés. Le modèle ne peut ni
  inventer, ni modifier une valeur affichée.
- **Repli déterministe.** Toute réponse invalide, tout échec d'Ollama, tout
  dépassement de délai et tout texte de plus de **120 mots** produisent une
  explication construite sans le modèle. **Aucune régénération** : à
  `temperature: 0` et `seed: 42`, une seconde tentative redonnerait la même
  sortie.
- **Modèle et exécution inchangés** par rapport à la section 8 : Ministral 3 8B
  Instruct Q4_K_M (digest `1922accd5827`), service `ollama` du
  `docker-compose.yml`, image figée par digest.
- **Autorisations de la route d'explication.** `analyst` et `admin` peuvent
  afficher le bouton et déclencher une explication. `auditor` ne voit pas le
  bouton (le fragment répond 200 vide) et reçoit **403** sur un déclenchement
  direct, sans appel à Ollama ni lecture en base. Tout rôle inconnu est refusé.
- **Timeout.** Valeur par défaut **120 s**, une seule tentative. Réglable par la
  variable d'environnement `SOUVERAIN_OLLAMA_TIMEOUT` : valeurs valides de 5 s à
  300 s ; variable absente, invalide ou hors bornes : 120 s. La campagne du
  lot v2 a été jouée avec 120 s. Décision du fondateur du 28 octobre 2026 :
  conserver 120 s, un seul appel à froid mesuré ne justifiant pas de le réduire.
- **Journalisation des replis.** Chaque repli produit une ligne JSON avec
  horodatage, identifiant d'alerte, cause (liste fermée : `faits_invalides`,
  `modele_indisponible`, `delai_depasse`, `reponse_invalide`,
  `texte_trop_long`) et durée mesurée par horloge monotone. Jamais de texte
  généré, de message d'exception, d'identifiant de compte ni de valeur de la
  variable de timeout.
- **Textes.** Aucun texte utilisateur n'est écrit en dur dans les routes ni
  dans les phrases du serveur : tout passe par `t()` (ADR-001, reconstruit
  rétroactivement le 25 octobre 2026).
- **Preuves et gel.** Lot de validation v2 (`docs/ETAPE_6B_LOT_VALIDATION_V2.md`),
  gelé par `docs/etape_6b_donnees/gel_v2.json` (commit `0ab1001`). Toute
  modification du prompt, du modèle, du contrôleur, des traductions ou du lot
  impose une version suivante du lot et le rejeu complet.
- **Invariants de la section 8 maintenus** : IA explicative uniquement, locale,
  à la demande, sans impact sur les Briques 4, 5 et 6, sans décision
  automatique, sans RAG, sans agent, sans génération de requête SQL ou Cypher,
  sans partage de données entre tenants. La décision humaine n'est jamais
  remplacée. Tout chiffre affiché est rattaché aux faits structurés.
- **Ancien défaut de fidélité de la 6a** (confusion poids/comptage) : classé
  « sans objet pour le design actuel » le 28 octobre 2026. Cette classification
  ne signifie pas que le défaut a été corrigé rétroactivement : le modèle ne
  produit plus de texte libre, donc le mécanisme en cause n'existe plus dans
  ce design.
- **Portée de la validation.** Prononcée « au regard du périmètre défini ». Elle
  ne vaut pas garantie de fiabilité générale (16 cas, 8 entrées de modèle, une
  seule machine, processeur seul) et **ne clôt pas les réserves** consignées
  dans `docs/ETAPE_6B_BILAN.md` (§6).

Ordre de reconstruction rappelé (déjà validé)
Fondations
PostgreSQL / TimescaleDB multi-tenant
Auth / RBAC minimal + fondations SOUVERAIN-ID
Générateur + ingestion de transactions synthétiques
Moteur de détection Hybrid-Stream
Scoring + alertes
Graphe Neo4j
Dashboard / investigation
Audit trail + Human-in-the-loop

Ordre entièrement reconstruit et validé (0 à 8) au 7 octobre 2026 .

Puis, en phase transverse : RAG, Ollama/Mistral, PQC, Redis/Celery, Prometheus/Grafana, SOUVERAIN-ID complet.

Règle de gouvernance de ce document

Ce fichier n'est modifié que par décision explicite du fondateur. Toute IA travaillant sur ce projet doit le consulter comme référence des décisions déjà tranchées, avant de proposer une nouvelle analyse ou de rouvrir une question déjà close.

## 10. MVP RAG — périmètre documentaire autorisé

**Statut : décision approuvée explicitement par le fondateur.** Cette décision est strictement limitée au MVP RAG défini dans la présente section. Elle ne modifie pas rétroactivement les décisions historiques des étapes 6a et 6b, ni les sections 8 et 9.

### Objet et portée

Cette section autorise la conception du MVP RAG de SOUVERAIN-OS, puis son éventuelle implémentation à l’étape 8 après une autorisation distincte. Elle est limitée à la recherche de références documentaires pour aider un analyste dans son investigation. Elle n’autorise aucune autre évolution de l’IA ou du pipeline métier.

### Corpus et données

Le corpus du MVP ne contient que des documents publics ou dont les droits d’acquisition, d’indexation et de présentation sont établis. La provenance, la version et les droits d’utilisation sont vérifiés pour chaque source avant ingestion.

Aucune transaction, donnée de compte, alerte, détection, décision humaine, commentaire d’analyste, ni autre donnée opérationnelle ou financière n’est intégrée au corpus, transformée en embedding, indexée ou conservée par le magasin vectoriel.

La recherche utilise une requête construite par le serveur depuis une liste fermée de types de patterns. Elle n’accepte pas de question libre en MVP et ne transmet au moteur de recherche aucun identifiant de compte, fait financier, contenu d’alerte ou décision humaine.

Les requêtes de recherche et les passages récupérés ne sont conservés durablement ni dans les journaux, ni dans un cache, ni dans un autre mécanisme de stockage. Seuls le corpus autorisé et l’index nécessaires à la recherche peuvent être conservés. Toute conservation durable supplémentaire requiert une décision ultérieure explicite du fondateur.

### Résultats et protection contre les injections documentaires

La première version présente les passages documentaires retrouvés avec leurs références vérifiables. Elle n’utilise aucun LLM pour rédiger, résumer ou classer les résultats.

Les documents et passages récupérés sont des **données non fiables**. Ils ne peuvent modifier les instructions, les règles de sécurité ou les autorisations du système et ne doivent jamais être interprétés comme des instructions par un éventuel composant IA futur.

Toute évolution qui transmettrait des passages à un composant IA devra faire l’objet d’une justification mesurée, d’une décision distincte du fondateur et de tests de sécurité et de qualité appropriés. Ce composant devra appliquer des contrôles techniques empêchant l’interprétation des documents comme instructions, notamment en séparant les instructions de confiance du contenu documentaire et en contrôlant strictement ses sorties et capacités.

### Architecture et fonctionnement

Le composant RAG est dédié et respecte le workspace `uv`, les limites entre briques et le sens des dépendances existantes. LlamaIndex reste dans la stack déclarée du projet. Les embeddings fonctionnent localement ; aucun modèle d’embedding n’est retenu sans évaluation préalable de sa qualité, de sa consommation mémoire, de ses performances et de sa licence.

ChromaDB en mode embarqué est réservé aux tests et au développement contrôlés. Avant toute exploitation opérationnelle nécessitant le magasin vectoriel, un mode serveur authentifié est requis. Ce serveur doit être protégé contre les accès non autorisés ; il ne peut pas être directement exposé au réseau sans contrôle d’accès adapté.

Le MVP fonctionne localement et ne dépend d’aucun service cloud externe pour l’ingestion, les embeddings ou la recherche.

### Interdictions du MVP

Le RAG ne modifie ni les résultats de détection, ni les scores, ni les alertes, ni les graphes. Il ne prend aucune décision à la place d’un humain, ne génère aucune requête SQL ou Cypher et ne crée aucun partage de données entre tenants.

Le MVP n’ajoute aucun snapshot d’explication ni table d’audit durable. Les journaux opérationnels sont minimisés : ils ne contiennent ni texte généré, ni requêtes de recherche, ni passages récupérés, ni données financières, ni identifiants de comptes, ni contenu sensible.

### Sécurité et exposition

Aucune exposition réseau non maîtrisée n’est autorisée. Toute exposition ultérieure doit être précédée d’une décision et de protections adaptées aux accès, aux méthodes HTTP, au CSRF, à l’authentification et à la séparation des tenants. Ces protections doivent préserver le fonctionnement des services existants, notamment le scraping Prometheus.

### Réserves conservées

Cette décision ne vaut pas validation des licences de toutes les sources, vérification juridique officielle des références nigériennes, choix d’un modèle d’embedding, définition des quotas futurs, autorisation de snapshots ou de journaux durables, choix de déploiement opérationnel de ChromaDB, autorisation de collections privées par tenant, ni clarification de la visibilité ou de la licence du dépôt. Ces sujets restent soumis aux conditions et décisions propres à leur périmètre.

### Conditions de validation de l’étape 7

La présente section ne déclare pas l’étape 7 validée et n’autorise pas l’étape 8. La validation de l’étape 7 exige des critères vérifiables et des preuves portant au minimum sur :

1. le respect du périmètre documentaire autorisé ;
2. l’absence de données opérationnelles dans le corpus, les embeddings et les journaux ;
3. **Séparation des accès :** démontrer que seul le service applicatif autorisé peut extraire les types de patterns prévus dans la liste fermée et les transmettre au composant RAG. Celui-ci ne peut accéder directement à aucune donnée opérationnelle, base métier ou donnée de tenant. Aucune information propre à un tenant ne peut être récupérée ou exposée à un autre tenant ;
4. la traçabilité et la vérification des sources documentaires présentées ;
5. le fonctionnement local du RAG, sans dépendance à un service cloud externe ;
6. les contrôles d’accès, les méthodes HTTP et les protections CSRF applicables ;
7. la journalisation minimale, sans conservation durable des requêtes ni des passages récupérés ;
8. les tests de sécurité, notamment contre les injections documentaires et les accès inter-tenant ;
9. **Performance de la recherche :**
   - **Étape 7 — protocole :** définir et valider le protocole de mesure du temps de recherche, indépendamment de toute génération par LLM. Le protocole précise le jeu de requêtes issu de la liste fermée des patterns, le corpus et sa version, l’environnement matériel et logiciel, les conditions de cache et de concurrence, les étapes chronométrées — construction de la requête, calcul local de l’embedding, recherche et vérification des sources — ainsi que la méthode statistique, le nombre de répétitions et les éléments à consigner pour permettre une mesure reproductible.
   - **Étape 8a — mesure réelle :** effectuer la mesure selon le protocole approuvé. L’objectif est un p95 strictement inférieur à deux secondes. Les conditions d’exécution et les résultats sont documentés de façon à permettre leur reproduction et leur vérification. L’absence de mesure réelle à l’étape 7 ne constitue pas un échec de cette étape.

La validation finale de l’étape 7 appartient exclusivement au fondateur. L’étape 8 ne commence qu’après une autorisation distincte.
