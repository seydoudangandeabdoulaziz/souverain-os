-- Cloisonnement PostgreSQL P0 : identités de connexion propres aux tenants.
-- À appliquer après B1/B2/B3/B4/B5/B8 et après création des schémas
-- des tenants existants. Cette migration est le dernier DDL du lot P0.
-- Les rôles tenant sont créés NOLOGIN ; une opération de provisioning
-- séparée leur attribue un secret local avant tout démarrage applicatif.
-- Cette migration n'est pas appliquée automatiquement.

CREATE TABLE IF NOT EXISTS shared.tenant_login_map (
    role_name NAME PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES shared.tenants_registry(tenant_id) ON DELETE CASCADE,
    purpose TEXT NOT NULL CHECK (purpose IN ('data', 'audit')),
    UNIQUE (tenant_id, purpose)
);
REVOKE ALL ON shared.tenant_login_map FROM PUBLIC;

CREATE OR REPLACE FUNCTION shared.current_login_tenant_id()
RETURNS UUID
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, shared
AS $$
    SELECT m.tenant_id
    FROM shared.tenant_login_map AS m
    WHERE m.role_name = session_user::name
$$;
REVOKE ALL ON FUNCTION shared.current_login_tenant_id() FROM PUBLIC;

DO $$
DECLARE
    t RECORD;
    data_role NAME;
    audit_role NAME;
    role_to_harden NAME;
    legacy_role NAME;
    member_role NAME;
    ns RECORD;
BEGIN
    FOREACH legacy_role IN ARRAY ARRAY[
        'souverain_app',
        'souverain_brique8_audit',
        'souverain_gouvernance_web',
        'souverain_gouvernance_cli'
    ]::NAME[] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = legacy_role) THEN
            EXECUTE format('ALTER ROLE %I NOINHERIT NOBYPASSRLS', legacy_role);
        END IF;
    END LOOP;

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'souverain_brique8_audit') THEN
        ALTER ROLE souverain_brique8_audit NOLOGIN PASSWORD NULL;
    END IF;

    -- Le rôle web global reste un rôle historique mais n'a plus de
    -- privilèges de données : les routes web utiliseront les rôles tenant.
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'souverain_gouvernance_web') THEN
        ALTER ROLE souverain_gouvernance_web NOLOGIN PASSWORD NULL;
    END IF;

    -- Les seules données partagées accessibles au rôle de contrôle sont
    -- les métadonnées de registre. Les comptes passent par le rôle tenant.
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'souverain_app') THEN
        REVOKE ALL ON shared.users FROM souverain_app;
        GRANT USAGE ON SCHEMA shared TO souverain_app;
        GRANT SELECT ON shared.tenants_registry TO souverain_app;
    END IF;

    -- CLI de gouvernance : identité opérateur distincte, hors des routes
    -- tenant. Elle conserve l'accès administratif au registre partagé.
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'souverain_gouvernance_cli') THEN
        GRANT USAGE ON SCHEMA shared TO souverain_gouvernance_cli;
    END IF;

    ALTER TABLE shared.tenants_registry ENABLE ROW LEVEL SECURITY;
    ALTER TABLE shared.tenants_registry FORCE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS tenant_registry_self ON shared.tenants_registry;
    CREATE POLICY tenant_registry_self ON shared.tenants_registry
        USING (tenant_id = shared.current_login_tenant_id())
        WITH CHECK (tenant_id = shared.current_login_tenant_id());
    DROP POLICY IF EXISTS tenant_registry_control ON shared.tenants_registry;
    CREATE POLICY tenant_registry_control ON shared.tenants_registry
        TO souverain_app, souverain_gouvernance_cli
        USING (true) WITH CHECK (true);

    ALTER TABLE shared.users ENABLE ROW LEVEL SECURITY;
    ALTER TABLE shared.users FORCE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS tenant_users_self ON shared.users;
    CREATE POLICY tenant_users_self ON shared.users
        USING (tenant_id = shared.current_login_tenant_id())
        WITH CHECK (tenant_id = shared.current_login_tenant_id());

    -- L'audit de gouvernance ne porte pas tenant_id. Son identité tenant
    -- est dérivée du registre pour les événements tenant et de la ligne
    -- users pour les événements utilisateur.
    ALTER TABLE shared.gouvernance_audit_log ENABLE ROW LEVEL SECURITY;
    ALTER TABLE shared.gouvernance_audit_log FORCE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS tenant_governance_audit ON shared.gouvernance_audit_log;
    CREATE POLICY tenant_governance_audit ON shared.gouvernance_audit_log
        USING (
            (domaine = 'tenant' AND cible_id = shared.current_login_tenant_id())
            OR
            (domaine = 'utilisateur' AND EXISTS (
                SELECT 1 FROM shared.users AS u
                WHERE u.user_id = cible_id
                  AND u.tenant_id = shared.current_login_tenant_id()
            ))
        )
        WITH CHECK (
            (domaine = 'tenant' AND cible_id = shared.current_login_tenant_id())
            OR
            (domaine = 'utilisateur' AND EXISTS (
                SELECT 1 FROM shared.users AS u
                WHERE u.user_id = cible_id
                  AND u.tenant_id = shared.current_login_tenant_id()
            ))
        );
    DROP POLICY IF EXISTS governance_cli_all ON shared.gouvernance_audit_log;
    CREATE POLICY governance_cli_all ON shared.gouvernance_audit_log
        TO souverain_gouvernance_cli USING (true) WITH CHECK (true);

    FOR t IN SELECT tenant_id, schema_name FROM shared.tenants_registry LOOP
        data_role := ('sov_t_' || replace(t.tenant_id::text, '-', ''))::NAME;
        audit_role := ('sov_a_' || replace(t.tenant_id::text, '-', ''))::NAME;

        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = data_role) THEN
            EXECUTE format(
                'CREATE ROLE %I NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS',
                data_role
            );
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = audit_role) THEN
            EXECUTE format(
                'CREATE ROLE %I NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS',
                audit_role
            );
        END IF;
        EXECUTE format('ALTER ROLE %I NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS', data_role);
        EXECUTE format('ALTER ROLE %I NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS', audit_role);

        -- Un rôle déterministe peut préexister avec des ACL ou appartenances
        -- historiques. Refuser l'ownership (REVOKE ne le neutralise pas), puis
        -- retirer toute appartenance et tout privilège hors du périmètre avant
        -- de poser les ACL minimales ci-dessous.
        FOREACH role_to_harden IN ARRAY ARRAY[data_role, audit_role] LOOP
            IF EXISTS (
                SELECT 1 FROM pg_class
                WHERE relowner = (SELECT oid FROM pg_roles WHERE rolname = role_to_harden)
            ) OR EXISTS (
                SELECT 1 FROM pg_namespace
                WHERE nspowner = (SELECT oid FROM pg_roles WHERE rolname = role_to_harden)
            ) THEN
                RAISE EXCEPTION 'Le rôle tenant % possède déjà des objets; migration interrompue', role_to_harden;
            END IF;

            FOR member_role IN
                SELECT granted.rolname
                FROM pg_auth_members m
                JOIN pg_roles granted ON granted.oid = m.roleid
                JOIN pg_roles member ON member.oid = m.member
                WHERE member.rolname = role_to_harden
            LOOP
                EXECUTE format('REVOKE %I FROM %I', member_role, role_to_harden);
            END LOOP;

            FOR ns IN
                SELECT nspname FROM pg_namespace
                WHERE nspname !~ '^pg_' AND nspname <> 'information_schema'
            LOOP
                EXECUTE format('REVOKE ALL ON SCHEMA %I FROM %I', ns.nspname, role_to_harden);
                EXECUTE format('REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA %I FROM %I', ns.nspname, role_to_harden);
                EXECUTE format('REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA %I FROM %I', ns.nspname, role_to_harden);
                EXECUTE format('REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA %I FROM %I', ns.nspname, role_to_harden);
            END LOOP;
            EXECUTE format('REVOKE CREATE ON DATABASE %I FROM %I', current_database(), role_to_harden);
        END LOOP;

        INSERT INTO shared.tenant_login_map(role_name, tenant_id, purpose)
        VALUES (data_role, t.tenant_id, 'data'), (audit_role, t.tenant_id, 'audit')
        ON CONFLICT (role_name) DO UPDATE SET tenant_id = EXCLUDED.tenant_id, purpose = EXCLUDED.purpose;

        EXECUTE format('GRANT CONNECT ON DATABASE %I TO %I', current_database(), data_role);
        EXECUTE format('GRANT CONNECT ON DATABASE %I TO %I', current_database(), audit_role);

        -- Retirer les ACL globales historiques et PUBLIC avant le GRANT
        -- tenant. Les rôles métier génériques ne gardent aucun accès ici.
        EXECUTE format('REVOKE ALL ON SCHEMA %I FROM PUBLIC', t.schema_name);
        FOREACH legacy_role IN ARRAY ARRAY[
            'souverain_app', 'souverain_brique8_audit',
            'souverain_gouvernance_web', 'souverain_gouvernance_cli'
        ]::NAME[] LOOP
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = legacy_role) THEN
                EXECUTE format('REVOKE ALL ON SCHEMA %I FROM %I', t.schema_name, legacy_role);
                EXECUTE format('REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA %I FROM %I', t.schema_name, legacy_role);
                EXECUTE format('REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA %I FROM %I', t.schema_name, legacy_role);
            END IF;
        END LOOP;

        EXECUTE format('GRANT USAGE, CREATE ON SCHEMA %I TO %I', t.schema_name, data_role);
        EXECUTE format('GRANT USAGE ON SCHEMA %I TO %I', t.schema_name, audit_role);
        EXECUTE format('GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA %I TO %I', t.schema_name, data_role);
        EXECUTE format('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA %I TO %I', t.schema_name, data_role);
        IF to_regclass(format('%I.audit_log', t.schema_name)) IS NOT NULL THEN
            EXECUTE format('REVOKE ALL ON TABLE %I.audit_log FROM %I', t.schema_name, data_role);
            EXECUTE format('GRANT SELECT, INSERT ON TABLE %I.audit_log TO %I', t.schema_name, audit_role);
        END IF;
        IF to_regclass(format('%I.alertes', t.schema_name)) IS NOT NULL THEN
            EXECUTE format('GRANT SELECT, UPDATE ON TABLE %I.alertes TO %I', t.schema_name, audit_role);
        END IF;

        EXECUTE format('GRANT SELECT, INSERT, UPDATE ON shared.users TO %I', data_role);
        EXECUTE format('GRANT SELECT ON shared.tenants_registry TO %I', data_role);
        EXECUTE format('GRANT SELECT, INSERT ON shared.gouvernance_audit_log TO %I', data_role);
        EXECUTE format('GRANT SELECT ON shared.users TO %I', audit_role);
        EXECUTE format('GRANT USAGE ON SCHEMA shared TO %I', data_role);
        EXECUTE format('GRANT USAGE ON SCHEMA shared TO %I', audit_role);
        EXECUTE format('GRANT EXECUTE ON FUNCTION shared.current_login_tenant_id() TO %I', data_role);
        EXECUTE format('GRANT EXECUTE ON FUNCTION shared.current_login_tenant_id() TO %I', audit_role);
    END LOOP;
END
$$;

-- Le rôle global B8 est désormais un groupe NOLOGIN sans accès direct.
-- Les rôles sov_a_<tenant UUID> portent les ACL d'audit par schéma.
REVOKE ALL ON ALL TABLES IN SCHEMA shared FROM souverain_app, souverain_brique8_audit, souverain_gouvernance_web;
REVOKE ALL ON ALL TABLES IN SCHEMA shared FROM PUBLIC;
GRANT SELECT ON shared.tenants_registry TO souverain_app;
GRANT USAGE ON SCHEMA shared TO souverain_app;
