# Brique 2 — Auth / RBAC minimal + fondations SOUVERAIN-ID

**Statut : VALIDÉE**

## Rôle

Authentification (JWT) et contrôle d'accès basé sur les rôles (RBAC minimal, 3 rôles), et fondations de SOUVERAIN-ID (identifiant déterministe par utilisateur — pas encore le passeport cryptographique PQC complet).

## Décisions d'architecture (validées avant implémentation)

1. Utilisateurs dans `shared.users`, avec `tenant_id` référencé vers `shared.tenants_registry` (FK `ON DELETE RESTRICT`).
2. Hachage des mots de passe : Argon2id (`argon2-cffi`).
3. Jetons : JWT signé HMAC-SHA256 (MVP — migration PQC en phase transverse).
4. `APIRouter` FastAPI inclus (`/auth/login`, `/auth/me`), testé via `TestClient`, sans serveur permanent.
5. Rôles MVP : `admin`, `analyst`, `auditor`.
6. SOUVERAIN-ID : fondation uniquement (UUID5 déterministe sur tenant+email).
7. Révocation : mécanisme `token_version` implémenté dès cette brique (pas de report en gap MVP — voir `docs/schema.md`).
8. Numérotation des migrations : locale à chaque brique (`brique_02_auth_rbac/migrations/0001_...`), dépendance d'ordre documentée en texte (pas de séquence globale).

Voir `docs/schema.md` pour le détail complet et les limitations MVP assumées.

## Limites explicites (hors périmètre de cette brique)

- RBAC granulaire par ressource/action → Brique 8.
- SOUVERAIN-ID complet (signature Dilithium-5) → phase transverse PQC.
- Rate-limiting anti-brute-force → nécessite Redis, phase transverse.
- Route publique de création de compte → non exposée (voir `docs/schema.md`).

## Structure

```text
brique_02_auth_rbac/
├── README.md
├── pyproject.toml
├── src/
│   └── brique_02_auth_rbac/
│       ├── __init__.py
│       ├── config.py               ← JwtSettings
│       ├── password_hashing.py     ← Argon2id
│       ├── jwt_tokens.py           ← création/décodage JWT
│       ├── souverain_id.py         ← fondation SOUVERAIN-ID
│       ├── schema_users.sql        ← shared.users
│       ├── repository.py           ← accès DB (asyncpg)
│       ├── session.py              ← résolution utilisateur courant (dépendance FastAPI)
│       ├── rbac.py                 ← Role enum + require_role()
│       └── api.py                  ← /auth/login, /auth/me
├── migrations/
│   └── 0001_init_users_table.sql
├── tests/
│   ├── test_password_hashing.py
│   ├── test_jwt_tokens.py
│   ├── test_souverain_id.py
│   ├── test_rbac.py
│   └── test_api.py
└── docs/
    └── schema.md
```

## Prérequis

- Brique 1 validée, avec sa migration appliquée (`shared.tenants_registry` doit exister).
- Docker + conteneur PostgreSQL démarré (`docker compose --profile postgres up -d`).
- `.env` avec `JWT_SECRET_KEY` défini (voir `.env.example`).

## Installation

```bash
cd briques/brique_02_auth_rbac
uv sync
```

## Appliquer la migration

**Prérequis** : la migration `0001_init_shared_schema.sql` de la Brique 1 doit déjà avoir été appliquée (elle crée `shared.tenants_registry`, référencée ici).

Depuis la racine du dépôt :

```bash
docker compose exec -T postgres psql -U souverain_admin -d souverain_os \
  < briques/brique_02_auth_rbac/migrations/0001_init_users_table.sql
```

## Vérifier que tout fonctionne

```bash
cd briques/brique_02_auth_rbac

# Tests unitaires (aucune DB requise) + tests d'intégration
# (auto-skippés si PostgreSQL n'est pas démarré ou migration absente)
uv run pytest -v

# Qualité de code
uv run ruff check .
uv run mypy src/
```

## Erreurs fréquentes et diagnostic

| Symptôme | Cause probable | Diagnostic |
|---|---|---|
| Tests d'intégration SKIPPED | PostgreSQL non démarré | `docker compose --profile postgres up -d` |
| `asyncpg.exceptions.UndefinedTableError: shared.tenants_registry` | Migration Brique 1 non appliquée | Appliquer d'abord `brique_01_postgresql/migrations/0001_init_shared_schema.sql` |
| `asyncpg.exceptions.UndefinedTableError: shared.users` | Migration Brique 2 non appliquée | Appliquer `migrations/0001_init_users_table.sql` de cette brique |
| `401` systématique sur `/auth/login` avec de bons identifiants | `JWT_SECRET_KEY` absent du `.env` (valeur par défaut insecure utilisée, incohérente entre process) | Vérifier `.env` à la racine, relancer |
| Tests `test_token_revoked_after_password_change...` échouent | Mécanisme `token_version` non appliqué (ancienne version de `session.py`) | Vérifier que `session.py` compare bien `user.token_version != payload.token_version` |

## Implications sécurité

- Aucun mot de passe en clair, jamais — uniquement des hachages Argon2id.
- Messages d'erreur de login génériques (`"Email ou mot de passe incorrect"`), pour ne pas permettre l'énumération de comptes.
- Révocation immédiate possible via `token_version` (changement de mot de passe, désactivation).
- Pas encore de rate-limiting — gap MVP assumé et documenté, à corriger en phase transverse (Redis).
- `.env` avec `JWT_SECRET_KEY` réel — jamais commité.

## Dépendances avec les briques futures

- Brique 3 (Ingestion) et Brique 5 (Scoring) : leurs futurs endpoints utiliseront `require_role()` de cette brique.
- Brique 8 (Audit) : étend le RBAC minimal en RBAC granulaire, ajoute l'audit des connexions, expose une route de création de compte protégée.
- Phase transverse PQC : `souverain_id` évoluera vers une signature Dilithium-5 sans changer `user_id` ni les FK existantes.

## Estimation RAM

Argon2id (~10-20 Mo, ponctuel) + PyJWT (négligeable) + FastAPI/Uvicorn en dev (~50-80 Mo) + pool asyncpg (déjà compté en Brique 1) → **< 150 Mo** additionnels. Cumulé avec la Brique 1, toujours très large sur 16 Go.

## Note sur les tests

**Brique validée le 13 août 2026** contre une vraie instance PostgreSQL/TimescaleDB, sur ThinkPad X1 Carbon Gen 6 : 24/24 tests passés, ruff et mypy propres. Un bug d'outillage de test a été détecté et corrigé pendant la validation : `TestClient` (thread séparé, boucle asyncio incompatible avec le pool `asyncpg`) remplacé par `httpx.AsyncClient` + `ASGITransport` (même boucle que les fixtures) — voir `avancement.md` pour le détail.
