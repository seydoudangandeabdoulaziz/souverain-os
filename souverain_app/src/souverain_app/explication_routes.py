"""Route d'explication locale d'une alerte — étape 6B."""
from __future__ import annotations

from html import escape
from uuid import UUID

from brique_01_postgresql.connection import create_pool
from brique_02_auth_rbac.session import AuthenticatedUser
from brique_05_scoring_alertes.seuils import POIDS_PAR_PATTERN, SEUIL_ALERTE
from brique_07_dashboard import lecture
from brique_07_dashboard.auth_cookie import get_current_user_from_cookie
from brique_07_dashboard.tenant_garde import MetadonneesTenant, tenant_valide
from fastapi import APIRouter, Depends, HTTPException
from starlette.responses import HTMLResponse

from souverain_app.explication_ia import FaitsAlerte, expliquer_alerte

router = APIRouter(tags=["explication-ia"])


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

    texte, repli_utilise = await expliquer_alerte(faits)
    texte_sain = escape(texte)
    origine = (
        "Explication de repli déterministe (modèle indisponible ou réponse rejetée)."
        if repli_utilise
        else "Explication générée localement par le modèle."
    )

    return HTMLResponse(
        content=(
            '<section class="explication-ia" aria-live="polite">'
            "<h2>Explication de l’alerte</h2>"
            f"<p>{texte_sain}</p>"
            f"<p class=\"avertissement\">{escape(origine)} "
            "Cette explication est indicative : elle ne constitue ni un verdict "
            "ni une recommandation d’action. Les seuils et poids actuels sont provisoires.</p>"
            "</section>"
        )
    )


def construire_routes_explication() -> APIRouter:
    """Retourne le routeur pour l'assemblage principal."""
    return router
