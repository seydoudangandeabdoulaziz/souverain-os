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
- **Lot de validation :** à réécrire en version suivante (v2) pour tester les
  16 jeux de faits (`FaitsAlerte`), la validation stricte de la réponse du
  modèle, la répétabilité de l'ordre sur 3 passages et le déclenchement du
  repli. Le lot v1 en texte libre n'est plus la preuve attendue.
- **Témoins historiques F03, F05, F07, F08 :** conservés comme sorties libres
  que le contrôleur doit rejeter (test déjà présent).
- **Journalisation :** aucun texte généré ni identifiant de compte dans les
  journaux ; uniquement horodatage, identifiant d'alerte, code d'échec, durée.
  À implémenter, non encore présent.
- **Performance et mémoire :** la mesure de durée et de RAM du conteneur,
  et la réserve historique de 6,618 Gio contre 6,5 Gio, restent à traiter.

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

## Points non couverts par cet ADR

- Les phrases françaises construites par le serveur dans `explication_ia.py`
  (texte de l'explication elle-même) sont encore écrites en dur : leur
  externalisation via `t()` reste à traiter, avec les tests du contrôleur.
- Le template de la Brique 7 contient des en-têtes de tableau en dur
  (« Pattern », « Détecté le »), antérieurs à la 6b : hors périmètre de cet
  ADR, à signaler au fondateur séparément.
- Nettoyage du dépôt et corrections mypy.

Ces points suivent comme étapes distinctes.
