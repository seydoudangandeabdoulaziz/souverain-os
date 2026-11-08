from __future__ import annotations

import hashlib
import json
from pathlib import Path

from souverain_rag.manifest import MANIFEST_VERSION, ValidatedManifest, valider_manifeste


def ecrire_corpus_autorise(tmp_path: Path, text: str = "Texte documentaire public.") -> Path:
    (tmp_path / "sources").mkdir(parents=True, exist_ok=True)
    (tmp_path / "rights").mkdir(parents=True, exist_ok=True)
    source = tmp_path / "sources" / "public.txt"
    source.write_text(text, encoding="utf-8")
    proof = tmp_path / "rights" / "permission.txt"
    proof.write_text("Permission vérifiée pour les cinq opérations MVP.", encoding="utf-8")
    record = {
        "document_id": "public-001",
        "title": "Référence publique",
        "publisher": "Éditeur public",
        "source_url": "https://example.invalid/ref",
        "published_at": "2026-01-01",
        "acquired_at": "2026-01-02",
        "language": "fr",
        "synthetic": True,
        "source_path": "sources/public.txt",
        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "rights": {
            "status": "approved",
            "proof_path": "rights/permission.txt",
            "proof_sha256": hashlib.sha256(proof.read_bytes()).hexdigest(),
            "allowed_operations": [
                "extract",
                "local_storage",
                "embedding",
                "vector_index",
                "display_passages",
            ],
            "validated_by": "test-fixture",
            "validated_at": "2026-01-03",
        },
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": MANIFEST_VERSION,
                "corpus_id": "fixture-v1",
                "documents": [record],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return manifest_path


def manifeste_valide(tmp_path: Path) -> ValidatedManifest:
    return valider_manifeste(ecrire_corpus_autorise(tmp_path))
