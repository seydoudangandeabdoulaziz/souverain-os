# Brique 1 — PostgreSQL / TimescaleDB multi-tenant

**Statut : VALIDÉE**

## Rôle

Poser le schéma PostgreSQL 16 + TimescaleDB fondateur, avec isolation multi-tenant native (schema-per-tenant), conformément au document fondateur.

## Décision d'architecture

**Isolation : schema-per-tenant** (voir `docs/schema.md` pour le détail complet). Chaque pays = un schéma PostgreSQL physique dédié. Le schéma `shared` ne contient que la gouvernance (registre des tenants), jamais de donnée métier.

## Limites explicites (hors périmètre de cette brique)

- Auth / RBAC → Brique 2.
- Ingestion réelle de transactions → Brique 3.
- `create_tenant()` complet avec gouvernance/audit → Brique 8. Cette brique fournit uniquement `provision_tenant_schema()`, le mécanisme technique bas niveau.

## Structure

```text
brique_01_postgresql/
├── README.md
├── pyproject.toml
├── src/
│   └── brique_01_postgresql/
│       ├── __init__.py
│       ├── config.py                   ← configuration (pydantic-settings)
│       ├── connection.py               ← pool de connexions asyncpg
│       ├── schema_shared.sql           ← schéma partagé (registre tenants)
│       ├── schema_tenant_template.sql  ← template rejoué par tenant
│       ├── tenant_provisioning.py      ← provisioning technique d'un schéma tenant
│       └── healthcheck_db.py           ← vérifications de santé DB
├── migrations/
│   └── 0001_init_shared_schema.sql
├── tests/
│   └── test_connection.py
├── scripts/
│   └── db_healthcheck.py
└── docs/
    └── schema.md
```

## Prérequis

- Brique 0 validée.
- Docker installé (pour PostgreSQL/TimescaleDB en conteneur).
- Fichier `.env` créé à partir de `.env.example` (racine du dépôt), avec les variables `POSTGRES_*` renseignées.

## Installation des dépendances Python

```bash
cd briques/brique_01_postgresql
uv sync
```

## Démarrer PostgreSQL/TimescaleDB (Docker)

Depuis la **racine du dépôt** :

```bash
docker compose --profile postgres up -d
```

Vérifier que le conteneur est prêt :

```bash
docker compose ps
```

## Appliquer les migrations

Depuis la racine du dépôt :

```bash
docker compose exec -T postgres psql -U souverain_admin -d souverain_os \
  < briques/brique_01_postgresql/migrations/0001_init_shared_schema.sql
```

Cette commande applique uniquement le schéma partagé initial. Pour le
correctif P0 d'identités PostgreSQL par tenant, l'ordre validé sur une base
scratch est :

1. B1 `0001` à `0005`, puis B2 `0001` à `0003` ;
2. provisionner les schémas des tenants existants, puis appliquer les
   migrations B3, B4, B5 et B8 (`0001`, puis B8 `0002`) ;
3. appliquer B1 `0006`, B1 `0007`, puis B1 `0008` en dernier ;
4. avant le démarrage applicatif, provisionner les rôles login par tenant :

   ```bash
   uv run python briques/brique_01_postgresql/scripts/provision_tenant_roles.py \
     --expected-database souverain_os
   ```

Le script vérifie le nom réel de la base, génère ou réutilise les secrets,
les écrit dans le `.env` local en mode `0600` et n'affiche aucune valeur
secrète. `0008` échoue si un rôle tenant déterministe possède déjà des
objets ; les appartenances et ACL résiduelles sont nettoyées avant
d'accorder les seuls droits attendus. Les tests et migrations de ce correctif
ont été exécutés sur des bases scratch uniquement. **Ne pas appliquer à la
base principale sans autorisation explicite du fondateur**, sauvegarde
vérifiée et contrôle préalable des rôles/ACL existants.

## Vérifier que tout fonctionne

```bash
cd briques/brique_01_postgresql

# Tests unitaires (aucune DB requise) + tests d'intégration
# (auto-skippés si PostgreSQL n'est pas démarré)
uv run pytest -v

# Healthcheck de la base réelle
uv run python scripts/db_healthcheck.py

# Qualité de code
uv run ruff check .
uv run mypy src/
```

## Erreurs fréquentes et diagnostic

| Symptôme | Cause probable | Diagnostic |
|---|---|---|
| `ConnectionRefusedError` au healthcheck | Conteneur PostgreSQL non démarré | `docker compose --profile postgres up -d`, puis `docker compose ps` pour vérifier l'état `healthy` |
| Tests d'intégration systématiquement SKIPPED | Normal si PostgreSQL n'est pas lancé — pas un échec | Démarrer le conteneur pour les exécuter réellement |
| `Extension TimescaleDB` en FAIL | Image Docker utilisée n'est pas l'image TimescaleDB | Vérifier que `docker-compose.yml` utilise bien `timescale/timescaledb:...`, pas `postgres:...` classique |
| `Schéma partagé` en FAIL après démarrage du conteneur | Migration non appliquée | Rejouer la commande d'application de `migrations/0001_init_shared_schema.sql` |
| `InvalidSchemaNameError` lors du provisioning | Nom de tenant non conforme (majuscules, tiret, etc.) | Utiliser uniquement minuscules/chiffres/underscore, ex. `tenant_ne` |

## Implications sécurité

- Isolation physique par schéma : un tenant ne peut techniquement pas requêter les données d'un autre tenant sans changer explicitement de schéma cible.
- `validate_schema_name()` empêche toute injection SQL lors de la création dynamique de schémas (les noms d'objets SQL ne peuvent pas être paramétrés comme des valeurs classiques par le driver — la validation stricte par regex est donc la défense).
- `.env` avec les identifiants réels — jamais commité.
- `data_classification` posée dès la fondation du schéma, pas ajoutée après coup.

## Dépendances avec les briques futures

- Brique 2 (Auth/RBAC) s'appuiera sur `shared.tenants_registry` pour résoudre le tenant courant.
- Brique 3 (Ingestion) écrira dans `{tenant}.transactions`.
- Brique 8 (Audit) étendra `provision_tenant_schema()` en `create_tenant()` complet avec RBAC et audit trail.

## Estimation RAM

PostgreSQL + TimescaleDB en conteneur (~150-250 Mo au repos) + pool de connexions Python (~20-30 Mo) → **< 400 Mo** au total. Marge très large sur la machine de référence (16 Go DDR4).

## Note sur les tests

**Brique validée le 13 août 2026** contre une vraie instance PostgreSQL/TimescaleDB (pas de mock), sur ThinkPad X1 Carbon Gen 6 : 15/15 tests passés (13 unitaires + 2 intégration), healthcheck SAIN, ruff et mypy propres.
