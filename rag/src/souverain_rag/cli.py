"""CLI locale d'ingestion et de recherche à types fermés."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

from souverain_rag.chroma_store import (
    ChromaVectorIndex,
    client_chroma_from_env,
    collection_name_pour_manifest,
)
from souverain_rag.embedder import E5SmallEmbedder
from souverain_rag.engine import SearchEngine
from souverain_rag.errors import RagError
from souverain_rag.ingestion import ingerer_chroma
from souverain_rag.manifest import valider_manifeste
from souverain_rag.patterns import PatternType


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="souverain-rag")
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser("ingest", help="Valide puis indexe les sources autorisées.")
    ingest.add_argument("--manifest", type=Path, required=True)
    ingest.add_argument("--model-path", type=Path, default=os.getenv("SOUVERAIN_RAG_MODEL_PATH"))
    search = commands.add_parser("search", help="Recherche par type de pattern fermé.")
    search.add_argument("--manifest", type=Path, required=True)
    search.add_argument("--model-path", type=Path, default=os.getenv("SOUVERAIN_RAG_MODEL_PATH"))
    search.add_argument("--pattern", choices=[item.value for item in PatternType], required=True)
    search.add_argument("--k", type=int, default=5)
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.model_path is None:
        print("SOUVERAIN_RAG_MODEL_PATH ou --model-path est requis.", file=sys.stderr)
        raise SystemExit(2)
    try:
        embedder = E5SmallEmbedder(args.model_path)
        if args.command == "ingest":
            collection_name = ingerer_chroma(args.manifest, embedder)
            print(json.dumps({"collection": collection_name}, ensure_ascii=False))
            return
        manifest = valider_manifeste(args.manifest)
        with ChromaVectorIndex(
            client_chroma_from_env(),
            collection_name_pour_manifest(manifest),
            embedder.fingerprint,
            args.manifest,
        ) as index:
            engine = SearchEngine(index, embedder)
            response = engine.search(PatternType(args.pattern), k=args.k)
            print(
                json.dumps(
                    {
                        "corpus_id": response.corpus_id,
                        "pattern_type": response.pattern_type.value,
                        "results": [asdict(result) for result in response.results],
                    },
                    ensure_ascii=False,
                )
            )
    except RagError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
