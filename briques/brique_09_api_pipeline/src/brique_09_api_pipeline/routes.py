"""Routes /api/v1 : jeton, ingestion, cycle. Aucun cookie accepté (Bearer seul)."""

from __future__ import annotations

import time
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from brique_09_api_pipeline.auth import (
    IdentiteService,
    authentifier_client,
    exiger_scope,
    parametres_api,
)
from brique_09_api_pipeline.config import ApiSettings
from brique_09_api_pipeline.cycle import CycleDejaEnCours, executer_cycle
from brique_09_api_pipeline.ingestion import ConflitIngestion, TenantInactif, ingerer_lot
from brique_09_api_pipeline.journal import journaliser
from brique_09_api_pipeline.schemas import (
    DemandeJeton,
    LotTransactions,
    ReponseCycle,
    ReponseIngestion,
    ReponseJeton,
)


class RouteBornee(APIRoute):
    """Refuse un corps trop gros AVANT sa lecture (413) ou sans longueur (411)."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original = super().get_route_handler()

        async def handler(request: Request) -> Response:
            longueur = request.headers.get("content-length")
            if longueur is None:
                # Corps en « chunked » sans longueur annoncée : refusé (on ne peut pas le
                # borner avant lecture). Aucune longueur ni transfert fragmenté = corps vide
                # (ex. `curl -X POST` sans données sur /pipeline/cycle) : accepté.
                if "transfer-encoding" in request.headers:
                    return JSONResponse({"detail": {"code": "longueur_requise"}}, status_code=411)
            elif not longueur.isdigit():
                return JSONResponse({"detail": {"code": "longueur_requise"}}, status_code=411)
            try:
                limite = parametres_api().max_body_bytes
            except HTTPException:
                return JSONResponse({"detail": {"code": "api_non_configuree"}}, status_code=503)
            if longueur is not None and int(longueur) > limite:
                return JSONResponse({"detail": {"code": "corps_trop_gros"}}, status_code=413)
            return await original(request)

        return handler


def construire_routes_pipeline() -> APIRouter:
    """Construit un routeur NEUF à chaque appel (pas d'état global partagé)."""
    router = APIRouter(prefix="/api/v1", route_class=RouteBornee)

    @router.post("/auth/token", response_model=ReponseJeton)
    async def obtenir_jeton(
        demande: DemandeJeton,
        requete: Request,
        settings: ApiSettings = Depends(parametres_api),  # noqa: B008
    ) -> ReponseJeton:
        adresse = requete.client.host if requete.client else "inconnue"
        return await authentifier_client(demande, adresse, settings)

    @router.post("/transactions", response_model=ReponseIngestion)
    async def ingerer(
        lot: LotTransactions,
        identite: IdentiteService = Depends(exiger_scope("ingest")),  # noqa: B008
        settings: ApiSettings = Depends(parametres_api),  # noqa: B008
    ) -> ReponseIngestion:
        limite = datetime.now(UTC) + timedelta(minutes=settings.future_tolerance_minutes)
        if any(t.occurred_at > limite for t in lot.transactions) or any(
            t.amount > settings.max_amount for t in lot.transactions
        ):
            raise HTTPException(422, detail={"code": "valeur_hors_limites"})
        debut = time.perf_counter()
        try:
            resultat = await ingerer_lot(
                identite.pool,
                identite.schema_name,
                identite.tenant_id,
                identite.source_code,
                lot.transactions,
            )
        except ConflitIngestion as exc:
            journaliser(
                "ingestion_conflit",
                client_id=identite.client_id,
                conflits=len(exc.external_ids),
            )
            raise HTTPException(
                409,
                detail={"code": "conflit_external_id", "external_ids": exc.external_ids[:50]},
            ) from exc
        except TenantInactif as exc:
            raise HTTPException(
                401, detail={"code": "non_authentifie"}, headers={"WWW-Authenticate": "Bearer"}
            ) from exc
        journaliser(
            "ingestion",
            client_id=identite.client_id,
            tenant_id=identite.tenant_id,
            recues=resultat.recues,
            inserees=resultat.inserees,
            doublons_ignores=resultat.doublons_ignores,
            duree_ms=round(1000 * (time.perf_counter() - debut)),
        )
        return ReponseIngestion(
            recues=resultat.recues,
            inserees=resultat.inserees,
            doublons_ignores=resultat.doublons_ignores,
        )

    @router.post("/pipeline/cycle", response_model=ReponseCycle)
    async def lancer_cycle(
        identite: IdentiteService = Depends(exiger_scope("cycle")),  # noqa: B008
        settings: ApiSettings = Depends(parametres_api),  # noqa: B008
    ) -> ReponseCycle:
        debut = time.perf_counter()
        try:
            resultat = await executer_cycle(
                identite.pool,
                identite.schema_name,
                identite.tenant_id,
                None
                if settings.episode_max_heures is None
                else timedelta(hours=settings.episode_max_heures),
            )
        except CycleDejaEnCours as exc:
            raise HTTPException(409, detail={"code": "cycle_en_cours"}) from exc
        journaliser(
            "cycle",
            client_id=identite.client_id,
            tenant_id=identite.tenant_id,
            nouvelles_transactions=resultat.nouvelles_transactions,
            comptes_touches=resultat.comptes_touches,
            transactions_relues=resultat.transactions_relues,
            detections_nouvelles=resultat.detections_nouvelles,
            replis_episode=resultat.replis_episode,
            episodes_tronques=resultat.episodes_tronques,
            alertes_creees=resultat.alertes_creees,
            alertes_mises_a_jour=resultat.alertes_mises_a_jour,
            duree_ms=round(1000 * (time.perf_counter() - debut)),
        )
        return ReponseCycle(**resultat.__dict__)

    return router
