"""Point d'entrée CLI de la Brique 7 : uv run souverain-dashboard.

Contrairement aux CLI batch des briques précédentes (souverain-scorer,
souverain-grapher...), celle-ci démarre un serveur HTTP persistant —
mais reste un point d'entrée unique, cohérent avec la convention CLI
déjà établie (pas de logique de démarrage dispersée ailleurs).
"""

from __future__ import annotations

import uvicorn

from brique_07_dashboard.config import get_dashboard_settings


def main() -> None:
    settings = get_dashboard_settings()
    print(f"[souverain-dashboard] Démarrage sur http://localhost:{settings.port}")
    uvicorn.run(
        "brique_07_dashboard.app:app",
        host="0.0.0.0",  # noqa: S104 — dev local uniquement, à restreindre en déploiement réel
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
