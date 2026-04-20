"""
Dual-encoder retrieval model for semantic matching between queries and products.

Key improvements over the original:
- Mean pooling (attention-masked) instead of CLS-only — correct for E5/BGE-family models
- FAISS IndexFlatIP for fast cosine search instead of O(N) numpy dot product
- Graceful fallback to numpy when faiss is unavailable
- encode_queries() alias for external callers (e.g. orchestrator personalization)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import torch

try:
    from transformers import AutoModel, AutoTokenizer
except ImportError as exc:
    raise ImportError("Install transformers to use the dual encoder") from exc

try:
    import faiss  # type: ignore
    _FAISS_AVAILABLE = True
except ImportError:
    _FAISS_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    item_id: str
    score: float
    metadata: Dict[str, str]


class DualEncoderRetriever:
    """
    Symmetric encoder that embeds both user queries and product documents.

    Uses mean pooling over non-padding tokens — the correct pooling strategy for
    E5 (intfloat/e5-base-v2) and BGE embedding models, which are trained with
    mean pooling. CLS pooling significantly degrades retrieval quality for these
    models.

    Retrieval uses FAISS IndexFlatIP (exact inner-product search on L2-normalised
    vectors, equivalent to cosine similarity) when faiss-cpu/faiss-gpu is installed.
    Falls back to a brute-force numpy dot product for small corpora or when FAISS
    is unavailable.
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
        self.encoder = AutoModel.from_pretrained(model_name)
        self.device = torch.device(device)
        self.encoder.to(self.device)
        self.encoder.eval()
        self.normalize = normalize
        self.metadata = metadata

        # Normalize corpus embeddings so dot product == cosine similarity
        corpus = index.astype(np.float32)
        if self.normalize and len(corpus) > 0:
            corpus = self._normalize_embeddings(corpus)

        self._dim = corpus.shape[1] if len(corpus) > 0 else 1
        self._faiss_index: Optional[object] = None
        self._corpus_np = corpus  # fallback numpy matrix

        if _FAISS_AVAILABLE and len(corpus) > 0:
            self._faiss_index = faiss.IndexFlatIP(self._dim)
            self._faiss_index.add(corpus)
            logger.info(f"FAISS IndexFlatIP built with {self._faiss_index.ntotal} vectors (dim={self._dim}).")
        elif len(corpus) > 0:
            logger.warning("faiss not installed — using O(N) numpy retrieval. Install faiss-cpu for better performance.")

    # ------------------------------------------------------------------
    # Embedding helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_embeddings(embeddings: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-12
        return embeddings / norms

    @staticmethod
    def _mean_pool(last_hidden_state: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        """
        Compute attention-masked mean pooling.
        Correct pooling for E5, BGE, and similar bi-encoder models.
        """
        mask = attention_mask.unsqueeze(-1).float()  # (B, T, 1)
        summed = (last_hidden_state * mask).sum(dim=1)  # (B, H)
        counts = mask.sum(dim=1).clamp(min=1e-9)       # (B, 1)
        return summed / counts                           # (B, H)

    def embed(self, texts: List[str]) -> np.ndarray:
        """Encode a list of texts into L2-normalised embeddings."""
        encoded = self.tokenizer(
            texts, padding=True, truncation=True, max_length=512, return_tensors="pt"
        ).to(self.device)
        with torch.no_grad():
            outputs = self.encoder(**encoded)
            embeddings = self._mean_pool(outputs.last_hidden_state, encoded["attention_mask"])
        embeddings = embeddings.cpu().numpy().astype(np.float32)
        if self.normalize:
            embeddings = self._normalize_embeddings(embeddings)
        return embeddings

    # Alias used by the orchestrator's personalization boosting stage
    def encode_queries(self, texts: List[str]) -> np.ndarray:
        return self.embed(texts)

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def retrieve(self, query: str, top_k: int = 10) -> List[RetrievalResult]:
        query_emb = self.embed([query])  # (1, dim)

        if self._faiss_index is not None:
            scores_2d, indices_2d = self._faiss_index.search(query_emb, min(top_k, self._faiss_index.ntotal))
            scores = scores_2d[0]
            indices = indices_2d[0]
        else:
            # Numpy fallback — O(N) dot product
            scores_1d = np.dot(self._corpus_np, query_emb[0])
            indices = np.argsort(scores_1d)[::-1][:top_k]
            scores = scores_1d[indices]

        results = []
        for score, idx in zip(scores, indices):
            if idx < 0 or idx >= len(self.metadata):
                continue
            results.append(
                RetrievalResult(
                    item_id=self.metadata[idx].get("item_id", str(idx)),
                    score=float(score),
                    metadata=self.metadata[idx],
                )
            )
        return results

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    @classmethod
    def from_disk(
        cls,
        model_name: str,
        index_path: Path,
        metadata_path: Path,
        device: str | torch.device = "cpu",
    ) -> "DualEncoderRetriever":
        if not index_path.exists() or not metadata_path.exists():
            raise FileNotFoundError("Retrieval assets missing. Run the index builder first.")
        index = np.load(index_path)
        metadata = np.load(metadata_path, allow_pickle=True).tolist()
        return cls(model_name=model_name, index=index, metadata=metadata, device=device)
