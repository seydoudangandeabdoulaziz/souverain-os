-- Brique 1 — rôle d'exécution à privilèges minimaux pour l'application web.
-- À appliquer avec le rôle d'administration après les migrations B1/B2 et
-- les migrations B4/B5 déjà nécessaires à l'affichage des alertes.
-- Le rôle est créé NOLOGIN : son activation et son mot de passe sont
-- renseignés manuellement, sans valeur secrète dans l'historique Git.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'souverain_app') THEN
        CREATE ROLE souverain_app NOLOGIN;
    END IF;
END
$$;

ALTER ROLE souverain_app
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;

DO $$
BEGIN
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO souverain_app', current_database());
END
$$;

GRANT USAGE ON SCHEMA shared TO souverain_app;
GRANT SELECT ON shared.tenants_registry, shared.users TO souverain_app;
GRANT UPDATE (last_login_at) ON shared.users TO souverain_app;

-- Accès de lecture aux seules tables consommées par le dashboard. Les
-- autres données de chaque tenant restent inaccessibles à ce rôle.
DO $$
DECLARE
    tenant RECORD;
BEGIN
    FOR tenant IN
        SELECT schema_name
        FROM shared.tenants_registry
    LOOP
        EXECUTE format('GRANT USAGE ON SCHEMA %I TO souverain_app', tenant.schema_name);
        IF to_regclass(format('%I.alertes', tenant.schema_name)) IS NOT NULL THEN
            EXECUTE format(
                'GRANT SELECT ON TABLE %I.alertes TO souverain_app', tenant.schema_name
            );
        END IF;
        IF to_regclass(format('%I.detections', tenant.schema_name)) IS NOT NULL THEN
            EXECUTE format(
                'GRANT SELECT ON TABLE %I.detections TO souverain_app', tenant.schema_name
            );
        END IF;
    END LOOP;
END
$$;
