"""
Retrieval evaluation harness for the NextGen dual-encoder.

Computes:
  - Recall@k  (k = 1, 5, 10, 20)
  - MRR       (Mean Reciprocal Rank)
  - NDCG@k    (k = 5, 10)

Input: a JSONL file where each line is:
  {
    "query": "red Nike running shoes under $100",
    "relevant_ids": ["item_123", "item_456"]   // ground-truth relevant item IDs
  }

If no retrieval test file is available the script generates a synthetic
benchmark from the product index itself (each product title is a query,
the product itself is the only relevant result — a sanity-check baseline).

Usage:
  python scripts/evaluate_retrieval.py \
      --index    backend_nextgen/data/retrieval/product_index.npy \
      --metadata backend_nextgen/data/retrieval/product_metadata.npy \
      --qrels    backend_nextgen/data/retrieval/qrels.jsonl \
      --top_k    20

  # Synthetic self-retrieval sanity check (no qrels required):
  python scripts/evaluate_retrieval.py \
      --index    backend_nextgen/data/retrieval/product_index.npy \
      --metadata backend_nextgen/data/retrieval/product_metadata.npy \
      --synthetic
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------

def recall_at_k(ranked_ids: List[str], relevant: set, k: int) -> float:
    """Fraction of relevant items found in the top-k results."""
    if not relevant:
        return 0.0
    hits = sum(1 for rid in ranked_ids[:k] if rid in relevant)
    return hits / len(relevant)


def reciprocal_rank(ranked_ids: List[str], relevant: set) -> float:
    """1 / rank of the first relevant result (0 if none found)."""
    for rank, rid in enumerate(ranked_ids, start=1):
        if rid in relevant:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(ranked_ids: List[str], relevant: set, k: int) -> float:
    """
    Normalised Discounted Cumulative Gain at k.
    Binary relevance: 1 if in relevant set, else 0.
    """
    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, rid in enumerate(ranked_ids[:k], start=1)
        if rid in relevant
    )
    # Ideal DCG: all relevant items at top positions
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / idcg if idcg > 0 else 0.0


# ---------------------------------------------------------------------------
# Core evaluator
# ---------------------------------------------------------------------------

def run_evaluation(
    retriever,
    qrels: List[Dict],
    top_k: int = 20,
    ks: Tuple[int, ...] = (1, 5, 10, 20),
) -> Dict[str, float]:
    """
    Evaluate retriever on a list of query-relevance pairs.

    Args:
        retriever: DualEncoderRetriever instance
        qrels: list of {"query": str, "relevant_ids": [str, ...]}
        top_k: maximum results to fetch per query
        ks: recall / NDCG cut-offs to report

    Returns:
        dict of metric_name -> mean value
    """
    recall_sums = {k: 0.0 for k in ks}
    ndcg_sums = {k: 0.0 for k in (5, 10) if k <= top_k}
    mrr_sum = 0.0
    n = 0

    for entry in qrels:
        query = entry["query"]
        relevant = set(entry["relevant_ids"])
        if not relevant:
            continue

        results = retriever.retrieve(query, top_k=top_k)
        ranked_ids = [r.item_id for r in results]

        for k in ks:
            if k <= top_k:
                recall_sums[k] += recall_at_k(ranked_ids, relevant, k)
        mrr_sum += reciprocal_rank(ranked_ids, relevant)
        for k in (5, 10):
            if k <= top_k:
                ndcg_sums[k] += ndcg_at_k(ranked_ids, relevant, k)
        n += 1

    if n == 0:
        logger.error("No valid qrels found — check your input file.")
        return {}

    metrics: Dict[str, float] = {}
    for k in ks:
        if k <= top_k:
            metrics[f"Recall@{k}"] = round(recall_sums[k] / n, 4)
    metrics["MRR"] = round(mrr_sum / n, 4)
    for k in (5, 10):
        if k <= top_k:
            metrics[f"NDCG@{k}"] = round(ndcg_sums[k] / n, 4)
    metrics["num_queries"] = n
    return metrics


def build_synthetic_qrels(metadata: List[Dict]) -> List[Dict]:
    """
    Self-retrieval sanity check: each product title is a query and the
    product itself is the only relevant result. A good retriever should
    achieve Recall@1 ≈ 1.0 on this task.
    """
    qrels = []
    for item in metadata:
        title = item.get("title") or item.get("name") or item.get("description", "")
        item_id = item.get("item_id", "")
        if title and item_id:
            qrels.append({"query": title, "relevant_ids": [item_id]})
    logger.info(f"Built {len(qrels)} synthetic (self-retrieval) qrels from product metadata.")
    return qrels


def load_qrels(path: Path) -> List[Dict]:
    qrels = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if "query" in obj and "relevant_ids" in obj:
                qrels.append(obj)
    logger.info(f"Loaded {len(qrels)} qrels from {path}")
    return qrels


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate NextGen retrieval (Recall@k, MRR, NDCG@k)")
    parser.add_argument("--index",    default="backend_nextgen/data/retrieval/product_index.npy")
    parser.add_argument("--metadata", default="backend_nextgen/data/retrieval/product_metadata.npy")
    parser.add_argument("--qrels",    default=None, help="JSONL file with {query, relevant_ids}")
    parser.add_argument("--synthetic", action="store_true",
                        help="Use synthetic self-retrieval benchmark (ignores --qrels)")
    parser.add_argument("--top_k",   type=int, default=20)
    parser.add_argument("--model",   default=None,
                        help="Override encoder model name (default: from config)")
    parser.add_argument("--device",  default="cpu")
    parser.add_argument("--output",  default=None, help="Save metrics JSON to this path")
    args = parser.parse_args()

    # Resolve encoder model name
    model_name = args.model
    if model_name is None:
        try:
            sys.path.insert(0, ".")
            from backend_nextgen.config.loader import load_config
            model_name = load_config().section("retrieval")["encoder_name"]
        except Exception as e:
            logger.error(f"Could not load encoder_name from config: {e}. Pass --model explicitly.")
            sys.exit(1)

    index_path = Path(args.index)
    meta_path = Path(args.metadata)

    if not index_path.exists() or not meta_path.exists():
        logger.error(
            f"Retrieval index not found at {index_path} / {meta_path}.\n"
            "Run the index builder first, or use --synthetic to test with product titles."
        )
        sys.exit(1)

    logger.info(f"Loading retriever — model: {model_name}, index: {index_path}")
    from backend_nextgen.retrieval.dual_encoder import DualEncoderRetriever
    retriever = DualEncoderRetriever.from_disk(
        model_name=model_name,
        index_path=index_path,
        metadata_path=meta_path,
        device=args.device,
    )
    logger.info(f"Index: {len(retriever.metadata)} items | FAISS: {retriever._faiss_index is not None}")

    if args.synthetic:
        qrels = build_synthetic_qrels(retriever.metadata)
    elif args.qrels:
        qrels = load_qrels(Path(args.qrels))
    else:
        logger.warning("No --qrels file and --synthetic not set. Using synthetic self-retrieval.")
        qrels = build_synthetic_qrels(retriever.metadata)

    if not qrels:
        logger.error("No qrels to evaluate. Exiting.")
        sys.exit(1)

    logger.info(f"Running retrieval evaluation on {len(qrels)} queries (top_k={args.top_k})…")
    metrics = run_evaluation(retriever, qrels, top_k=args.top_k)

    print("\n" + "=" * 50)
    print("  Retrieval Evaluation Results")
    print("=" * 50)
    for name, value in metrics.items():
        if name == "num_queries":
            print(f"  Queries evaluated: {int(value)}")
        else:
            print(f"  {name:<15} {value:.4f}")
    print("=" * 50)

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)
        logger.info(f"Metrics saved to {out}")


if __name__ == "__main__":
    main()
