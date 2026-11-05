# Instructions des agents — SOUVERAIN-OS

Ces instructions s'appliquent aux travaux d'analyse et de développement réalisés par des agents IA dans ce dépôt. **Codex peut charger `AGENTS.md` au niveau du dépôt. ChatGPT doit consulter explicitement ce fichier lorsqu'il est disponible.**

## Autorité documentaire

Consulter les sources dans cet ordre :

1. Les décisions verrouillées et arbitrages explicites du fondateur, dans leur périmètre.
2. Les ADR approuvés, sans étendre leur portée ni réécrire les décisions historiques.
3. La conception validée et la roadmap.
4. `avancement.md` pour l'état opérationnel du projet.
5. Les guides, vues d'architecture et prompts historiques, qui ne prévalent pas sur les sources ci-dessus.

Un ADR proposé ou un arbitrage encore ouvert n'est pas une décision. Distinguer les faits vérifiés, les hypothèses, les recommandations et les décisions du fondateur. Si un document cité est absent, le signaler sans le recréer, le remplacer ou en déduire le contenu.

## État du dépôt et autorisations

- Examiner l'état Git avant toute intervention et préserver toutes les modifications locales et les fichiers non suivis.
- Une approbation d'analyse ou de plan n'autorise pas une écriture. N'intervenir que dans le périmètre explicitement autorisé.
- Une autorisation documentaire n'autorise pas le code, les dépendances, les configurations, les migrations, les tests, le formatage, l'index Git, les commits ou les push.
- Ne lancer aucune commande qui modifie le dépôt ou un système externe sans autorisation correspondante. En particulier, `ruff format` modifie les fichiers.
- Ne jamais déclarer une étape validée ni commencer une étape qui exige une autorisation distincte sans décision explicite du fondateur.

## Règles de travail

- Pour une brique ou un chantier transverse : COMPRENDRE → ARCHITECTURER → VALIDER → IMPLÉMENTER → TESTER → DOCUMENTER → VALIDER.
- Traiter les changements locaux comme l'état de travail, pas comme des faits établis par l'historique Git.
- Rapporter les fichiers effectivement modifiés, les contrôles réellement réalisés et les réserves restantes. Ne pas prétendre avoir exécuté un test ou une vérification qui ne l'a pas été.

## Rôles

- **ChatGPT :** analyser, expliquer les options, évaluer les risques et préparer des propositions ; ne pas prétendre avoir modifié le dépôt.
- **Codex :** examiner le dépôt, puis exécuter uniquement les changements autorisés en préservant l'état préexistant ; rendre compte précisément du diff et des vérifications.

## Périmètre RAG

Les règles approuvées du MVP RAG sont définies dans [`docs/00_DECISIONS_VERROUILLEES.md`](docs/00_DECISIONS_VERROUILLEES.md), section 10. Les consulter comme référence ; ne pas en recopier ni en élargir le périmètre dans ces instructions.

La conception de l'étape 7 est validée. **L'étape 8 ne peut commencer qu'après une autorisation distincte explicite du fondateur.**
