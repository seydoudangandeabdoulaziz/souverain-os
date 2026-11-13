"""Le runtime B5 exige la préparation DDL par migration opérateur."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from brique_05_scoring_alertes.persistence import _assurer_tables


@pytest.mark.asyncio
async def test_schema_incomplet_refuse_le_scoring_sans_tenter_de_ddl() -> None:
    connexion = AsyncMock()
    connexion.fetchval.side_effect = [True, False]

    with pytest.raises(RuntimeError, match="migration B5 0001"):
        await _assurer_tables(connexion, "tenant_test")

    connexion.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_schema_complet_est_accepte_sans_tenter_de_ddl() -> None:
    connexion = AsyncMock()
    connexion.fetchval.side_effect = [True, True]

    await _assurer_tables(connexion, "tenant_test")

    connexion.execute.assert_not_awaited()
