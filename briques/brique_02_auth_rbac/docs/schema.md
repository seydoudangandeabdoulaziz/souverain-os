# Brique 2 — Documentation du schéma

## `shared.users`

| Colonne | Type | Description |
|---|---|---|
| `user_id` | UUID (PK) | Identifiant technique interne |
| `souverain_id` | UUID (unique) | Fondation SOUVERAIN-ID — déterministe (UUID5 sur tenant+email). **Pas encore** le passeport PQC complet |
| `tenant_id` | UUID (FK → `shared.tenants_registry`, `ON DELETE RESTRICT`) | Tenant d'appartenance — obligatoire, un utilisateur = un seul tenant en MVP |
| `email` | TEXT (unique globalement) | Identifiant de connexion |
| `password_hash` | TEXT | Hash Argon2id — jamais le mot de passe en clair |
| `role` | TEXT | `admin` / `analyst` / `auditor` |
| `data_classification` | TEXT | Cohérent avec le pattern Brique 1 |
| `token_version` | INTEGER | Incrémenté pour révoquer immédiatement les jetons JWT déjà émis |
| `is_active` | BOOLEAN | Désactivation logique — jamais de suppression physique |
| `created_at` / `updated_at` / `last_login_at` | TIMESTAMPTZ | Traçabilité |

## Pourquoi `shared.users` et pas `{tenant}.users` ?

Les comptes utilisateurs sont de la **gouvernance** (comme `tenants_registry`), pas de la donnée métier transactionnelle à isoler physiquement par pays. Autre raison pratique : au moment du login, le tenant de l'utilisateur n'est pas encore connu — il faut pouvoir chercher un compte par email sans présupposer son schéma.

## Pourquoi `souverain_id` séparé de `user_id` ?

`user_id` est la clé technique stable, utilisée dans toutes les relations internes (FK, jointures). `souverain_id` est destiné à évoluer (signature cryptographique post-quantique, interopérabilité inter-États) en phase transverse — les séparer évite de devoir un jour migrer toutes les clés étrangères du système.

## Mécanisme de révocation — `token_version`

Un JWT est par nature "stateless" : une fois émis, il reste valide jusqu'à expiration. `token_version` comble cette limite sans dépendre de Redis (indisponible avant la phase transverse) : chaque jeton émis embarque la valeur de `token_version` au moment de sa création. À chaque requête authentifiée, le serveur compare cette valeur à celle en base — si elles diffèrent (mot de passe changé, compte désactivé), le jeton est rejeté immédiatement malgré une signature valide.

## Limitations MVP assumées (pas des oublis)

- **Pas de refresh token** : à l'expiration (8h par défaut), reconnexion complète requise.
- **Pas de rate-limiting anti-brute-force** : nécessite Redis, indisponible avant la phase transverse. Gap documenté, pas corrigé dans cette brique.
- **Un utilisateur = un seul tenant** : la notion d'auditeur inter-États (mentionnée au Bloc 9 du document fondateur) est une Vision, traitée en Brique 8 ou en phase UEMOA.
- **Pas de route publique de création de compte** : `repository.create_user()` existe et est testé, mais n'est pas exposé via l'API dans cette brique (périmètre validé : `/auth/login` et `/auth/me` uniquement).

## Hors périmètre de la Brique 2 (rappel)

- RBAC granulaire par ressource/action → Brique 8.
- SOUVERAIN-ID complet (signature Dilithium-5, interopérabilité inter-États) → phase transverse, après la couche PQC.
- Audit des connexions/actions → Brique 8.
