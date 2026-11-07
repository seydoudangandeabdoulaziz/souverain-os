# Étape 8a.1 — Rapport du pilote comparatif d'embeddings

**État : pilote expérimental exécuté ; résultats provisoires ; aucun modèle sélectionné.**

Ce rapport documente le pilote autorisé par le fondateur. Il ne vaut ni validation complète de l'étape 8a, ni sélection définitive d'un modèle, ni autorisation d'implémenter le moteur RAG.

## 1. Périmètre et artefacts

- Corpus : `fatf-word-v1.1`, 487 passages issus des trois publications FATF autorisées. La version `fatf-word-v1` reste intacte.
- Requêtes : les cinq chaînes canoniques de `fatf-five-canonical-v1`, sans paraphrase.
- Comparaison : `multilingual-e5-small` et `multilingual-e5-base`, une exécution à la fois, résultats top-10 par requête.
- Entrées E5 : préfixes `passage: ` et `query: ` ; pooling moyen avec masque d'attention et normalisation L2 ; calcul CPU float32, batch passages de 4, 4 threads.
- Les cinq passages dépassant 512 tokens ont subi la même troncature à droite à 512 tokens, tokens spéciaux inclus, pour les deux modèles.
- Union des candidats : 83 couples requête–passage, représentant 46 passages distincts. Chaque couple a reçu une note de chaque évaluateur IA, soit 166 notes brutes.
- Artefacts détaillés, maintenus hors du dépôt Git : `SOUVERAIN-OS_DATA/corpus/fatf/experiments/e5-pilot-v1/`.

Les poids vérifiés sont épinglés aux révisions suivantes :

| Modèle | Révision | Dimension | SHA-256 de `model.safetensors` |
|---|---|---:|---|
| `multilingual-e5-small` | `614241f622f53c4eeff9890bdc4f31cfecc418b3` | 384 | `1a55775f53449dac10a2bcbc312469fac40b96d53198c407081a831f81c98477` |
| `multilingual-e5-base` | `d128750597153bb5987e10b1c3493a34e5a4502a` | 768 | `a18a44fad1d0b46ded15928144138cff1135d5cc8233bdd90be5f18822de09a7` |

## 2. Environnement et mesures matérielles

Mesure sur le ThinkPad X1 Carbon Gen 6, Intel i7-8650U (4 cœurs / 8 threads), 16 Go de RAM installée. L'environnement expose environ 14 Gio de mémoire totale au système. Runtime CPU : Python 3.14.4, PyTorch 2.14.1+cpu, Transformers 5.22.2, NumPy 2.5.4 ; aucun poids n'a été placé sur GPU.

| Mesure | E5-small | E5-base |
|---|---:|---:|
| Tokenisation des 487 passages | 0,562 s | 0,610 s |
| Encodage des 487 passages | 63,001 s | 182,804 s |
| Débit d'encodage des passages | 7,73 /s | 2,66 /s |
| Encodage des cinq requêtes en un batch | 0,064 s | 0,200 s |
| Pic RSS du processus échantillonné | 1,207 Gio | 2,101 Gio |
| Minimum de mémoire disponible échantillonné | 11,223 Gio | 10,841 Gio |
| Swap utilisé observé | 0 | 0 |
| Compteur système `oom_kill` avant / après | 0 / 0 | 0 / 0 |

Le scan de recherche est un calcul exact de similarité cosinus en mémoire sur 487 vecteurs, requête déjà encodée. Dix échauffements ont été exclus, puis 100 mesures ont été prises par requête ; le p95 utilise le rang le plus proche.

| Requête | E5-small p95 scan (ms) | E5-base p95 scan (ms) |
|---|---:|---:|
| `compte_pivot` | 0,1017 | 0,1302 |
| `flux_frontalier` | 0,0674 | 0,0910 |
| `micro_fractionnement` | 0,0573 | 0,0858 |
| `structure_etoile` | 0,0662 | 0,0816 |
| `transactions_nocturnes` | 0,0587 | 0,0823 |

Ces temps de scan ne comprennent ni l'encodage individuel d'une requête dans la boucle chronométrée, ni la vérification des sources, ni un appel à un magasin vectoriel. Ils ne démontrent donc pas le respect de la cible V8 de bout en bout (< 2 s). L'accès au démon Docker était indisponible ; PostgreSQL, Neo4j et les autres services actifs n'ont pas pu être vérifiés. Les mesures mémoire ne représentent pas le profil complet des services en exploitation.

## 3. Évaluations et limites

`annotation-rater-1.csv` reprend les propositions de ChatGPT ; `annotation-rater-2.csv` contient l'évaluation indépendante de Codex, réalisée sans consulter les scores du premier fichier. Les deux évaluations sont assistées par IA : elles ne constituent pas deux annotations humaines expertes et ne fournissent pas une validation humaine indépendante.

Avant l'adjudication, 65 couples sur 83 ont reçu la même note et 18 ont divergé. Le kappa de Cohen pondéré quadratiquement, calculé sur ces deux évaluations IA avant adjudication, est de **0,8346**. Les 18 propositions d'arbitrage et les qrels sont marqués provisoires et assistés par IA. Ce coefficient ne doit pas être interprété comme une mesure de reproductibilité entre experts humains.

Les métriques portent sur cinq requêtes seulement et sur l'union des top-10 des deux modèles. Elles ne mesurent pas le rappel sur l'ensemble des 487 passages. Pour le rappel approuvé, les notes 2 et 3 sont pertinentes. Les dénominateurs du `Recall@10_pool` sont les passages notés 2 ou 3 dans le pool commun pour chaque requête ; ils totalisent respectivement 4, 9, 2, 1 et 1 passages pertinents par requête. Ces faibles effectifs rendent le rappel macro instable.

## 4. Vérification et correction des métriques

Les nDCG sont calculés avec le gain gradué `2^note - 1`, puis moyennés à poids égal sur les cinq requêtes. Le nDCG utilise les qrels provisoires. Le tableau d'origine `metriques-comparatives-provisoires.csv` reproduit les nDCG. Son `Precision@5` et son `Recall@10_pool` classent toutefois toute note strictement supérieure à 0 comme pertinente. Cela ne correspond pas au seuil 2–3 approuvé pour le rappel.

| Métrique macro | E5-small | E5-base | Convention |
|---|---:|---:|---|
| nDCG@5 | 0,5721 | 0,6186 | Gain gradué `2^note - 1` |
| nDCG@10 | 0,6448 | 0,6992 | Gain gradué `2^note - 1` |
| Precision@5 (calcul complémentaire) | 0,2800 | 0,2800 | Pertinence binaire = note 2 ou 3 ; convention illustrative, non arbitrée comme critère officiel |
| Recall@10_pool | 0,8333 | 0,6111 | Pertinence binaire = note 2 ou 3 ; pool jugé uniquement, non exhaustif |

Les valeurs publiées précédemment (Precision@5 : 0,6000 / 0,8000 ; Recall@10_pool : 0,5567 / 0,7240) se reproduisent lorsque le seuil binaire est note ≥ 1. Elles sont conservées dans le fichier d'origine à des fins de traçabilité, mais ne sont pas les métriques conformes au seuil de rappel approuvé. En appliquant le seuil 2–3, le rappel moyen favorise E5-small, et non E5-base. Le fichier de recalcul provisoire est `metriques-recalculees-provisoires-seuil-2.csv`.

Le seuil 2–3 est l'orientation approuvée pour le rappel. Le calcul complémentaire de Precision@5 avec ce même seuil facilite la lecture, mais la définition de Precision@5 n'a pas été arbitrée comme critère officiel du pilote.

La moyenne de nDCG@10 E5-small obtenue à partir des valeurs non arrondies est 0,64484196, soit 0,6448 à quatre décimales. La valeur 0,6449 résulte de la moyenne des valeurs par requête déjà arrondies dans le fichier d'origine (double arrondi).

## 5. Verdict comparatif

- **E5-base** est le meilleur candidat en classement gradué sur ce jeu provisoire : son nDCG@5 et son nDCG@10 sont supérieurs. Il est environ 2,9 fois plus lent pour encoder les passages et son pic RSS mesuré est supérieur d'environ 0,894 Gio.
- **E5-small** est plus rapide et plus léger. Selon le rappel pool au seuil 2–3, il obtient ici un score moyen supérieur ; les petits dénominateurs et les annotations IA rendent ce résultat fragile.
- Aucun modèle n'est sélectionné. Le fondateur doit arbitrer le compromis après examen de ces résultats ; une validation humaine indépendante améliorerait sensiblement la confiance dans la comparaison.

Ce pilote ne valide pas le moteur RAG, le service de recherche, le respect de la cible de latence V8 de bout en bout, ni l'étape 8a dans son ensemble. L'implémentation RAG n'a pas commencé et reste soumise à une autorisation distincte.

## 6. Reproductibilité et pièces vérifiées

Les classements, mesures, annotations, qrels et métriques sources sont conservés sous `SOUVERAIN-OS_DATA/corpus/fatf/experiments/e5-pilot-v1/`, hors Git. Aucun script de calcul des métriques n'a été trouvé dans ce dossier ; les métriques ci-dessus ont été recalculées à partir des classements et qrels avec les formules décrites ici. `remplir_annotations.py`, présent à la racine comme fichier local non suivi, ne calcule pas les métriques et écrit dans `annotation-rater-1.csv` avec création d'une sauvegarde ; il n'a pas été exécuté pendant cette vérification.

Les sources FATF, le corpus v1.1, les poids et les classements n'ont pas été modifiés pendant la finalisation documentaire. Aucun embedding n'a été recalculé, aucun benchmark n'a été relancé, et aucune dépendance du workspace n'a été changée.
