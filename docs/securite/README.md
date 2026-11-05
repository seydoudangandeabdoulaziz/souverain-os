# Sécurité — Documentation

Voir [`SECURITY.md`](../../SECURITY.md) à la racine pour la politique de sécurité complète.

## Note historique — état de la Brique 0

**Instantané historique de la Brique 0 :** « Aucune surface d'attaque métier n'existe encore (pas de service réseau exposé, pas de base de données, pas de secret réel manipulé au-delà de `.env.example`). » Cette description ne représente pas la surface d'attaque actuelle. Consulter `avancement.md`, `SECURITY.md`, les décisions verrouillées et les ADR pour les états et mesures ultérieurs. Les principes Secure by Design et EBIOS Risk Manager s'appliquaient dès la Brique 0 à l'hygiène du dépôt :

- `.env` exclu du versioning (`.gitignore`).
- Aucun secret en dur dans le code.
- `detect-private-key` actif dans les hooks pre-commit.

Les implications de sécurité spécifiques sont documentées dans les dossiers des briques et les ADR concernés.
