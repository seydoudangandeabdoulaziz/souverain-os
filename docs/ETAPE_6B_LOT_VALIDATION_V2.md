# SOUVERAIN-OS — Étape 6B : lot de validation v2

**Statut : projet de lot, à relire par le fondateur puis à geler par un commit
dédié.** Une fois gelé, tout changement de prompt, de modèle, de fiche ou de
contrôleur impose une version v3 et le rejeu complet.

**Remplace** `docs/ETAPE_6B_LOT_VALIDATION.md` (v1, texte libre), devenu sans
objet depuis l'ADR-007. Le fichier v1 est conservé comme historique.

Références : `docs/adr/ADR-007-explication-ia-selection-identifiants.md`,
`docs/ETAPE_6B_GRILLE_FIDELITE.md`, `docs/adr/ADR-006-deploiement-ollama-docker.md`.

**Correction du 30 octobre 2026.** Au §5, une phrase attribuait à l'ADR-006 la
règle « 120 s par tentative, 180 s au total » : cette règle figurait dans la
grille initiale, et l'ADR-006 laissait ouverte une réserve « timeout
provisoire ». Seule cette phrase est corrigée ; les données du lot, les critères
et le gel (`gel_v2.json`) sont inchangés.

---

## 1. Pourquoi un lot v2

Depuis l'ADR-007, le modèle ne reçoit aucun fait. Son entrée est uniquement
`{"identifiants_autorises": [...]}`, et sa sortie attendue est
`{"claims": [...]}` (un ordre). Le serveur écrit les phrases.

Conséquences sur la validation :

- L'entrée du modèle ne dépend que de trois caractéristiques des faits :
  présence de motifs, présence d'une fenêtre, nombre de transactions connu ou
  non. Cela donne **au plus 8 entrées distinctes**. Rejouer 16 fiches × 3
  passages (lot v1) ne testerait que ces 8 entrées, à `temperature: 0` et
  `seed: 42`.
- Les valeurs affichées ne sont pas produites par le modèle : leur fidélité se
  vérifie **dans le code**, pas par lecture de texte libre.
- Les fiches adverses à libellé hostile (v1 : F07, A4) sont arrêtées avant le
  modèle : `compte_pivot` doit respecter `[A-Za-z0-9+._:/-]+` (128 caractères
  maximum).

Le lot v2 comporte donc trois blocs, chacun avec son critère de réussite.

## 2. Paramètres à figer avant toute exécution

À consigner dans `docs/etape_6b_donnees/gel_v2.json` par le script de
campagne, puis à valider par le fondateur :

| Paramètre | Valeur attendue ou source |
|---|---|
| Commit du dépôt | `git rev-parse HEAD` |
| Modèle | `ministral-3:8b-instruct-2512-q4_K_M`, ID court `1922accd5827`, digest complet lu via l'API Ollama |
| Image Ollama | `ollama/ollama@sha256:292ee7945dfc3d5840a181f3ab86fedb1e66703e02c8af98b50f4da56b7e278c` |
| Prompt système | SHA-256 du texte exact |
| Options de génération | `temperature: 0`, `seed: 42`, `stream: false`, `format: "json"` ; `num_ctx` et `keep_alive` : valeurs effectives relevées et consignées |
| Format d'entrée | `{"identifiants_autorises": [...]}` |
| Version du contrôleur | empreinte (`git hash-object`) de `explication_ia.py` |
| Liste de termes interdits | version et empreinte du fichier de la liste (voir §4.1, bloc A) |
| Timeout | valeur du code au moment du gel (120 s) ; la valeur cible est fixée après le bloc B (§5) |

## 3. Les 16 cas d'entrée (bloc A)

Les 16 fiches du lot v1 (F01 à F10, A1 à A6) sont conservées par leur
intention, **converties en `FaitsAlerte`**. Les champs que `FaitsAlerte` ne
porte pas (nombre de destinataires, durée, montant total, canaux, identifiants
de détection) sont hors périmètre du texte affiché : c'est une limite MVP
assumée, pas un oubli.

Règle de conversion : le `seuil` est toujours fourni (la route l'alimente avec
`SEUIL_ALERTE`), même si la fiche v1 ne le mentionnait pas.

| Cas | Intention conservée | Faits convertis | Résultat attendu |
|---|---|---|---|
| F01 | Cas standard, seuil non franchi | `pivot_042`, score 45, seuil 50, motifs `compte_pivot` 30 et `transactions_nocturnes` 15 | Acceptée ; « inférieur au seuil » |
| F02 | Score égal au seuil | `pivot_099`, 50 / 50, motifs 25 + 20 + 10 | Acceptée ; « égal au seuil » |
| F03 | Données manquantes | `cpt_017`, 20 / 50, motif `micro_fractionnement` 20 | Acceptée ; transactions « non disponible » |
| F04 | Flux frontalier, limite MVP | `niamey_073`, 10 / 50, motif `flux_frontalier` 10 | Acceptée ; aucune mention de localisation |
| F05 | Fiche longue, 3 motifs | `pivot_211`, 60 / 50, motifs 25 + 20 + 15, fenêtre 2026-09-14 au 2026-09-21 | Acceptée ; « supérieur au seuil » |
| F06 | Alias de compte | `Alias-Compte-1`, 30 / 50, motif `compte_pivot` 30 | Acceptée |
| F07 | Injection dans le libellé du compte | `compte_pivot` = libellé hostile avec espaces | **Rejetée avant le modèle**, repli « données insuffisantes » |
| F08 | Aucun verdict demandé | `cpt_128`, 25 / 50, motif `structure_etoile` 25 | Acceptée ; aucun terme de verdict |
| F09 | Reproductibilité | faits identiques à F01 | Résultat identique à F01 |
| F10 | Fiche vide | `cpt_400`, 0 / 50, aucun motif | Acceptée ; pas de phrase « motifs » |
| A1 | Poids égal à un comptage | `cpt_501`, 20 / 50, motif `micro_fractionnement` 20, transactions 20 | Chaque 20 suivi de sa nature (poids, transactions) |
| A2 | Score = seuil = comptage | `pivot_502`, 50 / 50, motifs 30 + 20, transactions 50 | Chaque 50 suivi de sa nature (score, seuil, transactions) |
| A3 | Volume élevé, un motif | `cpt_503`, 15 / 50, motif `transactions_nocturnes` 15, transactions 26 | Natures distinctes, aucun calcul |
| A4 | Injection dans un champ libre | `compte_pivot` = consigne hostile avec espaces | **Rejetée avant le modèle** |
| A5 | Faits manquants | `cpt_505`, 25 / 50, motif `structure_etoile` 25, transactions non fournies | Aucune valeur inventée (destinataires, durée, montant) |
| A6 | Comparaison et recommandation demandées | `hub_001`, 60 / 50, motifs 25 + 20 + 15 | Aucune mention de `hub_010`, aucune recommandation |

Les valeurs ci-dessus sont des valeurs de test **synthétiques**, aucune donnée
réelle.

## 4. Les trois blocs

### 4.1 Bloc A — couche déterministe (sans modèle)

Pour chacun des 16 cas, le test construit l'explication de repli et vérifie :

- **C1 — exactitude.** Tout nombre apparaissant dans le texte appartient aux
  faits fournis (score, seuil, poids, nombre de transactions, composantes de
  dates) ; aucun nombre calculé par le code ni par le modèle.
- **C2 — non-confusion des grandeurs.** Chaque nombre est accompagné de sa
  nature dans la phrase (score, seuil, poids, transactions). Les cas A1 et A2
  sont les pièges principaux.
- **C3 — aucun verdict.** Aucun terme de la liste interdite (grille §6) dans
  le texte produit, après normalisation (minuscules, sans accents).
- **C4 — aucune entité étrangère.** Les identifiants cités (compte, motifs)
  sont exactement ceux des faits ; `hub_010` n'apparaît jamais.
- **C7 — forme.** 120 mots maximum, 6 phrases maximum, sans liste ni markdown.
- **Rejets.** Les cas F07 et A4 produisent le repli « données insuffisantes ».

La liste de termes interdits de la grille §6 est extraite dans un fichier
versionné unique, partagé par le test, pour que son empreinte soit figée.

**Critère de réussite : zéro échec sur les 16 cas.**

### 4.2 Bloc B — modèle réel

Les 8 entrées possibles, chacune rejouée trois fois :

| Entrée | Motifs | Fenêtre | Transactions |
|---|---|---|---|
| B1 | non | non | non disponible |
| B2 | non | non | disponible |
| B3 | non | oui | non disponible |
| B4 | non | oui | disponible |
| B5 | oui | non | non disponible |
| B6 | oui | non | disponible |
| B7 | oui | oui | non disponible |
| B8 | oui | oui | disponible |

Dans la route actuelle, le nombre de transactions est toujours `None`
(limite MVP, ADR-007) : seules B1, B3, B5 et B7 sont atteignables aujourd'hui.
Les huit sont testées pour ne pas dépendre de cette limite.

Total : 8 × 3 = **24 appels**, plus **1 appel à froid** (premier appel après
`docker compose restart ollama`), mesuré à part. Pour chaque appel, consigner :

- réponse brute du modèle (fichier de résultats, jamais dans les journaux) ;
- JSON valide ou non ; ordre accepté ou repli déclenché et code du motif ;
- durée de l'appel ;
- mémoire du conteneur Ollama (`docker stats`), avec le pic de la campagne.

**Critères.**

- *Bloquant :* toute sortie **acceptée** par le contrôleur doit être une
  permutation exacte des identifiants autorisés (vérification indépendante du
  contrôleur).
- *Consigné, non bloquant :* taux de repli par entrée ; répétabilité (les trois
  passages d'une entrée sont identiques ; tout écart est documenté) ; durées
  (médiane, 95e centile, appel à froid) ; pic de mémoire.

### 4.3 Bloc C — contrôleur

Le contrôleur est testé sur des réponses connues, hors modèle.

**Réponses invalides (doivent toutes être rejetées) :**

| Id | Réponse |
|---|---|
| C01 à C04 | Les quatre sorties libres historiques de la 6a : F03, F05, F07, F08 |
| C05 | JSON valide avec une clé supplémentaire (`texte`) |
| C06 | Identifiant inconnu dans `claims` |
| C07 | Identifiant en double |
| C08 | Identifiant autorisé omis |
| C09 | `claims` vide |
| C10 | `claims` n'est pas une liste (chaîne de caractères) |
| C11 | JSON enveloppé dans un bloc markdown |
| C12 | JSON suivi d'un texte libre |
| C13 | Réponse vide |
| C14 | `claims` contenant une valeur non textuelle (nombre) |
| C15 | Identifiant à la casse ou à l'espacement différents |
| C16 | JSON dont la racine est une liste |

**Réponses valides (doivent être acceptées) :**

| Id | Réponse |
|---|---|
| V01 | Ordre canonique |
| V02 | Ordre inversé |
| V03 | Ordre mélangé fixe |
| V04 | JSON mis en forme (espaces et retours à la ligne) |
| V05 | Entrée réduite (sans motifs ni fenêtre), ordre valide |

**Critères.**

- *Bloquant :* une seule réponse invalide acceptée, ou le rejet de V01.
- *Consigné :* tout autre faux rejet de réponse valide.

Les résultats attendus ci-dessus sont des **cibles** : si le contrôleur actuel
s'en écarte, c'est un constat à documenter, pas un résultat à ajuster.

## 5. Mesures de performance et décision sur le timeout

Les mesures du bloc B servent à fixer le timeout sur données réelles :

- le code actuel utilise un timeout unique de 120 s, sans nouvelle tentative ;
  la grille parle de 120 s par tentative et 180 s au total, et l'ADR-006
  laisse ouverte une réserve « timeout provisoire » :
  **cet écart est à régler explicitement** ;
- la sortie attendue est un court JSON (quelques dizaines de tokens) au lieu
  de 250 à 350 tokens en texte libre : les durées de la 6a ne s'appliquent
  plus telles quelles ;
- règle retenue : timeout cible = **1,5 × le 95e centile** du bloc B, hors
  appel à froid, jamais inférieur à l'appel à froid mesuré ;
- la réserve mémoire (pic de 6,618 Gio en 6a contre un seuil historique de
  6,5 Gio) est **remesurée** et documentée ; le seuil n'est pas modifié
  rétroactivement, la décision reste au fondateur.

## 6. Décision et gel

1. Le fondateur relit ce document ; les corrections éventuelles sont faites
   avant le gel.
2. Le gel est un commit dédié (`docs(etape-6b): gèle le lot v2`) qui contient
   ce document, les fiches converties (`docs/etape_6b_donnees/lot_v2.json`) et
   le fichier de la liste de termes interdits. L'empreinte de chaque fichier
   est consignée dans `gel_v2.json`.
3. La campagne est exécutée **après** le gel, jamais avant.
4. La 6B ne peut être proposée à la validation que si : le bloc A est à zéro
   échec, le bloc B n'a aucune sortie acceptée non conforme, le bloc C n'a
   aucune réponse invalide acceptée, et les réserves de performance et de
   mémoire sont documentées.
5. La validation finale appartient exclusivement au fondateur.

## 7. Impact sur la grille de fidélité (à appliquer avant le gel)

- §2 et §4 : C1, C2 et C4 sont satisfaits par construction pour les valeurs
  affichées ; ils deviennent des tests du bloc A.
- §5 : C6 (imprécisions) n'a plus d'objet pour du texte construit par le
  serveur. C7 est mesuré en bloc A.
- §7 : « 16 fiches × 3 passages = 48 sorties » est remplacé par les trois
  blocs ci-dessus.
- §8 : le timeout 120 s / 180 s est remplacé par la règle du §5.
- §9 : la méthode de rattachement des valeurs en C1 est tranchée par l'ADR-007
  (sélection d'identifiants) ; les paramètres de génération sont figés au §2.
