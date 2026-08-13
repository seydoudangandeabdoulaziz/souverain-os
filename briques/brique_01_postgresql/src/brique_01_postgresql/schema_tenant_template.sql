-- ============================================================
-- SOUVERAIN-OS — TEMPLATE de schéma TENANT
-- ============================================================
-- Ce fichier est un TEMPLATE : {schema_name} est remplacé
-- programmatiquement (voir tenant_provisioning.py) par un nom de
-- schéma validé avant exécution — ex: 'tenant_ne' pour le Niger.
--
-- NE JAMAIS exécuter ce fichier tel quel : il doit toujours passer
-- par tenant_provisioning.provision_tenant_schema(), qui valide le
-- nom du schéma pour éviter toute injection SQL.
--
-- Rôle : structure de données ISOLÉE par tenant. Aucune donnée d'un
-- tenant n'est visible depuis le schéma d'un autre tenant.
--
-- Périmètre de la Brique 1 : uniquement la table "transactions" de
-- base (colonnes structurelles). La logique de scoring et de
-- détection sera ajoutée par les Briques 4 et 5, sans modifier ce
-- schéma de fondation.
-- ============================================================

CREATE SCHEMA IF NOT EXISTS {schema_name};

CREATE TABLE IF NOT EXISTS {schema_name}.transactions (
    transaction_id       UUID NOT NULL DEFAULT gen_random_uuid(),
    tenant_id            UUID NOT NULL,
    country_code         TEXT NOT NULL,
    data_classification  TEXT NOT NULL DEFAULT 'confidential'
        CHECK (data_classification IN ('public', 'internal', 'confidential', 'secret')),

    -- Champs métier de base (Mobile Money) — volontairement minimaux.
    amount                NUMERIC(18, 2) NOT NULL,
    currency              TEXT NOT NULL DEFAULT 'XOF',
    sender_account        TEXT NOT NULL,
    receiver_account      TEXT NOT NULL,
    channel               TEXT NOT NULL,  -- ex: 'orange_money', 'airtel_money', 'moov_money'

    -- Horodatage : occurred_at = quand la transaction a EU LIEU,
    -- ingested_at = quand SOUVERAIN-OS l'a reçue (peuvent différer).
    occurred_at            TIMESTAMPTZ NOT NULL,
    ingested_at            TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Données brutes non structurées de la source, conservées pour
    -- traçabilité/audit sans perte d'information.
    raw_payload            JSONB,

    -- PRIMARY KEY composite (transaction_id, occurred_at) : exigence
    -- TimescaleDB pour les hypertables (la clé de partitionnement
    -- doit faire partie de la clé primaire).
    PRIMARY KEY (transaction_id, occurred_at)
);

COMMENT ON TABLE {schema_name}.transactions IS
    'Transactions Mobile Money brutes pour ce tenant. Isolation physique totale via le schéma dédié.';

-- Transformation en hypertable TimescaleDB : découpe automatiquement
-- les données par tranches de temps (chunks), pour des requêtes
-- rapides sur de gros volumes de séries temporelles.
-- if_not_exists => idempotent, migration rejouable sans erreur.
SELECT create_hypertable(
    '{schema_name}.transactions',
    by_range('occurred_at'),
    if_not_exists => true
);

-- Index utiles dès la fondation (recherche par compte, par canal).
CREATE INDEX IF NOT EXISTS idx_{schema_name}_transactions_sender
    ON {schema_name}.transactions (sender_account);

CREATE INDEX IF NOT EXISTS idx_{schema_name}_transactions_receiver
    ON {schema_name}.transactions (receiver_account);

CREATE INDEX IF NOT EXISTS idx_{schema_name}_transactions_channel
    ON {schema_name}.transactions (channel);
