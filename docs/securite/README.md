# Sécurité — Documentation

Voir [`SECURITY.md`](../../SECURITY.md) à la racine pour la politique de sécurité complète.

## État pour la Brique 0

Aucune surface d'attaque métier n'existe encore (pas de service réseau exposé, pas de base de données, pas de secret réel manipulé au-delà de `.env.example`). Les principes Secure by Design et EBIOS Risk Manager s'appliquent dès cette brique au niveau de l'hygiène du dépôt :

- `.env` exclu du versioning (`.gitignore`).
- Aucun secret en dur dans le code.
- `detect-private-key` actif dans les hooks pre-commit.

Les implications sécurité spécifiques à chaque brique future seront documentées ici au fur et à mesure de leur implémentation.
