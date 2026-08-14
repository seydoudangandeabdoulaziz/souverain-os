-- ============================================================
-- SOUVERAIN-OS — Brique 2 : shared.users
-- ============================================================
-- Prérequis : la migration 0001_init_shared_schema.sql de la
-- Brique 1 (schema "shared" + table "tenants_registry") doit déjà
-- avoir été appliquée sur cette base.
--
-- Les comptes utilisateurs sont de la GOUVERNANCE (comme le registre
-- des tenants), pas de la donnée métier transactionnelle — d'où leur
-- emplacement dans le schéma partagé "shared", et non dans un schéma
-- par tenant.
-- ============================================================

CREATE TABLE IF NOT EXISTS shared.users (
    user_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- souverain_id est VOLONTAIREMENT distinct de user_id : cette
    -- colonne pourra évoluer (signature PQC, format interopérable
    -- inter-États) en phase transverse, sans jamais devoir changer la
    -- clé primaire ni casser les références existantes.
    souverain_id          UUID NOT NULL UNIQUE,

    tenant_id             UUID NOT NULL REFERENCES shared.tenants_registry (tenant_id)
                               ON DELETE RESTRICT,

    email                  TEXT NOT NULL UNIQUE,
    password_hash          TEXT NOT NULL,

    role                    TEXT NOT NULL
        CHECK (role IN ('admin', 'analyst', 'auditor')),

    data_classification     TEXT NOT NULL DEFAULT 'confidential'
        CHECK (data_classification IN ('public', 'internal', 'confidential', 'secret')),

    -- Incrémenté à chaque changement de mot de passe ou désactivation.
    -- Permet une révocation immédiate des jetons JWT déjà émis, sans
    -- attendre leur expiration naturelle (voir jwt_tokens.py).
    token_version           INTEGER NOT NULL DEFAULT 1,

    -- Désactivation logique uniquement — jamais de suppression
    -- physique d'un compte (traçabilité, cohérent avec l'esprit audit
    -- du projet).
    is_active                BOOLEAN NOT NULL DEFAULT true,

    created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at             TIMESTAMPTZ
);

COMMENT ON TABLE shared.users IS
    'Comptes utilisateurs SOUVERAIN-OS. Gouvernance centrale (comme tenants_registry) — pas de donnée métier.';

COMMENT ON COLUMN shared.users.souverain_id IS
    'Fondation SOUVERAIN-ID : identifiant déterministe (UUID5). PAS ENCORE le passeport cryptographique PQC complet (phase transverse).';

COMMENT ON COLUMN shared.users.token_version IS
    'Incrémenté pour révoquer immédiatement tous les jetons JWT déjà émis pour cet utilisateur.';

CREATE INDEX IF NOT EXISTS idx_users_tenant_id
    ON shared.users (tenant_id);

CREATE INDEX IF NOT EXISTS idx_users_is_active
    ON shared.users (is_active)
    WHERE is_active = true;
