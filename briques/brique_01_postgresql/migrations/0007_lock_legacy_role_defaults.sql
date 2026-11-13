-- Durcissement additif des rôles historiques créés avec LOGIN et des
-- mots de passe de démonstration dans les migrations 0002/0005.
-- À exécuter après les migrations B1, B2 et B8, avant le démarrage des
-- composants. Les comptes restent présents et leurs privilèges restent
-- intacts, mais aucune connexion n'est possible avant activation et
-- définition manuelle d'un secret propre à l'environnement.

DO $$
DECLARE
    role_name TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY[
        'souverain_app',
        'souverain_gouvernance_cli',
        'souverain_monitoring'
    ] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
            EXECUTE format(
                'ALTER ROLE %I NOLOGIN PASSWORD NULL NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS',
                role_name
            );
        END IF;
    END LOOP;
END
$$;
