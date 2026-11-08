"""Ingestion locale CLI ; aucune donnée d'alerte ou de tenant n'est acceptée."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from souverain_rag.chunking import Passage, decouper_pages
from souverain_rag.embedder import Embedder
from souverain_rag.errors import RagError
from souverain_rag.extract import extraire
from souverain_rag.index import construire_index
from souverain_rag.manifest import ValidatedManifest, valider_manifeste


def ingerer_chroma(
    manifest_path: Path,
    embedder: Embedder,
    client_factory: Callable[[], Any] | None = None,
) -> str:
    """Ingestion CLI vers le serveur Chroma authentifié du déploiement MVP."""
    from souverain_rag.chroma_store import construire_collection_chroma, passages_autorises

    manifest, passages = passages_autorises(manifest_path)
    if not passages:
        raise RagError("Les sources autorisées ne contiennent aucun texte extractible.")
    from souverain_rag.chroma_store import client_chroma_from_env

    client = (client_factory or client_chroma_from_env)()
    return construire_collection_chroma(client, manifest, passages, embedder)


def ingerer(manifest_path: Path, output_dir: Path, embedder: Embedder) -> Path:
    manifest: ValidatedManifest = valider_manifeste(manifest_path)
    passages: list[Passage] = []
    for document in manifest.documents:
        pages = extraire(document)
        passages.extend(
            decouper_pages(
                document.document_id,
                document.title,
                document.publisher,
                document.source_url,
                pages,
                document.synthetic,
            )
        )
    if not passages:
        raise RagError("Les sources autorisées ne contiennent aucun texte extractible.")
    return construire_index(output_dir, manifest, tuple(passages), embedder)
