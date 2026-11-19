-- Brique 9 — Migration 0001 : identités techniques de l'API (schéma shared).
--
-- Aucune table des Briques 1 à 8 n'est modifiée. Les tables par tenant
-- (ingestion_keys, pipeline_cursor, index) sont créées par
-- `souverain-api-provisionner` (rôle admin), tenant par tenant.
-- Idempotente. Non appliquée automatiquement.

CREATE TABLE IF NOT EXISTS shared.api_clients (
    client_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id      UUID NOT NULL REFERENCES shared.tenants_registry (tenant_id) ON DELETE RESTRICT,
    source_code    TEXT NOT NULL CHECK (source_code ~ '^[a-z0-9_]{3,40}$'),
    secret_hash    TEXT NOT NULL,
    scopes         TEXT[] NOT NULL
        CHECK (cardinality(scopes) > 0 AND scopes <@ ARRAY['ingest', 'cycle']::TEXT[]),
    is_active      BOOLEAN NOT NULL DEFAULT true,
    expires_at     TIMESTAMPTZ,
    secret_version INTEGER NOT NULL DEFAULT 1,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    rotated_at     TIMESTAMPTZ,
    revoked_at     TIMESTAMPTZ,
    UNIQUE (tenant_id, source_code)
);

CREATE INDEX IF NOT EXISTS idx_api_clients_tenant ON shared.api_clients (tenant_id);

ALTER TABLE shared.api_clients ENABLE ROW LEVEL SECURITY;
ALTER TABLE shared.api_clients FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS api_clients_tenant_select ON shared.api_clients;
CREATE POLICY api_clients_tenant_select ON shared.api_clients
    FOR SELECT USING (tenant_id = shared.current_login_tenant_id());

-- Journal des opérations de l'opérateur (création, rotation, révocation).
-- Insert-only, aucun accès pour les rôles tenant.
CREATE TABLE IF NOT EXISTS shared.api_client_events (
    event_id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    client_id   UUID NOT NULL,
    tenant_id   UUID NOT NULL,
    event_type  TEXT NOT NULL
        CHECK (event_type IN ('created', 'rotated', 'revoked', 'reactivated')),
    actor       TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
REVOKE ALL ON shared.api_client_events FROM PUBLIC;
REVOKE ALL ON shared.api_clients FROM PUBLIC;

-- Droits de lecture pour les rôles `pipeline` déjà provisionnés
-- (ceux provisionnés ensuite les reçoivent via B1, liste blanche).
DO $$
DECLARE r RECORD;
BEGIN
    FOR r IN SELECT role_name FROM shared.tenant_login_map WHERE purpose = 'pipeline' LOOP
        EXECUTE format('GRANT SELECT ON shared.api_clients TO %I', r.role_name);
    END LOOP;
END
$$;
