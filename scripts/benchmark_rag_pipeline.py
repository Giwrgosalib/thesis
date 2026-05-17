"""
End-to-end RAG pipeline latency benchmark.

Loads the dual-encoder retriever + the local generator (FLAN-T5-small or
whatever is configured under ``rag.generator_name``) and measures per-query
retrieval time, generation time, and total wall-clock time across a
configurable set of queries with N runs each (default: 20 queries x 3 runs
= 60 samples).

Computes mean, median (P50), and P95 latencies plus token throughput.

Output: results/rag_benchmark.json
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import List

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * pct / 100.0
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


def main():
    parser = argparse.ArgumentParser(description="Benchmark end-to-end RAG latency")
    parser.add_argument(
        "--test_csv", default="backend/data/unified_test.csv",
        help="Source of benchmark queries (column: 'query')",
    )
    parser.add_argument(
        "--num_queries", type=int, default=20,
        help="Number of distinct queries to benchmark",
    )
    parser.add_argument(
        "--runs", type=int, default=3,
        help="How many times to run each query (warmup excluded)",
    )
    parser.add_argument(
        "--warmup_runs", type=int, default=2,
        help="Warmup runs (per query) to exclude from timing",
    )
    parser.add_argument(
        "--config", default="backend_nextgen/config/nextgen_config.yml",
    )
    parser.add_argument(
        "--output", default="results/rag_benchmark.json",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
    )
    args = parser.parse_args()

    # ── Load benchmark queries ──
    df = pd.read_csv(args.test_csv)
    queries = (
        df["query"]
        .dropna()
        .drop_duplicates()
        .sample(n=args.num_queries, random_state=args.seed)
        .tolist()
    )
    print(f"Selected {len(queries)} benchmark queries from {args.test_csv}")

    # ── Load orchestrator components (retriever + generator + RAG pipeline) ──
    print("Loading config and components…")
    from backend_nextgen.config.loader import load_config
    from backend_nextgen.retrieval.dual_encoder import DualEncoderRetriever
    from backend_nextgen.rag.generator import GenerativeResponder
    from backend_nextgen.rag.pipeline import RAGPipeline

    config = load_config(Path(args.config))
    ret_cfg = config.section("retrieval")
    rag_cfg = config.section("rag")

    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")

    import numpy as np
    index_array = np.load(ret_cfg["index_path"], allow_pickle=False)
    metadata = list(np.load(ret_cfg["metadata_store"], allow_pickle=True))
    retriever = DualEncoderRetriever(
        model_name=ret_cfg["encoder_name"],
        index=index_array,
        metadata=metadata,
        device=device,
    )
    generator = GenerativeResponder(
        model_name=rag_cfg["generator_name"],
        max_tokens=rag_cfg["response_max_tokens"],
        temperature=rag_cfg["temperature"],
        device=device,
    )
    rag = RAGPipeline(
        retriever=retriever, generator=generator,
        max_context_docs=rag_cfg["max_context_docs"],
    )

    # ── Warmup ──
    print(f"Warmup: {args.warmup_runs} runs on first query…")
    for _ in range(args.warmup_runs):
        rag.answer(queries[0])

    # ── Benchmark loop ──
    retrieval_times: List[float] = []
    generation_times: List[float] = []
    total_times: List[float] = []
    tokens_generated: List[int] = []

    print(f"Benchmarking {len(queries)} queries x {args.runs} runs each = "
          f"{len(queries) * args.runs} samples…")

    for qi, q in enumerate(queries):
        for r in range(args.runs):
            t0 = time.perf_counter()
            retrieved = retriever.retrieve(q, top_k=rag_cfg["max_context_docs"])
            t1 = time.perf_counter()

            documents = [doc.metadata for doc in retrieved]
            t2 = time.perf_counter()
            response = rag.answer(q, documents=documents)
            t3 = time.perf_counter()

            ret_ms = (t1 - t0) * 1000
            gen_ms = (t3 - t2) * 1000
            total_ms = (t3 - t0) * 1000

            retrieval_times.append(ret_ms)
            generation_times.append(gen_ms)
            total_times.append(total_ms)

            # Approximate token count
            n_tokens = len(response.answer.split())
            tokens_generated.append(n_tokens)

        if (qi + 1) % 5 == 0:
            print(f"  [{qi + 1}/{len(queries)}] done")

    # ── Aggregate ──
    def agg(label, values):
        return {
            "label": label,
            "samples": len(values),
            "mean": round(statistics.mean(values), 2),
            "stddev": round(statistics.stdev(values), 2) if len(values) > 1 else 0.0,
            "median": round(statistics.median(values), 2),
            "p50": round(percentile(values, 50), 2),
            "p95": round(percentile(values, 95), 2),
            "p99": round(percentile(values, 99), 2),
            "min": round(min(values), 2),
            "max": round(max(values), 2),
        }

    total_tokens = sum(tokens_generated)
    total_gen_seconds = sum(generation_times) / 1000.0
    tokens_per_second = total_tokens / total_gen_seconds if total_gen_seconds else 0.0

    out = {
        "config": {
            "test_csv": args.test_csv,
            "num_queries": len(queries),
            "runs_per_query": args.runs,
            "warmup_runs": args.warmup_runs,
            "total_samples": len(total_times),
            "device": device,
            "generator_model": rag_cfg["generator_name"],
            "encoder_model": ret_cfg["encoder_name"],
            "max_context_docs": rag_cfg["max_context_docs"],
            "response_max_tokens": rag_cfg["response_max_tokens"],
            "temperature": rag_cfg["temperature"],
        },
        "retrieval_ms": agg("Retrieval", retrieval_times),
        "generation_ms": agg("Generation", generation_times),
        "total_ms": agg("Total (E2E)", total_times),
        "throughput": {
            "total_tokens_generated": total_tokens,
            "mean_tokens_per_response": round(statistics.mean(tokens_generated), 1),
            "tokens_per_second": round(tokens_per_second, 1),
        },
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    # Console summary
    print("\n" + "=" * 60)
    print("RAG Pipeline Latency Benchmark")
    print("=" * 60)
    print(f"Samples: {len(total_times)}  Device: {device}")
    print(f"Generator: {rag_cfg['generator_name']}")
    print()
    print(f"{'Metric':<30} {'Mean':>10} {'P50':>10} {'P95':>10}")
    for k in ("retrieval_ms", "generation_ms", "total_ms"):
        m = out[k]
        print(f"{m['label']:<30} {m['mean']:>10.2f} {m['p50']:>10.2f} {m['p95']:>10.2f}")
    print()
    print(f"Mean tokens / response: {out['throughput']['mean_tokens_per_response']}")
    print(f"Throughput:             {out['throughput']['tokens_per_second']} tok/s")
    print()
    print(f"Saved to {out_path}")


if __name__ == "__main__":
    main()
