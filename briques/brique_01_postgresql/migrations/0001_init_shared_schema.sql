-- ============================================================
-- Migration 0001 — Initialisation du schéma partagé
-- ============================================================
-- Contenu identique à src/brique_01_postgresql/schema_shared.sql.
-- Ce fichier est la copie "versionnée" appliquée lors du provisioning
-- initial de la base. Toute évolution future du schéma partagé
-- donnera lieu à une nouvelle migration numérotée (0002_..., etc.),
-- jamais à une modification rétroactive de ce fichier.
-- ============================================================

CREATE SCHEMA IF NOT EXISTS shared;

CREATE TABLE IF NOT EXISTS shared.tenants_registry (
    tenant_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_code         TEXT NOT NULL UNIQUE,
    country_code        TEXT NOT NULL,
    schema_name         TEXT NOT NULL UNIQUE,
    data_classification TEXT NOT NULL DEFAULT 'confidential'
        CHECK (data_classification IN ('public', 'internal', 'confidential', 'secret')),
    is_active           BOOLEAN NOT NULL DEFAULT true,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tenants_registry_country_code
    ON shared.tenants_registry (country_code);

CREATE INDEX IF NOT EXISTS idx_tenants_registry_is_active
    ON shared.tenants_registry (is_active)
    WHERE is_active = true;
