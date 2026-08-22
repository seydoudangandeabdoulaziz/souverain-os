# Brique 5 — Scoring + Alertes

**Statut : VALIDÉE.**

## Rôle

Transforme les événements de détection bruts de la Brique 4
(`{tenant}.detections`) en un score de risque agrégé par `compte_pivot`,
puis crée ou met à jour une alerte (`{tenant}.alertes`) quand ce score
franchit un seuil. Répond à "ce compte est-il dangereux dans l'ensemble",
pas "quel pattern isolé a été vu".

**Hors périmètre** : pas d'investigation ni de visualisation (Brique 7),
pas de graphe de relations (Brique 6), pas d'audit trail des décisions
humaines (Brique 8). CLI uniquement — pas d'endpoint FastAPI, même si le
document fondateur (Bloc 10) en mentionnait un à ce stade (voir l'ancien
README préparatoire de cette brique) : contradiction déjà signalée et
déjà tranchée différemment pour ce projet (cohérence avec
`souverain-generer`/`souverain-detecter`), non réimplémentée ici.

## Décisions actées

- **Granularité** : le score porte sur `compte_pivot` seul (déjà renseigné
  par les 5 règles de la Brique 4, jamais NULL en pratique). La fenêtre
  glissante n'est pas un axe de granularité séparé — c'est un paramètre
  de la formule d'agrégation.
- **Fenêtre glissante** : 7 jours (`FENETRE_JOURS`, `seuils.py`). Assez
  long pour capter la convergence de plusieurs patterns sur un compte
  (comptes dormants réactivés, redistribution en chaîne — Bloc 7), assez
  court pour que le score reste un reflet de l'activité récente.
- **Formule** : somme pondérée par `pattern_type`, **dédupliquée** — un
  même pattern détecté N fois sur la fenêtre ne compte qu'une seule fois.
  Poids (`POIDS_PAR_PATTERN`, tous provisoires) :

  | pattern_type | poids | raison |
  |---|---|---|
  | `compte_pivot` | 30 | signal le plus direct de hub de redistribution |
  | `structure_etoile` | 25 | diffusion multi-destinataires simultanée |
  | `micro_fractionnement` | 20 | contournement de seuil délibéré |
  | `transactions_nocturnes` | 15 | pattern le plus fréquent (26/69 réel), moins discriminant seul |
  | `flux_frontalier` | 10 | placeholder par convention de nommage (Brique 4), pas une vraie détection géographique |

- **Seuil d'alerte** : 50 (`SEUIL_ALERTE`, provisoire — à recalibrer après
  la première exécution réelle sur `tenant_ne`). Un seul pattern isolé,
  même le plus lourd, ne déclenche jamais d'alerte seul.
- **Anti-doublon** : une alerte `'ouverte'` par `compte_pivot`, mise à
  jour en place (UPSERT), jamais dupliquée. Une alerte `'fermee'` (geste
  humain, pleinement porté par la Brique 8) n'est jamais rouverte : une
  nouvelle détection qui referait franchir le seuil crée une **nouvelle**
  alerte — chaque épisode reste un historique distinct (auditabilité,
  Bloc 9).

## ⚠️ Correction actée pendant l'implémentation — lecture pleine fenêtre

Une première version incluait une table de suivi
(`{tenant}.detections_traitees`) pour éviter de relire les détections déjà
scorées à chaque cycle. **Retirée** : elle cassait le score cumulatif sur
la fenêtre glissante — une détection ancienne "déjà traitée" restait
exclue des cycles suivants même si elle était toujours dans la fenêtre de
7 jours, faisant perdre sa contribution au score (ex. `compte_pivot` seul
au jour 1, jamais recombiné avec `micro_fractionnement` détecté au jour
3, alors que les deux sont censés compter ensemble).

`lecture.py` relit désormais **l'intégralité de la fenêtre à chaque
cycle**, sans exclusion. L'UPSERT de `persistence.py` (index unique
partiel `compte_pivot WHERE statut='ouverte'`) est la **seule** garantie
anti-doublon — relire et recalculer plusieurs fois la même fenêtre est
sans risque, puisque l'écriture finale est idempotente.

**Limite MVP documentée, non implémentée** : à 69 détections (volume réel
actuel de `tenant_ne`), aucun souci de performance. Si le volume grossit
significativement (Vision), un index `(compte_pivot, detected_at)` sur
`{tenant}.detections` pourrait être ajouté via une migration future
portée par la Brique 5, sans toucher aux fichiers de la Brique 4.

## ⚠️ Limite MVP connue — chemin complet non observable avec le générateur actuel

`tenant_ne` produit actuellement 0 alerte, et **ne peut mathématiquement
pas en produire** avec le générateur de la Brique 3 tel qu'il existe :
chaque pattern y utilise un préfixe de compte distinct et fixe
(`hub_` → `structure_etoile`, `pivot_` → `compte_pivot`, `cpt_` →
`micro_fractionnement`/`transactions_nocturnes`, `niamey_` →
`flux_frontalier`). Un compte ne peut donc jamais cumuler deux patterns
différents, quel que soit le volume généré — ce n'est pas un manque de
données, augmenter le volume ne changerait rien.

Conséquence : le chemin complet "détection réelle → alerte réelle" n'est
**pas observable** sur `tenant_ne` en l'état, même si chaque maillon est
vérifié séparément :
- la formule d'agrégation est validée par `test_agregation.py`, avec des
  combinaisons de patterns construites librement en mémoire (ex.
  `compte_pivot` + `micro_fractionnement` sur un même compte arbitraire)
  — indépendamment de toute contrainte du générateur ;
- le cycle complet lecture → agrégation → UPSERT est validé par
  `test_integration.py`, contre une vraie base, avec des
  `DetectionEvent` construits directement (pas via le générateur) sur un
  même `compte_pivot` portant plusieurs `pattern_type`.

Ce que ces tests ne couvrent pas : une détection **réellement produite**
par le moteur de la Brique 4 à partir d'une transaction **réellement
générée** par la Brique 3, sur un compte qui cumule plusieurs patterns.
Une évolution future du générateur Brique 3 (scénario de test composite,
un compte volontairement construit pour déclencher plusieurs patterns)
pourrait lever cette limite — mais c'est une modification du code déjà
validé de la Brique 3, qui nécessite sa propre validation explicite, pas
un ajustement fait silencieusement depuis la Brique 5.

## Dépendances

- **Runtime** : `brique-01-postgresql` (pool, `validate_schema_name`)
- **Tests uniquement** (`dev` group, jamais importée en runtime) :
  `brique-04-detection`, pour réutiliser `DetectionEvent`/
  `enregistrer_detections` et injecter de vraies détections en mémoire
  dans les tests d'intégration.

## Commandes

```bash
# Depuis la racine du workspace
uv sync --all-packages

# Tests unitaires purs (sans DB) :
uv run pytest briques/brique_05_scoring_alertes/tests/test_agregation.py -v

# Tests d'intégration (contre vraie base, tenant éphémère) :
uv run pytest briques/brique_05_scoring_alertes/tests/test_integration.py -v -s

# Qualité :
uv run ruff check briques/brique_05_scoring_alertes
cd briques/brique_05_scoring_alertes && uv run mypy src && cd ../..

# Scoring réel sur tenant_ne (suppose que la Brique 4 a déjà tourné) :
uv run souverain-scorer --tenant tenant_ne
```

## Vérification manuelle

```sql
SELECT compte_pivot, score, statut, pattern_types_impliques
FROM tenant_ne.alertes
ORDER BY score DESC;
```

## Erreurs fréquentes

| Symptôme | Cause probable | Diagnostic |
|---|---|---|
| `ValueError: Aucun tenant actif trouvé` | Bootstrap non joué pour ce tenant | Voir README Brique 3 |
| 0 alerte alors que la Brique 4 a bien tourné | Normal et attendu sur `tenant_ne` avec le générateur actuel (voir la limite MVP ci-dessus) — un compte n'y cumule jamais 2 patterns par construction. Sur d'autres données : vérifier `SELECT compte_pivot, count(DISTINCT pattern_type) FROM tenant_ne.detections GROUP BY compte_pivot` | Ajuster `SEUIL_ALERTE` ou `POIDS_PAR_PATTERN` dans `seuils.py` si le constat sur données réelles le justifie |
| Score qui semble "oublier" une ancienne détection | Ne devrait plus arriver (voir correction ci-dessus) — si observé, vérifier que `lecture.py` filtre bien uniquement sur `detected_at >= fenetre_debut`, sans jointure résiduelle | Bug de régression, à corriger avant toute autre chose |

## Sécurité

- Validation anti-injection réutilisée de la Brique 1
  (`validate_schema_name`).
- Table `alertes` suit la même convention de gouvernance que
  `transactions`/`detections` (tenant_id/country_code/data_classification
  dupliqués).
- `details JSONB` porte le détail des poids par pattern, pour audit
  humain — pas de recalcul nécessaire en Brique 7.

## Dépendances avec les briques futures

- **Brique 6 (Neo4j)** : `compte_pivot` reste la clé de jointure naturelle
  vers les nœuds du graphe.
- **Brique 7 (Dashboard)** : lira `{tenant}.alertes` en lecture seule ;
  `details JSONB` évite un recalcul côté dashboard.
- **Brique 8 (Audit + Human-in-the-loop)** : portera la transition
  `statut: 'ouverte' → 'fermee'`, absente de cette brique.
- **Vision** : recalibrage de `FENETRE_JOURS`/`SEUIL_ALERTE`/
  `POIDS_PAR_PATTERN` sur données réelles, index de performance si le
  volume de détections grossit significativement.
