"""
Comprehensive retrieval evaluation: Recall@k, Precision@k, MAP, MRR (with
bootstrap 95% CI), NDCG@k, and average retrieval latency.

Matches the metric set reported in the thesis (Table 5.3).

Usage:
    python scripts/evaluate_retrieval_full.py \
        --qrels backend_nextgen/data/retrieval/qrels_strict.jsonl \
        --output results/retrieval_metrics.json
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def precision_at_k(ranked_ids: List[str], relevant: set, k: int) -> float:
    if k <= 0:
        return 0.0
    hits = sum(1 for rid in ranked_ids[:k] if rid in relevant)
    return hits / k


def recall_at_k(ranked_ids: List[str], relevant: set, k: int) -> float:
    if not relevant:
        return 0.0
    hits = sum(1 for rid in ranked_ids[:k] if rid in relevant)
    return hits / len(relevant)


def average_precision(ranked_ids: List[str], relevant: set) -> float:
    """Average Precision: mean of precisions at each rank where a relevant doc appears."""
    if not relevant:
        return 0.0
    hits = 0
    sum_prec = 0.0
    for rank, rid in enumerate(ranked_ids, start=1):
        if rid in relevant:
            hits += 1
            sum_prec += hits / rank
    return sum_prec / len(relevant) if relevant else 0.0


def reciprocal_rank(ranked_ids: List[str], relevant: set) -> float:
    for rank, rid in enumerate(ranked_ids, start=1):
        if rid in relevant:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(ranked_ids: List[str], relevant: set, k: int) -> float:
    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, rid in enumerate(ranked_ids[:k], start=1)
        if rid in relevant
    )
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / idcg if idcg > 0 else 0.0


def bootstrap_ci(values: List[float], n_iter: int = 1000, ci: float = 0.95,
                 rng_seed: int = 42) -> Tuple[float, float]:
    """Percentile bootstrap confidence interval for the mean."""
    if not values:
        return 0.0, 0.0
    rng = np.random.default_rng(rng_seed)
    arr = np.asarray(values)
    samples = rng.choice(arr, size=(n_iter, len(arr)), replace=True)
    means = samples.mean(axis=1)
    lo = (1.0 - ci) / 2.0 * 100
    hi = 100.0 - lo
    return float(np.percentile(means, lo)), float(np.percentile(means, hi))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index",    default="backend_nextgen/data/retrieval/product_index.npy")
    parser.add_argument("--metadata", default="backend_nextgen/data/retrieval/product_metadata.npy")
    parser.add_argument("--qrels",    required=True,
                        help="JSONL file with {query, relevant_ids}")
    parser.add_argument("--top_k",    type=int, default=20)
    parser.add_argument("--device",   default=None)
    parser.add_argument("--output",   default="results/retrieval_metrics.json")
    args = parser.parse_args()

    import torch
    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")

    # Load config + retriever
    from backend_nextgen.config.loader import load_config
    cfg = load_config()
    ret_cfg = cfg.section("retrieval")

    index = np.load(args.index, allow_pickle=False)
    metadata = list(np.load(args.metadata, allow_pickle=True))

    from backend_nextgen.retrieval.dual_encoder import DualEncoderRetriever
    retriever = DualEncoderRetriever(
        model_name=ret_cfg["encoder_name"],
        index=index, metadata=metadata, device=device,
    )
    logger.info(f"Index: {len(metadata)} items | Device: {device}")

    # Load qrels
    qrels: List[Dict] = []
    with open(args.qrels, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if "query" in obj and "relevant_ids" in obj:
                qrels.append(obj)
    logger.info(f"Loaded {len(qrels)} qrels from {args.qrels}")

    # Warmup
    for _ in range(2):
        retriever.retrieve(qrels[0]["query"], top_k=args.top_k)

    # Per-query metric collection
    per_query_mrr: List[float] = []
    per_query_ap: List[float] = []
    per_query_recall_k: Dict[int, List[float]] = {k: [] for k in (1, 5, 10, 20)}
    per_query_prec_k: Dict[int, List[float]] = {k: [] for k in (1, 5, 10)}
    per_query_ndcg_k: Dict[int, List[float]] = {k: [] for k in (5, 10)}
    latencies_ms: List[float] = []

    logger.info(f"Evaluating {len(qrels)} queries (top_k={args.top_k})…")
    for i, entry in enumerate(qrels):
        query = entry["query"]
        relevant = set(entry["relevant_ids"])
        if not relevant:
            continue

        t0 = time.perf_counter()
        results = retriever.retrieve(query, top_k=args.top_k)
        latencies_ms.append((time.perf_counter() - t0) * 1000)
        ranked_ids = [r.item_id for r in results]

        per_query_mrr.append(reciprocal_rank(ranked_ids, relevant))
        per_query_ap.append(average_precision(ranked_ids, relevant))
        for k in per_query_recall_k:
            if k <= args.top_k:
                per_query_recall_k[k].append(recall_at_k(ranked_ids, relevant, k))
        for k in per_query_prec_k:
            if k <= args.top_k:
                per_query_prec_k[k].append(precision_at_k(ranked_ids, relevant, k))
        for k in per_query_ndcg_k:
            if k <= args.top_k:
                per_query_ndcg_k[k].append(ndcg_at_k(ranked_ids, relevant, k))

        if (i + 1) % 25 == 0:
            logger.info(f"  [{i + 1}/{len(qrels)}] done")

    # Aggregate
    n = len(per_query_mrr)
    mrr = float(np.mean(per_query_mrr))
    mrr_ci_lo, mrr_ci_hi = bootstrap_ci(per_query_mrr)
    mean_ap = float(np.mean(per_query_ap))
    avg_lat = float(np.mean(latencies_ms))

    metrics = {
        "MRR":          round(mrr, 4),
        "MRR_95CI":     [round(mrr_ci_lo, 4), round(mrr_ci_hi, 4)],
        "MAP":          round(mean_ap, 4),
        "NDCG@5":       round(float(np.mean(per_query_ndcg_k[5])), 4),
        "NDCG@10":      round(float(np.mean(per_query_ndcg_k[10])), 4),
        "Recall@1":     round(float(np.mean(per_query_recall_k[1])), 4),
        "Recall@5":     round(float(np.mean(per_query_recall_k[5])), 4),
        "Recall@10":    round(float(np.mean(per_query_recall_k[10])), 4),
        "Recall@20":    round(float(np.mean(per_query_recall_k[20])), 4),
        "Precision@1":  round(float(np.mean(per_query_prec_k[1])), 4),
        "Precision@5":  round(float(np.mean(per_query_prec_k[5])), 4),
        "Precision@10": round(float(np.mean(per_query_prec_k[10])), 4),
        "avg_retrieval_latency_ms": round(avg_lat, 2),
        "num_queries":  n,
        "qrels_file":   args.qrels,
        "encoder":      ret_cfg["encoder_name"],
        "device":       device,
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    print("\n" + "=" * 60)
    print("  Comprehensive Retrieval Evaluation")
    print("=" * 60)
    print(f"  Queries:                 {n}")
    print(f"  Encoder:                 {metrics['encoder']}")
    print(f"  Device:                  {device}")
    print()
    print(f"  MRR:                     {metrics['MRR']}")
    print(f"  MRR (95% bootstrap CI):  [{metrics['MRR_95CI'][0]}, {metrics['MRR_95CI'][1]}]")
    print(f"  MAP:                     {metrics['MAP']}")
    print(f"  NDCG@5:                  {metrics['NDCG@5']}")
    print(f"  NDCG@10:                 {metrics['NDCG@10']}")
    print(f"  Precision@1:             {metrics['Precision@1']}")
    print(f"  Precision@5:             {metrics['Precision@5']}")
    print(f"  Recall@1:                {metrics['Recall@1']}")
    print(f"  Recall@5:                {metrics['Recall@5']}")
    print(f"  Recall@10:               {metrics['Recall@10']}")
    print(f"  Recall@20:               {metrics['Recall@20']}")
    print(f"  Avg retrieval latency:   {metrics['avg_retrieval_latency_ms']} ms")
    print("=" * 60)
    print(f"  Saved to {out}")


if __name__ == "__main__":
    main()
