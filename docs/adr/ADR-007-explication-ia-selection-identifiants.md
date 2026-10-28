# ADR-007 — Explication IA des alertes : sélection d'identifiants plutôt que rédaction libre

**Statut : Proposé.**
**Date : 25 octobre 2026.**
**Décideur : Seydou Dangande Abdoul Aziz (fondateur).**
**Contexte : Étape 6b. Complète ADR-004 (modèle) et ADR-006 (déploiement).**

---

## Contexte

La grille de fidélité (`docs/ETAPE_6B_GRILLE_FIDELITE.md`) et le lot de
validation (`docs/ETAPE_6B_LOT_VALIDATION.md`) supposent que le modèle
**rédige un texte libre** à partir d'une fiche de faits, texte ensuite jugé
par les critères C1 à C5. En 6a, ce mode a produit une confusion entre poids
d'un pattern et nombre de transactions sur 4 fiches sur 10.

Le code livré au commit `fb3d3b6` (`souverain_app/explication_ia.py`) applique
en réalité un autre principe, qui n'avait fait l'objet d'aucun ADR : le modèle
ne reçoit que la liste des identifiants d'affirmations autorisés, et le
serveur écrit lui-même les phrases. Cet ADR régularise cet écart.

## Décision

**Option 1 retenue.**

1. Le modèle ne reçoit **aucun fait** : uniquement une liste d'identifiants
   autorisés (`compte`, `comparaison_score_seuil`, `statut`, `motifs`,
   `transactions_disponibles` ou `transactions_indisponibles`, `fenetre`).
2. Le modèle retourne un JSON `{"claims": [...]}` : l'**ordre** des
   identifiants, rien d'autre.
3. Le serveur valide la réponse (clé unique `claims`, chaque identifiant
   autorisé exactement une fois, aucun ajout, aucune omission), puis
   construit le texte français à partir des faits structurés.
4. Toute réponse invalide, tout échec ou dépassement de timeout d'Ollama,
   et tout texte de plus de 120 mots déclenchent le **repli déterministe**
   (explication construite sans le modèle).
5. Les valeurs dérivées (comparaison score/seuil) sont calculées par le
   serveur, jamais par le modèle.

## Options considérées

1. **Sélection d'identifiants (retenue).** Le modèle ne peut ni inventer, ni
   déformer un chiffre, ni émettre un verdict : il n'écrit aucune phrase et ne
   voit aucun fait. L'injection de prompt dans les données est sans prise.
2. **Rédaction libre contrôlée (écartée).** Texte plus naturel, mais
   dépendant d'un contrôleur automatique de C1 à C4 à éprouver sur les erreurs
   connues, avec un risque résiduel de faux négatifs sur une confusion
   de grandeurs déjà observée en 6a.
3. **Aucun modèle (écartée).** L'explication serait purement déterministe,
   sans valeur ajoutée du modèle local. Le repli de l'option 1 constitue déjà
   ce comportement.

## Justification

- Cohérence avec l'invariant des décisions verrouillées (§8) : tout chiffre
  affiché est rattaché aux faits structurés de SOUVERAIN-OS, jamais produit
  par l'IA comme source autonome.
- La confusion poids/comptage de la 6a devient impossible par construction.
- La preuve de fidélité porte sur du code déterministe, testable et rejouable,
  et non sur un texte probabiliste.

## Conséquences

- **Valeur du modèle réduite et assumée :** il n'apporte que l'ordre des
  phrases. Une rédaction plus riche reste une Vision, hors MVP.
- **Grille de fidélité :** les critères C1, C2 et C4 sont satisfaits par
  construction pour les valeurs et identifiants, qui proviennent du serveur.
  Ils deviennent des tests du code de construction des phrases plutôt que des
  contrôles de texte libre. C3 (aucun verdict) et C7 (forme) restent à vérifier
  sur les phrases fixes. C5 (repli) reste le critère central à démontrer.
- **Lot de validation :** réécrit en v2 (`docs/ETAPE_6B_LOT_VALIDATION_V2.md`,
  validé par le fondateur le 27 octobre 2026) : 16 jeux de faits
  (`FaitsAlerte`), validation stricte de la réponse du modèle, répétabilité de
  l'ordre et déclenchement du repli. Le lot v1 en texte libre n'est plus la
  preuve attendue.
- **Témoins historiques F03, F05, F07, F08 :** conservés comme sorties libres
  que le contrôleur doit rejeter (test déjà présent).
- **Journalisation :** aucun texte généré ni identifiant de compte dans les
  journaux ; uniquement horodatage, identifiant d'alerte, code d'échec, durée.
  Implémentée le 27 octobre 2026 (cinq codes : `faits_invalides`,
  `modele_indisponible`, `delai_depasse`, `reponse_invalide`,
  `texte_trop_long`).
- **Performance et mémoire :** la mesure de durée et de RAM du conteneur,
  et la réserve historique de 6,618 Gio contre 6,5 Gio, restent à traiter.

## Timeout : valeur de campagne et valeur de déploiement

Deux valeurs distinctes, à ne pas confondre :

1. **Timeout de campagne : 120 s.** C'est la valeur par défaut du code, gelée
   avec le lot v2 (`gel_v2.json`, champ `timeout_code_secondes`). La campagne
   du bloc B est jouée dans ces conditions : le script refuse de démarrer si
   `SOUVERAIN_OLLAMA_TIMEOUT` donne une autre valeur, et consigne le timeout
   utilisé dans le fichier de résultats.
2. **Timeout de déploiement : valeur à retenir après mesure.** Règle du lot
   v2 (§5) : 1,5 fois le 95e centile du bloc B, hors appel à froid, jamais
   inférieur à l'appel à froid mesuré. Cette valeur est appliquée par la
   variable d'environnement `SOUVERAIN_OLLAMA_TIMEOUT`, **sans modifier le
   code** ni invalider le gel.

Règles de la variable (approuvées par le fondateur le 27 octobre 2026) :

- valeur valide : nombre fini compris entre **5 s et 300 s**, bornes incluses ;
- variable absente, vide, non numérique, `NaN`, infinie ou **hors bornes** :
  retour à **120 s** (une valeur hors bornes n'est pas ramenée à la borne) ;
- lue à chaque appel, jamais à l'import ; un `timeout` passé explicitement à
  `expliquer_alerte` prime sur la variable ;
- la valeur brute de la variable n'est jamais journalisée.

Cette décision remplace l'ancienne règle « 120 s par tentative, 180 s au
total » de l'ADR-006 et de la grille initiale : il n'y a plus de nouvelle
tentative (voir la grille, §8).

Le gel enregistre aussi les valeurs effectives de `context_length` et de
`keep_alive` (relevé de l'API `/api/ps` après le premier appel et en fin de
campagne), ou la raison pour laquelle ce relevé est indisponible.

Limites assumées :

- le timeout de déploiement retenu après mesure **n'est pas rejoué** par une
  seconde campagne : c'est un réglage d'exploitation qui peut seulement faire
  passer plus d'appels lents en repli, sans changer la logique de contrôle ;
- une valeur invalide de la variable retombe silencieusement sur 120 s : elle
  n'est pas signalée dans le journal ;
- `context_length` et `keep_alive` effectif ne sont relevés que si l'API
  `/api/ps` les expose (selon la version d'Ollama).

## Limites MVP

- `nombre_transactions` n'est pas encore alimenté par la route
  (valeur `None`) ; la phrase « non disponible » est donc toujours produite.
- Les seuils et poids actuels sont provisoires (Brique 5).
- Le gain de lisibilité apporté par le modèle n'est pas mesuré.

## Approbations du fondateur

- **25 octobre 2026 — modification de la Brique 7 approuvée.** Le fondateur
  approuve la modification de `alerte_detail.html` (Brique 7, déjà validée)
  dans les termes suivants : le bloc d'explication est remplacé par un
  `<div id="explication-ia">` **sans aucun texte**, qui charge le fragment
  `/alertes/{id}/explication` servi par `souverain_app`. Aucune autre ligne
  du fichier et aucun fichier Python de la Brique 7 ne sont modifiés. Le
  bouton et ses libellés viennent du mécanisme `t()` propre à `souverain_app`
  (`souverain_app/traductions/`), même principe que la Brique 8.
- **27 octobre 2026 — timeout configurable approuvé (option B).** Le
  fondateur approuve `SOUVERAIN_OLLAMA_TIMEOUT` (défaut 120 s, bornes 5 s à
  300 s, valeur absente ou invalide : 120 s), la distinction entre timeout de
  campagne et timeout de déploiement ci-dessus, et le relevé de
  `context_length` et `keep_alive` via `/api/ps`. Aucun changement du prompt,
  du contrôleur de sélection, des options du modèle ni du lot v2.
- **27 octobre 2026 — gabarits applicatifs conservés.** Le fondateur conserve
  telles quelles les formulations « Une vérification des données est
  nécessaire » et « réponse rejetée » (`fr.py`), déclarées comme exceptions
  explicites dans `tests/test_lot_v2.py`.

## Points non couverts par cet ADR

Traités le 27 octobre 2026 : externalisation des phrases du serveur via `t()`,
nettoyage du dépôt, corrections mypy, journalisation C5.

Restent ouverts :

- Le template de la Brique 7 contient des en-têtes de tableau en dur
  (« Pattern », « Détecté le »), antérieurs à la 6b : hors périmètre de cet
  ADR, décision du fondateur à prendre séparément.
- Les noms de patterns et le statut de l'alerte (`ouverte`, `fermee`) sont
  affichés comme identifiants bruts, non traduits.
- Mot de passe de démonstration en clair dans `scripts/demo_alertes.py`.
- Réserve mémoire de la 6a (6,618 Gio contre 6,5 Gio) et valeur finale du
  timeout de déploiement : à documenter après la campagne.
