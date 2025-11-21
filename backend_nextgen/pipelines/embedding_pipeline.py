"""
Utilities for building semantic indexes used by the dual-encoder retriever.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Dict

import numpy as np

from backend_nextgen.config.loader import load_config
from backend_nextgen.retrieval.dual_encoder import DualEncoderRetriever

import faiss  # type: ignore

@dataclass
class IndexArtifacts:
    embeddings: np.ndarray
    metadata: List[Dict[str, str]]


def load_products(jsonl_path: Path) -> Iterable[Dict[str, str]]:
    """
    Stream product metadata from a JSONL export.
    """
    with jsonl_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            yield json.loads(line)


def build_embeddings(dataset_path: Path, model_name: str) -> IndexArtifacts:
    """
    Encode product titles/descriptions into dense vectors.
    """
    items = list(load_products(dataset_path))
    retriever = DualEncoderRetriever(
        model_name=model_name,
        index=np.zeros((1, 1)),  # temporary placeholder
        metadata=[{"item_id": "0"}],
    )
    texts = [item.get("title", "") + " " + item.get("description", "") for item in items]
    embeddings = retriever.embed(texts)
    metadata = [{"item_id": item.get("item_id", str(idx)), **item} for idx, item in enumerate(items)]
    return IndexArtifacts(embeddings=embeddings, metadata=metadata)


def persist_index(artifacts: IndexArtifacts, index_path: Path, metadata_path: Path) -> None:
    """
    Save embedding matrix and metadata to disk; optionally create FAISS index.
    """
    index_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)

    np.save(index_path, artifacts.embeddings)
    np.save(metadata_path, np.array(artifacts.metadata, dtype=object))

    dim = artifacts.embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(artifacts.embeddings.astype(np.float32))
    faiss.write_index(index, str(index_path.with_suffix(".faiss")))


def run_embedding_pipeline(dataset_path: Path | None = None) -> None:
    """
    Orchestrate embedding creation using the config defaults.
    """
    config = load_config()
    retrieval_cfg = config.section("retrieval")

    if dataset_path is None:
        dataset_path = Path("data/products.jsonl")

    artifacts = build_embeddings(dataset_path, retrieval_cfg["encoder_name"])
    index_path = Path(retrieval_cfg["index_path"])
    metadata_path = Path(retrieval_cfg["metadata_store"])
    persist_index(artifacts, index_path=index_path, metadata_path=metadata_path)
