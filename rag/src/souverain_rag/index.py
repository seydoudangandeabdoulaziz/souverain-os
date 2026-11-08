"""Index vectoriel local exact fondé sur SQLite et des vecteurs float32."""

from __future__ import annotations

import json
import math
import os
import sqlite3
import struct
import tempfile
from dataclasses import dataclass
from pathlib import Path

from souverain_rag.chunking import Passage
from souverain_rag.embedder import MODEL_DIMENSION, Embedder
from souverain_rag.errors import IndexIntegrityError, RagError
from souverain_rag.manifest import ValidatedManifest, sha256_file, valider_manifeste

DB_NAME = "rag-index.sqlite3"
RECEIPT_NAME = "rag-index-receipt.json"


@dataclass(frozen=True, slots=True)
class SearchResult:
    passage_id: str
    document_id: str
    title: str
    publisher: str
    source_url: str
    page_number: int
    text: str
    synthetic: bool
    score: float


def _pack(vector: tuple[float, ...]) -> bytes:
    if len(vector) != MODEL_DIMENSION:
        raise RagError("Dimension d'embedding incorrecte.")
    return struct.pack(f"<{MODEL_DIMENSION}f", *vector)


def _unpack(blob: bytes) -> tuple[float, ...]:
    if len(blob) != MODEL_DIMENSION * 4:
        raise IndexIntegrityError("Vecteur de dimension ou taille invalide.")
    return struct.unpack(f"<{MODEL_DIMENSION}f", blob)


def construire_index(
    output_dir: Path,
    manifest: ValidatedManifest,
    passages: tuple[Passage, ...],
    embedder: Embedder,
) -> Path:
    if not passages:
        raise RagError("Aucun passage textuel à indexer.")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_dir = output_dir.resolve(strict=True)
    temp_fd, temp_name = tempfile.mkstemp(prefix=".rag-index-", suffix=".sqlite3", dir=output_dir)
    os.close(temp_fd)
    temporary = Path(temp_name)
    index_path = output_dir / DB_NAME
    receipt_path = output_dir / RECEIPT_NAME
    try:
        with sqlite3.connect(temporary) as connection:
            connection.execute("PRAGMA journal_mode=DELETE")
            connection.execute("PRAGMA synchronous=FULL")
            connection.executescript(
                """
                CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE passages (
                    passage_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    publisher TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    page_number INTEGER NOT NULL CHECK (page_number > 0),
                    text TEXT NOT NULL,
                    synthetic INTEGER NOT NULL CHECK (synthetic IN (0, 1)),
                    vector BLOB NOT NULL
                );
                CREATE INDEX passages_by_document ON passages(document_id, page_number);
                """
            )
            vectors = embedder.encode_passages([passage.text for passage in passages])
            if len(vectors) != len(passages):
                raise RagError("Le nombre de vecteurs ne correspond pas au nombre de passages.")
            metadata = {
                "corpus_id": manifest.corpus_id,
                "manifest_sha256": manifest.manifest_sha256,
                "model_fingerprint": embedder.fingerprint,
                "passage_count": str(len(passages)),
            }
            connection.executemany(
                "INSERT INTO metadata(key, value) VALUES (?, ?)", metadata.items()
            )
            connection.executemany(
                """INSERT INTO passages VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    (
                        passage.passage_id,
                        passage.document_id,
                        passage.title,
                        passage.publisher,
                        passage.source_url,
                        passage.page_number,
                        passage.text,
                        int(passage.synthetic),
                        _pack(vector),
                    )
                    for passage, vector in zip(passages, vectors, strict=True)
                ),
            )
        os.replace(temporary, index_path)
        receipt = {
            "receipt_version": "souverain-rag-index-v1",
            "corpus_id": manifest.corpus_id,
            "manifest_sha256": manifest.manifest_sha256,
            "index_sha256": sha256_file(index_path),
            "model_fingerprint": embedder.fingerprint,
            "passage_count": len(passages),
        }
        _write_json_atomic(receipt_path, receipt)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return index_path


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    fd, temp_name = tempfile.mkstemp(prefix=".rag-receipt-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    except Exception:
        Path(temp_name).unlink(missing_ok=True)
        raise


class VectorIndex:
    def __init__(self, index_path: Path, expected_model: str, manifest_path: Path) -> None:
        self.index_path = index_path.resolve(strict=True)
        receipt_path = self.index_path.parent / RECEIPT_NAME
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise IndexIntegrityError("Reçu d'index absent ou invalide.") from exc
        if receipt.get("index_sha256") != sha256_file(self.index_path):
            raise IndexIntegrityError("L'empreinte de l'index a changé.")
        if receipt.get("model_fingerprint") != expected_model:
            raise IndexIntegrityError("L'index n'est pas lié au modèle E5 configuré.")
        try:
            current_manifest = valider_manifeste(manifest_path)
        except RagError as exc:
            raise IndexIntegrityError("Le manifeste courant n'autorise plus ce corpus.") from exc
        if current_manifest.manifest_sha256 != receipt.get("manifest_sha256"):
            raise IndexIntegrityError("Le manifeste a changé depuis la construction de l'index.")
        connection = sqlite3.connect(self.index_path.as_uri() + "?mode=ro", uri=True)
        self._connection: sqlite3.Connection | None = connection
        connection.row_factory = sqlite3.Row
        metadata = dict(connection.execute("SELECT key, value FROM metadata").fetchall())
        if metadata.get("model_fingerprint") != expected_model:
            self.close()
            raise IndexIntegrityError("Métadonnées de modèle incohérentes dans l'index.")
        if metadata.get("manifest_sha256") != receipt.get("manifest_sha256"):
            self.close()
            raise IndexIntegrityError("Manifeste et index ne correspondent pas.")
        if metadata.get("corpus_id") != receipt.get("corpus_id"):
            self.close()
            raise IndexIntegrityError("Identifiant de corpus incohérent dans l'index.")
        if int(metadata.get("passage_count", "-1")) != receipt.get("passage_count"):
            self.close()
            raise IndexIntegrityError("Nombre de passages incohérent dans l'index.")
        self.corpus_id = metadata["corpus_id"]
        self.manifest_sha256 = metadata["manifest_sha256"]
        self._model_fingerprint = expected_model

    @property
    def model_fingerprint(self) -> str:
        return self._model_fingerprint

    def search(self, query: tuple[float, ...], k: int = 5) -> tuple[SearchResult, ...]:
        if len(query) != MODEL_DIMENSION:
            raise RagError("Dimension de requête incorrecte.")
        if not 1 <= k <= 10:
            raise RagError("Le nombre de résultats doit être entre 1 et 10.")
        connection = self._connection
        if connection is None:
            raise RagError("L'index local est fermé.")
        rows = connection.execute(
            "SELECT passage_id, document_id, title, publisher, source_url, page_number, text, "
            "synthetic, vector FROM passages"
        )
        scored: list[SearchResult] = []
        for row in rows:
            vector = _unpack(row["vector"])
            score = math.fsum(a * b for a, b in zip(query, vector, strict=True))
            scored.append(
                SearchResult(
                    passage_id=row["passage_id"],
                    document_id=row["document_id"],
                    title=row["title"],
                    publisher=row["publisher"],
                    source_url=row["source_url"],
                    page_number=row["page_number"],
                    text=row["text"],
                    synthetic=bool(row["synthetic"]),
                    score=score,
                )
            )
        scored.sort(key=lambda result: (-result.score, result.passage_id))
        return tuple(scored[:k])

    def close(self) -> None:
        connection = getattr(self, "_connection", None)
        if connection is not None:
            self._connection = None
            connection.close()

    def __enter__(self) -> VectorIndex:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
