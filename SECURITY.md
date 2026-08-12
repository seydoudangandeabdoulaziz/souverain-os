# Politique de sécurité — SOUVERAIN-OS

## Principes

- Secure by Design.
- Méthodologie EBIOS Risk Manager.
- Zero Trust entre tous les services internes.
- Isolation stricte des tenants (données, clés cryptographiques).
- Secrets systématiquement hors dépôt Git (`.env` jamais commité).
- Audit des actions sensibles.
- Pseudonymisation des données partagées.
- Chiffrement des données au repos et en transit (cible : post-quantique, Kyber-1024/Dilithium-5).
- Inférence IA strictement locale — aucune donnée ne quitte le territoire national.
- Mode dégradé (fallback) défini pour chaque composant critique.

## Référentiels visés

ANSSI, NIST, ISO 27001, ISO 42001, FATF/GAFI, BCEAO, EU CRA, MITRE ATT&CK.

> **Note de prudence** : ces références réglementaires sont des orientations de projet. Toute conformité réelle doit être vérifiée juridiquement avant implémentation formelle — ce document n'a pas valeur de validation légale.

## Signalement d'une vulnérabilité

Le projet étant en phase de reconstruction Greenfield et non encore déployé publiquement, tout signalement doit être adressé directement au fondateur (Seydou Dangande Abdoul Aziz) hors canal public, jusqu'à la mise en place d'un processus de disclosure formel.

## Gouvernance des données (rappel)

| Type de donnée | Accès |
|---|---|
| Données brutes | Tenant propriétaire uniquement |
| Scores anonymisés | Partage selon consentement |
| Empreintes criminelles | Partage bilatéral sur accord |
| Statistiques agrégées | Partage selon cadre prévu |
| Clés cryptographiques | Isolées par tenant, jamais partagées |
