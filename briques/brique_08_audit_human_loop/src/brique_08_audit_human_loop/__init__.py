"""SOUVERAIN-OS — Brique 8 : Audit trail + Human-in-the-loop.

Périmètre strictement limité (00_DECISIONS_VERROUILLEES.md, confirmé
28 août 2026) : fermeture d'alerte par un humain (analyst/admin), avec
motif structuré, et piste d'audit immuable de cette action.

Hors périmètre, documenté explicitement (pas un oubli) :
- create_tenant() / gouvernance multi-tenant complète — besoin réel
  identifié mais non positionné dans l'ordre numéroté (voir
  06_ROADMAP_ET_BRIQUES.md).
- Notifications citoyens — même statut.
- Tout ce qui dépasse la fermeture d'alerte (pas de réouverture, pas
  de modification du score, pas d'assignation d'alerte à un analyste).

Immuabilité de l'audit : garantie par un rôle PostgreSQL DÉDIÉ
(souverain_brique8_audit, voir migrations/0001) sans aucun privilège
UPDATE/DELETE sur {tenant}.audit_log — protection par privilège réel,
en plus de la discipline applicative (aucune route de modification/
suppression n'existe dans ce code).

Composition avec la Brique 7 : cette brique ne modifie AUCUN fichier
de la Brique 7 déjà validée. Elle réutilise get_current_user_from_cookie
et tenant_valide tels quels (imports directs), et s'assemble via
souverain_app/ (module racine neutre, voir ARCHITECTURE.md) plutôt que
d'être incluse depuis l'intérieur de brique_07_dashboard.app.
"""
