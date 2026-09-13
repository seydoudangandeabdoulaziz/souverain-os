-- Brique 1 V2 — Gouvernance des tenants
-- ============================================================
-- Migration portée par la Brique 1 (propriétaire historique de
-- shared.* depuis shared.tenants_registry, migration 0001).
--
-- Cette table est TRANSVERSE : elle couvre à la fois la gouvernance
-- des tenants (Brique 1, cette migration) et celle des utilisateurs
-- (Brique 2, extension — voir sa propre migration
-- 0002_gouvernance_web_role.sql, qui ajoute UNIQUEMENT ses propres
-- GRANT sur cette table déjà créée ici, ne la recrée jamais).
--
-- Distinction stricte {tenant}.audit_log (Brique 8) vs celle-ci :
-- {tenant}.audit_log = décisions métier sur les alertes (fermeture,
-- motif), par tenant. shared.gouvernance_audit_log = opérations
-- d'administration (créer/activer/désactiver un tenant, gérer un
-- compte utilisateur), transverses par nature — un tenant n'existe
-- pas encore au moment où on le crée, donc son audit ne peut pas
-- vivre dans son propre schéma.
-- ============================================================

CREATE TABLE IF NOT EXISTS shared.gouvernance_audit_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domaine         TEXT NOT NULL CHECK (domaine IN ('tenant', 'utilisateur')),
    action          TEXT NOT NULL CHECK (action IN (
        'tenant_creation', 'tenant_activation', 'tenant_desactivation',
        'utilisateur_creation', 'utilisateur_changement_role',
        'utilisateur_desactivation', 'utilisateur_reactivation'
    )),
    cible_id        UUID NOT NULL,
    acteur_type     TEXT NOT NULL CHECK (acteur_type IN ('cli_non_authentifie', 'utilisateur_authentifie')),
    acteur_declare  TEXT,
    acteur_user_id  UUID,
    details         JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Contrainte STRUCTURELLE, pas une convention : rend impossible de
    -- confondre une déclaration CLI non authentifiée avec une identité
    -- web authentifiée — exactement un seul des deux champs est rempli,
    -- selon acteur_type, vérifié par PostgreSQL à chaque insertion.
    CONSTRAINT acteur_coherent CHECK (
        (acteur_type = 'cli_non_authentifie'     AND acteur_declare IS NOT NULL AND acteur_user_id IS NULL)
        OR
        (acteur_type = 'utilisateur_authentifie' AND acteur_user_id IS NOT NULL AND acteur_declare IS NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_gouvernance_audit_cible
    ON shared.gouvernance_audit_log (domaine, cible_id, created_at DESC);

-- ============================================================
-- Rôle PostgreSQL dédié au CLI de gouvernance de tenants.
--
-- Distinct de souverain_admin (propriétaire de toutes les tables, qui
-- contournerait tout GRANT/REVOKE sur ses propres objets) ET distinct
-- du futur rôle web de la Brique 2 (souverain_gouvernance_web) — les
-- deux ont des besoins de privilèges différents par nature :
-- celui-ci a besoin de CREATE (provision_tenant_schema() exécute un
-- vrai CREATE SCHEMA), ce que le rôle web n'aura jamais besoin de
-- faire. Sa valeur de sécurité diffère aussi de celle de la Brique 8 :
-- l'opérateur CLI a de toute façon un accès serveur complet (il
-- pourrait passer par psql en admin) — ce rôle protège contre un bug
-- dans le CODE PYTHON de cette brique, pas contre une menace externe.
--
-- ⚠️ GRANT CREATE ON DATABASE souverain_os : si POSTGRES_DB diffère de
-- 'souverain_os' dans un environnement donné, cette ligne doit être
-- adaptée manuellement avant exécution.
-- ============================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'souverain_gouvernance_cli') THEN
        -- Mot de passe par défaut 'change_me_gouvernance_cli', même
        -- convention que NEO4J_PASSWORD / AUDIT_DB_PASSWORD : DOIT être
        -- changé avant tout déploiement réel, cohérent avec la variable
        -- .env correspondante (GOUVERNANCE_CLI_DB_PASSWORD).
        CREATE ROLE souverain_gouvernance_cli LOGIN PASSWORD 'change_me_gouvernance_cli';
    END IF;
END
$$;

GRANT CREATE ON DATABASE souverain_os TO souverain_gouvernance_cli;
GRANT USAGE ON SCHEMA shared TO souverain_gouvernance_cli;
GRANT INSERT, UPDATE, SELECT ON shared.tenants_registry TO souverain_gouvernance_cli;

-- INSERT + SELECT UNIQUEMENT sur l'audit — aucun GRANT UPDATE/DELETE,
-- c'est cette absence, précisément, qui constitue la garantie
-- d'immuabilité (même principe que souverain_brique8_audit, Brique 8).
GRANT INSERT, SELECT ON shared.gouvernance_audit_log TO souverain_gouvernance_cli;
