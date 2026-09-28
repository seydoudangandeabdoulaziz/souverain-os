-- Brique 1 — Étape 4b (Observabilité, rôle monitoring PostgreSQL)
-- ============================================================
-- Rôle dédié pour postgres-exporter (Prometheus). Privilèges
-- strictement en lecture via le rôle prédéfini PostgreSQL pg_monitor
-- (10+), disponible nativement sur cette image — accès aux vues
-- pg_stat_* nécessaires, SANS accès aux données métier d'aucun
-- tenant.
--
-- Contrairement au rôle d'audit de la Brique 8
-- (0001_create_audit_log_table.sql), aucune boucle par tenant n'est
-- nécessaire ici : pg_monitor est un privilège cluster-level
-- (pg_stat_activity, pg_stat_database, etc.), pas accordé schéma par
-- schéma.
-- ============================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'souverain_monitoring'
    ) THEN
        -- Mot de passe par défaut 'change_me_monitoring', même
        -- convention que les 3 rôles dédiés précédents (audit,
        -- gouvernance_cli, gouvernance_web) : DOIT être changé via
        -- ALTER ROLE avant tout déploiement réel, et doit alors
        -- correspondre exactement à MONITORING_DB_PASSWORD dans le
        -- .env réel (jamais lu automatiquement par ce fichier SQL —
        -- aucun mécanisme de templating n'existe dans ce projet,
        -- comme pour les 3 précédents).
        CREATE ROLE souverain_monitoring LOGIN PASSWORD 'change_me_monitoring';
    END IF;
END
$$;

-- Idempotent par nature : regranter un rôle déjà accordé est un
-- no-op en PostgreSQL, pas une erreur.
GRANT pg_monitor TO souverain_monitoring;

-- Aucun GRANT supplémentaire. pg_monitor suffit à lui seul pour les
-- métriques standard de postgres-exporter (connexions, taille des
-- bases, bgwriter, réplication...). Aucun accès à shared.* ni à
-- {tenant}.* — vérifié par test_monitoring_role.py.
