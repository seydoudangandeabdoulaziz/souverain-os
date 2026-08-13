# Brique 1 — Documentation du schéma

## Principe d'isolation retenu : schema-per-tenant

Conforme au document fondateur (Bloc 9) : *« chaque pays membre dispose d'un espace de données totalement isolé — PostgreSQL schema séparé »*.

```text
PostgreSQL (une seule base "souverain_os")
│
├── schema: shared                    ← métadonnées de gouvernance uniquement
│   └── tenants_registry              ← registre de tous les tenants
│
├── schema: tenant_ne                 ← Niger (MVP)
│   └── transactions                  ← hypertable TimescaleDB
│
├── schema: tenant_sn                 ← Sénégal (futur, Brique 8: create_tenant())
│   └── transactions
│
└── ... (un schéma par pays, ajouté dynamiquement plus tard)
```

## `shared.tenants_registry`

| Colonne | Type | Description |
|---|---|---|
| `tenant_id` | UUID (PK) | Identifiant unique du tenant |
| `tenant_code` | TEXT (unique) | Code court, ex. `NE` |
| `country_code` | TEXT | Code pays ISO 3166-1 alpha-2 |
| `schema_name` | TEXT (unique) | Nom du schéma physique, ex. `tenant_ne` |
| `data_classification` | TEXT | `public` / `internal` / `confidential` / `secret` |
| `is_active` | BOOLEAN | Tenant actif ou désactivé |
| `created_at` / `updated_at` | TIMESTAMPTZ | Horodatage |

## `{tenant}.transactions` (hypertable TimescaleDB)

| Colonne | Type | Description |
|---|---|---|
| `transaction_id` | UUID | Identifiant de la transaction |
| `tenant_id` | UUID | Référence au tenant (redondant avec l'isolation physique, utile pour l'audit) |
| `country_code` | TEXT | Code pays |
| `data_classification` | TEXT | Classification de la donnée |
| `amount` | NUMERIC(18,2) | Montant |
| `currency` | TEXT | Devise (défaut `XOF`) |
| `sender_account` | TEXT | Compte émetteur |
| `receiver_account` | TEXT | Compte destinataire |
| `channel` | TEXT | `orange_money` / `airtel_money` / `moov_money` / ... |
| `occurred_at` | TIMESTAMPTZ | Quand la transaction a eu lieu (clé de partitionnement TimescaleDB) |
| `ingested_at` | TIMESTAMPTZ | Quand SOUVERAIN-OS l'a reçue |
| `raw_payload` | JSONB | Donnée brute source, pour traçabilité |

**Clé primaire composite** : `(transaction_id, occurred_at)` — exigence TimescaleDB pour les hypertables (la colonne de partitionnement doit faire partie de la clé primaire).

## Hors périmètre de la Brique 1 (rappel)

- Pas de table `audit_log` (réservée à la Brique 8).
- Pas de RLS (Row-Level Security) — non nécessaire avec l'isolation schema-per-tenant.
- Pas de logique de scoring/détection dans le schéma (Briques 4 et 5).
- La fonction `create_tenant()` complète avec gouvernance et RBAC est réservée à la Brique 8. Cette brique fournit uniquement le mécanisme technique bas niveau (`provision_tenant_schema()`).
