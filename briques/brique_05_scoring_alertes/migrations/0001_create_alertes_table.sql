-- Brique 5 — Scoring + Alertes
-- Migration portée par la Brique 5 (ne modifie AUCUN fichier des Briques 1/3/4).
--
-- Crée {tenant}.alertes pour chaque tenant déjà enregistré dans
-- shared.tenants_registry. Même mécanique que is_synthetic (Brique 3)
-- et detections (Brique 4) : une boucle sur les tenants existants au
-- moment de l'exécution, complétée par une fonction d'auto-réparation
-- côté application (persistence.py) pour couvrir les tenants
-- provisionnés après coup (tests, futurs tenants).
--
-- Pas de table {tenant}.detections_traitees : une première version
-- l'incluait comme table de suivi anti-relecture, mais elle cassait le
-- score cumulatif sur la fenêtre glissante (une détection ancienne
-- "déjà traitée" restait exclue même si toujours dans la fenêtre de
-- 7 jours). lecture.py relit désormais l'intégralité de la fenêtre à
-- chaque cycle ; l'index unique partiel ci-dessous (compte_pivot,
-- WHERE statut='ouverte') est la seule garantie anti-doublon, via
-- l'UPSERT de persistence.py.

DO $$
DECLARE
    tenant_schema TEXT;
BEGIN
    FOR tenant_schema IN
        SELECT schema_name FROM shared.tenants_registry
    LOOP
        -- {tenant}.alertes : une ligne par épisode d'alerte sur un
        -- compte_pivot. L'index unique partiel garantit, au niveau
        -- base, qu'il ne peut exister qu'une seule alerte 'ouverte'
        -- par compte_pivot — pas seulement par convention applicative.
        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS %I.alertes (
                alerte_id UUID PRIMARY KEY,
                tenant_id UUID NOT NULL,
                country_code TEXT NOT NULL,
                data_classification TEXT NOT NULL,
                compte_pivot TEXT NOT NULL,
                score INTEGER NOT NULL,
                statut TEXT NOT NULL DEFAULT ''ouverte''
                    CHECK (statut IN (''ouverte'', ''fermee'')),
                pattern_types_impliques TEXT[] NOT NULL,
                detection_ids UUID[] NOT NULL,
                fenetre_debut TIMESTAMPTZ NOT NULL,
                fenetre_fin TIMESTAMPTZ NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                details JSONB
            );',
            tenant_schema
        );

        EXECUTE format(
            'CREATE UNIQUE INDEX IF NOT EXISTS idx_%s_alertes_ouverte_compte
             ON %I.alertes (compte_pivot)
             WHERE statut = ''ouverte'';',
            tenant_schema, tenant_schema
        );

        EXECUTE format(
            'CREATE INDEX IF NOT EXISTS idx_%s_alertes_statut
             ON %I.alertes (statut, updated_at);',
            tenant_schema, tenant_schema
        );
    END LOOP;
END $$;

-- Idempotent : CREATE TABLE/INDEX IF NOT EXISTS ⇒ rejouable sans erreur.
-- ⚠️ Comme pour les migrations des Briques 3 et 4, celle-ci ne couvre
-- que les tenants déjà enregistrés au moment où elle s'exécute.
-- persistence.py s'assure de la présence de la table avant chaque
-- écriture.
--
-- Limite MVP documentée, non implémentée maintenant : à 69 détections
-- (volume réel actuel de tenant_ne), aucun souci de performance sur la
-- lecture pleine fenêtre de {tenant}.detections. Si le volume grossit
-- significativement (Vision), un index (compte_pivot, detected_at) sur
-- {tenant}.detections pourrait être ajouté via une migration future
-- portée par la Brique 5, sans toucher aux fichiers de la Brique 4.
