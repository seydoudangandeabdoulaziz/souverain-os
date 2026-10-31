# SOUVERAIN-OS — Étape 6b : bilan final

**Date : rédigé le 28 octobre 2026, mis à jour jusqu'au 30 octobre 2026.**
**Statut : VALIDÉE le 30 octobre 2026 par le fondateur (Seydou Dangande
Abdoul Aziz), sur ThinkPad X1 Carbon Gen 6.** La validation est prononcée « au
regard du périmètre défini », après les résultats des tests, les vérifications
avec de vraies sessions et les contrôles de sécurité. **Elle ne clôt pas les
réserves et améliorations du §6, qui restent ouvertes.**

Références : `docs/adr/ADR-007-explication-ia-selection-identifiants.md`,
`docs/ETAPE_6B_GRILLE_FIDELITE.md`, `docs/ETAPE_6B_LOT_VALIDATION_V2.md`,
`docs/etape_6b_donnees/gel_v2.json`.

---

## 1. Verdict

Aucun échec bloquant n'a été constaté dans les trois blocs du lot v2. Les
preuves attendues par le lot (§6) sont produites, et les vérifications
manuelles sont faites (§3, §3 bis et §3 ter). Le fondateur a validé l'étape le
30 octobre 2026. Les réserves sont documentées au §6 et toutes conservées.

**Portée.** Zéro échec bloquant sur ce lot ne garantit pas une fiabilité
générale : le lot compte 16 cas d'entrée et 8 entrées possibles pour le
modèle, sur une seule machine. Les invariants de l'étape sont respectés :
aucune modification des Briques 4, 5 et 6, aucun RAG, agent ni SQL/Cypher
généré, aucun texte généré ni identifiant de compte dans les journaux.

## 2. Ce qui a été construit

Design retenu (ADR-007, Option 1) : le modèle ne reçoit aucun fait. Il ne
voit que la liste des identifiants d'affirmations autorisés et retourne leur
ordre en JSON. Le serveur contrôle strictement la réponse, puis écrit les
phrases à partir des faits structurés. Toute réponse invalide, tout échec
d'Ollama, tout dépassement de délai et tout texte de plus de 120 mots
déclenchent un repli déterministe, sans nouvelle tentative.

Régularisation du cadre et construction des preuves (commits locaux, non
poussés au moment de ce bilan) :

| Commit | Contenu |
|---|---|
| `fd5256a` | ADR-001 reconstruit, ADR-007, textes de la route via `t()` |
| `ff63471` | fichiers résiduels et doublon retirés, README resynchronisé |
| `7bb83a3` | erreurs mypy corrigées |
| `b6a1d03` | phrases du serveur externalisées via `t()` |
| `3b133d1` | grille alignée sur l'ADR-007, lot v2, tests des blocs A et C |
| `37a1b30` | script de gel et de campagne du bloc B |
| `15f1a50` | journalisation C5 des replis (cinq codes) |
| `b647d4e` | timeout configurable, relevé `/api/ps`, ADR-007 à jour |
| `0ab1001` | gel du lot v2 |
| `1006e30` | résultats de la campagne du bloc B (`resultats_bloc_b_20261028_122418.json`) |

Ces commits n'étaient pas poussés à la dernière vérification du fondateur.
Ce bilan et `avancement.md` restent à commiter.

## 3. Preuves du lot v2

| Bloc | Contenu | Résultat |
|---|---|---|
| A — couche déterministe | 16 cas convertis en `FaitsAlerte` (C1, C2, C3, C4, C7, rejet des entrées hostiles) | **0 échec** |
| B — modèle réel | 8 entrées × 3 passages, plus 1 appel à froid | **0 sortie acceptée non conforme**, 0 repli, 0 erreur |
| C — contrôleur | 4 témoins historiques et 12 réponses invalides, 5 réponses valides, 720 permutations | **tous les invalides rejetés, 0 faux rejet** |

Les blocs A et C ont été rejoués au moment du gel : 114 tests passés
(`tests/test_lot_v2.py`). Tests ciblés de l'étape chez le fondateur le
27 octobre 2026 : **258 passés**, Ruff propre, mypy sans erreur.

**Suite complète** (PostgreSQL et Neo4j réels, chez le fondateur) :
**463 tests passés, aucun échec, aucune erreur** (86 s). Le total correspond
au calcul annoncé : 256 tests antérieurs + 207 ajoutés par la 6b.

**Autorisations (décision du 29 octobre 2026, après cette suite complète).**
23 tests ajoutés (`tests/test_explication_roles.py`) : matrice des rôles
`admin`, `analyst`, `auditor`, `visiteur` et rôle vide sur les deux routes, 403
sans lecture en base ni appel à Ollama, 404 conservé pour les rôles autorisés,
redirection vers `/login` sans session. Cinq mutations du code des routes
(retrait du contrôle, fragment qui ignore le rôle, 403 au lieu de 200 vide,
auditeur ajouté aux rôles autorisés, tenant évalué avant le rôle) sont toutes
détectées. Dans l'environnement de préparation (sans base de données) :
286 tests ciblés passés (281 + 5 d'intégration sans base), Ruff et mypy
propres. **La suite complète n'a pas
été rejouée depuis cet ajout** au moment de la rédaction de ce paragraphe ;
elle l'a été ensuite : voir le §3 ter.

Les cas A1 et A2 (le poids égal à un comptage, le score égal au seuil et au
comptage) sont vérifiés par code : chaque nombre affiché est celui des faits,
suivi de sa propre nature (`score`, `seuil`, `poids`, `transactions`), même
quand deux valeurs sont égales. Le texte produit pour A1 contient « Le score
est de 20 », « (poids 20) » et « fourni est 20 », chacun relié à son libellé.

Le gel (`gel_v2.json`, commit `0ab1001`) fige : modèle
`ministral-3:8b-instruct-2512-q4_K_M` (digest `1922accd5827…`), image Ollama
par digest, prompt (SHA-256 `52430bc8…`), `temperature: 0`, `seed: 42`,
`format: json`, contrôleur (SHA-256 `68b29a9c…`), seuil de 120 mots, lot et
liste de termes interdits. La campagne a été jouée avec le timeout du gel
(120 s).

## 3 bis. Vérifications manuelles dans le navigateur (29 octobre 2026)

Réalisées par le fondateur sur le tenant de démonstration
`tenant_demo_souverain`, avec le compte `analyste-demo@souverain.local`
(rôle `analyst`) et l'alerte `DEMO_COMPTE_001` (score 50, statut `ouverte`).

| Vérification | Résultat observé |
|---|---|
| Bouton « Expliquer cette alerte » et explication avec le modèle | Affichés. Mention « Explication générée localement par le modèle ». Les phrases arrivent dans l'ordre fenêtre, statut, motifs, transactions, score, compte |
| Valeurs affichées | Exactes : compte, statut `ouverte`, fenêtre 2026-10-15 au 2026-10-22, `compte_pivot` (poids 30), `micro_fractionnement` (poids 20), nombre de transactions « non disponible », « Le score est de 50, égal au seuil de 50 » (cas score égal au seuil, jusque-là testé par code seulement) |
| Avertissement final | Présent : « ni un verdict ni une recommandation d'action » |
| Conteneur Ollama arrêté | Mention « Explication de repli déterministe », mêmes valeurs, ordre canonique des phrases |
| Journal C5 en conditions réelles | Une ligne JSON avec cinq champs (voir ci-dessous) |

Ligne de journal relevée avec le conteneur arrêté :

`{"evenement": "explication_repli", "horodatage": "2026-10-29T23:09:40.313+00:00", "alerte_id": "29278543-3cc9-4b73-8a2f-0b577c9813c8", "cause": "modele_indisponible", "duree_ms": 5.7}`

Elle ne contient ni identifiant de compte, ni texte généré, ni message
d'exception. Dans l'extrait de journal fourni, le clic avec le modèle n'a produit
**aucune** ligne `explication_repli` : un succès n'est pas journalisé,
conformément à la conception.

Premier clic après le redémarrage du conteneur : la requête `/expliquer` a
duré **53,7 s** (journal de l'application, réponse 200 avec le modèle). C'est
une seconde observation à froid, supérieure aux 47,6 s que la règle du lot
aurait donnés comme timeout : avec cette valeur, ce clic aurait basculé en
repli. Elle conforte la décision de conserver 120 s sans la démontrer
(deux observations).

Constats sans rapport avec la 6b : le formulaire de fermeture répond 503 sur ce
tenant, qui n'est pas provisionné pour l'audit (limite connue, ADR-005) ; les
trois requêtes du graphe répondent « aucun résultat », ce compte de
démonstration n'étant pas dans Neo4j (comportement documenté depuis la
Brique 7).

## 3 ter. Vérifications après l'ajout des autorisations (30 octobre 2026)

Réalisées par le fondateur, avec de vraies sessions.

| Vérification | Résultat observé |
|---|---|
| **Suite complète** (PostgreSQL et Neo4j) | **486 tests passés** en 78 s (463 + 23), aucun échec |
| `analyst` : bouton et explication | Bouton et phrase d'aide affichés ; clic : `/expliquer` → **200**, explication « générée localement par le modèle », valeurs exactes, en 48,9 s (Ollama venait de redémarrer) |
| `auditor` : fragment | 200, **pas de bouton**, pas de « … » laissé à l'écran |
| `auditor` : accès direct à `/expliquer` | **403**, message `{"detail":"Vous n'avez pas les droits nécessaires pour cette action."}`, en 12,8 ms, sans appel au modèle |
| `admin` | Non vérifié visuellement ; couvert par les tests |

Remarque de méthode : deux requêtes `/expliquer` avaient d'abord reçu 303. C'était
la redirection d'un utilisateur sans session valide, pas un refus de rôle ; la
vérification a été refaite avec une session d'auditeur valide.

**Troisième observation d'un démarrage à froid** : 48,9 s, après 47,6 s
(campagne) et 53,7 s (premier clic). Les deux clics réels dépassent 47,6 s.
Elles confortent la décision de conserver 120 s sans la démontrer.

Constat sans rapport avec la 6b : la page de détail d'une alerte **déjà
fermée**, vue par l'analyste, affiche encore le formulaire « Fermer cette
alerte ». Comportement de la Brique 8 non examiné ici ; le formulaire n'a pas
été utilisé.

## 4. Mesures du bloc B (campagne du 28 octobre 2026)

| Mesure | Valeur |
|---|---|
| Appel à froid (après redémarrage du conteneur) | 47,6 s (1 seule mesure) |
| Appels à chaud (24) : médiane / p95 / extrêmes | 9,3 s / 11,6 s / 7,8 à 12,0 s |
| Taux de repli | 0 % |
| Matériel | processeur seul (`size_vram` = 0), contexte effectif 4096, keep_alive effectif 300 s |
| Pic de mémoire du conteneur | 6,284 Gio |

**Mémoire — unité et méthode.** Mesure par `docker stats --no-stream` sur le
conteneur Ollama. Le script attend 2 secondes entre deux relevés, et chaque
relevé dure lui-même un temps non mesuré : **la période réelle est donc
supérieure à 2 secondes** et un pic plus court pourrait ne pas avoir été
observé. L'unité est le gibioctet (Gio, soit
2^30 octets, noté « GiB » par Docker). Le seuil historique de 6,5 n'a jamais
précisé son unité : la 6a l'écrit « Go », l'ADR-006 et `avancement.md`
l'écrivent « Gio ». Lu en Gio, 6,284 est sous 6,5 ; lu en gigaoctets
décimaux, 6,5 Go équivaut à environ 6,05 Gio et 6,284 Gio le dépasse. Le seuil
n'est **pas modifié**. Le constat est consigné ; la décision sur ce critère
reste au fondateur.

**Écart historique de la 6a, signalé sans choisir de valeur.** Deux chiffres
coexistent dans le dépôt pour la mémoire de la 6a :

- **6,53 GiB** (`VERDICT_ETAPE_6A.md`, ADR-004) : RSS du processus
  `llama-server` natif, installation native d'Ollama, test de la 6a ;
- **6,618 Gio** (ADR-006, 21 octobre 2026) : pic mémoire du **conteneur**
  pendant une inférence de test à froid (72,74 s).

Ce ne sont pas deux arrondis d'une même mesure : la méthode (RSS d'un
processus natif contre mémoire d'un conteneur), la date et la charge
diffèrent. Les documents n'établissent pas lequel prévaut. La mesure du
28 octobre (6,284 Gio) est de même nature que celle de l'ADR-006 (conteneur),
mais aucune cause n'est démontrée pour l'écart entre les deux.

## 5. Décisions du fondateur (28 octobre 2026)

1. **Timeout de déploiement : 120 s conservé** (valeur par défaut). Un seul
   appel à froid ne justifie pas de le réduire. La règle du lot (1,5 fois le
   p95, jamais sous l'appel à froid) aurait donné 47,6 s. La variable
   `SOUVERAIN_OLLAMA_TIMEOUT` reste disponible pour un réglage ultérieur.
2. **Mémoire : pic de 6,284 Gio documenté** avec son unité et sa fréquence
   d'échantillonnage ; seuil de 6,5 inchangé ; écart historique 6,53 GiB /
   6,618 Gio signalé séparément (§4).
3. **Variation d'ordre de B7 : non bloquante** (§6, réserve 1).
4. **Ancien défaut poids/comptage de la 6a : « sans objet pour le design
   actuel ».** Cette classification ne signifie pas que le défaut a été
   corrigé rétroactivement : le modèle ne produit plus de texte libre, donc
   le mécanisme qui a causé la confusion n'existe plus dans ce design. La
   vérification porte sur le code et les tests A1 et A2 (§3).
5. **Autorisations de la route d'explication (variante 1).** `analyst` et
   `admin` déclenchent une explication ; `auditor` ne voit pas le bouton
   (fragment 200 vide) et reçoit 403 sur un déclenchement direct, sans appel à
   Ollama. Aucun effet sur le gel : seul `explication_routes.py` change, les
   empreintes restent celles du commit `0ab1001` (vérifié). Détail : ADR-007,
   section « Autorisations de la route d'explication ».

## 6. Réserves et limites (toutes conservées après la validation)

1. **Répétabilité de B7.** Sur les trois passages et l'appel à froid, le
   modèle a placé `motifs` et `transactions_indisponibles` dans un ordre
   différent au passage 1 (et à froid) par rapport aux passages 2 et 3.
   Vérification faite sur les sorties : les quatre sont des permutations
   exactes des six identifiants autorisés, sans doublon ; les passages 2 et 3
   sont identiques ; seules deux positions voisines diffèrent. Les phrases et
   le nombre de mots (47) sont les mêmes. **La cause est inconnue**, aucune
   explication n'est démontrée. Classée non bloquante par le lot.
2. **Apport du modèle limité.** Il ne fait qu'ordonner les phrases. Dans la
   campagne, l'ordre est presque constant, pour 8 à 12 s à chaud et 47,6 s à
   froid, contre 0 s pour le repli déterministe. Le gain de lisibilité n'est
   pas mesuré (limite déjà déclarée dans l'ADR-007).
3. **Un seul appel à froid mesuré**, juste après un redémarrage du
   conteneur. Un démarrage à froid après un redémarrage de la machine peut
   être plus long. L'inactivité décharge le modèle après 5 minutes
   (keep_alive effectif).
4. **Mesures sur la machine de développement uniquement**, sans GPU, avec un
   contexte de 4096. Aucune mesure sous charge concurrente.
5. `nombre_transactions` n'est pas alimenté par la route (`None`) : seules les
   entrées B1, B3, B5 et B7 sont atteignables aujourd'hui. Les huit ont été
   testées.
6. Une valeur invalide de `SOUVERAIN_OLLAMA_TIMEOUT` retombe sur 120 s sans
   message dans le journal.
7. Deux gabarits applicatifs contiennent un terme de la liste interdite :
   « Une vérification des données est nécessaire » et « réponse rejetée ».
   Le fondateur les conserve (exceptions explicites dans
   `tests/test_lot_v2.py`).
8. **Premier clic à froid : 53,7 s.** Aucun indicateur de chargement n'est
   prévu dans le fragment du bouton (lecture du code ; l'affichage n'a pas été
   observé visuellement). **Amélioration d'interface à traiter séparément, hors
   du périmètre de validation de la 6b.**
9. **Vérification dans le navigateur** : faite pour `analyst` et `auditor`
   (§3 ter) ; non faite visuellement pour `admin` (couvert par les tests). Elle
   porte sur deux tenants, démonstration et `tenant_ne`.
10. **Réserves distinctes, évolutions ultérieures** (ADR-007) : (a) aucune
    limite de fréquence ni de concurrence des générations ; (b) l'identité de
    la personne qui déclenche une génération n'est ni journalisée ni
    enregistrée ; (c) la route est un GET et le cookie est `SameSite=lax` : un
    site tiers pourrait faire lancer une génération (non testé) ; (d)
    stockage et consultation des explications par l'auditeur : non positionné
    dans l'ordre de construction.
11. Hors périmètre de la 6b, ouverts : en-têtes « Pattern » et « Détecté le »
   en dur dans la Brique 7, noms de patterns et statut affichés bruts,
   mot de passe de démonstration dans `scripts/demo_alertes.py`.

## 7. Suites après la validation

1. ~~Vérification dans le navigateur~~ et ~~suite complète~~ : faites
   (§3 ter), 486 sur 486.
2. ~~ADR-007 au statut « Accepté »~~ et ~~statut de l'étape 6b « VALIDÉE » dans
   `avancement.md`~~ : préparés avec ce bilan, à commiter par le fondateur.
3. Commiter la modification des routes, les tests, l'ADR-007, ce bilan et
   `avancement.md`, puis décider du push des commits locaux.
4. Proposition d'ajout de l'ADR-007 aux décisions verrouillées :
   `docs/PROPOSITION_DECISIONS_VERROUILLEES_6B.md`. L'application est
   réservée au fondateur.
5. Documents à mettre à jour séparément, car ils mentionnent encore la 6b « en
   test » : `README.md` et le statut de l'ADR-006 (« Accepté en principe —
   réserves ouvertes »). `ARCHITECTURE.md` est aussi en retard sur l'ensemble
   du projet (il décrit seulement la Brique 0), ce qui est antérieur à la 6b.
6. Réserves et améliorations ouvertes, à traiter séparément et dans l'ordre
   que décidera le fondateur : celles du §6, notamment l'indicateur de
   chargement du bouton (amélioration d'interface), la limite de fréquence et
   de concurrence, la traçabilité de l'utilisateur, le déclenchement possible
   par un site tiers, le stockage et la consultation des explications, l'unité
   du seuil de mémoire et l'écart historique de la 6a.
7. L'étape 7 (Sécurité IA/RAG, conception) est **non commencée** : elle ne
   démarre que sur demande explicite du fondateur. Aucune étape 6C n'est
   ajoutée.
