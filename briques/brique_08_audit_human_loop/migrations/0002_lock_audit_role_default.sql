-- Sécurité additive : neutralise le LOGIN et le secret de démonstration
-- du rôle d'audit créé historiquement par la migration 0001.
-- Ses privilèges d'insertion/lecture ne changent pas.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'souverain_brique8_audit'
    ) THEN
        ALTER ROLE souverain_brique8_audit
            NOLOGIN PASSWORD NULL NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
    END IF;
END
$$;
