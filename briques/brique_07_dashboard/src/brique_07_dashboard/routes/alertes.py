"""Routes de consultation des alertes — strictement lecture seule.

Le détail d'une alerte est scindé en deux requêtes HTTP volontairement :
1. GET /alertes/{id} — la page elle-même (alerte + détections liées,
   PostgreSQL, rapide).
2. GET /alertes/{id}/graphe — fragment HTMX chargé après coup
   (hx-trigger="load"), qui retraverse tout le graphe Neo4j du tenant
   avant filtrage côté Python (Option A validée à l'analyse).

Scission délibérée : la page se charge immédiatement, le fragment
graphe (le plus lent des deux, voir le point de vigilance documenté au
README) s'affiche avec un état de chargement plutôt que de bloquer
l'affichage de toute la page.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from brique_01_postgresql.connection import create_pool
from brique_02_auth_rbac.session import AuthenticatedUser
from brique_06_neo4j import requetes as requetes_graphe
from brique_06_neo4j.connexion import create_driver
from brique_06_neo4j.lecture import lire_comptes_alertes
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates

from brique_07_dashboard import lecture
from brique_07_dashboard.auth_cookie import get_current_user_from_cookie
from brique_07_dashboard.tenant_garde import MetadonneesTenant, tenant_valide
from brique_07_dashboard.traductions import langue_pour_pays

router = APIRouter(tags=["alertes"])


def construire_routes_alertes(templates: Jinja2Templates) -> APIRouter:
    @router.get("/alertes")
    async def liste_alertes(
        request: Request,
        tenant: MetadonneesTenant = Depends(tenant_valide),  # noqa: B008
        utilisateur: AuthenticatedUser = Depends(get_current_user_from_cookie),  # noqa: B008
    ) -> object:
        pool = await create_pool()
        alertes = await lecture.lister_alertes_ouvertes(pool, tenant.schema_name)
        langue = langue_pour_pays(tenant.country_code)

        return templates.TemplateResponse(
            request,
            "alertes_liste.html",
            {"alertes": alertes, "langue": langue, "role": utilisateur.role},
        )

    @router.get("/alertes/{alerte_id}")
    async def detail_alerte(
        request: Request,
        alerte_id: UUID,
        tenant: MetadonneesTenant = Depends(tenant_valide),  # noqa: B008
        utilisateur: AuthenticatedUser = Depends(get_current_user_from_cookie),  # noqa: B008
    ) -> object:
        pool = await create_pool()
        alerte = await lecture.lire_alerte(pool, tenant.schema_name, alerte_id)

        if alerte is None:
            raise HTTPException(status_code=404, detail="erreur.non_trouve")

        langue = langue_pour_pays(tenant.country_code)

        return templates.TemplateResponse(
            request,
            "alerte_detail.html",
            {"alerte": alerte, "langue": langue, "role": utilisateur.role},
        )

    @router.get("/alertes/{alerte_id}/graphe")
    async def fragment_graphe_alerte(
        request: Request,
        alerte_id: UUID,
        compte_pivot: str,
        tenant: MetadonneesTenant = Depends(tenant_valide),  # noqa: B008
    ) -> object:
        """Fragment HTMX — voir docstring du module sur la scission délibérée.

        compte_pivot passé en query param par le template appelant
        (déjà connu de la page de détail) plutôt que rechargé ici —
        évite une deuxième lecture de {tenant}.alertes pour la même
        information.
        """
        pool = await create_pool()
        driver = await create_driver()
        tenant_id_str = str(tenant.tenant_id)

        # Risque connexe identifié après le bug de TenantSansDonnees :
        # lire_comptes_alertes() (Brique 6) laisse délibérément
        # UndefinedTableError remonter brute (philosophie assumée côté
        # Brique 6 : brique batch CLI, public développeur). Accès
        # direct/manuel à cette URL sur un tenant où la Brique 5 n'a
        # jamais tourné (table absente) → même risque de 500 brut que
        # le bug corrigé précédemment. Ici, fonctionnellement, "table
        # absente" et "0 compte alerté" reviennent au même pour cette
        # requête précise — traité comme liste vide, comportement déjà
        # validé par les tests de la Brique 6 (comptes_pont/chemins
        # avec liste vide en entrée). Correctif scopé à la Brique 7
        # uniquement, aucune modification de la Brique 6.
        try:
            comptes_alertes = await lire_comptes_alertes(pool, tenant.schema_name)
        except asyncpg.exceptions.UndefinedTableError:
            comptes_alertes = []

        # Option A validée à l'analyse : les 3 fonctions retournent les
        # résultats pour TOUT le tenant, filtrage côté Python ensuite.
        # Voir le point de vigilance documenté au README — c'est ici,
        # précisément, que la latence de cette limite MVP se matérialise.
        toutes_chaines = await requetes_graphe.chaines_redistribution(driver, tenant_id_str)
        tous_ponts = await requetes_graphe.comptes_pont(driver, tenant_id_str, comptes_alertes)
        tous_chemins = await requetes_graphe.plus_courts_chemins_entre_alertes(
            driver, tenant_id_str, comptes_alertes
        )

        chaines = [c for c in toutes_chaines if compte_pivot in c.comptes]
        ponts = [
            p
            for p in tous_ponts
            if compte_pivot in (p.compte_pont, p.compte_alerte_source, p.compte_alerte_cible)
        ]
        chemins = [c for c in tous_chemins if compte_pivot in c.comptes]

        langue = langue_pour_pays(tenant.country_code)

        return templates.TemplateResponse(
            request,
            "graphe_fragment.html",
            {"chaines": chaines, "ponts": ponts, "chemins": chemins, "langue": langue},
        )

    return router
