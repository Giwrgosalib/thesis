"""
Unified NER evaluation for Legacy (BiLSTM-CRF) and NextGen (DeBERTa) engines.

Loads the unified test set, runs both engines, and computes entity-level
precision / recall / F1 against gold annotations using text+label matching.

Usage:
    python scripts/evaluate_engines.py
    python scripts/evaluate_engines.py --engine legacy --output results/legacy_eval.json
    python scripts/evaluate_engines.py --engine both --output results/evaluation.json
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend_nextgen.config.entity_schema import normalise_label


def parse_gold_entities(query: str, entities_str: str) -> Set[Tuple[str, str]]:
    try:
        entities = ast.literal_eval(entities_str)
    except (ValueError, SyntaxError):
        return set()
    result = set()
    for ent in entities:
        if len(ent) == 3:
            start, end, label = ent
            text = query[start:end].lower().strip()
            canon = normalise_label(label)
            if canon is None:
                canon = label.upper().strip()
            if text:
                result.add((text, canon))
    return result


def extract_legacy_entities(nlp, query: str) -> Tuple[Set[Tuple[str, str]], float]:
    t0 = time.perf_counter()
    result = nlp.extract_entities(query)
    latency = (time.perf_counter() - t0) * 1000
    entities = set()
    for raw in result.get("raw_entities", []):
        label = raw.get("label", "")
        value = raw.get("value", "").lower().strip()
        canon = normalise_label(label)
        if canon is None:
            canon = label.upper().strip()
        if value:
            entities.add((value, canon))
    return entities, latency


def extract_nextgen_entities(ner, query: str) -> Tuple[Set[Tuple[str, str]], float]:
    t0 = time.perf_counter()
    result = ner.extract_entities(query)
    latency = (time.perf_counter() - t0) * 1000
    entities = set()
    for raw in result.get("raw_entities", []):
        label = raw.get("label", "")
        value = raw.get("value", "").lower().strip()
        canon = normalise_label(label)
        if canon is None:
            canon = label.upper().strip()
        if value:
            entities.add((value, canon))
    return entities, latency


def compute_metrics(
    all_gold: List[Set[Tuple[str, str]]],
    all_pred: List[Set[Tuple[str, str]]],
) -> Dict:
    tp_total = fp_total = fn_total = 0
    per_type_tp: Dict[str, int] = defaultdict(int)
    per_type_fp: Dict[str, int] = defaultdict(int)
    per_type_fn: Dict[str, int] = defaultdict(int)

    for gold, pred in zip(all_gold, all_pred):
        tp = gold & pred
        fp = pred - gold
        fn = gold - pred
        tp_total += len(tp)
        fp_total += len(fp)
        fn_total += len(fn)
        for _, label in tp:
            per_type_tp[label] += 1
        for _, label in fp:
            per_type_fp[label] += 1
        for _, label in fn:
            per_type_fn[label] += 1

    precision = tp_total / (tp_total + fp_total) if (tp_total + fp_total) else 0.0
    recall = tp_total / (tp_total + fn_total) if (tp_total + fn_total) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    all_types = sorted(set(per_type_tp) | set(per_type_fp) | set(per_type_fn))
    per_type = {}
    for t in all_types:
        tp_t = per_type_tp[t]
        fp_t = per_type_fp[t]
        fn_t = per_type_fn[t]
        p = tp_t / (tp_t + fp_t) if (tp_t + fp_t) else 0.0
        r = tp_t / (tp_t + fn_t) if (tp_t + fn_t) else 0.0
        f = 2 * p * r / (p + r) if (p + r) else 0.0
        per_type[t] = {
            "precision": round(p, 4),
            "recall": round(r, 4),
            "f1": round(f, 4),
            "support": tp_t + fn_t,
        }

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "tp": tp_total,
        "fp": fp_total,
        "fn": fn_total,
        "per_type": per_type,
    }


def main():
    parser = argparse.ArgumentParser(description="Unified NER evaluation")
    parser.add_argument("--test_csv", default="backend/data/unified_test.csv")
    parser.add_argument("--engine", choices=["legacy", "nextgen", "both"], default="both")
    parser.add_argument("--output", default="results/evaluation.json")
    parser.add_argument("--max_samples", type=int, default=None)
    parser.add_argument(
        "--nextgen_model_path",
        default="backend_nextgen/models/ner",
        help="Path to the NextGen NER model directory (use backend_nextgen/models/deberta_crf/best_model for the CRF variant).",
    )
    args = parser.parse_args()

    df = pd.read_csv(args.test_csv)
    if args.max_samples and len(df) > args.max_samples:
        df = df.sample(n=args.max_samples, random_state=42).reset_index(drop=True)
    print(f"Evaluating on {len(df)} test queries from {args.test_csv}")

    gold_entities = [
        parse_gold_entities(row["query"], row["entities"])
        for _, row in df.iterrows()
    ]
    queries = df["query"].tolist()

    results: Dict = {
        "test_csv": args.test_csv,
        "num_queries": len(df),
    }

    if args.engine in ("legacy", "both"):
        print("\n--- Loading Legacy engine ---")
        from backend.custom_nlp import EBayNLP
        legacy_nlp = EBayNLP()

        legacy_preds = []
        legacy_latencies = []
        for i, query in enumerate(queries):
            pred, lat = extract_legacy_entities(legacy_nlp, query)
            legacy_preds.append(pred)
            legacy_latencies.append(lat)
            if (i + 1) % 50 == 0:
                print(f"  Legacy: {i+1}/{len(queries)}")

        legacy_metrics = compute_metrics(gold_entities, legacy_preds)
        legacy_metrics["avg_latency_ms"] = round(sum(legacy_latencies) / len(legacy_latencies), 1)
        legacy_metrics["p50_latency_ms"] = round(sorted(legacy_latencies)[len(legacy_latencies) // 2], 1)
        results["legacy"] = legacy_metrics
        print(f"  Legacy F1={legacy_metrics['f1']:.4f}  P={legacy_metrics['precision']:.4f}  R={legacy_metrics['recall']:.4f}  avg_lat={legacy_metrics['avg_latency_ms']}ms")

    if args.engine in ("nextgen", "both"):
        print("\n--- Loading NextGen engine ---")
        from backend_nextgen.nlp.inference import TransformerNERInference
        nextgen_ner = TransformerNERInference(
            model_path=args.nextgen_model_path,
            device="cuda" if torch.cuda.is_available() else "cpu",
        )

        nextgen_preds = []
        nextgen_latencies = []
        for i, query in enumerate(queries):
            pred, lat = extract_nextgen_entities(nextgen_ner, query)
            nextgen_preds.append(pred)
            nextgen_latencies.append(lat)
            if (i + 1) % 50 == 0:
                print(f"  NextGen: {i+1}/{len(queries)}")

        nextgen_metrics = compute_metrics(gold_entities, nextgen_preds)
        nextgen_metrics["avg_latency_ms"] = round(sum(nextgen_latencies) / len(nextgen_latencies), 1)
        nextgen_metrics["p50_latency_ms"] = round(sorted(nextgen_latencies)[len(nextgen_latencies) // 2], 1)
        results["nextgen"] = nextgen_metrics
        print(f"  NextGen F1={nextgen_metrics['f1']:.4f}  P={nextgen_metrics['precision']:.4f}  R={nextgen_metrics['recall']:.4f}  avg_lat={nextgen_metrics['avg_latency_ms']}ms")

    if args.engine == "both" and "legacy" in results and "nextgen" in results:
        lf1 = results["legacy"]["f1"]
        nf1 = results["nextgen"]["f1"]
        llat = results["legacy"]["avg_latency_ms"]
        nlat = results["nextgen"]["avg_latency_ms"]
        results["comparison"] = {
            "f1_delta": round(nf1 - lf1, 4),
            "nextgen_f1_improvement_pct": round((nf1 - lf1) / lf1 * 100, 1) if lf1 > 0 else None,
            "speedup_factor": round(llat / nlat, 1) if nlat > 0 else None,
        }
        print(f"\n  F1 delta (nextgen - legacy): {results['comparison']['f1_delta']:+.4f}")
        if results['comparison']['speedup_factor']:
            print(f"  Speedup: {results['comparison']['speedup_factor']}x")

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
