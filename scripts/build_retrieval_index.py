"""
Build a retrieval index from the product/query dataset.

Since the project doesn't ship a separate product catalog, this script
treats each unique training query as a "product" (title = query text,
item_id = row index). This gives us a realistic embedding space to run
the retrieval evaluation harness against.

Usage:
    python scripts/build_retrieval_index.py \
        --data   backend/data/train_enriched.csv \
        --outdir backend_nextgen/data/retrieval \
        --model  intfloat/e5-base-v2 \
        --device cuda

Outputs:
    <outdir>/product_index.npy    — float32 embeddings, shape (N, dim)
    <outdir>/product_metadata.npy — object array of dicts with item_id / title
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Embedding helpers (self-contained — no dependency on DualEncoderRetriever)
# ---------------------------------------------------------------------------

def _mean_pool(last_hidden: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
    mask = attention_mask.unsqueeze(-1).float()
    return (last_hidden * mask).sum(1) / mask.sum(1).clamp(min=1e-9)


def embed_texts(texts: list[str], model_name: str, device: str, batch_size: int = 64) -> np.ndarray:
    from transformers import AutoModel, AutoTokenizer
    logger.info(f"Loading encoder: {model_name}")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name).to(device)
    model.eval()

    all_embs: list[np.ndarray] = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start:start + batch_size]
        enc = tokenizer(batch, padding=True, truncation=True, max_length=512, return_tensors="pt").to(device)
        with torch.no_grad():
            out = model(**enc)
            emb = _mean_pool(out.last_hidden_state, enc["attention_mask"])
        emb_np = emb.cpu().float().numpy()
        # L2-normalise (cosine retrieval)
        norms = np.linalg.norm(emb_np, axis=1, keepdims=True) + 1e-12
        all_embs.append(emb_np / norms)
        if (start // batch_size + 1) % 5 == 0:
            logger.info(f"  Embedded {start + len(batch)}/{len(texts)}")

    return np.vstack(all_embs).astype(np.float32)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Build retrieval index from training queries")
    parser.add_argument("--data",   default="backend/data/train_enriched.csv")
    parser.add_argument("--outdir", default="backend_nextgen/data/retrieval")
    parser.add_argument("--model",  default="intfloat/e5-base-v2")
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--batch_size", type=int, default=64)
    args = parser.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        logger.error(f"Data file not found: {data_path}")
        sys.exit(1)

    logger.info(f"Loading data from {data_path}")
    df = pd.read_csv(data_path)

    # Deduplicate queries; use query text as the "product title"
    df = df.drop_duplicates(subset=["query"]).reset_index(drop=True)
    texts = df["query"].tolist()
    logger.info(f"Building index for {len(texts)} unique queries/products")

    # Embed
    embeddings = embed_texts(texts, model_name=args.model, device=args.device, batch_size=args.batch_size)
    logger.info(f"Embeddings shape: {embeddings.shape}")

    # Build metadata list
    metadata = [
        {"item_id": str(i), "title": text}
        for i, text in enumerate(texts)
    ]

    # Save
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    index_path = out / "product_index.npy"
    meta_path  = out / "product_metadata.npy"

    np.save(index_path, embeddings)
    np.save(meta_path, np.array(metadata, dtype=object))

    logger.info(f"Saved embeddings  -> {index_path}")
    logger.info(f"Saved metadata    -> {meta_path}")
    logger.info("Done. Run evaluate_retrieval.py --synthetic to verify the index.")


if __name__ == "__main__":
    main()
