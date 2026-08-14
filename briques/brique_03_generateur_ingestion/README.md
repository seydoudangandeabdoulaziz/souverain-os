# Brique 3 — Générateur + ingestion de transactions synthétiques

## Rôle

Génère des transactions Mobile Money synthétiques (légitimes + patterns
criminels sahéliens du document fondateur, Bloc 7) et les insère dans le
schéma tenant réel posé en Brique 1. Fournit la matière première pour les
Briques 4 (détection), 5 (scoring) et 6 (graphe).

## Décisions actées pour cette brique

- **Réalisme des patterns** : niveau Intermédiaire — paramétrable (intensité,
  fenêtre temporelle, montants), bruit contrôlé, seed fixe pour reproductibilité.
- **Mode de génération** : batch (one-shot). Le mode stream continu est une
  extension naturelle de la Brique 4 (Hybrid-Stream), pas de cette brique.
- **Stockage** : table `transactions` réelle de la Brique 1, avec une colonne
  `is_synthetic` ajoutée par une migration portée par cette brique (ne modifie
  aucun fichier de la Brique 1 — même mécanique que Brique 2 → Brique 1).
- **Déclenchement** : CLI uniquement (`uv run souverain-generer`), réservé à la
  machine de dev. Pas d'endpoint API en MVP.
- **Volumétrie** : configurable, valeur par défaut 5 000 transactions,
  jusqu'à 50 000 recommandé (baseline document fondateur : 50 000/heure).
- **Tenants** : un seul tenant simulé en MVP (`tenant_001`, Niger). `tenant_id`
  reste un paramètre générique de `inserer_transactions()` pour une extension
  triviale à d'autres tenants plus tard.

## ⚠️ Hypothèses à vérifier avant le premier lancement

Ce code a été écrit sans accès direct au dépôt GitHub privé. Trois points
sont des suppositions raisonnables à confronter au code réel avant `uv sync` :

1. **Colonnes de `{tenant}.transactions`** (`ingestion.py`) : suppose
   `sender_id, receiver_id, amount, currency, channel, occurred_at, is_synthetic`.
   Compare aux colonnes réelles créées en Brique 1 et adapte `_REQUETE_INSERT`
   si les noms diffèrent.
2. **Colonne identifiant le schéma dans `shared.tenants_registry`**
   (`migrations/0001_add_is_synthetic.sql`) : suppose `schema_name`.
3. **Pool asyncpg** (`cli.py`, `_creer_pool`) : crée son propre pool plutôt que
   d'importer un module de pool partagé. Si la Brique 1 expose déjà une
   fonction de création de pool réutilisable, remplace `_creer_pool()` par
   son import pour éviter la duplication de logique de connexion.

## Commandes

```bash
# Depuis la racine du workspace, après avoir ajouté cette brique aux membres
# du pyproject.toml racine (voir LISEZ_MOI_DELTA.md) :
uv sync

# Appliquer la migration (après les migrations Brique 1 et Brique 2) :
docker compose --profile postgres up -d
uv run psql "$DATABASE_URL" -f briques/brique_03_generateur_ingestion/migrations/0001_add_is_synthetic.sql
# (ou psql directement si uv run psql n'est pas configuré chez toi)

# Lancer les tests unitaires (sans DB) :
uv run pytest briques/brique_03_generateur_ingestion/tests/test_generateur_legitime.py \
              briques/brique_03_generateur_ingestion/tests/test_patterns_suspects.py -v

# Lancer les tests d'intégration (avec DB réelle) :
uv run pytest briques/brique_03_generateur_ingestion/tests/test_ingestion.py -v

# Générer et insérer 5 000 transactions (défaut) pour tenant_001 :
uv run souverain-generer --tenant tenant_001

# Générer 50 000 transactions avec intensité forte :
uv run souverain-generer --tenant tenant_001 --nb-transactions 50000 --intensite forte
```

## Sortie attendue (exemple)

```text
Génération : 4750 légitimes + 250 suspectes (seed=42, intensité=moyenne)
✅ 5000 transactions insérées dans le schéma tenant_001 (is_synthetic=true)
```

## Vérification manuelle

```sql
SELECT pattern_label_absent, count(*)  -- pattern_label n'est PAS stocké en base
FROM tenant_001.transactions
WHERE is_synthetic = true
GROUP BY channel;
```

Note : `pattern_label` existe uniquement côté Python (utile pour les tests et
pour vérifier plus tard que la Brique 4 détecte bien les patterns injectés) —
il n'est volontairement pas stocké en base, pour ne pas donner d'indice au
détecteur qu'il n'aurait pas en production réelle.

## Erreurs fréquentes

| Symptôme | Cause probable | Diagnostic |
|---|---|---|
| `ValidationError: database_url field required` | `.env` non trouvé ou `DATABASE_URL` absent | Vérifier que `.env` existe à la racine du repo et contient `DATABASE_URL=...` |
| `ValueError: Nom de schéma tenant invalide` | `--tenant` contient un caractère non alphanumérique | Utiliser uniquement lettres/chiffres/underscore |
| `asyncpg.exceptions.UndefinedColumnError` | Les colonnes de `_REQUETE_INSERT` ne correspondent pas au schéma réel | Voir section Hypothèses ci-dessus, adapter `ingestion.py` |
| `RuntimeError: attached to a different loop` | `TestClient` utilisé au lieu de `httpx.AsyncClient` | Non applicable ici (pas d'API), mais même piège que Brique 2 si un endpoint est ajouté plus tard |

## Sécurité

- Protection contre l'injection SQL sur le nom de schéma (`_valider_nom_schema`),
  même logique que `provision_tenant_schema()` en Brique 1.
- Aucune donnée personnelle réelle : tous les identifiants de comptes sont
  générés (`cpt_XXXXXX`), aucun lien avec des personnes réelles.
- `is_synthetic` permet un audit et une purge propres des données de test —
  important avant tout déploiement avec des données réelles (Vision).

## Dépendances avec les briques futures

- **Brique 4 (Hybrid-Stream)** : consommera potentiellement ces transactions
  en mode batch pour ses premiers tests, avant l'ajout d'un vrai flux continu.
- **Brique 6 (Neo4j)** : les patterns `structure_etoile` et `compte_pivot`
  sont conçus pour produire des sous-graphes reconnaissables une fois la
  Brique 6 en place.
