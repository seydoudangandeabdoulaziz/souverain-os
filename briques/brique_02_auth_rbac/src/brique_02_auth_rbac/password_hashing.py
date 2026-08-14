"""
Hachage sécurisé des mots de passe — Argon2id.

Pourquoi Argon2id et pas un hash simple (SHA-256, MD5, etc.) ?
Un hash simple est rapide à calculer — exactement ce qu'on NE veut PAS
pour un mot de passe : un attaquant qui vole la base de données peut
tester des milliards de mots de passe par seconde avec un hash rapide.
Argon2id est volontairement lent et gourmand en mémoire, ce qui rend
les attaques par force brute nettement plus coûteuses, même contre
du matériel spécialisé (GPU/ASIC). C'est le standard recommandé
actuellement par l'OWASP.

Ce module ne fait QUE du hachage — aucune notion de session, de JWT
ou d'utilisateur ici (une seule responsabilité par fichier).
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error, InvalidHashError

_hasher = PasswordHasher()


def hash_password(plain_password: str) -> str:
    """
    Hache un mot de passe en clair.

    Le résultat inclut le sel et les paramètres Argon2id utilisés
    (format auto-descriptif) — pas besoin de stocker le sel séparément.
    """
    return _hasher.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """
    Vérifie qu'un mot de passe en clair correspond à un hash stocké.

    Ne lève jamais d'exception vers l'appelant : retourne simplement
    True/False. Couvre à la fois le cas "mot de passe incorrect"
    (VerifyMismatchError, sous-classe d'Argon2Error) et le cas
    "hash malformé/corrompu" (InvalidHashError, qui hérite en réalité
    de ValueError et non d'Argon2Error dans argon2-cffi — d'où les
    deux exceptions listées explicitement ci-dessous).
    """
    try:
        return _hasher.verify(password_hash, plain_password)
    except (Argon2Error, InvalidHashError):
        return False
