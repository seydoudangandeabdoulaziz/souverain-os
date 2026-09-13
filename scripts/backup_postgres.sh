#!/usr/bin/env bash
# ============================================================
# Sauvegarde PostgreSQL — Étape 1 (Hygiène de socle)
# ============================================================
# ⚠️ Portée volontairement minimale, actée à la conception : ceci
# PROUVE que la mécanique fonctionne, ce n'est PAS une stratégie de
# production. Pas d'automatisation (cron), pas de rétention, pas de
# stockage distant, pas de chiffrement — tout ça reste FUTUR,
# documenté comme tel dans docs/DIFFERENCIATION_STRATEGIQUE.md et la
# revue d'architecture qui a précédé ce script.
#
# Format --format=plain (SQL brut) plutôt que --format=custom :
# lisible, auditable, cohérent avec la préférence du projet pour des
# artefacts explicites. Le format custom (compression, restauration
# sélective) reste une optimisation future si le besoin apparaît.
#
# Usage :
#   ./scripts/backup_postgres.sh
#
# Lit les identifiants depuis les variables d'environnement déjà
# utilisées par le reste du projet (POSTGRES_*, voir .env.example) —
# aucune nouvelle convention de configuration introduite.
# ============================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"

# Même correction que restore_postgres.sh (bug réel trouvé le 7
# septembre 2026) : préserve toute variable déjà explicitement
# définie par l'appelant AVANT de charger .env — .env reste un repli
# par défaut, jamais une priorité qui écraserait un choix explicite.
POSTGRES_HOST_APPELANT="${POSTGRES_HOST:-}"
POSTGRES_PORT_APPELANT="${POSTGRES_PORT:-}"
POSTGRES_DB_APPELANT="${POSTGRES_DB:-}"
POSTGRES_USER_APPELANT="${POSTGRES_USER:-}"

if [ -f "$ENV_FILE" ]; then
    # shellcheck disable=SC1090
    set -a
    source "$ENV_FILE"
    set +a
fi

[ -n "$POSTGRES_HOST_APPELANT" ] && POSTGRES_HOST="$POSTGRES_HOST_APPELANT"
[ -n "$POSTGRES_PORT_APPELANT" ] && POSTGRES_PORT="$POSTGRES_PORT_APPELANT"
[ -n "$POSTGRES_DB_APPELANT" ] && POSTGRES_DB="$POSTGRES_DB_APPELANT"
[ -n "$POSTGRES_USER_APPELANT" ] && POSTGRES_USER="$POSTGRES_USER_APPELANT"

POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_DB="${POSTGRES_DB:-souverain_os}"
POSTGRES_USER="${POSTGRES_USER:-souverain_admin}"

BACKUP_DIR="$REPO_ROOT/backups"
mkdir -p "$BACKUP_DIR"

HORODATAGE="$(date -u +%Y%m%dT%H%M%SZ)"
FICHIER_SORTIE="$BACKUP_DIR/souverain_os_${HORODATAGE}.sql"

echo "[backup_postgres] Sauvegarde de ${POSTGRES_DB}@${POSTGRES_HOST}:${POSTGRES_PORT} vers ${FICHIER_SORTIE}"

docker compose exec -T postgres pg_dump \
    -U "$POSTGRES_USER" \
    -d "$POSTGRES_DB" \
    --format=plain \
    --no-owner \
    --no-privileges \
    > "$FICHIER_SORTIE"

TAILLE="$(du -h "$FICHIER_SORTIE" | cut -f1)"
echo "[backup_postgres] Terminé — ${FICHIER_SORTIE} (${TAILLE})"
echo "[backup_postgres] Rappel : ce fichier n'est PAS chiffré et n'est PAS répliqué ailleurs."
