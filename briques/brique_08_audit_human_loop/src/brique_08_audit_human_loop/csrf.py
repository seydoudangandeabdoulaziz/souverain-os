"""Protection CSRF — double-submit cookie.

Pourquoi c'est nécessaire ICI et pas en Brique 7 : Brique 7 est
strictement lecture seule (GET partout), aucune action d'état à
protéger. La fermeture d'alerte (POST, Brique 8) est la PREMIÈRE
action d'écriture du dashboard, déclenchée par un navigateur via cookie
de session — donc vulnérable au CSRF par nature (contrairement à une
API pure protégée par un header Authorization que le navigateur
n'attache jamais automatiquement).

Principe du double-submit : un jeton aléatoire est déposé dans un
cookie ET renvoyé comme champ caché du formulaire. Un site tiers
malveillant peut forcer le navigateur à soumettre le formulaire (et
donc envoyer le cookie automatiquement), mais ne peut PAS lire la
valeur du cookie pour la recopier dans le champ caché (Same-Origin
Policy) — donc les deux valeurs ne concorderont jamais dans une
requête forgée depuis l'extérieur.
"""

from __future__ import annotations

import secrets

from fastapi import HTTPException, Request, Response, status

NOM_COOKIE_CSRF = "souverain_csrf"


def generer_jeton_csrf() -> str:
    return secrets.token_urlsafe(32)


def obtenir_ou_generer_jeton_csrf(request: Request) -> tuple[str, bool]:
    """Retourne (jeton, doit_etre_pose_en_cookie).

    Ne pose PAS le cookie elle-même : contrairement à une route qui
    retournerait un objet quelconque (dict/modèle) laissé à FastAPI le
    soin de fusionner un `Response` injecté, cette route retourne un
    `TemplateResponse` — un objet Response DIFFÉRENT de celui que
    FastAPI injecterait via Depends. FastAPI ne fusionne les
    headers/cookies d'un `Response` injecté que si la route retourne
    autre chose qu'un Response ; ici, poser le cookie sur l'objet
    injecté aurait été silencieusement perdu (bug réel trouvé en
    testant sur une vraie base — un mock de Response n'aurait rien
    révélé). Le cookie doit donc être posé explicitement sur le
    TemplateResponse réellement retourné, dans routes.py.
    """
    jeton = request.cookies.get(NOM_COOKIE_CSRF)
    if jeton is not None:
        return jeton, False
    return generer_jeton_csrf(), True


def poser_cookie_csrf(reponse: Response, jeton: str) -> None:
    """Pose le cookie CSRF sur la réponse RÉELLEMENT retournée par la route."""
    reponse.set_cookie(NOM_COOKIE_CSRF, jeton, httponly=True, samesite="strict")


def verifier_csrf(request: Request, jeton_formulaire: str) -> None:
    """Lève 403 si le jeton du formulaire ne correspond pas au cookie.

    secrets.compare_digest : comparaison à temps constant, évite une
    attaque par mesure de temps sur la comparaison de chaînes (même
    discipline que pour une comparaison de secret/mot de passe).
    """
    jeton_cookie = request.cookies.get(NOM_COOKIE_CSRF)
    if not jeton_cookie or not secrets.compare_digest(jeton_cookie, jeton_formulaire):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Jeton de sécurité invalide ou expiré — merci de recharger la page.",
        )
