"""SOUVERAIN-OS — Brique 6 : Graphe criminel Neo4j.

Projette le flux transactionnel de {tenant}.transactions (Brique 1)
dans un graphe Neo4j, pour révéler des motifs de réseau invisibles aux
règles séquentielles de la Brique 4 (chaînes de redistribution
multi-sauts, comptes pont).

⚠️ Double dépendance de lecture, jamais vers la Brique 4 directement :
- Brique 1 (PostgreSQL) : source des transactions à projeter.
- Brique 5 (alertes) : source des comptes déjà alertés, nécessaires
  aux requêtes b) et c) (voir garde_isolation.py). Dupliquée en
  lecture directe, jamais importée en runtime — même principe que
  Brique 5 → Brique 4.

Isolation multi-tenant : Neo4j Community Edition ne supporte qu'une
seule base de données (le multi-base est une fonctionnalité
Enterprise). L'isolation est donc LOGIQUE, par propriété tenant_id sur
chaque nœud et chaque relation — jamais physique comme le
schema-per-tenant de PostgreSQL. Voir garde_isolation.py pour le
mécanisme d'application systématique de ce filtre.
"""
