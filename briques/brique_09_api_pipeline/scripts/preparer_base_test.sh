#!/usr/bin/env bash
# Prépare une base PostgreSQL/TimescaleDB JETABLE pour les tests et mesures de la Brique 9.
#
# POURQUOI UN CONTENEUR À PART : les rôles PostgreSQL sont GLOBAUX au serveur. Les migrations
# 0006-0008 de B1 modifient des rôles (souverain_app, rôles legacy, rôles par tenant). Les rejouer
# dans une seconde base du conteneur `postgres` du projet pourrait désactiver les rôles de ta
# vraie base. Ce script crée donc un conteneur séparé (port 55432, aucun volume, supprimé avec
# `docker rm -f souverain-pipeline-test`) et ne touche jamais à ta base principale.
#
# Usage (depuis la racine du dépôt) :  bash briques/brique_09_api_pipeline/scripts/preparer_base_test.sh
set -euo pipefail

RACINE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
CONTENEUR="${CONTENEUR:-souverain-pipeline-test}"
PORT="${PORT_TEST:-55432}"
MDP_SUPER="${MDP_SUPER:-devpw_local_uniquement}"
MDP_CONTROLE="ctlpw_ctlpw_ctlpw_ctlpw_ctlpw_0123"   # attendu par tests/conftest.py (souverain_app)
BASE="souverain_pipeline_test"
A=11111111-1111-1111-1111-111111111111
B=22222222-2222-2222-2222-222222222222
PYTHON_CMD="${PYTHON_CMD:-uv run python}"
B1="$RACINE/briques/brique_01_postgresql/migrations"
B2="$RACINE/briques/brique_02_auth_rbac/migrations"
B3="$RACINE/briques/brique_03_generateur_ingestion/migrations"
B4="$RACINE/briques/brique_04_detection/migrations"
B5="$RACINE/briques/brique_05_scoring_alertes/migrations"
B8="$RACINE/briques/brique_08_audit_human_loop/migrations"
B9="$RACINE/briques/brique_09_api_pipeline/migrations"

if [ -z "${PSQL_LOCAL:-}" ]; then
  if ! docker ps -a --format '{{.Names}}' | grep -qx "$CONTENEUR"; then
    docker run -d --name "$CONTENEUR" -e POSTGRES_PASSWORD="$MDP_SUPER" \
      -p "127.0.0.1:$PORT:5432" timescale/timescaledb:2.17.2-pg16 >/dev/null
  fi
  docker start "$CONTENEUR" >/dev/null
  # Attendre le VRAI serveur : l'image démarre d'abord un serveur temporaire d'initialisation
  # (socket Unix seulement, puis arrêt). Seul le serveur final écoute en TCP.
  until docker exec "$CONTENEUR" pg_isready -h 127.0.0.1 -U postgres >/dev/null 2>&1; do sleep 1; done
  sleep 1
fi
# PSQL_LOCAL (optionnel) : psql direct, pour valider ce script hors Docker.
psql_base() { # $1 = base ; entrée standard = SQL
  if [ -n "${PSQL_LOCAL:-}" ]; then PGPASSWORD="$MDP_SUPER" psql -v ON_ERROR_STOP=1 -q -X -U postgres -h 127.0.0.1 -p "$PORT" -d "$1"
  else docker exec -i "$CONTENEUR" psql -v ON_ERROR_STOP=1 -q -X -U postgres -d "$1"; fi
}
appliquer() { echo ">> $(basename "$1")"; psql_base "$BASE" < "$1" 2>&1 | grep -v -E "^NOTICE|^$" || true; }

# `souverain_os` factice : la migration 0002 de B1 y accorde CONNECT (nom en dur).
for b in souverain_os "$BASE"; do
  echo "SELECT 1" | psql_base postgres >/dev/null
  echo "SELECT 'CREATE DATABASE $b' WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname='$b')\gexec" | psql_base postgres
done
echo "CREATE EXTENSION IF NOT EXISTS timescaledb;" | psql_base "$BASE"

appliquer "$B1/0001_init_shared_schema.sql"
appliquer "$B1/0002_create_gouvernance_audit_log.sql"
appliquer "$B2/0001_init_users_table.sql"
echo "INSERT INTO shared.tenants_registry(tenant_id,tenant_code,country_code,schema_name) VALUES ('$A','TA','NE','tenant_pl_a'),('$B','TB','SN','tenant_pl_b') ON CONFLICT DO NOTHING" | psql_base "$BASE"
export PGB_DSN="postgresql://postgres:$MDP_SUPER@127.0.0.1:$PORT/$BASE"
$PYTHON_CMD - <<PY
import asyncio, os, asyncpg
from brique_01_postgresql.tenant_provisioning import provision_tenant_schema
async def main():
    c = await asyncpg.connect(os.environ["PGB_DSN"])
    for s in ("tenant_pl_a", "tenant_pl_b"):
        await provision_tenant_schema(c, s)
    await c.close()
asyncio.run(main())
PY
appliquer "$B3/0001_add_is_synthetic.sql"
appliquer "$B4/0001_create_detections_table.sql"
appliquer "$B5/0001_create_alertes_table.sql"
for f in 0003_integrite_donnees_log 0004_event_trigger_integrite 0005_create_monitoring_role; do appliquer "$B1/$f.sql"; done
appliquer "$B2/0002_gouvernance_web_role.sql"
appliquer "$B2/0003_lock_web_role_default.sql"
appliquer "$B8/0001_create_audit_log_table.sql"
for f in 0006_app_runtime_role 0007_lock_legacy_role_defaults 0008_tenant_scoped_roles 0009_tenant_pipeline_role; do appliquer "$B1/$f.sql"; done
appliquer "$B9/0001_create_api_clients.sql"
echo "ALTER ROLE souverain_app LOGIN PASSWORD '$MDP_CONTROLE'" | psql_base "$BASE"

echo
echo "Base prête. Exporter puis lancer les tests :"
echo "  export SOUVERAIN_PIPELINE_TEST_DSN='postgresql://postgres:$MDP_SUPER@127.0.0.1:$PORT/$BASE'"
echo "  uv run pytest briques/brique_09_api_pipeline -q"
echo "Mesures (volumes à adapter) :"
echo "  uv run python briques/brique_09_api_pipeline/benchmarks/bench_pg.py --volume 50000 --comptes 5000"
