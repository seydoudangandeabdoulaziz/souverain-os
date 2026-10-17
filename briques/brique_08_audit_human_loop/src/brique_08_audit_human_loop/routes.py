"""Routes de la Brique 8 — les deux SEULES routes d'écriture du dashboard.

GET  /alertes/{id}/fermeture   — fragment HTMX : historique d'audit +
                                  formulaire de fermeture (affiché
                                  uniquement si le rôle courant peut
                                  fermer — analyst/admin).
POST /alertes/{id}/fermeture   — action de fermeture, protégée par
                                  RBAC (analyst/admin) et CSRF.

Réutilise get_current_user_from_cookie ET tenant_valide de la Brique 7
TELS QUELS (import direct, jamais dupliqués une troisième fois) — la
Brique 7 les a déjà écrits précisément pour ce contexte (cookie
httpOnly, dashboard HTMX). Aucun fichier de la Brique 7 n'est modifié
par cet import.

Instance Jinja2Templates PROPRE à cette brique (répertoire
templates/ local) plutôt que de réutiliser celle de
brique_07_dashboard.app.creer_application() — cette dernière n'expose
pas son instance de toute façon (encapsulée dans creer_application()),
et ça évite tout couplage sur les clés de traduction de la Brique 7
(voir traductions/, dictionnaire distinct).
"""

from __future__ import annotations

import logging
from pathlib import Path
from uuid import UUID

from brique_02_auth_rbac.rbac import Role, require_role
from brique_02_auth_rbac.session import AuthenticatedUser
from brique_07_dashboard.auth_cookie import get_current_user_from_cookie
from brique_07_dashboard.tenant_garde import MetadonneesTenant, tenant_valide
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.templating import Jinja2Templates

from brique_08_audit_human_loop.connection import create_audit_pool
from brique_08_audit_human_loop.csrf import (
    obtenir_ou_generer_jeton_csrf,
    poser_cookie_csrf,
    verifier_csrf,
)
from brique_08_audit_human_loop.lecture import lire_historique_audit
from brique_08_audit_human_loop.modeles import (
    AlerteNonFermable,
    AuditNonProvisionne,
    MotifFermeture,
)
from brique_08_audit_human_loop.persistence import fermer_alerte_avec_audit
from brique_08_audit_human_loop.traductions import t

journal = logging.getLogger(__name__)

_ROLES_AUTORISES_FERMETURE = (Role.ANALYST, Role.ADMIN)
_REPERTOIRE_TEMPLATES = Path(__file__).resolve().parent / "templates"


def _reponse_audit_indisponible(schema: str, exc: AuditNonProvisionne) -> HTTPException:
    """503 générique : ni nom de schéma, ni rôle, ni SQLSTATE (ADR-005, D5).

    Le détail utile (schéma, code `raison`) va dans le journal, pas dans la
    réponse.
    """
    journal.error("b8.audit_indisponible schema=%s raison=%s", schema, exc.raison.value)
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=t("fermeture.indisponible"),
    )


def construire_routes_audit() -> APIRouter:
    """Router construit ICI, pas au niveau module.

    Découvert en vérifiant l'assemblage de cette brique (pas un bug de
    Brique 7 reproduit à l'identique par erreur, mais le même piège :
    un `router = APIRouter()` au niveau module accumule les routes à
    chaque appel de cette fonction dans le même process Python — chaque
    test qui reconstruit l'app ré-enregistrerait les mêmes routes sur
    le même routeur partagé. Signalé pour information : Brique 7
    (routes/alertes.py, routes/auth.py) a le même motif au niveau
    module — fonctionnellement inoffensif tant que les doublons sont
    des handlers strictement identiques, mais générateur des mêmes
    avertissements "Duplicate Operation ID" observés ici avant cette
    correction. Fichier déjà validé, non modifié — signalé, pas corrigé
    silencieusement.
    """
    router = APIRouter(tags=["audit"])
    templates = Jinja2Templates(directory=str(_REPERTOIRE_TEMPLATES))
    templates.env.globals["t"] = t

    @router.get("/alertes/{alerte_id}/fermeture")
    async def fragment_fermeture(
        request: Request,
        alerte_id: UUID,
        tenant: MetadonneesTenant = Depends(tenant_valide),  # noqa: B008
        utilisateur: AuthenticatedUser = Depends(get_current_user_from_cookie),  # noqa: B008
    ) -> object:
        """Fragment chargé après coup dans alerte_detail.html (Brique 7),
        même pattern que le fragment graphe déjà en place : hx-trigger="load".

        Le rôle courant détermine si le FORMULAIRE de fermeture est
        affiché (analyst/admin) ou seulement l'historique en lecture
        (auditor) — la vraie barrière de sécurité reste le RBAC de la
        route POST ci-dessous, ceci n'est qu'un affinage d'affichage.
        """
        pool_audit = await create_audit_pool()
        try:
            historique = await lire_historique_audit(pool_audit, tenant.schema_name, alerte_id)
        except AuditNonProvisionne as exc:
            raise _reponse_audit_indisponible(tenant.schema_name, exc) from exc
        jeton_csrf, doit_poser_cookie = obtenir_ou_generer_jeton_csrf(request)

        reponse = templates.TemplateResponse(
            request,
            "fermeture_fragment.html",
            {
                "alerte_id": alerte_id,
                "historique": historique,
                "peut_fermer": utilisateur.role in {r.value for r in _ROLES_AUTORISES_FERMETURE},
                "jeton_csrf": jeton_csrf,
                "motifs": list(MotifFermeture),
                "vient_de_fermer": False,
            },
        )
        # Posé sur la réponse RÉELLEMENT retournée — voir csrf.py pour
        # pourquoi un Response injecté via Depends ne suffit pas ici.
        if doit_poser_cookie:
            poser_cookie_csrf(reponse, jeton_csrf)
        return reponse

    @router.post("/alertes/{alerte_id}/fermeture")
    async def fermer_alerte(
        request: Request,
        alerte_id: UUID,
        motif: MotifFermeture = Form(...),  # noqa: B008
        commentaire: str | None = Form(default=None),  # noqa: B008
        jeton_csrf: str = Form(...),  # noqa: B008
        tenant: MetadonneesTenant = Depends(tenant_valide),  # noqa: B008
        utilisateur: AuthenticatedUser = Depends(  # noqa: B008
            require_role(  # noqa: B008
                *_ROLES_AUTORISES_FERMETURE, user_dependency=get_current_user_from_cookie
            )
        ),
    ) -> object:
        verifier_csrf(request, jeton_csrf)

        pool_audit = await create_audit_pool()
        try:
            await fermer_alerte_avec_audit(
                pool_audit,
                tenant.schema_name,
                alerte_id=alerte_id,
                tenant_id=tenant.tenant_id,
                user_id=utilisateur.user_id,
                motif=motif,
                commentaire=commentaire,
            )
        except AlerteNonFermable as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cette alerte est introuvable ou a déjà été fermée.",
            ) from exc
        except AuditNonProvisionne as exc:
            raise _reponse_audit_indisponible(tenant.schema_name, exc) from exc

        # Ré-affiche le même fragment, désormais avec l'historique à jour
        # et sans formulaire (l'alerte n'est plus 'ouverte') — cohérent
        # avec le hx-swap="innerHTML" du conteneur (voir template Brique 7).
        historique = await lire_historique_audit(pool_audit, tenant.schema_name, alerte_id)

        return templates.TemplateResponse(
            request,
            "fermeture_fragment.html",
            {
                "alerte_id": alerte_id,
                "historique": historique,
                "peut_fermer": False,
                "jeton_csrf": "",
                "motifs": list(MotifFermeture),
                "vient_de_fermer": True,
            },
        )

    return router
