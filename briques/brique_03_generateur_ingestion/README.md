# Brique 3 — Générateur + ingestion de transactions synthétiques

## ⚠️ Ceci est une CORRECTION de la version précédemment livrée

La version de cette brique déjà présente dans le dépôt (commit
`docs(avancement): valider la brique 2`) a été écrite avant que j'aie accès
au vrai code des Briques 0/1/2 (dépôt privé). Elle contenait trois erreurs
qui l'empêchaient de fonctionner contre ton vrai schéma :

1. Colonnes `sender_id`/`receiver_id` inexistantes → corrigé en
   `sender_account`/`receiver_account` (vrai schéma).
2. Connexion DB autonome (`DATABASE_URL` supposée) au lieu de réutiliser
   `brique_01_postgresql.connection.create_pool()` → corrigé.
3. Tenant `tenant_001` qui n'a jamais existé → corrigé en `tenant_ne`
   (convention réelle, voir `briques/brique_01_postgresql/docs/schema.md`).

**Remplace intégralement** les fichiers déjà commités de cette brique par
ceux de cette livraison — voir `LISEZ_MOI_DELTA.md` à la racine de
l'archive pour la procédure exacte.

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
  aucun fichier de la Brique 1).
- **Déclenchement** : CLI uniquement (`uv run souverain-generer`), réservé à la
  machine de dev. Pas d'endpoint API en MVP.
- **Volumétrie** : configurable, valeur par défaut 5 000 transactions,
  jusqu'à 50 000 recommandé.
- **Tenants** : un seul tenant simulé en MVP (`tenant_ne`, Niger).

## 🔴 Dépendance réelle découverte pendant l'implémentation

`{tenant}.transactions.tenant_id/country_code/data_classification` sont des
colonnes `NOT NULL` qui doivent correspondre à une vraie ligne de
`shared.tenants_registry`. Or **rien n'enregistre encore de tenant** dans ce
registre : `provision_tenant_schema()` (Brique 1) crée uniquement le schéma
physique, et `create_tenant()` complet (avec gouvernance) est explicitement
réservé à la **Brique 8**.

**Solution retenue** : `scripts/bootstrap_tenant_ne.sql`, un script minimal et
**explicitement provisoire**, qui enregistre uniquement `tenant_ne` (Niger).
Il ne remplace pas `create_tenant()` — il sera supprimé/remplacé quand la
Brique 8 sera implémentée. Voir le commentaire en tête de ce fichier.

`inserer_transactions()` est aussi rendue **auto-réparatrice** : elle
s'assure que la colonne `is_synthetic` existe sur le tenant ciblé avant
d'insérer (`ADD COLUMN IF NOT EXISTS`, idempotent), indépendamment de l'ordre
d'exécution de `migrations/0001_add_is_synthetic.sql` — qui, elle, ne couvre
que les tenants déjà enregistrés au moment où elle tourne.

## ⚠️ Autre point signalé, hors périmètre de cette brique

Le `pyproject.toml` racine liste `briques/brique_02_auth_rbac` comme membre
du workspace, mais au moment de ma première analyse ce dossier ne contenait
que le `README.md`. Tu as depuis poussé le code réel — vérifié dans cette
correction, tout s'installe et s'importe correctement ensemble. Rien à faire
de ce côté, c'était un signalement, pas un blocage persistant.

## Réutilisation du code de la Brique 1 (au lieu de duplication)

Cette correction ajoute une vraie dépendance workspace `uv` vers
`brique-01-postgresql` (voir `pyproject.toml`, `[tool.uv.sources]`), et
réutilise directement :
- `brique_01_postgresql.connection.create_pool()` / `close_pool()`
- `brique_01_postgresql.tenant_provisioning.validate_schema_name()` /
  `InvalidSchemaNameError`

Aucune logique de connexion ou de validation n'est plus dupliquée.

## Commandes — ordre d'exécution complet

```bash
# 1. Démarrer PostgreSQL
docker compose --profile postgres up -d

# 2. Vérifier que la migration Brique 1 est appliquée
#    (shared.tenants_registry doit exister)

# 3. Installer le workspace (depuis la racine)
uv sync

# 4. Bootstrap MVP — enregistrer tenant_ne dans shared.tenants_registry
docker compose exec -T postgres psql -U souverain_admin -d souverain_os \
  < briques/brique_03_generateur_ingestion/scripts/bootstrap_tenant_ne.sql

# 5. Provisionner physiquement le schéma tenant_ne (utilise la Brique 1)
uv run python -c "
import asyncio
from brique_01_postgresql.connection import create_pool, close_pool
from brique_01_postgresql.tenant_provisioning import provision_tenant_schema

async def main():
    pool = await create_pool()
    async with pool.acquire() as conn:
        await provision_tenant_schema(conn, 'tenant_ne')
    await close_pool()

asyncio.run(main())
"

# 6. Tests unitaires purs (sans DB) :
uv run pytest briques/brique_03_generateur_ingestion/tests/test_generateur_legitime.py \
              briques/brique_03_generateur_ingestion/tests/test_patterns_suspects.py -v
# → 15/15 attendus (déjà vérifié en environnement de génération, avec le vrai code Brique 1)

# 7. Tests d'intégration (contre la vraie base, tenant éphémère auto-provisionné/nettoyé) :
uv run pytest briques/brique_03_generateur_ingestion/tests/test_ingestion.py -v

# 8. Qualité :
uv run ruff check briques/brique_03_generateur_ingestion
uv run mypy briques/brique_03_generateur_ingestion/src

# 9. Génération réelle, 5000 transactions pour tenant_ne :
uv run souverain-generer --tenant tenant_ne
```

## Sortie attendue (exemple)

```text
Génération : 4750 légitimes + 250 suspectes (seed=42, intensité=moyenne)
✅ 5000 transactions insérées dans le schéma tenant_ne (is_synthetic=true)
```

## Vérification manuelle

```sql
SELECT channel, count(*)
FROM tenant_ne.transactions
WHERE is_synthetic = true
GROUP BY channel;
```

Note : `pattern_label` existe uniquement côté Python (tests) — il n'est
volontairement pas stocké en base, pour ne pas donner d'indice au détecteur
(Brique 4) qu'il n'aurait pas en production réelle.

## Erreurs fréquentes

| Symptôme | Cause probable | Diagnostic |
|---|---|---|
| `ValueError: Aucun tenant actif trouvé pour le schéma 'tenant_ne'` | Bootstrap MVP non joué | Étape 4 ci-dessus |
| `asyncpg.exceptions.InvalidSchemaNameError` (ou `UndefinedTableError`) | Schéma `tenant_ne` non provisionné physiquement | Étape 5 ci-dessus |
| `asyncpg.exceptions.UndefinedTableError: shared.tenants_registry` | Migration Brique 1 non appliquée | Appliquer `brique_01_postgresql/migrations/0001_init_shared_schema.sql` |
| Tests d'intégration lents/bloqués | PostgreSQL non démarré | `docker compose --profile postgres up -d` |

## Sécurité

- Validation anti-injection sur le nom de schéma : réutilise
  `validate_schema_name()` de la Brique 1 (même garantie que
  `provision_tenant_schema()`).
- Aucune donnée personnelle réelle : identifiants de comptes générés,
  aucun lien avec des personnes réelles.
- `is_synthetic` permet un audit et une purge propres des données de test.
- Le bootstrap MVP (`scripts/bootstrap_tenant_ne.sql`) est scellé et
  documenté comme provisoire — à ne jamais généraliser à d'autres tenants
  sans passer par la vraie gouvernance de la Brique 8.

## Dépendances avec les briques futures

- **Brique 4 (Hybrid-Stream)** : consommera ces transactions en mode batch.
- **Brique 6 (Neo4j)** : `structure_etoile` et `compte_pivot` produisent des
  sous-graphes reconnaissables.
- **Brique 8 (Audit + gouvernance)** : devra remplacer
  `scripts/bootstrap_tenant_ne.sql` par un vrai `create_tenant()`.
