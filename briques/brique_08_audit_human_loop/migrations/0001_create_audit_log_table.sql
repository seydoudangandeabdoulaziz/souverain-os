-- Brique 8 — Audit trail + Human-in-the-loop
-- Migration portée par la Brique 8 (ne modifie AUCUN fichier des Briques
-- précédentes — même convention que les migrations des Briques 3/4/5).
--
-- Deux responsabilités dans ce fichier :
-- 1. Créer le rôle PostgreSQL dédié souverain_brique8_audit — protection
--    par PRIVILÈGE RÉEL, pas seulement une discipline applicative
--    (décision validée à l'analyse, "défense en profondeur").
-- 2. Créer {tenant}.audit_log pour chaque tenant déjà enregistré, et
--    accorder à ce rôle EXACTEMENT les privilèges dont il a besoin,
--    ni plus ni moins.
--
-- ⚠️ Le rôle souverain_admin (propriétaire de toutes les tables) EST
-- superutilisateur de ses propres objets et contournerait n'importe
-- quel GRANT/REVOKE sur les tables qu'il possède. C'est pour cette
-- raison précise qu'un rôle SÉPARÉ, non-propriétaire, est nécessaire :
-- la restriction n'a de sens que si l'application se connecte à
-- audit_log avec CE rôle, jamais avec souverain_admin (voir
-- connection.py de cette brique).
--
-- Pourquoi ce rôle a aussi besoin d'UPDATE sur {tenant}.alertes :
-- la fermeture d'une alerte et l'écriture de son entrée d'audit
-- doivent être ATOMIQUES (une seule transaction, validée à l'analyse)
-- — donc sur UNE SEULE connexion, donc SOUS UN SEUL rôle. Ce rôle a
-- exactement les deux privilèges nécessaires à cette transaction :
-- UPDATE (+ SELECT, requis par PostgreSQL pour évaluer le WHERE) sur
-- alertes, et INSERT + SELECT (jamais UPDATE ni DELETE) sur
-- audit_log. C'est cette dernière absence, précisément, qui constitue
-- la garantie d'immuabilité.

-- --- 1. Rôle dédié, créé une seule fois (pas par tenant : les rôles
--        PostgreSQL sont globaux au cluster, pas au schéma). ---
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'souverain_brique8_audit') THEN
        -- Mot de passe par défaut 'change_me_audit', même convention
        -- que NEO4J_PASSWORD (docker-compose.yml) : DOIT être changé
        -- via ALTER ROLE avant tout déploiement réel, et doit alors
        -- correspondre exactement à AUDIT_DB_PASSWORD dans le .env
        -- réel (voir .env.example, section Brique 8).
        CREATE ROLE souverain_brique8_audit LOGIN PASSWORD 'change_me_audit';
    END IF;
END
$$;

-- Lecture de l'email de l'utilisateur qui a fermé une alerte (affichage
-- de l'historique d'audit, lecture.py) : un seul GRANT, shared n'est
-- pas bouclé par tenant.
GRANT USAGE ON SCHEMA shared TO souverain_brique8_audit;
GRANT SELECT ON shared.users TO souverain_brique8_audit;

-- --- 2. Table + privilèges, par tenant déjà enregistré. ---
DO $$
DECLARE
    tenant_schema TEXT;
BEGIN
    FOR tenant_schema IN
        SELECT schema_name FROM shared.tenants_registry
    LOOP
        -- {tenant}.audit_log : une ligne par action humaine de
        -- fermeture d'alerte. Pas de FK déclarée vers {tenant}.alertes
        -- ni vers shared.users — même convention que {tenant}.alertes
        -- elle-même (tenant_id stocké en UUID simple, jamais de FK
        -- inter-schéma dans ce projet).
        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS %I.audit_log (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                alerte_id UUID NOT NULL,
                tenant_id UUID NOT NULL,
                user_id UUID NOT NULL,
                motif TEXT NOT NULL
                    CHECK (motif IN (
                        ''faux_positif'', ''confirme'', ''en_cours_investigation''
                    )),
                commentaire TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );',
            tenant_schema
        );

        EXECUTE format(
            'CREATE INDEX IF NOT EXISTS idx_%s_audit_log_alerte
             ON %I.audit_log (alerte_id, created_at DESC);',
            tenant_schema, tenant_schema
        );

        -- Accès du rôle restreint à ce schéma tenant.
        EXECUTE format('GRANT USAGE ON SCHEMA %I TO souverain_brique8_audit;', tenant_schema);

        -- alertes : SELECT (requis par le WHERE du UPDATE) + UPDATE
        -- uniquement — jamais INSERT ni DELETE, la création d'alertes
        -- reste le monopole de la Brique 5.
        EXECUTE format(
            'GRANT SELECT, UPDATE ON %I.alertes TO souverain_brique8_audit;', tenant_schema
        );

        -- audit_log : INSERT + SELECT UNIQUEMENT. Aucun GRANT UPDATE,
        -- aucun GRANT DELETE — c'est la protection recherchée.
        EXECUTE format(
            'GRANT INSERT, SELECT ON %I.audit_log TO souverain_brique8_audit;', tenant_schema
        );
    END LOOP;
END
$$;

-- Idempotent : DO $$ ... IF NOT EXISTS / CREATE ... IF NOT EXISTS / GRANT
-- (rejouable sans erreur) ⇒ rejouable sans erreur.
-- ⚠️ Comme les migrations des Briques 3/4/5, celle-ci ne couvre que les
-- tenants déjà enregistrés au moment de son exécution. persistence.py
-- s'assure de la présence de la table (et des GRANT) avant chaque
-- écriture, via le pool ADMIN (Brique 1) — le rôle restreint lui-même
-- n'a volontairement aucun privilège DDL (CREATE/GRANT), donc ne peut
-- pas réparer sa propre table.
