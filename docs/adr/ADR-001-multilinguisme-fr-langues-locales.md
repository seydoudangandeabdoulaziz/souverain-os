# ADR-001 — Multilinguisme : français et langues locales selon le pays

**Statut : Accepté (décision d'origine) — document reconstruit rétroactivement.**
**Date de la décision d'origine : août 2026, au plus tard le 15 août 2026
(date de l'ADR-002 qui s'y réfère). La date exacte n'a pas pu être retrouvée.**
**Date de la reconstruction : 25 octobre 2026.**
**Décideur : Seydou Dangande Abdoul Aziz (fondateur).**

---

## Avertissement de reconstruction

Le fichier d'origine de cet ADR n'a jamais été versionné dans le dépôt :
aucune trace dans l'historique git. Il était pourtant cité par
`00_DECISIONS_VERROUILLEES.md` (§6), l'ADR-002, la grille de fidélité de la 6b,
la roadmap, `avancement.md` et le code de la Brique 7.
`docs/MODELISATION_OPERATIONNELLE.md` (sections 20 et 21) avait décidé de le
recréer rétroactivement, en l'indiquant honnêtement.

**Cet ADR ne crée aucune décision nouvelle.** Il consigne par écrit une
décision déjà validée et appliquée. Chaque point ci-dessous provient d'une
source existante du dépôt, citée en fin de document. Tout détail de la
décision d'origine qui n'apparaît dans aucune de ces sources est absent ici.

## Contexte

SOUVERAIN-OS vise le Niger puis l'UEMOA. Les utilisateurs et les citoyens
concernés ne parlent pas tous français. Le Niger compte notamment le haoussa
et le zarma ; l'expansion UEMOA ajoute le fulfulde et d'autres langues.
Le principe fondateur « ajouter un pays = ajouter un tenant, sans modifier le
code » implique que la langue ne soit pas codée en dur dans l'application.

## Décision

1. **Objectif produit.** Le produit est multilingue : français plus langues
   locales selon le pays (haoussa et zarma pour le Niger ; fulfulde et autres
   à l'expansion UEMOA).
2. **Implémentation différée.** L'implémentation de la traduction est
   différée à la Brique 7 (dashboard) et à une future brique « notifications
   citoyens », non positionnée à ce jour dans l'ordre numéroté. Les Briques 0
   à 4 n'affichaient aucun texte à un utilisateur humain : rien à traduire.
3. **Règle contraignante pour la Brique 7, dès son premier jour d'analyse.**
   Aucun texte utilisateur n'est écrit en dur dans le code. Tout est
   externalisé dans des fichiers de traduction, même si seul le français est
   livré initialement.
4. **Détermination de la langue.** La langue vient de la préférence explicite
   de l'utilisateur ou du citoyen quand elle existe. Sinon, une valeur par
   défaut est dérivée de `country_code`, déjà présent dans le schéma tenant
   depuis la Brique 1. Aucune modification de schéma n'est nécessaire.
5. **Moteur technique.** Le choix du moteur est traité dans l'ADR-002 :
   NLLB-200-distilled-600M, composant distinct d'Ollama.
6. **Traduction assistée par IA : premier jet uniquement.** Une relecture
   humaine par un locuteur natif est obligatoire avant toute mise en
   production.
7. **Pas de traduction à la volée pour les messages citoyens.** Les templates
   (par exemple les SMS d'alerte fraude) sont traduits et validés une fois,
   jamais générés en temps réel sans validation préalable.
8. **Règle STRUCTURE ≠ IMPLÉMENTATION.** Poser la structure d'externalisation
   n'oblige pas à implémenter le moteur de traduction. Cette règle est citée
   dans l'ADR-002.

## Options considérées

Les sources du dépôt n'établissent pas de comparaison d'options propre à cet
ADR. Seules les alternatives de moteur de traduction sont documentées, dans
l'ADR-002. Cet ADR n'en ajoute aucune a posteriori.

## Conséquences

- **Brique 7.** Le mécanisme `t(cle, langue)` existe en global Jinja2, avec
  `traductions/fr.py` livré seul. Ajouter une langue signifie ajouter un
  fichier de traduction.
- **Brique 8 et gouvernance.** Chaque brique qui affiche du texte porte son
  propre mécanisme `t()` isolé de celui de la Brique 7.
- **Étape 6b.** La grille de fidélité (C5) prévoit que le message
  d'indisponibilité de l'explication IA passe par `t()`. Les textes affichés
  par la fonction d'explication relèvent de la même règle : voir l'ADR-007 et
  l'étape de régularisation correspondante.
- **Traduction réelle.** Aucun moteur de traduction n'est implémenté. Une
  future brique notifications citoyens n'est pas positionnée.
- **Zarma.** Langue à très faibles ressources : qualité à évaluer au moment de
  l'implémentation, avec M2M100 en repli (voir ADR-002).

## Limites

- Seul le français est livré.
- Aucune relecture par un locuteur natif n'a eu lieu : aucune traduction
  n'existe encore.
- Les textes qui seraient restés en dur dans des briques déjà validées ne sont
  pas recensés par cet ADR.

## Sources de la reconstruction

- `00_DECISIONS_VERROUILLEES.md`, §6 (ajouté le 15 août 2026).
- `docs/adr/ADR-002-moteur-traduction.md`.
- `docs/architecture/decisions.md`, ligne « Multilinguisme produit ».
- `docs/MODELISATION_OPERATIONNELLE.md`, sections 16, 20 et 21.
- `avancement.md`, Brique 7 : « Multilinguisme posé dès cette brique ».
- `briques/brique_07_dashboard/src/brique_07_dashboard/__init__.py` et
  `traductions/`.
- `06_ROADMAP_ET_BRIQUES.md`, « Points en suspens ».
