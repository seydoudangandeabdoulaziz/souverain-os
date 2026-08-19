-- Brique 5 — Scoring + Alertes
-- Migration portée par la Brique 5 uniquement.
-- Ne modifie AUCUN fichier des Briques 1 à 4 (même discipline que
-- 0001_add_is_synthetic.sql en Brique 3 et 0001_create_detections_table.sql
-- en Brique 4).
--
-- Cette migration est appliquée dans le schéma d'un tenant donné
-- (ex. tenant_ne), au même titre que les tables detections, transactions.
--
-- Trois tables :
--   1. alertes              : le score agrégé par compte_pivot (Q1/Q5)
--   2. alertes_detections   : table de jonction, traçabilité alerte -> détections (Q6)
--   3. detections_traitees  : table de suivi séparée, remplace le flag
--                             "traité" qui n'existe pas sur detections
--                             (GAP RÉEL découvert en Brique 5 — cf. avancement.md)

-- =============================================================
-- 1. Table alertes
-- =============================================================
CREATE TABLE IF NOT EXISTS alertes (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Correction du 17/08/2026 : tenant_id est UUID dans transactions
    -- et detections (vérifié contre le vrai schéma), pas TEXT comme
    -- initialement supposé. Corrigé ici pour rester cohérent.
    tenant_id              UUID NOT NULL,
    country_code           TEXT NOT NULL,
    data_classification    TEXT NOT NULL,

    -- Clé de regroupement (Q1). Colonne réelle de detections.compte_pivot,
    -- jamais NULL sur une ligne d'alerte : une détection avec
    -- compte_pivot NULL est exclue en amont du scoring (cf. lecture.py).
    compte_pivot           TEXT NOT NULL,

    -- Score agrégé (0-100), plafonné. Mis à jour en place, jamais dupliqué
    -- tant qu'une alerte 'ouverte' existe pour ce compte_pivot (Q5).
    score                  INTEGER NOT NULL CHECK (score >= 0 AND score <= 100),

    -- Valeur MVP unique : 'ouverte'. Le workflow humain complet
    -- (fermeture, traitement) appartient à la Brique 8, qui étendra
    -- cette colonne via sa propre migration.
    statut                 TEXT NOT NULL DEFAULT 'ouverte',

    premiere_detection_at  TIMESTAMPTZ NOT NULL,
    derniere_detection_at  TIMESTAMPTZ NOT NULL,

    -- Calculé (pas propagé) : true seulement si 100% des transactions
    -- liées à toutes les détections contributrices sont synthétiques.
    -- Recalculé à chaque mise à jour de l'alerte. Cf. alertes.py.
    is_synthetic           BOOLEAN NOT NULL DEFAULT FALSE,

    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Une seule alerte 'ouverte' par compte_pivot : anti-doublon (Q5).
-- Index partiel plutôt que contrainte UNIQUE globale, car le statut
-- pourra évoluer (Brique 8) sans empêcher l'historique de plusieurs
-- alertes fermées pour un même compte.
CREATE UNIQUE INDEX IF NOT EXISTS ix_alertes_compte_pivot_ouverte
    ON alertes (tenant_id, compte_pivot)
    WHERE statut = 'ouverte';

CREATE INDEX IF NOT EXISTS ix_alertes_compte_pivot
    ON alertes (compte_pivot);

CREATE INDEX IF NOT EXISTS ix_alertes_statut
    ON alertes (statut);

-- =============================================================
-- 2. Table de jonction alertes_detections (Q6)
-- =============================================================
CREATE TABLE IF NOT EXISTS alertes_detections (
    alerte_id      UUID NOT NULL REFERENCES alertes (id) ON DELETE CASCADE,
    detection_id   UUID NOT NULL,
    linked_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (alerte_id, detection_id)
);

CREATE INDEX IF NOT EXISTS ix_alertes_detections_detection_id
    ON alertes_detections (detection_id);

-- =============================================================
-- 3. Table de suivi detections_traitees (Correction 1)
-- =============================================================
-- Remplace un flag "traité" qui n'existe pas sur detections (GAP RÉEL,
-- vérifié contre la vraie migration Brique 4). Rôle : repérer quels
-- compte_pivot ont une activité NOUVELLE à recalculer (déclencheur),
-- jamais un filtre d'exclusion du calcul de score lui-même — le
-- recalcul relit TOUTES les détections du compte dans la fenêtre de
-- 7 jours, traitées ou non (résolution de la tension flag/fenêtre,
-- cf. analyse validée).
CREATE TABLE IF NOT EXISTS detections_traitees (
    detection_id   UUID PRIMARY KEY,
    traitee_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
