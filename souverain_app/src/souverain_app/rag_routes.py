"""Recherche documentaire sourcée, bornée aux patterns et rôles autorisés."""

from __future__ import annotations

import asyncio
import os
from functools import lru_cache
from html import escape
from pathlib import Path

from brique_02_auth_rbac.rbac import Role, require_role
from brique_02_auth_rbac.session import AuthenticatedUser
from brique_07_dashboard.auth_cookie import get_current_user_from_cookie
from brique_07_dashboard.tenant_garde import tenant_valide
from brique_07_dashboard.traductions import langue_pour_pays
from fastapi import APIRouter, Depends, HTTPException
from souverain_rag.chroma_store import (
    ChromaVectorIndex,
    client_chroma_from_env,
    collection_name_pour_manifest,
)
from souverain_rag.embedder import E5SmallEmbedder
from souverain_rag.engine import SearchEngine, SingleProcessSearchGate
from souverain_rag.errors import RagError, SearchBusy
from souverain_rag.manifest import valider_manifeste
from souverain_rag.patterns import PatternType
from starlette.responses import HTMLResponse

from souverain_app.traductions import t

_ROLES_AUTORISES = (Role.ANALYST, Role.ADMIN)
_SEARCH_GATE = SingleProcessSearchGate()
_DEPENDANCE_ROLE = require_role(
    *_ROLES_AUTORISES, user_dependency=get_current_user_from_cookie
)


@lru_cache(maxsize=1)
def _charger_moteur() -> SearchEngine:
    try:
        model_path = Path(os.environ["SOUVERAIN_RAG_MODEL_PATH"])
        manifest_path = Path(os.environ["SOUVERAIN_RAG_MANIFEST_PATH"])
        manifest = valider_manifeste(manifest_path)
    except KeyError as exc:
        raise RagError("Configuration locale RAG incomplète.") from exc
    embedder = E5SmallEmbedder(model_path)
    index = ChromaVectorIndex(
        client_chroma_from_env(),
        collection_name_pour_manifest(manifest),
        embedder.fingerprint,
        manifest_path,
    )
    return SearchEngine(index, embedder)


def construire_routes_rag() -> APIRouter:
    router = APIRouter(tags=["rag-documentaire"])

    @router.get("/references/{pattern_type}", response_class=HTMLResponse)
    async def rechercher_references_route(
        pattern_type: PatternType,
        utilisateur: AuthenticatedUser = Depends(_DEPENDANCE_ROLE),  # noqa: B008
    ) -> HTMLResponse:
        """Le RAG ne reçoit que le type fermé ; le tenant reste dans l'adaptateur."""
        # Faire la validation après require_role : FastAPI résout les dépendances
        # voisines avant l'endpoint, ce qui pourrait autrement toucher le registre
        # tenant avant le refus d'un rôle non autorisé.
        tenant = await tenant_valide(utilisateur)
        del utilisateur
        langue = langue_pour_pays(tenant.country_code)
        try:
            response = await asyncio.to_thread(
                _SEARCH_GATE.run,
                lambda: _charger_moteur().search(pattern_type, k=5),
            )
        except SearchBusy as exc:
            raise HTTPException(
                status_code=429,
                detail=t("rag.concurrence", langue),
                headers={"Retry-After": "1"},
            ) from exc
        except (RagError, OSError, ValueError) as exc:
            raise HTTPException(status_code=503, detail=t("rag.indisponible", langue)) from exc

        if not response.results:
            message = escape(t("rag.aucun_resultat", langue))
            return HTMLResponse(f'<p class="rag-vide">{message}</p>')

        fragments: list[str] = []
        for result in response.results:
            synthetic_label = (
                f"<p>{escape(t('rag.synthetique', langue))}</p>" if result.synthetic else ""
            )
            fragments.append(
                "".join(
                    [
                        (
                            '<article class="rag-reference">'
                            f"<h4>{escape(t('rag.reference', langue))} — "
                            f"{escape(result.title)}</h4>"
                            f"<blockquote>{escape(result.text)}</blockquote>"
                            f"<p>{escape(result.publisher)} · {escape(t('rag.page', langue))} "
                            f"{result.page_number}</p>"
                            f'<p><a href="{escape(result.source_url, quote=True)}" '
                            f'rel="noopener noreferrer">{escape(t("rag.source", langue))}</a></p>'
                        ),
                        synthetic_label,
                        "</article>",
                    ]
                )
            )
        return HTMLResponse("".join(fragments))

    return router
