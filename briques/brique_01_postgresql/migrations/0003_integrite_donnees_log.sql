-- Brique 1 — Étape 2 : Intégrité des données métier
-- ============================================================
-- Fonction transverse réutilisable : pour UN schéma tenant et UNE
-- table cible ('alertes' ou 'detections') donnés, assure la présence
-- de (1) la table de journalisation d'intégrité, (2) la fonction de
-- trigger de ligne PROPRE à ce schéma, (3) le trigger de ligne
-- lui-même. Idempotente — rejouable sans erreur (CREATE ... IF NOT
-- EXISTS / CREATE OR REPLACE / DROP ... IF EXISTS puis CREATE).
--
-- Appelée par deux chemins, jamais par un troisième :
--   a) shared.fn_event_trigger_integrite() (migration 0004), pour
--      tout futur CREATE TABLE alertes/detections d'un tenant.
--   b) Le rattrapage explicite ci-dessous (migration 0004), pour les
--      tenants déjà existants au moment de cette migration.
--
-- Ne duplique AUCUNE colonne de alertes/detections : to_jsonb(OLD)
-- et to_jsonb(NEW) capturent la ligne entière génériquement, quelle
-- que soit sa structure — seule la colonne de clé primaire doit être
-- connue (passée en paramètre au trigger), pour permettre de
-- retrouver une ligne précise dans les logs a posteriori.
--
-- Détection, jamais blocage (décision verrouillée à l'analyse) :
-- AFTER UPDATE OR DELETE uniquement — un INSERT normal (fonctionnement
-- courant de ces tables) n'est jamais journalisé ici.
--
-- Limite reconnue, non résolue par cette étape : souverain_admin
-- (propriétaire de toutes les tables) pourrait désactiver ou
-- supprimer ces triggers. Cette protection détecte une modification
-- directe non accompagnée d'une désactivation délibérée du mécanisme
-- lui-même — pas une garantie absolue contre un compte admin
-- compromis, documenté ainsi dès la conception.
-- ============================================================

CREATE OR REPLACE FUNCTION shared.assurer_protection_integrite(
    p_schema TEXT,
    p_table TEXT
)
RETURNS VOID
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
LANGUAGE plpgsql AS $$
DECLARE
    v_colonne_pk TEXT;
BEGIN
    IF p_table = 'alertes' THEN
        v_colonne_pk := 'alerte_id';
    ELSIF p_table = 'detections' THEN
        v_colonne_pk := 'detection_id';
    ELSE
        -- Table non concernée par cette protection — ne rien faire,
        -- jamais lever d'erreur (appelée depuis un contexte défensif
        -- par construction, voir migration 0004).
        RETURN;
    END IF;

    -- 1. Table de journalisation d'intégrité, propre à ce schéma.
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I.integrite_donnees_log (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            table_source     TEXT NOT NULL,
            ligne_id         TEXT NOT NULL,
            operation        TEXT NOT NULL
                CHECK (operation IN (''UPDATE'', ''DELETE'')),
            donnees_avant    JSONB NOT NULL,
            donnees_apres    JSONB,
            role_postgresql  TEXT NOT NULL,
            adresse_ip       INET,
            detecte_le       TIMESTAMPTZ NOT NULL DEFAULT now()
        )',
        p_schema
    );

    EXECUTE format(
        'CREATE INDEX IF NOT EXISTS idx_%s_integrite_donnees_cible
         ON %I.integrite_donnees_log (table_source, ligne_id, detecte_le DESC)',
        p_schema, p_schema
    );

    -- 2. Fonction de trigger de ligne — JAMAIS partagée entre tenants,
    -- une instance par schéma, même principe d'isolation stricte que
    -- garde_isolation.py (Brique 6, point de passage unique par
    -- tenant). SECURITY DEFINER : le trigger doit pouvoir écrire ici
    -- quel que soit le rôle qui a déclenché l'UPDATE/DELETE d'origine
    -- (souverain_admin ou souverain_brique8_audit). session_user
    -- (pas current_user, qui refléterait le PROPRIÉTAIRE de la
    -- fonction sous SECURITY DEFINER, pas l'appelant réel) capture le
    -- rôle qui a réellement déclenché la modification.
    EXECUTE format(
        'CREATE OR REPLACE FUNCTION %I.fn_integrite_donnees_log()
         RETURNS TRIGGER
         SECURITY DEFINER
         SET search_path = pg_catalog, pg_temp
         LANGUAGE plpgsql AS $func$
         DECLARE
             v_ligne_id TEXT;
         BEGIN
             v_ligne_id := (to_jsonb(OLD) ->> TG_ARGV[0]);
             INSERT INTO %I.integrite_donnees_log
                 (table_source, ligne_id, operation, donnees_avant,
                  donnees_apres, role_postgresql, adresse_ip)
             VALUES (
                 TG_TABLE_NAME,
                 v_ligne_id,
                 TG_OP,
                 to_jsonb(OLD),
                 CASE WHEN TG_OP = ''UPDATE'' THEN to_jsonb(NEW) ELSE NULL END,
                 session_user,
                 inet_client_addr()
             );
             RETURN NULL;
         END;
         $func$',
        p_schema, p_schema
    );

    -- 3. Trigger de ligne, attaché à la table cible précise.
    -- DROP IF EXISTS puis CREATE : équivalent idempotent de
    -- "CREATE TRIGGER IF NOT EXISTS", qui n'existe pas nativement en
    -- PostgreSQL.
    EXECUTE format(
        'DROP TRIGGER IF EXISTS trg_integrite_%s ON %I.%I',
        p_table, p_schema, p_table
    );
    EXECUTE format(
        'CREATE TRIGGER trg_integrite_%s
         AFTER UPDATE OR DELETE ON %I.%I
         FOR EACH ROW EXECUTE FUNCTION %I.fn_integrite_donnees_log(%L)',
        p_table, p_schema, p_table, p_schema, v_colonne_pk
    );
END;
$$;
