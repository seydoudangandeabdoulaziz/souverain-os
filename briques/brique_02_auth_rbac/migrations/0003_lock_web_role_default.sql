-- Sécurité additive : neutralise le LOGIN et le secret de démonstration
-- du rôle de gouvernance web créé historiquement par la migration 0002.
-- Les privilèges sont conservés ; l'opérateur active le rôle après avoir
-- défini un secret propre à l'environnement.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'souverain_gouvernance_web'
    ) THEN
        ALTER ROLE souverain_gouvernance_web
            NOLOGIN PASSWORD NULL NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
    END IF;
END
$$;
