# Architecture — Brique 3 : Générateur + ingestion de transactions synthétiques

## Position dans le pipeline

```text
[Brique 1: PostgreSQL/TimescaleDB]
    ├── connection.create_pool()/close_pool()   ← réutilisé tel quel
    ├── tenant_provisioning.validate_schema_name() ← réutilisé tel quel
    └── schema_tenant_template.sql               ← colonnes réelles suivies
              │
              ▼
[Brique 3: Générateur + ingestion]
    ├── scripts/bootstrap_tenant_ne.sql  (provisoire, remplacé en Brique 8)
    ├── generateur_legitime.py + patterns_suspects.py  (purs, sans DB)
    └── ingestion.py  (seul module qui touche asyncpg)
              │
              ▼
[Brique 4: Détection Hybrid-Stream]  ← consommateur futur
```

## Flux interne (inchangé sur le fond, corrigé sur les colonnes)

```text
cli.py
    │
    ├─► brique_01_postgresql.connection.create_pool()
    │        (réutilise PostgresSettings, POSTGRES_* du .env)
    │
    ├─► generateur_legitime.generer_lot_legitime()
    │        → sender_account/receiver_account, pattern_label=None
    │
    ├─► patterns_suspects.generer_*()
    │        → sender_account/receiver_account, pattern_label renseigné
    │          (jamais persisté en base)
    │
    ├─► mélange + shuffle (seed)
    │
    └─► ingestion.inserer_transactions(pool, "tenant_ne", transactions)
             ├─► recuperer_metadonnees_tenant()
             │      lookup shared.tenants_registry → tenant_id/country_code/
             │      data_classification (colonnes NOT NULL du vrai schéma)
             ├─► ADD COLUMN IF NOT EXISTS is_synthetic (auto-réparateur)
             └─► INSERT par lots de 500, colonnes réelles :
                  transaction_id, tenant_id, country_code, data_classification,
                  amount, currency, sender_account, receiver_account, channel,
                  occurred_at, is_synthetic
```

## Pourquoi la dépendance vers `shared.tenants_registry` était invisible au départ

**Analogie :** le schéma `{tenant}.transactions` n'est pas une simple table
"par pays" — chaque ligne insérée doit pouvoir prouver, via `tenant_id`,
`country_code` et `data_classification`, à quel tenant *enregistré* elle
appartient. C'est la différence entre écrire une adresse sur une enveloppe
(le schéma physique suffit) et l'envoyer via un service postal qui vérifie
que le destinataire existe dans son registre (le tenant doit être enregistré
avant qu'on puisse lui envoyer quoi que ce soit).

Cette vérification n'existait dans aucun code visible avant l'implémentation
réelle, parce que la Brique 1 s'arrête volontairement à la mécanique
technique (`provision_tenant_schema()`), et que la gouvernance complète
(`create_tenant()`) est réservée à la Brique 8. La Brique 3 est la première
à avoir besoin d'un tenant *utilisable de bout en bout* — d'où la découverte
du trou à ce moment précis, pas avant.

## Le bootstrap MVP (`scripts/bootstrap_tenant_ne.sql`)

Volontairement minimal : un seul `INSERT ... ON CONFLICT DO NOTHING`, pas de
fonction Python, pas de validation métier, pas d'audit. Il ne doit **jamais**
être généralisé à d'autres tenants sans passer par la Brique 8 — le
commentaire en tête du fichier le rappelle explicitement pour éviter qu'il
devienne, par facilité, le mécanisme de fait de création de tenants.

## Auto-réparation de la colonne `is_synthetic`

`inserer_transactions()` exécute `ADD COLUMN IF NOT EXISTS` avant chaque
insertion, en plus de la migration `0001_add_is_synthetic.sql`. Nécessaire
car la migration ne boucle que sur les tenants *déjà enregistrés* au moment
où elle s'exécute — un tenant provisionné après coup (typiquement en test)
ne serait pas couvert sans cette sécurité. Coût négligible : `ADD COLUMN IF
NOT EXISTS` est un no-op quasi instantané si la colonne existe déjà.

## Sécurité — implications de cette brique

- Validation anti-injection réutilisée de la Brique 1 (`validate_schema_name`).
- Aucune donnée personnelle réelle.
- `is_synthetic` : traçabilité et purge propres.
- Le bootstrap MVP est scellé, documenté et scopé à `tenant_ne` uniquement.

## Dépendances vers les briques futures

| Brique | Dépendance |
|---|---|
| 4 — Détection Hybrid-Stream | Consomme les transactions `is_synthetic=true` en mode batch. |
| 6 — Neo4j | `structure_etoile`/`compte_pivot` → sous-graphes reconnaissables. |
| 8 — Audit + gouvernance | **Doit remplacer** `scripts/bootstrap_tenant_ne.sql` par un vrai `create_tenant()`. Point de vigilance explicite à reprendre à ce moment-là. |

## Points explicitement hors périmètre (Vision)

- Calibrage statistique des patterns sur données réelles GIABA/UNODC
- Comportement adaptatif des acteurs simulés
- Génération multi-tenant simultanée
- Mode stream continu (porté par la Brique 4)
- Endpoint API de déclenchement (RBAC)
- Gouvernance complète de création de tenant (Brique 8)
