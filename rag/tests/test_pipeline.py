from __future__ import annotations

import pytest
from souverain_rag.chunking import PageText, decouper_pages
from souverain_rag.engine import SearchEngine, SingleProcessSearchGate
from souverain_rag.errors import IndexIntegrityError, SearchBusy
from souverain_rag.index import VectorIndex, construire_index
from souverain_rag.patterns import CANONICAL_QUERIES, PatternType, construire_requete

from rag.tests.support import manifeste_valide


class FakeEmbedder:
    fingerprint = "fixture-embedder-v1"

    def encode_passages(self, texts: list[str]) -> list[tuple[float, ...]]:
        return [self._vector(text) for text in texts]

    def encode_query(self, text: str) -> tuple[float, ...]:
        return self._vector(text)

    @staticmethod
    def _vector(text: str) -> tuple[float, ...]:
        vector = [0.0] * 384
        vector[0 if "pivot" in text.casefold() else 1] = 1.0
        return tuple(vector)


def test_chunking_stable_et_limite_a_une_page() -> None:
    words = " ".join(f"mot{i}" for i in range(460))
    pages = (PageText(1, words), PageText(2, "fin page deux"))

    first = decouper_pages("doc", "Titre", "Éditeur", "https://example.invalid", pages, True)
    second = decouper_pages("doc", "Titre", "Éditeur", "https://example.invalid", pages, True)

    assert first == second
    assert [passage.page_number for passage in first] == [1, 1, 1, 2]
    assert len(first[0].text.split()) == 220
    assert first[1].text.split()[0] == "mot180"
    assert all(passage.synthetic for passage in first)


def test_five_types_fermés_ont_une_requete_et_aucun_texte_libre() -> None:
    assert set(CANONICAL_QUERIES) == set(PatternType)
    for pattern in PatternType:
        assert construire_requete(pattern) == CANONICAL_QUERIES[pattern]
    with pytest.raises(TypeError):
        construire_requete("question arbitraire")  # type: ignore[arg-type]


def test_index_local_readonly_et_recherche_sourcée(tmp_path) -> None:
    manifest = manifeste_valide(tmp_path / "corpus")
    passages = (
        *decouper_pages(
            "pivot-doc", "Pivot", "Publisher", "https://example.invalid/pivot",
            (PageText(3, "Le compte pivot reçoit puis redistribue."),), False,
        ),
        *decouper_pages(
            "other-doc", "Autre", "Publisher", "https://example.invalid/other",
            (PageText(7, "Un document sans ce motif."),), False,
        ),
    )
    index_path = construire_index(tmp_path / "index", manifest, passages, FakeEmbedder())

    with VectorIndex(index_path, FakeEmbedder.fingerprint, manifest.manifest_path) as index:
        response = SearchEngine(index, FakeEmbedder()).search(PatternType.COMPTE_PIVOT)

    assert response.corpus_id == "fixture-v1"
    assert response.results[0].document_id == "pivot-doc"
    assert response.results[0].page_number == 3
    assert response.results[0].text == "Le compte pivot reçoit puis redistribue."


def test_index_modifie_refuse_au_chargement(tmp_path) -> None:
    manifest = manifeste_valide(tmp_path / "corpus")
    passages = decouper_pages(
        "doc", "Titre", "Publisher", "https://example.invalid", (PageText(1, "Texte"),), True
    )
    path = construire_index(tmp_path / "index", manifest, passages, FakeEmbedder())
    path.write_bytes(path.read_bytes() + b"tampered")

    with pytest.raises(IndexIntegrityError, match="empreinte"):
        VectorIndex(path, FakeEmbedder.fingerprint, manifest.manifest_path)


def test_limiteur_refuse_rapidement_le_second_traitement() -> None:
    gate = SingleProcessSearchGate()
    assert gate.run(lambda: "premier") == "premier"
    gate._semaphore.acquire()
    try:
        with pytest.raises(SearchBusy):
            gate.run(lambda: "ne doit pas tourner")
    finally:
        gate._semaphore.release()
