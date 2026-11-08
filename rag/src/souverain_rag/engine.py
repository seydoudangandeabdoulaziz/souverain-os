"""Orchestration des cinq recherches documentaires prédéfinies."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, TypeVar

from souverain_rag.embedder import Embedder
from souverain_rag.errors import SearchBusy
from souverain_rag.index import SearchResult
from souverain_rag.patterns import PatternType, construire_requete

T = TypeVar("T")


class SearchIndex(Protocol):
    @property
    def model_fingerprint(self) -> str: ...

    @property
    def corpus_id(self) -> str: ...

    def search(self, query: tuple[float, ...], k: int = 5) -> tuple[SearchResult, ...]: ...


@dataclass(frozen=True, slots=True)
class SearchResponse:
    corpus_id: str
    pattern_type: PatternType
    results: tuple[SearchResult, ...]


class SearchEngine:
    """API de recherche n'acceptant ni question libre ni identifiant métier."""

    def __init__(self, index: SearchIndex, embedder: Embedder) -> None:
        if index.model_fingerprint != embedder.fingerprint:
            raise ValueError("Le modèle de recherche ne correspond pas à l'index.")
        self._index = index
        self._embedder = embedder

    def search(self, pattern_type: PatternType, *, k: int = 5) -> SearchResponse:
        query_text = construire_requete(pattern_type)
        query_vector = self._embedder.encode_query(query_text)
        return SearchResponse(
            corpus_id=self._index.corpus_id,
            pattern_type=pattern_type,
            results=self._index.search(query_vector, k=k),
        )


class SingleProcessSearchGate:
    """Sémaphore non bloquant, conforme au déploiement MVP mono-processus."""

    def __init__(self) -> None:
        self._semaphore = threading.BoundedSemaphore(value=1)

    def run(self, callback: Callable[[], T]) -> T:
        if not self._semaphore.acquire(blocking=False):
            raise SearchBusy("Une recherche documentaire est déjà en cours.")
        try:
            return callback()
        finally:
            self._semaphore.release()
