-- ============================================================
-- Migration 0001 (Brique 2) — shared.users
-- ============================================================
-- PRÉREQUIS : la migration 0001_init_shared_schema.sql de la
-- Brique 1 (briques/brique_01_postgresql/migrations/) doit déjà
-- avoir été appliquée sur cette base — cette migration référence
-- shared.tenants_registry.
--
-- Contenu identique à src/brique_02_auth_rbac/schema_users.sql.
-- Toute évolution future donnera lieu à une nouvelle migration
-- numérotée dans CE dossier (0002_..., etc.), jamais à une
-- modification rétroactive de ce fichier.
-- ============================================================

CREATE TABLE IF NOT EXISTS shared.users (
    user_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    souverain_id          UUID NOT NULL UNIQUE,
    tenant_id             UUID NOT NULL REFERENCES shared.tenants_registry (tenant_id)
                               ON DELETE RESTRICT,
    email                  TEXT NOT NULL UNIQUE,
    password_hash          TEXT NOT NULL,
    role                    TEXT NOT NULL
        CHECK (role IN ('admin', 'analyst', 'auditor')),
    data_classification     TEXT NOT NULL DEFAULT 'confidential'
        CHECK (data_classification IN ('public', 'internal', 'confidential', 'secret')),
    token_version           INTEGER NOT NULL DEFAULT 1,
    is_active                BOOLEAN NOT NULL DEFAULT true,
    created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at             TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_users_tenant_id
    ON shared.users (tenant_id);

CREATE INDEX IF NOT EXISTS idx_users_is_active
    ON shared.users (is_active)
    WHERE is_active = true;
