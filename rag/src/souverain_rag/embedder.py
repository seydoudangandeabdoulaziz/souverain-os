"""Encodeur E5-small strictement local, CPU, révision et poids épinglés."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Protocol

from souverain_rag.errors import ModelUnavailable, RagError

MODEL_ID = "intfloat/multilingual-e5-small"
MODEL_REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
MODEL_SHA256 = "1a55775f53449dac10a2bcbc312469fac40b96d53198c407081a831f81c98477"
MODEL_DIMENSION = 384
MAX_TOKENS = 512
DEFAULT_THREADS = 4
DEFAULT_BATCH_SIZE = 4


class Embedder(Protocol):
    @property
    def fingerprint(self) -> str: ...

    def encode_passages(self, texts: list[str]) -> list[tuple[float, ...]]: ...

    def encode_query(self, text: str) -> tuple[float, ...]: ...


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as model_file:
        for block in iter(lambda: model_file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class E5SmallEmbedder:
    def __init__(
        self,
        model_path: Path,
        *,
        threads: int = DEFAULT_THREADS,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        if not 1 <= threads <= 4 or not 1 <= batch_size <= 8:
            raise RagError("Threads (1–4) ou batch (1–8) hors limites MVP.")
        model_root = model_path.resolve(strict=True)
        weights = model_root / "model.safetensors"
        if not weights.is_file() or sha256_path(weights) != MODEL_SHA256:
            raise ModelUnavailable("Poids locaux absents ou empreinte E5-small incorrecte.")
        try:
            import torch
            from transformers import AutoModel, AutoTokenizer

            torch.set_num_threads(threads)
            self._torch = torch
            self._tokenizer = AutoTokenizer.from_pretrained(
                model_root, local_files_only=True, trust_remote_code=False
            )
            self._model = AutoModel.from_pretrained(
                model_root,
                local_files_only=True,
                trust_remote_code=False,
                use_safetensors=True,
            ).to("cpu")
            self._model.eval()
        except Exception as exc:
            raise ModelUnavailable(
                "Impossible de charger E5-small localement ; "
                "aucun téléchargement distant n'est tenté."
            ) from exc
        self._batch_size = batch_size
        self._fingerprint = f"{MODEL_ID}@{MODEL_REVISION}:{MODEL_SHA256}"

    @property
    def fingerprint(self) -> str:
        return self._fingerprint

    def encode_passages(self, texts: list[str]) -> list[tuple[float, ...]]:
        return self._encode([f"passage: {text}" for text in texts])

    def encode_query(self, text: str) -> tuple[float, ...]:
        return self._encode([f"query: {text}"])[0]

    def _encode(self, inputs: list[str]) -> list[tuple[float, ...]]:
        torch = self._torch
        vectors: list[tuple[float, ...]] = []
        try:
            with torch.inference_mode():
                for offset in range(0, len(inputs), self._batch_size):
                    encoded = self._tokenizer(
                        inputs[offset : offset + self._batch_size],
                        padding=True,
                        truncation=True,
                        max_length=MAX_TOKENS,
                        return_tensors="pt",
                    )
                    output = self._model(**encoded)
                    mask = encoded["attention_mask"].unsqueeze(-1).to(
                        output.last_hidden_state.dtype
                    )
                    pooled = (output.last_hidden_state * mask).sum(dim=1) / mask.sum(dim=1).clamp(
                        min=1
                    )
                    normalized = torch.nn.functional.normalize(pooled, p=2, dim=1)
                    for row in normalized.cpu().tolist():
                        if len(row) != MODEL_DIMENSION:
                            raise RagError("Dimension E5-small inattendue.")
                        vectors.append(tuple(float(item) for item in row))
        except RagError:
            raise
        except Exception as exc:
            raise RagError("Échec de calcul local des embeddings.") from exc
        return vectors
