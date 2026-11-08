"""Validation fail-closed de provenance, empreintes et droits."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from souverain_rag.errors import IngestionBlocked, ManifestError

MANIFEST_VERSION = "souverain-rag-manifest-v1"
MAX_MANIFEST_BYTES = 2_000_000
MAX_DOCUMENTS = 100
MAX_SOURCE_BYTES = 25_000_000
MAX_CORPUS_BYTES = 250_000_000
REQUIRED_OPERATIONS = frozenset(
    {"extract", "local_storage", "embedding", "vector_index", "display_passages"}
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class AuthorizedDocument:
    document_id: str
    title: str
    publisher: str
    source_url: str
    published_at: str
    acquired_at: str
    language: str
    synthetic: bool
    source_path: Path
    source_bytes: bytes
    source_sha256: str
    manifest_root: Path


@dataclass(frozen=True, slots=True)
class ValidatedManifest:
    corpus_id: str
    manifest_path: Path
    manifest_sha256: str
    documents: tuple[AuthorizedDocument, ...]


def _required_text(obj: dict[str, Any], key: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"Champ obligatoire invalide : {key}.")
    return value.strip()


def _resolve_file(root: Path, relative: str, label: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute():
        raise ManifestError(f"{label} doit être un chemin relatif au corpus.")
    resolved = (root / candidate).resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ManifestError(f"{label} sort du répertoire du corpus.") from exc
    if not resolved.exists() or not resolved.is_file():
        raise ManifestError(f"{label} doit désigner un fichier régulier.")
    return resolved


def valider_manifeste(path: Path) -> ValidatedManifest:
    """Valide toutes les preuves avant toute extraction ou écriture d'index."""
    manifest_path = path.resolve(strict=True)
    if not manifest_path.is_file() or manifest_path.stat().st_size > MAX_MANIFEST_BYTES:
        raise ManifestError("Manifeste absent, non régulier ou trop volumineux.")
    raw = manifest_path.read_bytes()
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManifestError("Le manifeste doit être un JSON UTF-8 valide.") from exc
    if not isinstance(payload, dict) or set(payload) != {
        "manifest_version",
        "corpus_id",
        "documents",
    }:
        raise ManifestError("La structure racine du manifeste est invalide.")
    if payload["manifest_version"] != MANIFEST_VERSION:
        raise ManifestError("Version de manifeste non prise en charge.")
    corpus_id = _required_text(payload, "corpus_id")
    raw_documents = payload["documents"]
    if not isinstance(raw_documents, list) or not raw_documents:
        raise ManifestError("Le manifeste doit contenir au moins une source.")
    if len(raw_documents) > MAX_DOCUMENTS:
        raise ManifestError("Le nombre de sources dépasse la limite MVP.")

    root = manifest_path.parent.resolve(strict=True)
    prepared: list[tuple[dict[str, Any], dict[str, Any], Path, Path]] = []
    seen_ids: set[str] = set()
    total_size = 0
    # Premier passage : les droits sont contrôlés avant l'accès aux fichiers source.
    for record in raw_documents:
        if not isinstance(record, dict) or set(record) != {
            "document_id",
            "title",
            "publisher",
            "source_url",
            "published_at",
            "acquired_at",
            "language",
            "synthetic",
            "source_path",
            "sha256",
            "rights",
        }:
            raise ManifestError("Champs de source invalides ou inconnus.")
        document_id = _required_text(record, "document_id")
        if document_id in seen_ids:
            raise ManifestError("Les identifiants de sources doivent être uniques.")
        seen_ids.add(document_id)
        rights = record["rights"]
        if not isinstance(rights, dict) or set(rights) != {
            "status",
            "proof_path",
            "proof_sha256",
            "allowed_operations",
            "validated_by",
            "validated_at",
        }:
            raise IngestionBlocked(f"Droits incomplets pour {document_id}.")
        if rights.get("status") != "approved":
            raise IngestionBlocked(f"Droits non approuvés pour {document_id}.")
        operations = rights.get("allowed_operations")
        if not isinstance(operations, list) or not REQUIRED_OPERATIONS.issubset(
            {item for item in operations if isinstance(item, str)}
        ):
            raise IngestionBlocked(
                f"La permission ne couvre pas tous les usages pour {document_id}."
            )
        try:
            date.fromisoformat(_required_text(rights, "validated_at"))
            date.fromisoformat(_required_text(record, "published_at"))
            date.fromisoformat(_required_text(record, "acquired_at"))
        except ValueError as exc:
            raise ManifestError("Les dates du manifeste doivent être ISO YYYY-MM-DD.") from exc
        proof = _resolve_file(root, _required_text(rights, "proof_path"), "La preuve de droits")
        proof_hash = _required_text(rights, "proof_sha256").lower()
        if len(proof_hash) != 64 or sha256_file(proof) != proof_hash:
            raise IngestionBlocked(f"Preuve de droits absente ou altérée pour {document_id}.")
        _required_text(rights, "validated_by")
        source = _resolve_file(root, _required_text(record, "source_path"), "La source")
        size = source.stat().st_size
        total_size += size
        if size <= 0 or size > MAX_SOURCE_BYTES:
            raise ManifestError(f"Taille de source hors limites pour {document_id}.")
        if source.suffix.lower() not in {".pdf", ".txt", ".md"}:
            raise ManifestError("Formats pris en charge : PDF, TXT et Markdown.")
        prepared.append((record, rights, source, proof))

    if total_size > MAX_CORPUS_BYTES:
        raise ManifestError("Taille totale du corpus supérieure à la limite MVP.")

    documents: list[AuthorizedDocument] = []
    actual_total_size = 0
    for record, _, source, _ in prepared:
        # Keep the exact byte sequence that is hashed. Extraction must not
        # reopen the mutable path after this validation step.
        with source.open("rb") as source_file:
            source_bytes = source_file.read(MAX_SOURCE_BYTES + 1)
        if not source_bytes or len(source_bytes) > MAX_SOURCE_BYTES:
            raise ManifestError(f"Taille de source hors limites pour {record['document_id']}.")
        actual_total_size += len(source_bytes)
        if actual_total_size > MAX_CORPUS_BYTES:
            raise ManifestError("Taille totale du corpus supérieure à la limite MVP.")
        expected_hash = _required_text(record, "sha256").lower()
        if len(expected_hash) != 64 or hashlib.sha256(source_bytes).hexdigest() != expected_hash:
            raise ManifestError(f"Empreinte SHA-256 incorrecte pour {record['document_id']}.")
        synthetic = record["synthetic"]
        if not isinstance(synthetic, bool):
            raise ManifestError("Le champ synthetic doit être booléen.")
        documents.append(
            AuthorizedDocument(
                document_id=record["document_id"],
                title=_required_text(record, "title"),
                publisher=_required_text(record, "publisher"),
                source_url=_validate_source_url(_required_text(record, "source_url")),
                published_at=_required_text(record, "published_at"),
                acquired_at=_required_text(record, "acquired_at"),
                language=_required_text(record, "language"),
                synthetic=synthetic,
                source_path=source,
                source_bytes=source_bytes,
                source_sha256=expected_hash,
                manifest_root=root,
            )
        )
    return ValidatedManifest(
        corpus_id=corpus_id,
        manifest_path=manifest_path,
        manifest_sha256=hashlib.sha256(raw).hexdigest(),
        documents=tuple(documents),
    )


def _validate_source_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ManifestError("La référence source doit être une URL HTTPS sans identifiants.")
    return value
