"""Accès au Chroma serveur authentifié pour l'usage applicatif MVP."""

from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path
from typing import Any

from souverain_rag.chunking import Passage
from souverain_rag.embedder import MODEL_DIMENSION, Embedder
from souverain_rag.errors import IndexIntegrityError, RagError
from souverain_rag.index import SearchResult
from souverain_rag.manifest import ValidatedManifest, valider_manifeste

_BATCH_SIZE = 32
_COLLECTION_METADATA_KEYS = frozenset(
    {"corpus_id", "manifest_sha256", "model_fingerprint", "passage_count"}
)
_PASSAGE_METADATA_KEYS = frozenset(
    {"document_id", "title", "publisher", "source_url", "page_number", "synthetic"}
)


def collection_name_pour_manifest(manifest: ValidatedManifest) -> str:
    suffix = hashlib.sha256(
        f"{manifest.corpus_id}:{manifest.manifest_sha256}".encode()
    ).hexdigest()[:20]
    return f"rag_{suffix}"


def client_chroma_from_env() -> Any:
    host = os.environ.get("SOUVERAIN_RAG_CHROMA_HOST", "127.0.0.1")
    try:
        port = int(os.environ.get("SOUVERAIN_RAG_CHROMA_PORT", "8000"))
    except ValueError as exc:
        raise RagError("Port Chroma invalide.") from exc
    token = os.environ.get("SOUVERAIN_RAG_CHROMA_TOKEN")
    if not token or not 1 <= port <= 65535:
        raise RagError("La connexion Chroma doit être configurée avec un jeton.")
    try:
        import chromadb

        return chromadb.HttpClient(
            host=host,
            port=port,
            headers={"Authorization": f"Bearer {token}"},
        )
    except Exception as exc:
        raise RagError("Connexion impossible au serveur Chroma authentifié.") from exc


def _metadonnees_collection_valides(
    actual: object, expected: dict[str, str | int]
) -> bool:
    if not isinstance(actual, dict) or set(actual) != _COLLECTION_METADATA_KEYS:
        return False
    return (
        type(actual.get("corpus_id")) is str
        and type(actual.get("manifest_sha256")) is str
        and type(actual.get("model_fingerprint")) is str
        and type(actual.get("passage_count")) is int
        and actual == expected
    )


def _metadonnees_passage(passage: Passage) -> dict[str, str | int | bool]:
    return {
        "document_id": passage.document_id,
        "title": passage.title,
        "publisher": passage.publisher,
        "source_url": passage.source_url,
        "page_number": passage.page_number,
        "synthetic": passage.synthetic,
    }


def _metadonnees_passage_valides(actual: object, expected: dict[str, str | int | bool]) -> bool:
    if not isinstance(actual, dict) or set(actual) != _PASSAGE_METADATA_KEYS:
        return False
    return (
        type(actual.get("document_id")) is str
        and type(actual.get("title")) is str
        and type(actual.get("publisher")) is str
        and type(actual.get("source_url")) is str
        and type(actual.get("page_number")) is int
        and type(actual.get("synthetic")) is bool
        and actual == expected
    )


def _collection_existante_conforme(collection: Any, passages: tuple[Passage, ...]) -> bool:
    """Autorise le no-op d'une ingestion identique, sans faire confiance au compte seul."""
    records = collection.get(include=["documents", "metadatas"])
    ids = records.get("ids")
    documents = records.get("documents")
    metadatas = records.get("metadatas")
    if not isinstance(ids, list) or not isinstance(documents, list) or not isinstance(
        metadatas, list
    ):
        return False
    if not (len(ids) == len(documents) == len(metadatas) == len(passages)):
        return False
    expected = {passage.passage_id: passage for passage in passages}
    if len(expected) != len(passages) or set(ids) != set(expected):
        return False
    actual_by_id = dict(zip(ids, zip(documents, metadatas, strict=True), strict=True))
    return all(
        actual_by_id[passage_id][0] == passage.text
        and _metadonnees_passage_valides(
            actual_by_id[passage_id][1], _metadonnees_passage(passage)
        )
        for passage_id, passage in expected.items()
    )


def construire_collection_chroma(
    client: Any,
    manifest: ValidatedManifest,
    passages: tuple[Passage, ...],
    embedder: Embedder,
) -> str:
    if not passages:
        raise RagError("Aucun passage textuel à indexer.")
    name = collection_name_pour_manifest(manifest)
    metadata: dict[str, str | int] = {
        "corpus_id": manifest.corpus_id,
        "manifest_sha256": manifest.manifest_sha256,
        "model_fingerprint": embedder.fingerprint,
        "passage_count": len(passages),
    }
    try:
        collection = client.get_or_create_collection(
            name=name,
            metadata=metadata,
            embedding_function=None,
            configuration={"hnsw": {"space": "cosine"}},
        )
        existing_count = collection.count()
        if type(existing_count) is not int or existing_count < 0:
            raise IndexIntegrityError("Le nombre de passages de la collection est invalide.")
        if not _metadonnees_collection_valides(collection.metadata, metadata):
            raise IndexIntegrityError(
                "Métadonnées de collection incohérentes ; collection conservée sans modification."
            )
        if existing_count:
            if existing_count == len(passages) and _collection_existante_conforme(
                collection, passages
            ):
                return name
            raise IndexIntegrityError(
                "Collection partielle ou incohérente ; conservée sans modification. "
                "Une récupération manuelle est requise."
            )
        for offset in range(0, len(passages), _BATCH_SIZE):
            batch = passages[offset : offset + _BATCH_SIZE]
            vectors = embedder.encode_passages([passage.text for passage in batch])
            collection.add(
                ids=[passage.passage_id for passage in batch],
                embeddings=[list(vector) for vector in vectors],
                documents=[passage.text for passage in batch],
                metadatas=[_metadonnees_passage(passage) for passage in batch],
            )
    except RagError:
        raise
    except Exception as exc:
        raise RagError("Échec de création de collection Chroma authentifiée.") from exc
    return name


class ChromaVectorIndex:
    """Vue en lecture seule applicative sur une collection Chroma serveur."""

    def __init__(
        self,
        client: Any,
        collection_name: str,
        expected_model: str,
        manifest_path: Path,
    ) -> None:
        current, passages = passages_autorises(manifest_path)
        if collection_name != collection_name_pour_manifest(current):
            raise IndexIntegrityError("La collection ne correspond pas au manifeste validé.")
        try:
            collection = client.get_collection(name=collection_name, embedding_function=None)
        except Exception as exc:
            raise IndexIntegrityError("Collection Chroma introuvable ou inaccessible.") from exc
        metadata = collection.metadata
        expected_metadata: dict[str, str | int] = {
            "corpus_id": current.corpus_id,
            "manifest_sha256": current.manifest_sha256,
            "model_fingerprint": expected_model,
            "passage_count": len(passages),
        }
        try:
            actual_count = collection.count()
        except Exception as exc:
            raise IndexIntegrityError("Impossible de vérifier le nombre de passages.") from exc
        if (
            not _metadonnees_collection_valides(metadata, expected_metadata)
            or type(actual_count) is not int
            or actual_count != len(passages)
        ):
            raise IndexIntegrityError("La collection Chroma ne correspond pas au manifeste/modèle.")
        self._collection = collection
        self._corpus_id = current.corpus_id
        self._manifest_sha256 = current.manifest_sha256
        self._model_fingerprint = expected_model
        self._documents = {document.document_id: document for document in current.documents}
        self._passages = {
            passage.passage_id: (
                passage.document_id,
                passage.page_number,
                hashlib.sha256(passage.text.encode("utf-8")).digest(),
            )
            for passage in passages
        }

    @property
    def model_fingerprint(self) -> str:
        return self._model_fingerprint

    @property
    def corpus_id(self) -> str:
        return self._corpus_id

    def search(self, query: tuple[float, ...], k: int = 5) -> tuple[SearchResult, ...]:
        if len(query) != MODEL_DIMENSION or not 1 <= k <= 10:
            raise RagError("Dimension de requête ou nombre de résultats invalide.")
        try:
            response = self._collection.query(
                query_embeddings=[list(query)],
                n_results=k,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            raise RagError("La recherche Chroma a échoué.") from exc
        ids = response["ids"][0]
        documents = response["documents"][0]
        metadatas = response["metadatas"][0]
        distances = response["distances"][0]
        results: list[SearchResult] = []
        for passage_id, document, metadata, distance in zip(
            ids, documents, metadatas, distances, strict=True
        ):
            if (
                not isinstance(metadata, dict)
                or set(metadata) != _PASSAGE_METADATA_KEYS
                or not isinstance(passage_id, str)
            ):
                raise IndexIntegrityError("La provenance du passage retourné est invalide.")
            source_id = metadata.get("document_id")
            title = metadata.get("title")
            publisher = metadata.get("publisher")
            source_url = metadata.get("source_url")
            page_number = metadata.get("page_number")
            synthetic = metadata.get("synthetic")
            expected_passage = self._passages.get(passage_id)
            source = self._documents.get(source_id) if type(source_id) is str else None
            if (
                source is None
                or type(page_number) is not int
                or page_number < 1
                or expected_passage is None
                or expected_passage[0] != source.document_id
                or expected_passage[1] != page_number
                or type(title) is not str
                or title != source.title
                or type(publisher) is not str
                or publisher != source.publisher
                or type(source_url) is not str
                or source_url != source.source_url
                or type(synthetic) is not bool
                or synthetic is not source.synthetic
                or not isinstance(document, str)
                or not document
                or hashlib.sha256(document.encode("utf-8")).digest() != expected_passage[2]
                or isinstance(distance, bool)
                or not isinstance(distance, (int, float))
                or not math.isfinite(distance)
            ):
                raise IndexIntegrityError("La provenance du passage retourné est incohérente.")
            results.append(
                SearchResult(
                    passage_id=passage_id,
                    document_id=source.document_id,
                    title=source.title,
                    publisher=source.publisher,
                    source_url=source.source_url,
                    page_number=page_number,
                    text=document,
                    synthetic=source.synthetic,
                    score=1.0 - float(distance),
                )
            )
        return tuple(results)

    def close(self) -> None:
        """Le client HTTP Chroma n'expose pas de ressource de fichier à fermer."""

    def __enter__(self) -> ChromaVectorIndex:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def passages_autorises(manifest_path: Path) -> tuple[ValidatedManifest, tuple[Passage, ...]]:
    """Validation des droits avant toute ouverture/extraction de source."""
    from souverain_rag.chunking import decouper_pages
    from souverain_rag.extract import extraire

    manifest = valider_manifeste(manifest_path)
    passages: list[Passage] = []
    for document in manifest.documents:
        passages.extend(
            decouper_pages(
                document.document_id,
                document.title,
                document.publisher,
                document.source_url,
                extraire(document),
                document.synthetic,
            )
        )
    return manifest, tuple(passages)
