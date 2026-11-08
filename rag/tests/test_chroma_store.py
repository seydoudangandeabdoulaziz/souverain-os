from __future__ import annotations

from pathlib import Path

import pytest
from souverain_rag.chroma_store import (
    ChromaVectorIndex,
    client_chroma_from_env,
    collection_name_pour_manifest,
    construire_collection_chroma,
    passages_autorises,
)
from souverain_rag.chunking import Passage
from souverain_rag.errors import IndexIntegrityError, RagError

from .support import manifeste_valide


class _Collection:
    def __init__(
        self,
        metadata: dict[str, object],
        passage: Passage,
        *,
        returned_text: str | None = None,
        returned_synthetic: object = True,
        extra_metadata: bool = False,
    ) -> None:
        self.metadata = metadata
        self.passage = passage
        self.returned_text = returned_text or passage.text
        self.returned_synthetic = returned_synthetic
        self.extra_metadata = extra_metadata

    def count(self) -> int:
        return int(self.metadata["passage_count"])

    def query(self, **_kwargs):
        metadata = {
            "document_id": self.passage.document_id,
            "title": self.passage.title,
            "publisher": self.passage.publisher,
            "source_url": self.passage.source_url,
            "page_number": self.passage.page_number,
            "synthetic": self.returned_synthetic,
        }
        if self.extra_metadata:
            metadata["unexpected"] = "value"
        return {
            "ids": [[self.passage.passage_id]],
            "documents": [[self.returned_text]],
            "metadatas": [[metadata]],
            "distances": [[0.1]],
        }


class _Client:
    def __init__(self, collection: _Collection) -> None:
        self.collection = collection

    def get_collection(self, **_kwargs) -> _Collection:
        return self.collection


def test_chroma_refuse_si_le_jeton_est_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SOUVERAIN_RAG_CHROMA_TOKEN", raising=False)
    with pytest.raises(RagError, match="jeton"):
        client_chroma_from_env()


def _index_fixture(tmp_path, **collection_options):
    manifest = manifeste_valide(tmp_path)
    manifest_path = Path(manifest.manifest_path)
    _, passages = passages_autorises(manifest_path)
    metadata = {
        "corpus_id": manifest.corpus_id,
        "manifest_sha256": manifest.manifest_sha256,
        "model_fingerprint": "e5-pinned",
        "passage_count": len(passages),
    }
    collection = _Collection(metadata, passages[0], **collection_options)
    index = ChromaVectorIndex(
        _Client(collection),
        collection_name_pour_manifest(manifest),
        "e5-pinned",
        manifest_path,
    )
    return index, manifest, passages, collection


def test_chroma_revalide_manifeste_et_retourne_passages_sourcés(tmp_path) -> None:
    index, _manifest, passages, _collection = _index_fixture(tmp_path)
    result = index.search((0.0,) * 384)[0]
    assert result.text == passages[0].text
    assert result.source_url == "https://example.invalid/ref"
    assert result.score == pytest.approx(0.9)


def test_chroma_refuse_un_texte_qui_ne_correspond_pas_a_la_source(tmp_path) -> None:
    index, *_ = _index_fixture(tmp_path, returned_text="Passage substitué")
    with pytest.raises(IndexIntegrityError, match="provenance"):
        index.search((0.0,) * 384)


def test_chroma_refuse_synthetic_entier_meme_si_vrai_en_python(tmp_path) -> None:
    index, *_ = _index_fixture(tmp_path, returned_synthetic=1)
    with pytest.raises(IndexIntegrityError, match="provenance"):
        index.search((0.0,) * 384)


def test_chroma_refuse_une_metadonnee_de_passage_inconnue(tmp_path) -> None:
    index, *_ = _index_fixture(tmp_path, extra_metadata=True)
    with pytest.raises(IndexIntegrityError, match="provenance"):
        index.search((0.0,) * 384)


def test_chroma_refuse_une_collection_d_un_autre_modele(tmp_path) -> None:
    manifest = manifeste_valide(tmp_path)
    _, passages = passages_autorises(manifest.manifest_path)
    metadata = {
        "corpus_id": manifest.corpus_id,
        "manifest_sha256": manifest.manifest_sha256,
        "model_fingerprint": "autre-modele",
        "passage_count": 1,
    }
    with pytest.raises(IndexIntegrityError):
        ChromaVectorIndex(
            _Client(_Collection(metadata, passages[0])),
            collection_name_pour_manifest(manifest),
            "e5-pinned",
            manifest.manifest_path,
        )


def test_chroma_refuse_metadonnee_de_collection_inconnue(tmp_path) -> None:
    manifest = manifeste_valide(tmp_path)
    _, passages = passages_autorises(manifest.manifest_path)
    metadata = {
        "corpus_id": manifest.corpus_id,
        "manifest_sha256": manifest.manifest_sha256,
        "model_fingerprint": "e5-pinned",
        "passage_count": len(passages),
        "unexpected": "value",
    }
    with pytest.raises(IndexIntegrityError, match="collection Chroma"):
        ChromaVectorIndex(
            _Client(_Collection(metadata, passages[0])),
            collection_name_pour_manifest(manifest),
            "e5-pinned",
            manifest.manifest_path,
        )


class _PartialCollection:
    def __init__(
        self,
        metadata: dict[str, object],
        *,
        count: int = 1,
        records: dict[str, object] | None = None,
    ) -> None:
        self.metadata = metadata
        self._count = count
        self.records = records
        self.add_calls = 0

    def count(self) -> int:
        return self._count

    def get(self, **_kwargs):
        assert self.records is not None
        return self.records

    def add(self, **_kwargs) -> None:
        self.add_calls += 1


class _PartialClient:
    def __init__(self, collection: _PartialCollection) -> None:
        self.collection = collection

    def get_or_create_collection(self, **_kwargs) -> _PartialCollection:
        return self.collection


def test_ingestion_interrompue_refuse_sans_supprimer_ni_completer(tmp_path) -> None:
    manifest = manifeste_valide(tmp_path)
    passages = (
        Passage(
            "public-001:1:a",
            "public-001",
            "Référence publique",
            "Éditeur public",
            "https://example.invalid/ref",
            1,
            "Passage synthétique un.",
            True,
        ),
        Passage(
            "public-001:1:b",
            "public-001",
            "Référence publique",
            "Éditeur public",
            "https://example.invalid/ref",
            1,
            "Passage synthétique deux.",
            True,
        ),
    )
    metadata = {
        "corpus_id": manifest.corpus_id,
        "manifest_sha256": manifest.manifest_sha256,
        "model_fingerprint": "e5-pinned",
        "passage_count": len(passages),
    }
    partial = _PartialCollection(metadata)

    class MustNotEncode:
        fingerprint = "e5-pinned"

        def encode_passages(self, texts: list[str]) -> list[tuple[float, ...]]:
            raise AssertionError("La collection partielle ne doit pas être complétée.")

        def encode_query(self, text: str) -> tuple[float, ...]:
            raise AssertionError("Aucune requête ne doit être encodée.")

    with pytest.raises(IndexIntegrityError, match="conservée sans modification"):
        construire_collection_chroma(
            _PartialClient(partial), manifest, passages, MustNotEncode()
        )

    assert partial.add_calls == 0


@pytest.mark.parametrize("tamper", [False, True])
def test_ingestion_existante_ne_reutilise_que_les_passages_identiques(tmp_path, tamper) -> None:
    manifest = manifeste_valide(tmp_path)
    _, passages = passages_autorises(manifest.manifest_path)
    passage = passages[0]
    metadata = {
        "corpus_id": manifest.corpus_id,
        "manifest_sha256": manifest.manifest_sha256,
        "model_fingerprint": "e5-pinned",
        "passage_count": 1,
    }
    passage_metadata = {
        "document_id": passage.document_id,
        "title": passage.title,
        "publisher": passage.publisher,
        "source_url": passage.source_url,
        "page_number": passage.page_number,
        "synthetic": passage.synthetic,
    }
    existing = _PartialCollection(
        metadata,
        count=1,
        records={
            "ids": [passage.passage_id],
            "documents": ["contenu modifié" if tamper else passage.text],
            "metadatas": [passage_metadata],
        },
    )

    class MustNotEncode:
        fingerprint = "e5-pinned"

        def encode_passages(self, texts: list[str]) -> list[tuple[float, ...]]:
            raise AssertionError("Une collection complète n'a pas à être réindexée.")

        def encode_query(self, text: str) -> tuple[float, ...]:
            raise AssertionError("Aucune requête ne doit être encodée.")

    if tamper:
        with pytest.raises(IndexIntegrityError, match="récupération manuelle"):
            construire_collection_chroma(
                _PartialClient(existing), manifest, passages, MustNotEncode()
            )
    else:
        assert (
            construire_collection_chroma(
                _PartialClient(existing), manifest, passages, MustNotEncode()
            )
            == collection_name_pour_manifest(manifest)
        )
    assert existing.add_calls == 0
