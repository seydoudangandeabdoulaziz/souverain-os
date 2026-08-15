-- Brique 3 — Générateur + ingestion de transactions synthétiques
-- Migration portée par la Brique 3 (ne modifie AUCUN fichier de la Brique 1).
--
-- Rôle : ajouter une colonne is_synthetic sur la table transactions de
-- chaque tenant existant, pour distinguer/purger les données de test
-- des données réelles.
--
-- Confirmé contre le vrai schéma (shared.tenants_registry.schema_name,
-- Brique 1, migrations/0001_init_shared_schema.sql) — plus une hypothèse.

DO $$
DECLARE
    tenant_schema TEXT;
BEGIN
    FOR tenant_schema IN
        SELECT schema_name FROM shared.tenants_registry
    LOOP
        EXECUTE format(
            'ALTER TABLE %I.transactions
             ADD COLUMN IF NOT EXISTS is_synthetic BOOLEAN NOT NULL DEFAULT false;',
            tenant_schema
        );
    END LOOP;
END $$;

-- Rétrocompatible : DEFAULT false ⇒ aucune transaction réelle existante n'est affectée.
-- Idempotent : ADD COLUMN IF NOT EXISTS ⇒ rejouable sans erreur.
--
-- ⚠️ ORDRE D'EXÉCUTION : cette migration doit être jouée APRÈS le
-- bootstrap MVP (scripts/bootstrap_tenant_ne.sql) ET après le
-- provisionnement physique du schéma tenant_ne (sinon la boucle
-- ci-dessus ne trouve aucun schéma à altérer — pas d'erreur, mais
-- rien n'est fait). Voir README.md, section "Ordre d'exécution".
