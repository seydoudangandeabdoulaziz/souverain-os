-- Brique 4 — Moteur de détection Hybrid-Stream
-- Migration portée par la Brique 4 (ne modifie AUCUN fichier des Briques 1/3).
--
-- Crée {tenant}.detections pour chaque tenant déjà enregistré dans
-- shared.tenants_registry. Même mécanique que is_synthetic en Brique 3 :
-- une boucle sur les tenants existants au moment de l'exécution, complétée
-- par une fonction d'auto-réparation côté application (persistence.py)
-- pour couvrir les tenants provisionnés après coup (tests, futurs tenants).

DO $$
DECLARE
    tenant_schema TEXT;
BEGIN
    FOR tenant_schema IN
        SELECT schema_name FROM shared.tenants_registry
    LOOP
        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS %I.detections (
                detection_id UUID PRIMARY KEY,
                tenant_id UUID NOT NULL,
                country_code TEXT NOT NULL,
                data_classification TEXT NOT NULL,
                pattern_type TEXT NOT NULL,
                transaction_ids UUID[] NOT NULL,
                compte_pivot TEXT,
                fenetre_debut TIMESTAMPTZ NOT NULL,
                fenetre_fin TIMESTAMPTZ NOT NULL,
                detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                details JSONB
            );',
            tenant_schema
        );
        EXECUTE format(
            'CREATE INDEX IF NOT EXISTS idx_detections_pattern_type
             ON %I.detections (pattern_type, detected_at);',
            tenant_schema
        );
    END LOOP;
END $$;

-- Idempotent : CREATE TABLE/INDEX IF NOT EXISTS ⇒ rejouable sans erreur.
-- ⚠️ Comme pour 0001_add_is_synthetic.sql (Brique 3), cette migration ne
-- couvre que les tenants déjà enregistrés au moment où elle s'exécute.
-- persistence.py s'assure de la présence de la table avant chaque écriture.
