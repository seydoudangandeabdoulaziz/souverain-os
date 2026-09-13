#!/usr/bin/env bash
# ============================================================
# Restauration PostgreSQL — Étape 1 (Hygiène de socle)
# ============================================================
# ⚠️ Restaure sur la base configurée par POSTGRES_DB (.env) — PAS de
# garde-fou "es-tu sûr de vouloir écraser une base non-vide" au-delà
# de la confirmation interactive ci-dessous. Portée volontairement
# minimale (voir backup_postgres.sh pour le contexte complet).
#
# Usage :
#   ./scripts/restore_postgres.sh backups/souverain_os_XXXXXXXXTXXXXXXZ.sql
# ============================================================

set -euo pipefail

if [ $# -ne 1 ]; then
    echo "Usage : $0 <chemin_vers_le_dump.sql>" >&2
    exit 1
fi

FICHIER_DUMP="$1"

if [ ! -f "$FICHIER_DUMP" ]; then
    echo "[restore_postgres] ERREUR : fichier introuvable : $FICHIER_DUMP" >&2
    exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"

# Préserve toute variable déjà explicitement définie par l'appelant
# (ex: POSTGRES_DB=autre_base ./restore_postgres.sh ...) — AVANT de
# charger .env, pour que .env reste un REPLI PAR DÉFAUT, jamais une
# priorité absolue qui écraserait un choix explicite de l'opérateur.
# Bug réel trouvé en conditions réelles (7 septembre 2026) : sans
# cette préservation, `source .env` écrasait silencieusement
# POSTGRES_DB déjà positionné par l'appelant, redirigeant la
# restauration vers la mauvaise base sans que le script ne s'en
# aperçoive — la confirmation affichée reflétait déjà la mauvaise
# valeur, donc rien ne permettait de le détecter avant qu'il ne soit
# trop tard.
POSTGRES_DB_APPELANT="${POSTGRES_DB:-}"

if [ -f "$ENV_FILE" ]; then
    # shellcheck disable=SC1090
    set -a
    source "$ENV_FILE"
    set +a
fi

if [ -n "$POSTGRES_DB_APPELANT" ]; then
    POSTGRES_DB="$POSTGRES_DB_APPELANT"
fi

POSTGRES_DB="${POSTGRES_DB:-souverain_os}"
POSTGRES_USER="${POSTGRES_USER:-souverain_admin}"

echo "[restore_postgres] ⚠️  Ceci va exécuter le contenu SQL de ${FICHIER_DUMP}"
echo "[restore_postgres]     contre la base ${POSTGRES_DB} — données existantes en conflit écrasées."
echo "[restore_postgres]"
echo "[restore_postgres] Pour confirmer, retape EXACTEMENT le nom de la base ci-dessus :"
read -r -p "[restore_postgres] Nom de la base à restaurer : " CONFIRMATION

if [ "$CONFIRMATION" != "$POSTGRES_DB" ]; then
    echo "[restore_postgres] Annulé — le nom saisi ne correspond pas exactement à '${POSTGRES_DB}'."
    exit 1
fi

docker compose exec -T postgres psql \
    -U "$POSTGRES_USER" \
    -d "$POSTGRES_DB" \
    < "$FICHIER_DUMP"

echo "[restore_postgres] Terminé."
