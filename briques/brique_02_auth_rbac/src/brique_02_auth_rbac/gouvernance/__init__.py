"""
Brique 2 V2 — extension de gouvernance des utilisateurs.

Périmètre : création, changement de rôle, désactivation, réactivation
d'un compte — strictement limité au tenant de l'administrateur
appelant. Aucun nouveau rôle (toujours admin/analyst/auditor).

Décisions actées à l'analyse (voir conversation de conception,
antérieure à ce code) :
- Seul le rôle `admin` a accès à ces routes — première différenciation
  fonctionnelle réelle entre admin et analyst.
- Un admin ne peut ni se désactiver, ni se rétrograder lui-même.
- session_cookie.py et csrf.py DUPLIQUENT intentionnellement des
  mécanismes des Briques 7 et 8 plutôt que de les importer — Brique 2
  est en amont de ces deux briques dans le graphe de dépendances,
  les importer aurait inversé ce graphe.
- Toute opération est enregistrée dans shared.gouvernance_audit_log
  (table transverse, migration portée par la Brique 1) via le rôle
  PostgreSQL dédié souverain_gouvernance_web (INSERT/SELECT
  uniquement, jamais UPDATE/DELETE).
"""
