# ADR-004 — Changement de modèle LLM : Mistral 7B Q4_K_M → Ministral 3 8B Instruct Q4_K_M

**Statut : Accepté.**
**Date : 7 octobre 2026 (passage sur l'hallucination corrigé le 13 octobre 2026).**
**Décideur : Seydou Dangande Abdoul Aziz (fondateur).**


---

## Contexte

Le document fondateur (`01_DOCUMENT_REFERENCE_FONDATEUR.md`, `SOUVERAIN-OS_Prompt_Definitif.docx`, Bloc 6) spécifie littéralement « Ollama + Mistral 7B Q4_K_M » dans la stack imposée. Le cahier des charges (`03_CAHIER_DES_CHARGES.md`) précise que cette stack est obligatoire « sauf décision explicite de changement ». Aucune décision verrouillée (`00_DECISIONS_VERROUILLEES.md`) ne fixait ce choix de modèle avant ce jour — seule une mention indirecte en §6 (multilinguisme) y faisait référence, pour exclure NLLB de la « stack Mistral existante ».

Au moment d'aborder l'Étape 6 (phase transverse), le fondateur a constaté par vérification externe que Mistral 7B v0.3 est présenté par son éditeur comme retiré des nouvelles intégrations recommandées, au profit de Ministral 3 (disponible en 3B, 8B, 14B), avec une orientation explicite vers le déploiement edge/local — exactement le cas d'usage de SOUVERAIN-OS.

## Décision

Retenir **Ministral 3 8B Instruct**, quantification **Q4_K_M** (tag Ollama exact : `ministral-3:8b-instruct-2512-q4_K_M`), comme modèle LLM local pour l'assistance IA de SOUVERAIN-OS, en remplacement de Mistral 7B Q4_K_M.

Mistral 7B est conservé dans ce document uniquement comme **référence historique** — il n'a pas été installé ni benchmarké dans le cadre de cette décision (voir « Options considérées »).

## Options considérées

1. **Benchmark comparatif multi-modèles** (Ministral 3 8B, Mistral 7B v0.3 en référence, Qwen3 8B, Gemma 4 E4B) — option initialement envisagée à l'ouverture de l'analyse, puis explicitement écartée par décision du fondateur avant toute exécution, pour éviter un investissement en temps disproportionné pour une fonction d'assistance à la demande, hors du chemin critique de détection.
2. **Test de faisabilité ciblé sur un candidat unique** (Ministral 3 8B), avec Ministral 3 3B comme secours uniquement en cas d'échec matériel mesuré (RAM ou latence) — **option retenue**.
3. **Conserver Mistral 7B sans réévaluation** — écartée, le modèle étant présenté comme obsolète par son éditeur pour les nouvelles intégrations, sans qu'aucune décision verrouillée n'empêche son remplacement.

## Justification

- **Licence** : Apache 2.0, vérifiée directement depuis le modèle installé (`ollama show --license`), compatible avec l'exigence « 100 % open source et auditable » du document fondateur.
- **Génération plus récente de la même famille** (Mistral), cohérent avec le libellé « Ollama/Mistral » qui structure le projet depuis l'origine — ce n'est pas un changement de famille, seulement de génération.
- **Faisabilité confirmée empiriquement** sur le matériel cible réel (ThinkPad X1 Carbon Gen 6, CPU seul) — voir `VERDICT_ETAPE_6A.md` pour le détail complet des mesures.
- **Comportement de sécurité observé au-delà de l'attendu** : résistance démontrée à une tentative d'injection de prompt (fiche F07), avec signalement explicite de l'instruction ignorée dans la réponse elle-même.
- **Fonctionnement confirmé sans connexion réseau** (test manuel, WiFi physiquement coupé), cohérent avec l'exigence de souveraineté stricte du projet.

## Conséquences

- **Positives** : modèle plus récent, faisabilité matérielle confirmée par la mesure plutôt que supposée, aucune dépendance à un modèle présenté comme en fin de vie par son éditeur.
- **Négatives / risques assumés** :
  - Une confusion récurrente a été identifiée lors du test : le modèle prend le poids numérique d'un pattern de détection pour un nombre de transactions ou d'occurrences (4 fiches sur 10 : F03, F05, F07, F08 ; d'abord documentée à tort comme un cas unique, corrigé le 13 octobre 2026). Elle n'apparaît pas sur un test complémentaire où les faits sont étiquetés explicitement (4 fiches, un passage), mais de petites imprécisions persistent. Détail dans `VERDICT_ETAPE_6A.md`. Jugée non bloquante le 7 octobre sur la base d'un seul cas : **décision à reconfirmer** par le fondateur ; elle renforce la nécessité des invariants d'intégration déjà actés.
  - La RAM mesurée (6,53 GiB) dépasse légèrement le seuil initialement fixé (6,5 Go) — écart de 0,46 %, accepté avec réserve documentée, seuil non modifié rétroactivement.
  - Qwen3 8B et Gemma 4 E4B n'ont pas été évalués, par choix de périmètre assumé — cette absence ne doit pas être lue comme un jugement de leur qualité, seulement comme une limitation volontaire de l'effort d'analyse à ce stade.

## Invariants inchangés, renforcés par le test

L'assistance IA reste strictement : locale, à la demande, explicative uniquement, sans impact sur B4/B5/B6 (qui restent déterministes), sans décision automatique, sans RAG, sans agent, sans génération de requête SQL/Cypher, sans partage de données inter-tenant. Tout chiffre produit par le modèle doit être rattaché aux faits structurés de SOUVERAIN-OS et présenté comme à vérifier, jamais comme une source de vérité autonome.

## Point non tranché par cet ADR

L'installation testée est **native** (hors Docker), suite à un problème réseau non résolu avec certitude touchant l'exécution de conteneurs Docker sur la machine de développement (voir `VERDICT_ETAPE_6A.md`, section « Écart au protocole initial »). La question du retour à une exécution conteneurisée pour l'intégration finale (Étape 6b), par cohérence avec le reste de l'architecture SOUVERAIN-OS, reste ouverte et devra faire l'objet d'une décision explicite séparée.

## Références

- `VERDICT_ETAPE_6A.md` — détail complet du protocole et des mesures.
- `00_DECISIONS_VERROUILLEES.md` — amendement correspondant ajouté le même jour (voir document séparé).
- `01_DOCUMENT_REFERENCE_FONDATEUR.md`, Bloc 6 — mention d'origine de Mistral 7B Q4_K_M, non modifiée (ce document reste la source historique, cf. règle de gouvernance de `00_DECISIONS_VERROUILLEES.md`).
