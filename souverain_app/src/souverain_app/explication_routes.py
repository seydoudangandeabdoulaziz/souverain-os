"""Routes d'explication locale d'une alerte — étape 6B (ADR-007).

Deux routes :
- GET /alertes/{id}/explication : fragment HTMX contenant le bouton, chargé
  par la page de détail de la Brique 7 (qui ne contient aucun texte pour ce
  bloc) ;
- GET /alertes/{id}/expliquer : produit l'explication, à la demande.

Aucun texte utilisateur n'est écrit en dur : tout passe par t() (ADR-001).
"""
from __future__ import annotations

from html import escape
from uuid import UUID

from brique_01_postgresql.connection import create_pool
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


@router.get("/alertes/{alerte_id}/explication", response_class=HTMLResponse)
async def fragment_explication_route(
    alerte_id: UUID,
    tenant: MetadonneesTenant = Depends(tenant_valide),  # noqa: B008
    utilisateur: AuthenticatedUser = Depends(get_current_user_from_cookie),  # noqa: B008
) -> HTMLResponse:
    """Retourne le bouton d'explication, sans accès à la base ni au modèle."""
    del utilisateur  # L'identité protège la route ; elle n'est pas utilisée ici.

    langue = langue_pour_pays(tenant.country_code)
    return HTMLResponse(
        content=(
            f'<button type="button" hx-get="/alertes/{alerte_id}/expliquer" '
            'hx-target="#explication-ia" hx-swap="innerHTML">'
            f"{escape(t('explication.bouton', langue))}</button>"
            f'<p class="aide">{escape(t("explication.aide", langue))}</p>'
        )
    )


@router.get("/alertes/{alerte_id}/expliquer", response_class=HTMLResponse)
async def expliquer_alerte_route(
    alerte_id: UUID,
    tenant: MetadonneesTenant = Depends(tenant_valide),  # noqa: B008
    utilisateur: AuthenticatedUser = Depends(get_current_user_from_cookie),  # noqa: B008
) -> HTMLResponse:
    """Explique une alerte déjà enregistrée, dans le contexte du tenant authentifié."""
    # Les dépendances d'authentification et de tenant sont évaluées avant la route.
    del utilisateur  # L'identité est requise pour protéger la route, pas envoyée au modèle.

    pool = await create_pool()
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
    texte, repli_utilise = await expliquer_alerte(faits, langue=langue)
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
