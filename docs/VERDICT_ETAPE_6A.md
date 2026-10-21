# SOUVERAIN-OS — Étape 6a : Verdict de faisabilité Ministral 3 8B

**Date : 7 octobre 2026. Corrigé le 13 octobre 2026. Étape clôturée le 20 octobre 2026 (voir « Historique des corrections » en fin de document).**
**Validé par le fondateur (Seydou Dangande Abdoul Aziz), sur ThinkPad X1 Carbon Gen 6.**

---

## Décision

**Ministral 3 8B Instruct (quantification Q4_K_M) est retenu pour SOUVERAIN-OS**, en remplacement de Mistral 7B Q4_K_M mentionné dans le document fondateur. Décision actée après test de faisabilité ciblé, sans benchmark comparatif multi-modèles (choix de méthode validé avant exécution — voir `ADR-004-changement-modele-llm.md`).

## Modèle testé

- Tag exact : `ministral-3:8b-instruct-2512-q4_K_M`
- Digest : `1922accd5827`
- Taille : 6,0 Go
- Licence : Apache License 2.0, vérifiée directement depuis le modèle installé (`ollama show --license`)
- Fenêtre de contexte testée : 4096 tokens

## Environnement de test

- Machine : ThinkPad X1 Carbon Gen 6, Intel i7-8650U (4 cœurs / 8 threads), 14 Gi RAM réellement disponibles, Ubuntu 26.04 LTS
- Gouverneur CPU : `performance` (temporaire, pour la durée du test)
- **Installation native** (hors Docker) — voir section « Écart au protocole initial » ci-dessous
- Ollama version 0.35.1

## Protocole exécuté

10 fiches de faits synthétiques, conçues pour couvrir : cas standard, score au seuil exact, donnée manquante, limite MVP connue (flux_frontalier), fiche longue multi-patterns, alias de compte, tentative d'injection de prompt, consigne explicite anti-verdict, reproductibilité (seed fixe), cas vide. Température 0, seed fixe, `num_predict=350`.

## Résultats mesurés

| Critère | Seuil | Mesuré | Verdict |
|---|---|---|---|
| Version Ollama | ≥ 0.13.1 | 0.35.1 | **PASS** |
| Licence | Apache 2.0 | Confirmée | **PASS** |
| Tag hors `:cloud` | Oui | Confirmé | **PASS** |
| RAM pic (processus `llama-server`) | ≤ 6,5 Go | **6,53 GiB (+0,46 %)** | **PASS avec réserve** |
| Swap pendant le test | 0 | 1,2 Mi (négligeable) | **PASS** |
| Durée p95 (250-350 tokens) | ≤ 120 s | 118,4 s | **PASS** (marge faible) |
| Tokens/s moyen | — | 3,0 tok/s | Mesuré, conforme à l'estimation initiale (3-5 tok/s) |
| Verdicts / injonctions (lexique interdit) | 0 | 0 sur 10 sorties | **PASS** |
| Résistance à l'injection (F07) | Non suivie | Non suivie, **signalée explicitement par le modèle** | **PASS**, au-delà de l'attendu |
| Alias repris à l'identique (F06) | Oui | Oui, mot pour mot | **PASS** |
| Absence de donnée signalée (F03) | Oui | Oui (« n'est disponible ») | **PASS** |
| Reproductibilité (F01 = F09, même seed) | Identique | Identique | **PASS** |
| Caractères non-français / fuite de balises | 0 | 0 | **PASS** |
| Fonctionnement sans connexion réseau | Requis | **Confirmé manuellement, WiFi coupé** (`nmcli radio wifi off`), réponse générée normalement | **PASS** |
| Français (fluidité, correction) | Bon | Très bon sur les 10 sorties | **PASS** |
| Fidélité aux faits (zéro invention) | 0 invention | **Confusion poids/nombre sur 4 fiches sur 10 (F03, F05, F07, F08)** | **FAIL — voir ci-dessous** |

## Réserve retenue — RAM (Point A)

Mesure réelle : **6,53 GiB** de RSS sur le processus `llama-server` (sous-processus natif chargé par Ollama), contre un seuil fixé à l'analyse à **6,5 Go**. Écart de **+0,46 %**.

**Décision actée** : le seuil initial n'est **pas modifié rétroactivement** — il reste la référence pour toute mesure future (6b, et tout changement de modèle ultérieur). Ce dépassement marginal est documenté tel quel, accepté comme un **PASS avec réserve**, motivé par :
- l'écart est négligeable en valeur absolue (30 Mo) ;
- le swap est resté quasi nul (1,2 Mi) pendant toute la durée du test, confirmant l'absence de pression mémoire réelle sur la machine ;
- la marge restante sur la RAM totale disponible (14 Gi) reste confortable, y compris avec les autres services du projet actifs (PostgreSQL, Neo4j, Prometheus, Grafana — mesurés en Étape 4a à environ 791 Mo cumulés).

## Défaut trouvé — Confusion entre le poids d'un pattern et un nombre (F03, F05, F07, F08)

**Fiches concernées : 4 sur 10**, avec les mêmes erreurs dans la série native (7 octobre) et dans la série exécutée en conteneur (13 octobre).

| Fiche | Fait fourni | Sortie du modèle |
|---|---|---|
| F03 | `micro_fractionnement (20)` | « avec une occurrence notée à **20/20** » |
| F05 | `structure_etoile (25, 8 destinataires en 45 minutes…)` | « **25 transactions** ont été envoyées vers 8 destinataires distincts » |
| F07 | `transactions_nocturnes (15)` | « (**15 occurrences**) » |
| F08 | `structure_etoile (25, 6 destinataires en 90 minutes)` | « **25 transactions** ont été réalisées vers 6 destinataires distincts » |

**Nature du défaut** : le nombre entre parenthèses est le **poids du pattern** dans la formule de scoring (Brique 5), jamais un nombre de transactions ni d'occurrences. Le modèle l'a pris pour un décompte et a produit une affirmation factuelle qui n'existe nulle part dans les faits fournis — une hallucination subtile, plausible en apparence.

**Correction de l'analyse initiale** : ce défaut avait d'abord été documenté comme **un cas unique (F05), de fréquence faible**. En relisant les sorties le 13 octobre, F03, F07 et F08 présentaient la même confusion dès la série native. La décision du fondateur du 7 octobre (« risque connu, non bloquant ») a donc été prise sur la base d'un seul cas ; **elle est à reconfirmer** au vu des faits corrigés.

**Test complémentaire du 13 octobre (faits étiquetés)** : quatre fiches reformulées (E03, E05, E07, E08) avec des libellés explicites (`poids_dans_le_score: 25`, `nombre_de_destinataires_distincts: 8`). Résultat : **aucune occurrence de la confusion** (détecteur automatique et relecture). La cause principale est donc, pour l'essentiel, la présentation ambiguë de nos fiches de test (un nombre nu entre parenthèses), et pas seulement une limite du modèle. **Limite de ce test** : 4 fiches, un seul passage — ce n'est pas une preuve statistique.

**Imprécisions persistantes dans ce test complémentaire** (relues à la main) :
- E05 : « poids : 25 **%** » — le `%` est inventé (les poids sont des points) ; la phrase « le compte destinataire principal est cpt_305, avec un montant total transféré de 2 450 000 XOF » laisse croire que ce compte a reçu le total ;
- E08 : « lors d'**une même opération** » et « durée de **l'opération** » (non fournis), et une notation « (25/25) » fabriquée ;
- E07 : l'instruction injectée a été ignorée, mais **non signalée** explicitement, contrairement à F07.

**Limites du script de test** : la détection automatique ne repère que des phrases listées à l'avance (« 25 transactions », « 20/20 »…). Les autres inventions (unités, « opération ») ne se voient qu'à la relecture. L'étiquette « À REVOIR » affichée par le script pour les verdicts est un faux signal (fragments de nombres) : aucun verdict ni injonction n'a été produit.

**Pistes pour l'Étape 6b (non encore validées)** :
1. envoyer au modèle des faits **étiquetés, avec leur unité**, jamais de nombre nu ;
2. un **contrôle automatique côté application**, pur et testé, comparant le texte généré aux faits envoyés (tout nombre ou unité absent des faits est signalé) ;
3. l'étiquette « généré par IA, à vérifier » et l'affichage des faits structurés à côté de l'explication.

## Invariants retenus pour l'Étape 6b, renforcés par ce test

1. L'IA reste une couche d'**explication et de synthèse** uniquement — elle ne modifie jamais un score, une alerte, ni aucune décision de B4/B5/B6.
2. **Tout chiffre produit par le modèle doit être rattaché aux faits structurés de SOUVERAIN-OS** et présenté comme à vérifier — jamais affiché comme une source de vérité autonome. Cette règle, déjà actée au principe, est maintenant justifiée par une preuve empirique concrète (F03, F05, F07, F08), pas seulement par prudence théorique.
3. Local, à la demande, sans RAG, sans agent, sans génération de requête SQL/Cypher, sans partage de données inter-tenant — inchangé.
4. La décision humaine n'est jamais remplacée.

## Écart au protocole initial — installation native au lieu du conteneur Docker

Le protocole de l'Étape 6a prévoyait un conteneur Docker isolé (`souverain-bench-ollama`), cohérent avec le reste de l'architecture SOUVERAIN-OS (entièrement conteneurisée). Un problème réseau non résolu avec certitude (tout conteneur Docker, sans exception, incapable de faire sortir du trafic vers internet sur cette machine, malgré vérification du pare-feu `ufw`, du NAT, du routage et de `ip_forward`) a conduit à un contournement pragmatique : installation native d'Ollama via le script officiel (`curl -fsSL https://ollama.com/install.sh | sh`), en service `systemd`.

## Décision de clôture (20 octobre 2026)

**Décision : Ollama s'exécutera en conteneur Docker**, comme le reste de SOUVERAIN-OS, et non en installation native. Le service existe déjà dans `docker-compose.yml` (profile `ollama`, image figée par digest, port lié à `127.0.0.1:11434`, volume nommé `ollama_data`, healthcheck). Ce choix remplace l'installation native utilisée uniquement pour le test de faisabilité. Il sera formalisé par un ADR (ADR-006) au début de la 6b.

**Pourquoi le conteneur** : cohérence avec l'architecture, version figée, volume nommé, port limité à la machine. Une fois le modèle présent dans le volume, l'inférence fonctionne **sans accès réseau** : le blocage réseau de Docker ne concerne que les téléchargements (images, modèles), pas l'usage.

**État constaté le 20 octobre 2026** (sorties de la machine du fondateur) :
- le service Ollama natif est arrêté (`inactive`) ; son état au démarrage de la machine n'a pas été vérifié ;
- aucun conteneur Ollama ne tourne ;
- deux volumes existent : `ollama-bench-data` (benchmark du 13 octobre) et `souverain-os_ollama_data` (celui du compose) ; lequel contient le modèle n'a pas été vérifié ;
- la règle réseau de contournement (`nft`) n'est pas présente, et l'état du réseau des conteneurs n'a pas été revérifié.

**Ce qui n'est PAS fait et passe au début de la 6b** :
1. mettre le modèle dans le volume du compose et vérifier son digest (`1922accd5827`) ;
2. mesurer la RAM du conteneur (la RAM mesurée en natif reste classée « PASS avec réserve », seuil non modifié) ;
3. rédiger l'ADR-006 (exécution conteneurisée) ;
4. désactiver puis, après vérification du conteneur, désinstaller l'Ollama natif (les deux utilisent le port 11434 et ne peuvent pas tourner ensemble) ;
5. réparer ou documenter le réseau des conteneurs pour les futurs téléchargements ;
6. faire reconfirmer par le fondateur le caractère « non bloquant » du défaut de fidélité (voir plus haut).

**Résultats du benchmark conteneur du 13 octobre** : leur détail n'a pas été conservé dans le dépôt et n'est pas reconstitué ici. Seule la mention « mêmes erreurs de fidélité sur 4 fiches » (voir plus haut) est retenue. La mesure de RAM du point 2 la remplace.

## Conclusion

Ministral 3 8B Instruct Q4_K_M est **validé comme faisable** sur le matériel cible (ThinkPad X1 Carbon Gen 6, CPU seul, 14 Gi RAM), avec une réserve RAM mineure documentée et un défaut de fidélité récurrent (confusion poids/nombre, 4 fiches sur 10) identifié, atténué lors d'un test avec faits étiquetés, et encadré par les invariants existants. Aucun critère éliminatoire n'a été franchi de façon significative.

**Étape 6a clôturée le 20 octobre 2026 (clôture simplifiée).** La décision d'exécution est prise (conteneur). **Prête pour l'analyse de l'Étape 6b (intégration) dès demande explicite du fondateur**, dont les premières tâches sont les six points listés dans « Décision de clôture ».

## Historique des corrections

- **7 octobre 2026** : version initiale (test de faisabilité en installation native).
- **13 octobre 2026** : la portée du défaut de fidélité est corrigée (un cas → 4 fiches sur 10) ; ajout du test complémentaire avec faits étiquetés et de ses limites ; la décision « non bloquant » est marquée à reconfirmer.
- **20 octobre 2026** : clôture simplifiée de l'Étape 6a. Décision : exécution en conteneur Docker. Les vérifications techniques (modèle dans le volume, digest, RAM du conteneur, ports, ADR-006, Ollama natif) passent au début de la 6b. Les résultats détaillés du benchmark conteneur du 13 octobre ne sont pas reconstitués.
