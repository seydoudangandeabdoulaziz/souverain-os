-- ============================================================
-- Brique 3 — Bootstrap MVP temporaire du tenant Niger (tenant_ne)
-- ============================================================
-- ⚠️ CE SCRIPT EST PROVISOIRE. Il ne remplace PAS create_tenant()
-- (Brique 8, gouvernance complète : audit, RBAC, validation).
--
-- Pourquoi ce script existe : au moment de la Brique 3, aucun
-- mécanisme ne permet encore d'enregistrer un tenant dans
-- shared.tenants_registry (provision_tenant_schema() de la Brique 1
-- crée uniquement le schéma physique, pas la ligne de registre).
-- Sans ligne de registre, la Brique 3 ne peut pas déterminer
-- tenant_id/country_code/data_classification pour ses inserts
-- (colonnes NOT NULL de {tenant}.transactions).
--
-- À FAIRE en Brique 8 : ce script devra être remplacé par un appel
-- à create_tenant() réel, avec gouvernance, audit et validation —
-- ne pas reconduire ce pattern SQL brut au-delà du MVP.
--
-- Idempotent : ON CONFLICT DO NOTHING, rejouable sans erreur.
-- ============================================================

INSERT INTO shared.tenants_registry
    (tenant_code, country_code, schema_name, data_classification, is_active)
VALUES
    ('NE', 'NE', 'tenant_ne', 'confidential', true)
ON CONFLICT (schema_name) DO NOTHING;

-- Provisionner ensuite le schéma physique (Brique 1) :
--   uv run python -c "
--     import asyncio
--     from brique_01_postgresql.connection import create_pool, close_pool
--     from brique_01_postgresql.tenant_provisioning import provision_tenant_schema
--     async def main():
--         pool = await create_pool()
--         async with pool.acquire() as conn:
--             await provision_tenant_schema(conn, 'tenant_ne')
--         await close_pool()
--     asyncio.run(main())
--   "
-- (voir README.md de cette brique pour la commande complète)
