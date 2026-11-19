-- Migration 0009 (Brique 1) : autorise le but de rôle tenant 'pipeline'.
--
-- Extension STRICTEMENT ADDITIVE du modèle P0 (0008) : le CHECK de
-- shared.tenant_login_map.purpose passe de ('data','audit') à
-- ('data','audit','pipeline'). Aucun rôle, aucun privilège, aucune ligne
-- existante ne sont modifiés ; les rôles `data` et `audit` restent inchangés.
--
-- Cette migration ne crée AUCUN rôle `pipeline`. Ils sont créés (NOLOGIN),
-- puis dotés de leurs droits minimaux, par le provisionnement explicite
-- (tenant_roles.provision_tenant_role(..., 'pipeline')) et activés par
-- scripts/provision_tenant_roles.py --with-pipeline.
--
-- Idempotente. Prérequis : 0008 appliquée. Non appliquée automatiquement.

DO $$
DECLARE
    c RECORD;
BEGIN
    IF to_regclass('shared.tenant_login_map') IS NULL THEN
        RAISE EXCEPTION 'shared.tenant_login_map absente : appliquer 0008 avant 0009';
    END IF;

    FOR c IN
        SELECT conname
        FROM pg_constraint
        WHERE conrelid = 'shared.tenant_login_map'::regclass
          AND contype = 'c'
          AND pg_get_constraintdef(oid) LIKE '%purpose%'
    LOOP
        EXECUTE format('ALTER TABLE shared.tenant_login_map DROP CONSTRAINT %I', c.conname);
    END LOOP;

    ALTER TABLE shared.tenant_login_map
        ADD CONSTRAINT tenant_login_map_purpose_check
        CHECK (purpose IN ('data', 'audit', 'pipeline'));
END
$$;
