"""
Brique 1 — PostgreSQL / TimescaleDB multi-tenant SOUVERAIN-OS.

Cette brique fournit :
- le schéma PARTAGÉ (registre des tenants) ;
- le TEMPLATE de schéma rejoué pour chaque nouveau tenant
  (isolation "schema-per-tenant", conforme au document fondateur,
  Bloc 9 : "chaque pays membre dispose d'un espace de données
  totalement isolé — PostgreSQL schema séparé") ;
- une couche de connexion asynchrone (asyncpg) ;
- un healthcheck de connexion réelle à la base.

Hors périmètre de cette brique (voir README.md) : Auth/RBAC (Brique 2),
ingestion réelle (Brique 3), fonction create_tenant() complète avec
gouvernance (Brique 8).
"""

__version__ = "0.1.0"
