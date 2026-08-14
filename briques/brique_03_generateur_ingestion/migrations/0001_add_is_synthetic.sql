-- Brique 3 — Générateur + ingestion de transactions synthétiques
-- Migration portée par la Brique 3 (ne modifie AUCUN fichier de la Brique 1).
--
-- Rôle : ajouter une colonne is_synthetic sur la table transactions de chaque
-- tenant existant, pour pouvoir distinguer/purger les données de test des
-- données réelles, sans jamais mélanger les deux silencieusement.
--
-- HYPOTHÈSE À VÉRIFIER : ce script suppose que shared.tenants_registry
-- contient une colonne nommée "schema_name" identifiant le schéma PostgreSQL
-- de chaque tenant (posé en Brique 1). Si le nom réel de cette colonne est
-- différent dans ton schéma, adapte la ligne SELECT ci-dessous avant
-- d'exécuter cette migration.

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
