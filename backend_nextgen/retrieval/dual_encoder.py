"""
Dual-encoder retrieval model for semantic matching between queries and products.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import torch

try:
    from transformers import AutoModel, AutoTokenizer
except ImportError as exc:
    raise ImportError("Install transformers to use the dual encoder") from exc


@dataclass
class RetrievalResult:
    item_id: str
    score: float
    metadata: Dict[str, str]


class DualEncoderRetriever:
    """
    Symmetric encoder that embeds both user queries and product documents.
    """

    def __init__(
        self,
        model_name: str,
        index: np.ndarray,
        metadata: List[Dict[str, str]],
        device: str | torch.device = "cpu",
        normalize: bool = True,
    ) -> None:
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.encoder = AutoModel.from_pretrained(model_name, weights_only=False)
        self.device = torch.device(device)
        self.encoder.to(self.device)
        self.normalize = normalize

        self.index = index
        self.metadata = metadata

        if self.normalize:
            self.index = self._normalize_embeddings(self.index)

    @staticmethod
    def _normalize_embeddings(embeddings: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-12
        return embeddings / norms

    def embed(self, texts: List[str]) -> np.ndarray:
        encoded = self.tokenizer(texts, padding=True, truncation=True, return_tensors="pt").to(self.device)
        with torch.no_grad():
            outputs = self.encoder(**encoded)
            embeddings = outputs.last_hidden_state[:, 0, :]  # CLS pooling
        embeddings = embeddings.cpu().numpy()
        if self.normalize:
            embeddings = self._normalize_embeddings(embeddings)
        return embeddings

    def retrieve(self, query: str, top_k: int = 10) -> List[RetrievalResult]:
        query_emb = self.embed([query])[0]
        scores = np.dot(self.index, query_emb)
        top_indices = np.argsort(scores)[::-1][:top_k]
        return [
            RetrievalResult(
                item_id=self.metadata[idx].get("item_id", str(idx)),
                score=float(scores[idx]),
                metadata=self.metadata[idx],
            )
            for idx in top_indices
        ]

    @classmethod
    def from_disk(cls, model_name: str, index_path: Path, metadata_path: Path, device: str | torch.device = "cpu"):
        if not index_path.exists() or not metadata_path.exists():
            raise FileNotFoundError("Retrieval assets missing. Run the index builder first.")
        index = np.load(index_path)
        metadata = np.load(metadata_path, allow_pickle=True).tolist()
        return cls(model_name=model_name, index=index, metadata=metadata, device=device)
