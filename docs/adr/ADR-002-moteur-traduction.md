# ADR-002 — Moteur technique de traduction (langues locales)

**Statut : Acceptée**
**Date : 15 août 2026**
**Décideur : Seydou Dangande Abdoul Aziz (fondateur)**

## Contexte

Suite à l'ADR-001 (multilinguisme produit acté, implémentation différée),
une recherche technique a été menée pour identifier un moteur de
traduction open-source, auto-hébergeable, compatible avec la contrainte
"zéro cloud étranger" et le hardware contraint du fondateur (ThinkPad X1
Carbon, 16 Go RAM).

Constat technique important : les modèles de traduction dédiés
(encodeur-décodeur) sont une famille différente des LLM de chat comme
Mistral 7B. **Ollama, prévu dans la stack imposée pour Mistral, n'est pas
conçu pour ce type de modèle.** Ce sera un composant technique séparé.

## Options identifiées

- **NLLB-200 (Meta)** : couvre plus de 200 langues, dont le haoussa et
  le fulfulde (futurs pays UEMOA). Existe en plusieurs tailles, de 600M
  à 54,5B de paramètres. La version **distillée 600M** est la seule
  compatible avec un hardware contraint solo.
- **M2M100 (418M)** : couverture multilingue large, traduction directe
  entre langues sans passer par l'anglais comme pivot.
- **Ressource spécifique au zarma** : un projet de recherche ("Feriji")
  a constitué un corpus parallèle français-zarma et testé plusieurs
  modèles dessus. Le zarma est une langue à très faibles ressources —
  très peu de corpus existent, ce qui rend cette ressource
  particulièrement précieuse pour ce projet.
- **Runtime d'inférence** : Hugging Face Transformers (standard, large
  écosystème) ou CTranslate2 (moteur d'inférence optimisé pour CPU,
  pertinent vu la contrainte hardware — à valider par un test de
  performance réel au moment de l'implémentation, pas supposé ici).

## Décision

- **Moteur principal : NLLB-200-distilled-600M**, pour l'ensemble des
  langues cibles (haoussa, zarma, et fulfulde en Vision UEMOA) — un seul
  modèle à maintenir et opérer, plus simple que plusieurs modèles
  spécialisés par langue.
- **Cas particulier zarma, documenté explicitement** : la qualité de
  NLLB sur le zarma devra être évaluée concrètement au moment de
  l'implémentation. Si insuffisante, M2M100 est l'option de repli
  identifiée (comparaison déjà documentée par le projet Feriji), avec
  possibilité d'exploiter le corpus Feriji pour un fine-tuning ciblé.
  Décision finale entre "NLLB partout" et "NLLB + exception zarma"
  différée à l'implémentation réelle, sur la base de tests de qualité
  concrets — pas tranchée par anticipation ici.
- **Runtime** : Hugging Face Transformers par défaut ; évaluation de
  CTranslate2 au moment de l'implémentation si les temps d'inférence sur
  le hardware réel s'avèrent un problème.
- **Composant technique distinct d'Ollama** — pas d'intégration au
  serveur Ollama existant, pas de modification de la stack Mistral.
- **Aucune implémentation avant que la Brique 7 ou une future brique
  notifications citoyens ne soit réellement démarrée** (cohérent avec
  ADR-001 et la règle STRUCTURE ≠ IMPLÉMENTATION).
- Rappel de l'ADR-001, toujours en vigueur : traduction assistée par IA
  autorisée uniquement pour un premier jet, relecture humaine par un
  locuteur natif obligatoire avant toute mise en production.

## Conséquences

- Nouvelle dépendance technique identifiée pour plus tard (`transformers`
  et/ou `ctranslate2`, poids du modèle NLLB-600M à télécharger une fois)
  — à ajouter au `pyproject.toml` de la brique concernée le moment venu,
  pas maintenant.
- Le corpus/glossaire du projet Feriji (français-zarma) est identifié
  comme ressource à investiguer prioritairement pour la qualité du
  zarma — recherche à mener au moment de l'implémentation.
- Aucun impact sur les Briques 0 à 4 déjà validées.

## Alternatives envisagées

- Faire porter la traduction par Ollama/Mistral directement : écartée,
  Mistral est un LLM généraliste de chat, moins fiable qu'un modèle
  dédié traduction sur les langues à faibles ressources comme le zarma.
- Service de traduction cloud (Google Translate, DeepL, etc.) : écartée,
  contredit directement la contrainte "100% open source, zéro cloud
  étranger" du document fondateur.
