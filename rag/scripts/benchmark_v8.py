"""Protocole V8 : 10 échauffements et 100 mesures par type, ordre reproductible."""

from __future__ import annotations

import argparse
import json
import os
import platform
import random
import resource
import statistics
import time
from pathlib import Path

from souverain_rag.chroma_store import (
    ChromaVectorIndex,
    client_chroma_from_env,
    collection_name_pour_manifest,
)
from souverain_rag.embedder import E5SmallEmbedder
from souverain_rag.engine import SearchEngine
from souverain_rag.manifest import valider_manifeste
from souverain_rag.patterns import PatternType


def _percentile_95(values: list[float]) -> float:
    """Nearest-rank p95 (95e observation sur 100, protocole V8)."""
    return sorted(values)[94]


def mesurer(model_path: Path, manifest_path: Path) -> dict[str, object]:
    embedder = E5SmallEmbedder(model_path)
    manifest = valider_manifeste(manifest_path)
    with ChromaVectorIndex(
        client_chroma_from_env(),
        collection_name_pour_manifest(manifest),
        embedder.fingerprint,
        manifest_path,
    ) as index:
        engine = SearchEngine(index, embedder)
        patterns = list(PatternType)
        for pattern in patterns:
            for _ in range(10):
                engine.search(pattern, k=5)

        order = patterns * 100
        random.Random(8008).shuffle(order)
        samples: dict[PatternType, list[float]] = {pattern: [] for pattern in patterns}
        for pattern in order:
            started = time.perf_counter()
            engine.search(pattern, k=5)
            samples[pattern].append((time.perf_counter() - started) * 1000)

        memory = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # Linux reports KiB; macOS reports bytes.
        peak_memory_mib = memory / 1024 if platform.system() == "Linux" else memory / 1024**2
        return {
            "protocol": "V8",
            "environment": {
                "platform": platform.platform(),
                "python": platform.python_version(),
                "cpu_count": os.cpu_count(),
                "peak_rss_mib": round(peak_memory_mib, 1),
            },
            "corpus_id": index.corpus_id,
            "model_fingerprint": embedder.fingerprint,
            "warmups_per_pattern": 10,
            "timed_runs_per_pattern": 100,
            "cache_policy": "application cache disabled; OS page cache not flushed",
            "patterns": {
                pattern.value: {
                    "p50_ms": round(statistics.median(values), 3),
                    "p95_ms": round(_percentile_95(values), 3),
                    "max_ms": round(max(values), 3),
                    "under_2s": _percentile_95(values) < 2000,
                }
                for pattern, values in samples.items()
            },
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    arguments = parser.parse_args()
    print(
        json.dumps(
            mesurer(arguments.model, arguments.manifest),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
