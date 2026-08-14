"""
Brique 2 — Auth / RBAC minimal + fondations SOUVERAIN-ID.

Cette brique fournit :
- le hachage sécurisé des mots de passe (Argon2id) ;
- l'émission et la vérification de jetons JWT (HMAC-SHA256, MVP) ;
- un RBAC minimal à 3 rôles (admin, analyst, auditor) ;
- les fondations de SOUVERAIN-ID (identifiant déterministe par
  utilisateur — PAS ENCORE le passeport cryptographique PQC complet) ;
- un routeur FastAPI (/auth/login, /auth/me).

Hors périmètre (voir README.md) : RBAC granulaire par ressource,
audit avancé, révocation par liste noire distribuée (nécessite
Redis, phase transverse), SOUVERAIN-ID complet avec signature
Dilithium-5.
"""

__version__ = "0.1.0"
