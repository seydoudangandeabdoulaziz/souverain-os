-- ============================================================
-- SOUVERAIN-OS — Schéma PARTAGÉ (shared)
-- ============================================================
-- Rôle : registre central de tous les tenants (pays) connus du
-- système. Ce schéma NE contient AUCUNE donnée métier (aucune
-- transaction) — uniquement les métadonnées de gouvernance.
--
-- Isolation : chaque tenant a ensuite son propre schéma physique
-- (voir schema_tenant_template.sql), listé ici par référence.
-- ============================================================

CREATE SCHEMA IF NOT EXISTS shared;

-- Registre des tenants : un pays = un tenant = un schéma dédié.
CREATE TABLE IF NOT EXISTS shared.tenants_registry (
    tenant_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_code         TEXT NOT NULL UNIQUE,        -- ex: 'NE' (Niger), 'SN' (Sénégal)
    country_code        TEXT NOT NULL,               -- code pays ISO 3166-1 alpha-2
    schema_name         TEXT NOT NULL UNIQUE,        -- ex: 'tenant_ne'
    data_classification TEXT NOT NULL DEFAULT 'confidential'
        CHECK (data_classification IN ('public', 'internal', 'confidential', 'secret')),
    is_active           BOOLEAN NOT NULL DEFAULT true,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE shared.tenants_registry IS
    'Registre central des tenants (pays). Ne contient aucune donnée métier — uniquement la gouvernance multi-tenant.';

COMMENT ON COLUMN shared.tenants_registry.schema_name IS
    'Nom du schéma PostgreSQL physique dédié à ce tenant. Doit correspondre exactement au schéma créé via schema_tenant_template.sql.';

COMMENT ON COLUMN shared.tenants_registry.data_classification IS
    'Classification de données par défaut pour ce tenant, conforme à 05_SECURITE_ET_GOUVERNANCE.md.';

-- Index pour les recherches fréquentes par code pays.
CREATE INDEX IF NOT EXISTS idx_tenants_registry_country_code
    ON shared.tenants_registry (country_code);

CREATE INDEX IF NOT EXISTS idx_tenants_registry_is_active
    ON shared.tenants_registry (is_active)
    WHERE is_active = true;
