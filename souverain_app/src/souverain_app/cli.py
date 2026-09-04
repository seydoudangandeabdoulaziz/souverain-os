"""Point d'entrée CLI de l'application assemblée : uv run souverain-app.

Remplace `uv run souverain-dashboard` (Brique 7 seule) comme point
d'entrée à utiliser désormais pour tout usage réel du dashboard, dès
lors que la fermeture d'alerte (Brique 8) doit être disponible.
`souverain-dashboard` reste fonctionnel (Brique 7 seule, lecture seule
uniquement) — utile pour isoler un bug côté Brique 7 pure si besoin,
mais ne montre pas le formulaire de fermeture.
"""

from __future__ import annotations

import uvicorn
from brique_07_dashboard.config import get_dashboard_settings


def main() -> None:
    settings = get_dashboard_settings()
    print(f"[souverain-app] Démarrage sur http://localhost:{settings.port}")
    uvicorn.run(
        "souverain_app.main:app",
        host="0.0.0.0",  # noqa: S104 — dev local uniquement, à restreindre en déploiement réel
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
