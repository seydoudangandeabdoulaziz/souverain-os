# Différenciation stratégique de SOUVERAIN-OS

**Statut : document de conception stratégique, en attente de dernière
lecture avant décision sur les extensions Briques 1/2.**

**Date de rédaction : 5 septembre 2026, révisé après recherche externe
suite aux corrections du fondateur sur la première version.**

**Méthode** : recherche web menée sur les solutions comparables
(Quantexa, Tazama, MaiGuard, PayGuard, GIABA/ECOAML, suites AML
entreprise classiques) avant rédaction — la première version de ce
document contenait trois erreurs factuelles, corrigées ici. Chaque
capacité est classée selon 5 catégories, comme demandé :

- **[PRATIQUE]** — bonne pratique industrielle standard, pas un différenciateur.
- **[DISPONIBLE AILLEURS]** — capacité déjà offerte par au moins un concurrent identifié.
- **[POTENTIEL]** — différenciateur potentiel de SOUVERAIN-OS, plausible mais à valider en conditions réelles.
- **[À PROUVER]** — différenciateur revendiqué mais non démontré à ce jour, y compris par SOUVERAIN-OS lui-même.
- **[FUTUR]** — ambition non implémentée, hors de toute comparaison possible aujourd'hui.

---

## 1. Solutions comparables — mise à jour après recherche

### Quantexa
Plateforme de "Contextual Decision Intelligence" : résolution
d'entités, graphe de relations, détection AML/fraude. Utilisée par
Standard Chartered, HSBC, et des agences gouvernementales.
**Correction de la première version** : Quantexa revendique
aujourd'hui explicitement une offre "Sovereign AI" — déploiement
cloud, cloud souverain, hybride ou on-premise au choix du client, avec
contrôle des données, des modèles et de la gouvernance. Contrat
récent de 175 millions £ avec HMRC (fisc britannique) pour un
programme national de "sovereign, governed AI" sur 10 ans. La
souveraineté n'est donc pas un vide de marché — c'est un axe de
positionnement mature chez un acteur bien financé.

### Tazama
Projet **open source** de monitoring transactionnel temps réel
(détection fraude + AML), gouverné par Linux Foundation Charities,
financé par la Fondation Gates, reconnu comme Digital Public Good.
Conçu explicitement pour les marchés émergents et les paiements
mobiles, architecture mettant l'accent sur la souveraineté des
données, la vie privée et la transparence. **Explore déjà des
synergies avec BankservAfrica, IPSL, JoPACC et BCEAO directement** —
c'est le comparateur le plus proche de SOUVERAIN-OS sur l'axe
"open source + Afrique + souveraineté", plus proche que Quantexa sur
ce point précis, même si son axe central reste la fraude
transactionnelle temps réel (scoring/typologies), pas
l'investigation par graphe de réseau au sens de la Brique 6.

### MaiGuard / PayGuard
Produits commerciaux (API/SDK) de détection de fraude en temps réel
pour fintechs et opérateurs Mobile Money africains. PayGuard :
décisions en moins de 100ms, modèles ML entraînés spécifiquement sur
les patterns de paiement africains, détection SIM swap/social
engineering/prise de contrôle de compte. Déployés par des banques,
telcos et fintechs à travers l'Afrique. **Correction de la première
version** : des acteurs africains natifs existent bel et bien sur ce
segment — l'affirmation "aucun acteur ne cible le Mobile Money
africain" était fausse.

Différence structurelle importante avec SOUVERAIN-OS : ces produits
sont des moteurs de décision **au moment de la transaction**
(bloquer/autoriser en <100ms), intégrés par API dans l'infrastructure
d'un opérateur — pas des plateformes d'investigation avec graphe de
réseau, audit humain et gouvernance multi-pays destinées à une
institution de supervision (CENTIF) plutôt qu'à l'opérateur lui-même.

### Suites AML entreprise classiques
NICE Actimize, SAS Financial Crimes, Oracle FCCM, LexisNexis, Napier
AI, HAWK:AI, Alessa. Scoring par règles + ML, criblage de sanctions,
gestion de cas, réduction de faux positifs — standard de l'industrie,
peu ou pas d'orientation Afrique/Mobile Money spécifique.

### GIABA / ECOAML
GIABA reste fondamentalement un organisme de **coordination
politique et d'évaluation mutuelle** (formation, standards FATF,
rapports pays) entre les 17 États membres. **Correction de la
première version** : GIABA porte désormais un outil nommé
**ECOAML**, décrit comme "outil régional AML/CFT" — son existence est
confirmée. Cependant, la page publique du service ne présentait aucun
contenu accessible au moment de cette recherche (erreur 404 en accès
direct), et je n'ai trouvé aucune description publique détaillée de
ses capacités réelles. **Je ne peux donc pas confirmer si ECOAML fait
de la coordination inter-FIU (échange de renseignement entre CENTIF
nationaux), de l'analyse transactionnelle opérationnelle, ou les
deux** — à traiter comme une inconnue, pas comme un fait établi dans
un sens ou dans l'autre. Ce qui est sûr : GIABA n'est pas un
fournisseur de plateforme de détection déployée *au sein* de chaque
institution nationale (rôle que vise SOUVERAIN-OS) — son rôle est
supra-national.

---

## 2. Classification par capacité

| Capacité | Statut |
|---|---|
| Graphe de relations pour l'analyse AML | **[PRATIQUE]** — Quantexa le fait depuis des années, mieux financé et plus mature. |
| Scoring pondéré multi-signaux, réduction faux positifs | **[PRATIQUE]** — standard chez tous les acteurs listés. |
| Audit trail, RBAC, gestion de cas | **[PRATIQUE]** — standard de l'industrie. |
| Déploiement souverain/on-premise/hybride | **[DISPONIBLE AILLEURS]** — offre mature chez Quantexa (contrat HMRC 175M£). |
| Open source + orientation marchés émergents/Mobile Money | **[DISPONIBLE AILLEURS]** — Tazama le fait déjà, avec synergies BCEAO explorées. |
| ML entraîné spécifiquement sur patterns de paiement africains | **[DISPONIBLE AILLEURS]** — MaiGuard, PayGuard le font déjà, en production. |
| Inférence LLM strictement locale (Ollama, zéro appel cloud, y compris pour le raisonnement RAG futur) | **[POTENTIEL]** — aucun des comparateurs identifiés ne combine ceci avec le reste ; Tazama et les suites entreprise n'utilisent pas de LLM local à ma connaissance. |
| Multi-tenant physique par pays dès la fondation (schema-per-tenant, pas une évolution ajoutée) | **[POTENTIEL]** — les concurrents vendent généralement une instance par client, pas un modèle "ajouter un pays = ajouter un tenant" pensé dès l'architecture. |
| Décision humaine comme invariant vérifié par le code (pas seulement déclaré) | **[POTENTIEL]** — testé concrètement (`test_fermeture_refusee_pour_un_auditor`), différenciateur de posture plus que de fonctionnalité brute. |
| Plateforme d'investigation + audit destinée à l'institution de supervision (CENTIF), pas à l'opérateur | **[POTENTIEL]** — MaiGuard/PayGuard visent l'opérateur (décision en <100ms), pas l'organe de contrôle étatique ; Tazama vise aussi plutôt le fournisseur de services financiers. |
| Combinaison open source + souverain + Sahel/UEMOA + investigation institutionnelle en une seule plateforme intégrée | **[À PROUVER]** — chaque brique de cette combinaison existe séparément ailleurs (Quantexa pour la souveraineté, Tazama pour l'open source africain, MaiGuard/PayGuard pour le ML localisé) ; personne d'identifié ne les combine toutes, mais SOUVERAIN-OS ne l'a pas encore démontré non plus au-delà d'un MVP à un seul tenant. |
| Mémoire criminelle collective inter-États | **[FUTUR]** — non implémenté ; occupe potentiellement un espace où GIABA/ECOAML pourrait déjà jouer un rôle de coordination (incertain, voir section 1). |
| Passeport financier africain | **[FUTUR]** — non implémenté, aucune comparaison possible à ce stade. |
| Standard de compliance UEMOA | **[FUTUR]** — non implémenté ; risque de chevauchement avec le rôle normatif déjà occupé par GIABA (à clarifier, pas à assumer résolu). |

---

## 3. Différenciateurs stratégiques révisés (6, avec statut de preuve)

1. **[POTENTIEL]** Inférence IA locale combinée à une architecture multi-tenant physique pensée dès la fondation — la combinaison précise, pas chacun des deux éléments pris isolément.
2. **[POTENTIEL]** Positionnement plateforme d'investigation et d'audit pour l'institution de supervision (CENTIF), distinct des moteurs de décision temps réel destinés à l'opérateur (MaiGuard, PayGuard) et des suites entreprise génériques.
3. **[POTENTIEL]** 100% open source et auditable, à la fois par l'État hébergeur et, potentiellement, par un tiers indépendant — Tazama partage ce principe, mais sans le graphe d'investigation par réseau ni le modèle multi-tenant pays par pays.
4. **[À PROUVER]** Décision humaine comme invariant architectural vérifié par test, pas comme clause déclarative — réel aujourd'hui dans le code, mais sa valeur différenciante face à un client institutionnel reste à démontrer, pas à supposer.
5. **[À PROUVER]** Combinaison intégrée souveraineté + open source + orientation Sahel/Mobile Money + gouvernance multi-pays en une seule plateforme — chaque élément existe séparément chez un concurrent, la combinaison complète reste à prouver en conditions réelles, pas seulement sur MVP à un tenant.
6. **[FUTUR, non comparable aujourd'hui]** Mémoire criminelle collective inter-États et standard de compliance UEMOA — ambitions qui pourraient chevaucher un rôle déjà occupé, au moins partiellement, par GIABA/ECOAML ; à clarifier avant d'investir dessus, pas à assumer comme un espace vide.

Je m'arrête à 6, pas 8 : les deux candidats supplémentaires envisagés
dans la première version (mémoire criminelle inter-États, passeport
financier africain) sont regroupés ici comme ambitions futures non
comparables, pas comme différenciateurs actuels distincts — les
présenter séparément aurait gonflé artificiellement la liste sans
ajouter de substance vérifiable.

---

## 4. Alignement avec la vision initiale — mise à jour

Les 6 points restent cohérents avec le document fondateur
(souveraineté, IA locale, multi-tenant Niger→UEMOA→UA, décision
humaine). Deux nuances supplémentaires par rapport à la première
version :

- La découverte de Tazama (open source, Gates Foundation, synergies
  BCEAO déjà explorées) change la lecture du calendrier concurrentiel
  : ce n'est plus seulement "un espace vide à occuper", c'est un
  espace où un acteur bien financé et institutionnellement soutenu
  avance déjà, avec un lien direct vers la même banque centrale
  (BCEAO) que celle visée par SOUVERAIN-OS.
- La valorisation cible de 10-50 milliards USD du document fondateur
  (comparaison à Palantir et Stripe) reste, comme déjà noté dans
  l'analyse précédente, déconnectée des différenciateurs réels
  d'aujourd'hui (1 tenant, 139 tests, aucune donnée réelle). Cette
  tension n'est pas nouvelle mais elle est confirmée, pas atténuée,
  par cette recherche : les comparateurs identifiés sont soit des
  entreprises massivement financées (Quantexa) soit des projets
  soutenus par des fondations internationales (Tazama) — le chemin
  vers cette valorisation, s'il existe, passe par une exécution
  démontrée, pas par l'absence de concurrents.

---

## 5. Risque concurrentiel à signaler explicitement

**Risque de calendrier, pas seulement de position** : Tazama est déjà
en production, open source, avec un backing institutionnel
(Linux Foundation, Gates Foundation) et des synergies BCEAO en cours
d'exploration. Si Tazama (ou un déploiement dérivé) devient le
standard de fait pour le monitoring transactionnel dans la zone UEMOA
avant que SOUVERAIN-OS n'atteigne un déploiement réel au-delà du MVP,
l'espace visé par SOUVERAIN-OS se réduit — non pas parce que
SOUVERAIN-OS serait moins bon techniquement, mais parce que le premier
déploiement institutionnel réel a souvent un avantage structurel
(données réelles accumulées, confiance déjà établie, coûts de
migration pour l'institution qui voudrait changer). Ce risque ne
remet pas en cause la pertinence du projet, mais justifie de ne pas
traiter la fenêtre de temps comme illimitée.

---

## Ce que ça implique pour la suite (à discuter, pas décidé ici)

Cette révision ne change pas la conclusion précédente sur la
priorité — la gestion des utilisateurs et des tenants (extensions
Briques 1/2) reste la chose qui empêche concrètement un usage réel
aujourd'hui, indépendamment de la position concurrentielle. Mais elle
ajoute un argument supplémentaire pour ne pas trop allonger le délai
avant un premier déploiement réel au-delà du MVP : la fenêtre
concurrentielle sur l'axe "souveraineté + Mobile Money + UEMOA" n'est
plus à considérer comme ouverte indéfiniment.

Aucune décision d'implémentation n'est prise dans ce document.
