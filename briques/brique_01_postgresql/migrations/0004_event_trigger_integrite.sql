-- Brique 1 — Étape 2 : Event Trigger d'attachement automatique
-- ============================================================
-- Portée : réagit à TOUT CREATE TABLE du cluster (contrainte du
-- moteur PostgreSQL — un event trigger n'existe qu'au niveau base,
-- jamais au niveau schéma). Filtre strictement en interne : (a) le
-- schéma doit être un tenant enregistré dans shared.tenants_registry,
-- (b) le nom de la table doit être exactement 'alertes' ou
-- 'detections'. Toute autre table (y compris integrite_donnees_log
-- elle-même, créée en conséquence) ne déclenche rien — c'est ce
-- filtre sur le nom de table qui empêche toute récursion, pas un
-- mécanisme séparé.
--
-- Ne modifie AUCUN fichier des Briques 4/5/8 — préserve leur
-- responsabilité sur leurs propres tables. Brique 1 ne connaît que
-- deux noms de table et un nom de colonne de clé primaire chacune
-- (voir migration 0003), jamais leur structure complète.
--
-- Défensif par construction : requiert un superutilisateur pour être
-- créé (vérifié avant cette migration : souverain_admin l'est bien).
-- Toute erreur interne au handler est journalisée (RAISE WARNING) et
-- JAMAIS propagée — un bug dans ce mécanisme ne doit jamais faire
-- échouer le CREATE TABLE d'origine de Brique 4/5.
-- ============================================================

CREATE OR REPLACE FUNCTION shared.fn_event_trigger_integrite()
RETURNS event_trigger
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
LANGUAGE plpgsql AS $$
DECLARE
    r RECORD;
    v_schema TEXT;
    v_table TEXT;
    v_est_tenant BOOLEAN;
BEGIN
    FOR r IN SELECT * FROM pg_event_trigger_ddl_commands()
    LOOP
        BEGIN
            IF r.command_tag != 'CREATE TABLE' THEN
                CONTINUE;
            END IF;

            -- object_identity est déjà pleinement qualifié
            -- ("schema.table") pour un CREATE TABLE — découpage sûr.
            v_schema := split_part(r.object_identity, '.', 1);
            v_table := split_part(r.object_identity, '.', 2);

            IF v_table NOT IN ('alertes', 'detections') THEN
                CONTINUE;
            END IF;

            SELECT EXISTS (
                SELECT 1 FROM shared.tenants_registry WHERE schema_name = v_schema
            ) INTO v_est_tenant;

            IF NOT v_est_tenant THEN
                CONTINUE;
            END IF;

            PERFORM shared.assurer_protection_integrite(v_schema, v_table);

        EXCEPTION WHEN OTHERS THEN
            -- Ne JAMAIS laisser un échec ici faire échouer le
            -- CREATE TABLE d'origine (Brique 4/5) — voir conception.
            RAISE WARNING
                'fn_event_trigger_integrite: échec non bloquant pour % — %',
                r.object_identity, SQLERRM;
        END;
    END LOOP;
END;
$$;

-- Nécessite un superutilisateur pour être créé (vérifié : souverain_admin
-- l'est). WHEN TAG s'évalue AVANT l'appel de la fonction — tout DDL
-- qui n'est pas un CREATE TABLE, n'importe où dans le cluster, ne
-- déclenche même pas l'exécution du handler.
DROP EVENT TRIGGER IF EXISTS trg_event_integrite_donnees;
CREATE EVENT TRIGGER trg_event_integrite_donnees
    ON ddl_command_end
    WHEN TAG IN ('CREATE TABLE')
    EXECUTE FUNCTION shared.fn_event_trigger_integrite();

-- ============================================================
-- Rattrapage explicite pour les tenants déjà existants au moment de
-- cette migration : l'event trigger ne réagit qu'aux FUTURS
-- CREATE TABLE, jamais rétroactivement. Pour un tenant où
-- alertes/detections n'existent pas encore (aucun cycle Brique 4/5
-- exécuté), rien à faire ici — l'event trigger protégera
-- automatiquement dès leur première création réelle.
-- ============================================================
DO $$
DECLARE
    r RECORD;
    v_existe BOOLEAN;
BEGIN
    FOR r IN SELECT schema_name FROM shared.tenants_registry
    LOOP
        SELECT to_regclass(format('%I.alertes', r.schema_name)) IS NOT NULL
        INTO v_existe;
        IF v_existe THEN
            PERFORM shared.assurer_protection_integrite(r.schema_name, 'alertes');
        END IF;

        SELECT to_regclass(format('%I.detections', r.schema_name)) IS NOT NULL
        INTO v_existe;
        IF v_existe THEN
            PERFORM shared.assurer_protection_integrite(r.schema_name, 'detections');
        END IF;
    END LOOP;
END;
$$;
