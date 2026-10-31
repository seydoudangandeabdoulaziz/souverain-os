# Proposition d'ajout aux décisions verrouillées — étape 6b

**Statut : proposition, non appliquée.** Le document `00_DECISIONS_VERROUILLEES.md`
n'est modifié que par décision explicite du fondateur. Ce fichier prépare le
texte ; rien n'a été écrit dans le document verrouillé.

**Origine :** validation de l'étape 6b par le fondateur le 30 octobre 2026,
ADR-007 au statut « Accepté ».

## Comment l'appliquer

1. Ajouter la section 9 ci-dessous à la suite de la section 8, avant
   « Ordre de reconstruction rappelé (déjà validé) ».
2. Mettre à jour la ligne « Dernière mise à jour » de l'en-tête (par exemple
   « 30 octobre 2026 — section 9 ajoutée, étape 6b »).
3. Au choix du fondateur, appliquer l'amendement proposé à la section 8
   (voir la fin de ce fichier).

---

## Texte proposé : section 9

### 9. Explication IA des alertes — sélection d'identifiants (ADR-007)

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

---

## Amendement proposé à la section 8 (optionnel)

La section 8 contient deux passages que la 6b a rendus obsolètes. Le fondateur
peut les remplacer, ou laisser la section 8 telle quelle et s'en remettre à la
section 9.

**Passage à remplacer :**

> La décision « non bloquant » du 7 octobre, prise sur la base d'un seul cas,
> est à reconfirmer par le fondateur.

**Remplacement proposé :**

> Ce point est clôturé le 28 octobre 2026 : le défaut est classé « sans objet
> pour le design actuel » (ADR-007, section 9), sans prétendre à une correction
> rétroactive de la 6a.

**Passage à examiner :** « L'ADR-006 formalisera ce choix au début de la 6b… ».
L'ADR-006 existe désormais, au statut « Accepté en principe — réserves
ouvertes ». Son statut doit être revu séparément : il laisse ouverte la réserve
« timeout provisoire », que l'ADR-007 résout. Ce fichier ne propose pas de texte
pour ce passage.
