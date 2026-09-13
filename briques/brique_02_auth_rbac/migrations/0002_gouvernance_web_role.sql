-- Brique 2 V2 — Gouvernance des utilisateurs (routes web)
-- ============================================================
-- Ne recrée JAMAIS shared.gouvernance_audit_log (déjà créée par la
-- migration 0002 de la Brique 1) — ajoute uniquement le rôle dédié
-- aux routes web de gestion des comptes, et ses propres GRANT.
-- ============================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'souverain_gouvernance_web') THEN
        -- Mot de passe par défaut 'change_me_gouvernance_web', même
        -- convention que les autres rôles dédiés du projet — DOIT être
        -- changé avant tout déploiement réel.
        CREATE ROLE souverain_gouvernance_web LOGIN PASSWORD 'change_me_gouvernance_web';
    END IF;
END
$$;

GRANT USAGE ON SCHEMA shared TO souverain_gouvernance_web;

-- Nécessaire : creer_utilisateur() (persistence.py) lit tenant_code
-- depuis shared.tenants_registry pour générer le SOUVERAIN-ID — oublié
-- dans la première version de cette migration, révélé par un vrai
-- test d'intégration sur la machine réelle du fondateur
-- (InsufficientPrivilegeError), pas détectable en environnement de
-- génération sans base réelle.
GRANT SELECT ON shared.tenants_registry TO souverain_gouvernance_web;

-- DML uniquement sur shared.users — AUCUN privilège DDL (contrairement
-- au rôle CLI de la Brique 1, ce rôle n'a jamais besoin de CREATE
-- SCHEMA/TABLE : la gestion des comptes ne crée jamais de tenant).
GRANT INSERT, SELECT, UPDATE ON shared.users TO souverain_gouvernance_web;

-- INSERT + SELECT UNIQUEMENT sur l'audit transverse — jamais
-- UPDATE/DELETE, même principe que le rôle CLI de la Brique 1 et que
-- souverain_brique8_audit (Brique 8).
GRANT INSERT, SELECT ON shared.gouvernance_audit_log TO souverain_gouvernance_web;
