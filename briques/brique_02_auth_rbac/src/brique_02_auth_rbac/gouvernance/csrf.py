"""
Protection CSRF — double-submit cookie, DUPLIQUÉE depuis
brique_08_audit_human_loop.csrf, pas importée.

Même raison de duplication que session_cookie.py : Brique 2 est censée
être en amont de Brique 8 (Brique 8 dépend de Brique 2, jamais
l'inverse). Mécanique volontairement minimale (~40 lignes), couverte
par ses propres tests, identique dans son principe à celle de la
Brique 8 : un jeton aléatoire déposé en cookie httpOnly ET renvoyé en
champ caché du formulaire, comparés à temps constant à la soumission.
"""

from __future__ import annotations

import secrets

from fastapi import HTTPException, Request, Response, status

NOM_COOKIE_CSRF = "souverain_csrf"


def generer_jeton_csrf() -> str:
    return secrets.token_urlsafe(32)


def obtenir_ou_generer_jeton_csrf(request: Request) -> tuple[str, bool]:
    """Retourne (jeton, doit_etre_pose_en_cookie).

    Ne pose PAS le cookie elle-même — même leçon tirée de la Brique 8 :
    poser le cookie sur un `Response` injecté via Depends est perdu si
    la route retourne un `TemplateResponse` distinct. Le cookie doit
    être posé explicitement sur l'objet réellement retourné, dans
    routes.py.
    """
    jeton = request.cookies.get(NOM_COOKIE_CSRF)
    if jeton is not None:
        return jeton, False
    return generer_jeton_csrf(), True


def poser_cookie_csrf(reponse: Response, jeton: str) -> None:
    reponse.set_cookie(NOM_COOKIE_CSRF, jeton, httponly=True, samesite="strict")


def verifier_csrf(request: Request, jeton_formulaire: str) -> None:
    jeton_cookie = request.cookies.get(NOM_COOKIE_CSRF)
    if not jeton_cookie or not secrets.compare_digest(jeton_cookie, jeton_formulaire):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Jeton de sécurité invalide ou expiré — merci de recharger la page.",
        )
