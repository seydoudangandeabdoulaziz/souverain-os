"""Limitation des échecs d'authentification (mémoire du processus, D7)."""

from __future__ import annotations

import time
from collections.abc import Callable


class LimiteurEchecs:
    def __init__(
        self,
        maxi: int,
        fenetre_s: int,
        blocage_s: int,
        horloge: Callable[[], float] = time.monotonic,
    ) -> None:
        self._maxi, self._fenetre, self._blocage = maxi, fenetre_s, blocage_s
        self._horloge = horloge
        self._echecs: dict[str, list[float]] = {}
        self._bloque_jusqua: dict[str, float] = {}

    def verrouille(self, cle: str) -> bool:
        jusqua = self._bloque_jusqua.get(cle)
        if jusqua is None:
            return False
        if self._horloge() >= jusqua:
            del self._bloque_jusqua[cle]
            self._echecs.pop(cle, None)
            return False
        return True

    def enregistrer_echec(self, cle: str) -> None:
        maintenant = self._horloge()
        recents = [t for t in self._echecs.get(cle, []) if maintenant - t < self._fenetre]
        recents.append(maintenant)
        self._echecs[cle] = recents
        if len(recents) >= self._maxi:
            self._bloque_jusqua[cle] = maintenant + self._blocage

    def reinitialiser(self, cle: str) -> None:
        self._echecs.pop(cle, None)
        self._bloque_jusqua.pop(cle, None)
