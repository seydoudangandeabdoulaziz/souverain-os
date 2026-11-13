"""Routes d'explication locale d'une alerte — étape 6B (ADR-007).

Deux routes :
- GET /alertes/{id}/explication : fragment HTMX contenant le bouton, chargé
  par la page de détail de la Brique 7 (qui ne contient aucun texte pour ce
  bloc) ;
- GET /alertes/{id}/expliquer : produit l'explication, à la demande.

Autorisations (ADR-007) : seuls `analyst` et `admin` peuvent afficher le bouton
et déclencher une génération. Pour `auditor` (ou tout rôle inconnu) :
- le fragment répond 200 avec un contenu vide, pour que la page de détail ne
  garde pas un indicateur de chargement bloqué ;
- `/expliquer` répond 403, avant toute lecture en base et tout appel à Ollama.

Aucun texte utilisateur n'est écrit en dur : tout passe par t() (ADR-001).
"""
from __future__ import annotations

from html import escape
from uuid import UUID

from brique_01_postgresql.connection import create_tenant_pool
from brique_02_auth_rbac.rbac import Role, require_role
from brique_02_auth_rbac.session import AuthenticatedUser
from brique_05_scoring_alertes.seuils import POIDS_PAR_PATTERN, SEUIL_ALERTE
from brique_07_dashboard import lecture
from brique_07_dashboard.auth_cookie import get_current_user_from_cookie
from brique_07_dashboard.tenant_garde import MetadonneesTenant, tenant_valide
from brique_07_dashboard.traductions import langue_pour_pays
from fastapi import APIRouter, Depends, HTTPException
from starlette.responses import HTMLResponse

from souverain_app.explication_ia import FaitsAlerte, expliquer_alerte
from souverain_app.traductions import t

router = APIRouter(tags=["explication-ia"])

# Indicateur d'attente du bouton : une animation CSS, sans aucun texte, donc
# sans nouvelle traduction (le gel du lot v2 couvre le fichier des traductions).
# htmx affiche l'indicateur pendant la requête puis la réponse remplace tout le
# fragment ; le bouton est désactivé pendant l'attente.
_ID_INDICATEUR = "explication-attente"
_STYLE_INDICATEUR = (
    "<style>"
    ".explication-spinner{display:inline-block;width:1em;height:1em;"
    "margin-left:.6em;vertical-align:middle;border:2px solid currentColor;"
    "border-right-color:transparent;border-radius:50%;"
    "animation:explication-rotation .8s linear infinite}"
    "@keyframes explication-rotation{to{transform:rotate(360deg)}}"
    "@media (prefers-reduced-motion:reduce)"
    "{.explication-spinner{animation-duration:2.4s}}"
    "</style>"
)

# Source unique des rôles autorisés, partagée par les deux routes.
_ROLES_AUTORISES_EXPLICATION: tuple[Role, ...] = (Role.ANALYST, Role.ADMIN)


def _role_peut_expliquer(role: str) -> bool:
    """Refus par défaut : tout rôle absent de la liste autorisée est refusé."""
    return role in {autorise.value for autorise in _ROLES_AUTORISES_EXPLICATION}


@router.get("/alertes/{alerte_id}/explication", response_class=HTMLResponse)
async def fragment_explication_route(
    alerte_id: UUID,
    tenant: MetadonneesTenant = Depends(tenant_valide),  # noqa: B008
    utilisateur: AuthenticatedUser = Depends(get_current_user_from_cookie),  # noqa: B008
) -> HTMLResponse:
    """Retourne le bouton d'explication, sans accès à la base ni au modèle.

    Réponse 200 vide pour un rôle non autorisé : HTMX remplace alors le
    contenu provisoire de la page de détail par rien (un 4xx ne serait pas
    substitué et laisserait l'indicateur de chargement affiché).
    """
    if not _role_peut_expliquer(utilisateur.role):
        return HTMLResponse(content="")

    langue = langue_pour_pays(tenant.country_code)
    return HTMLResponse(
        content=(
            f'<button type="button" hx-get="/alertes/{alerte_id}/expliquer" '
            'hx-target="#explication-ia" hx-swap="innerHTML" '
            f'hx-indicator="#{_ID_INDICATEUR}" hx-disabled-elt="this">'
            f"{escape(t('explication.bouton', langue))}</button>"
            f'<span id="{_ID_INDICATEUR}" '
            'class="htmx-indicator explication-spinner" aria-hidden="true"></span>'
            f"{_STYLE_INDICATEUR}"
            f'<p class="aide">{escape(t("explication.aide", langue))}</p>'
        )
    )


@router.get("/alertes/{alerte_id}/expliquer", response_class=HTMLResponse)
async def expliquer_alerte_route(
    alerte_id: UUID,
    # Le rôle est vérifié en premier : un refus (403) n'accède ni à PostgreSQL
    # ni à Ollama. Même motif que la fermeture d'alerte de la Brique 8.
    utilisateur: AuthenticatedUser = Depends(  # noqa: B008
        require_role(  # noqa: B008
            *_ROLES_AUTORISES_EXPLICATION,
            user_dependency=get_current_user_from_cookie,
        )
    ),
    tenant: MetadonneesTenant = Depends(tenant_valide),  # noqa: B008
) -> HTMLResponse:
    """Explique une alerte déjà enregistrée, dans le contexte du tenant authentifié."""
    # L'identité sert à contrôler l'accès ; elle n'est ni envoyée au modèle ni journalisée.
    del utilisateur

    pool = await create_tenant_pool(tenant.tenant_id)
    alerte = await lecture.lire_alerte(pool, tenant.schema_name, alerte_id)
    if alerte is None:
        raise HTTPException(status_code=404, detail="erreur.non_trouve")

    details = alerte.details if isinstance(alerte.details, dict) else {}
    motifs: list[tuple[str, int]] = []

    for pattern in alerte.pattern_types_impliques:
        poids = details.get(pattern)
        if (
            pattern in POIDS_PAR_PATTERN
            and isinstance(poids, int)
            and not isinstance(poids, bool)
            and poids >= 0
        ):
            motifs.append((pattern, poids))

    faits = FaitsAlerte(
        compte_pivot=str(alerte.compte_pivot),
        score=int(alerte.score),
        seuil=int(SEUIL_ALERTE),
        statut=str(alerte.statut),
        motifs=tuple(motifs),
        nombre_transactions=None,
        fenetre_debut=alerte.fenetre_debut.date(),
        fenetre_fin=alerte.fenetre_fin.date(),
    )

    langue = langue_pour_pays(tenant.country_code)
    texte, repli_utilise = await expliquer_alerte(
        faits, langue=langue, alerte_id=alerte_id
    )
    cle_origine = (
        "explication.origine_repli" if repli_utilise else "explication.origine_modele"
    )
    origine = t(cle_origine, langue)

    return HTMLResponse(
        content=(
            '<section class="explication-ia" aria-live="polite">'
            f"<h2>{escape(t('explication.titre', langue))}</h2>"
            f"<p>{escape(texte)}</p>"
            f'<p class="avertissement">{escape(origine)} '
            f"{escape(t('explication.avertissement', langue))}</p>"
            "</section>"
        )
    )


def construire_routes_explication() -> APIRouter:
    """Retourne le routeur pour l'assemblage principal."""
    return router
