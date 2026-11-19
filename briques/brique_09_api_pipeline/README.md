# Brique 9 — API d'ingestion et de scoring (identité technique par tenant)

**Statut : EN TEST — non validée.** Le cycle incrémental n'est pas considéré comme validé tant que les tests différentiels *et* les mesures sur la machine du fondateur ne sont pas concluants. Périmètre et décisions : `docs/API_INGESTION_SCORING_PERIMETRE.md`.

## Rôle

Un client technique d'un tenant envoie des transactions (`POST /api/v1/transactions`) puis déclenche détection et scoring (`POST /api/v1/pipeline/cycle`). Les alertes sont ensuite consommées par le dashboard (B7) et la fermeture humaine (B8), inchangés. Les Briques 2 à 8 ne sont pas modifiées ; la Brique 1 reçoit uniquement une extension additive (rôle PostgreSQL `pipeline`, migration `0009`).

## Modèle de sécurité

- **Identité technique** (`shared.api_clients`) : séparée des utilisateurs humains, liée à un tenant et à une `source` d'ingestion, portées minimales `ingest` / `cycle`, secret Argon2id, expiration optionnelle, rotation et révocation immédiates.
- **Jeton court** (15 min, `typ=service`, clé et `aud` dédiés) : un jeton humain n'est jamais accepté ici, ni l'inverse. L'autorité réelle (actif, version du secret, portées, tenant actif) est relue en base à chaque requête.
- **Rôle PostgreSQL `pipeline`** (un par tenant, créé par B1) : `INSERT`/`SELECT` sur `transactions`, `detections`, `ingestion_keys` ; `UPDATE` seulement sur `alertes` et `pipeline_cursor` ; **aucun** `CREATE`, `DELETE`, `TRUNCATE`, accès à `shared.users`, à l'audit ou à un autre tenant. Le rôle `data` n'est pas modifié.
- **Idempotence garantie par la base** : clé primaire `(source, external_id)` par tenant. Rejeu identique = aucune insertion ; même identifiant avec un contenu différent = `409 conflit_external_id` et lot entièrement annulé.
- Aucun cookie accepté, corps borné (411/413), échecs d'authentification limités par client et par adresse, journaux sans compte, montant, secret ni corps.

## Cycle incrémental (sans recalcul global)

Pour chaque compte touché, relecture de son historique depuis le début de son épisode d'activité (écart > 6 h), moteur B4 inchangé, filtrage des comptes touchés, dédoublonnage par chevauchement d'intervalle, insertion + curseur dans **une seule transaction SQL**, puis scoring B5 inchangé. Un seul cycle à la fois par tenant (`409 cycle_en_cours`).

**Limites connues**
- Une transaction arrivée très en retard peut relier deux salves d'activité : le recalcul complet y verrait un seul épisode, alors que le cycle avait déjà enregistré la seconde salve. La ligne est conservée (les détections sont des preuves immuables) ; aucun épisode n'est jamais perdu. Mesuré : 4 lignes sur 245 dans le scénario le plus défavorable des tests.
- Pour des comptes à activité continue, le coût d'un cycle approche celui de la relecture de leur historique (repli compté dans `replis_episode`).
- Les transactions insérées par la CLI B3 ne passent pas par `ingestion_keys` : ne pas mélanger la CLI B4 (`souverain-detecter`) et l'API sur un même tenant.
- Pas de verdict synchrone par transaction (Vision).

## Mise en route (opérateur, base principale : uniquement après autorisation du fondateur)

```bash
# 1. Migrations (dans l'ordre) : B1 0009 puis B9 0001
docker compose --profile postgres exec -T postgres psql -U "$POSTGRES_USER" -d souverain_os \
  < briques/brique_01_postgresql/migrations/0009_tenant_pipeline_role.sql
docker compose --profile postgres exec -T postgres psql -U "$POSTGRES_USER" -d souverain_os \
  < briques/brique_09_api_pipeline/migrations/0001_create_api_clients.sql

# 2. Objets B9 du tenant (tables, index) + droits du rôle pipeline
uv run souverain-api-provisionner --expected-database souverain_os --tenant-code NE

# 3. Activer le rôle pipeline (secret dans TENANT_DB_CREDENTIALS_JSON, clé pipeline_password)
uv run python briques/brique_01_postgresql/scripts/provision_tenant_roles.py \
  --expected-database souverain_os --with-pipeline

# 4. Créer l'identité technique (secret affiché une seule fois)
uv run souverain-api-client --expected-database souverain_os creer \
  --tenant-code NE --source orange_money_feed --scopes ingest cycle --acteur "nom.operateur"
```

Variable obligatoire : `SOUVERAIN_API_JWT_SECRET` (≥ 32 caractères, distincte de la clé des jetons humains).

## Tests

```bash
# Base jetable souverain_pipeline_test (migrations B1 0001-0009, B2, B3-B5, B8, B9 0001)
export SOUVERAIN_PIPELINE_TEST_DSN='postgresql://…/souverain_pipeline_test'
uv run pytest briques/brique_09_api_pipeline
uv run python briques/brique_09_api_pipeline/benchmarks/bench_pg.py --volume 50000 --comptes 5000
```
