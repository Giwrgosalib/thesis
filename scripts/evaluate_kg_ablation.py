"""
Knowledge-graph ablation study: measure the marginal contribution of
KG-based query expansion to retrieval quality.

For each test query:
  1. Run retrieval with the original query (baseline).
  2. Apply KG expansion: if the query mentions a BRAND that exists in the
     expanded KG, append the brand's neighbour categories/product-types
     to the query string, then re-retrieve.
  3. Score both with the same entity-based qrels.

Reports delta in MRR, NDCG@10, Recall@10, etc.

Output: results/kg_ablation.json
"""

from __future__ import annotations

import argparse
import ast
import json
import math
import sys
import time
from pathlib import Path
from typing import Dict, List, Set, Tuple

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


STOPWORDS = {
    "the", "a", "an", "for", "with", "in", "on", "and", "or", "of", "to",
    "any", "some", "new", "good", "best", "i", "want", "need", "show", "me",
    "looking", "find", "buy", "get", "have", "do", "you", "your",
}


def parse_entities(entities_str: str, query: str) -> dict:
    try:
        spans = ast.literal_eval(entities_str)
    except (ValueError, SyntaxError):
        return {}
    out: dict = {}
    for s in spans:
        if len(s) != 3:
            continue
        text = query[s[0]:s[1]].strip().lower()
        label = s[2].upper()
        if text and text not in STOPWORDS:
            out.setdefault(label, []).append(text)
    return out


def load_kg_neighbours(triples_path: Path) -> Dict[str, Set[str]]:
    """Return {brand_name_lower -> set(category_or_product_type_names)}."""
    neighbours: Dict[str, Set[str]] = {}
    with triples_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            head, relation, tail = parts[0], parts[1], parts[2]
            # Only follow brand-outbound edges
            if not head.startswith("brand:"):
                continue
            brand = head.split(":", 1)[1].lower()
            tail_type, _, tail_name = tail.partition(":")
            if tail_type in ("category", "product_type"):
                neighbours.setdefault(brand, set()).add(tail_name)
    return neighbours


def expand_query(query: str, ents: dict, kg: Dict[str, Set[str]]) -> str:
    """
    Append KG-derived terms to the query string only when the query is
    brand-anchored but lacks a product-type entity — i.e., when expansion
    can fill in missing semantic structure rather than dilute existing
    specificity.
    """
    brands = ents.get("BRAND", [])
    if not brands:
        return query
    # If the query already specifies a product type, do not dilute it.
    if ents.get("PRODUCT_TYPE"):
        return query
    expansions: Set[str] = set()
    for b in brands:
        for term in kg.get(b.lower(), set()):
            expansions.add(term.lower())
    if expansions:
        # Limit to top-3 most common expansions to avoid query explosion.
        capped = sorted(expansions)[:3]
        return query + " " + " ".join(capped)
    return query


def reciprocal_rank(ranked_ids: List[str], relevant: set) -> float:
    for rank, rid in enumerate(ranked_ids, start=1):
        if rid in relevant:
            return 1.0 / rank
    return 0.0


def recall_at_k(ranked_ids: List[str], relevant: set, k: int) -> float:
    if not relevant:
        return 0.0
    hits = sum(1 for rid in ranked_ids[:k] if rid in relevant)
    return hits / len(relevant)


def ndcg_at_k(ranked_ids: List[str], relevant: set, k: int) -> float:
    dcg = sum(1.0 / math.log2(rank + 1)
              for rank, rid in enumerate(ranked_ids[:k], start=1)
              if rid in relevant)
    ideal = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(r + 1) for r in range(1, ideal + 1))
    return dcg / idcg if idcg > 0 else 0.0


def bootstrap_ci(values, n=1000, ci=0.95, seed=42):
    if not values:
        return (0.0, 0.0)
    rng = np.random.default_rng(seed)
    arr = np.asarray(values)
    samples = rng.choice(arr, size=(n, len(arr)), replace=True)
    means = samples.mean(axis=1)
    lo = (1 - ci) / 2 * 100
    hi = 100 - lo
    return float(np.percentile(means, lo)), float(np.percentile(means, hi))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test_csv", default="backend/data/unified_test.csv")
    parser.add_argument("--qrels",    default="backend_nextgen/data/retrieval/qrels_balanced.jsonl")
    parser.add_argument("--triples",  default="backend_nextgen/data/knowledge_graph/expanded_triples.tsv")
    parser.add_argument("--index",    default="backend_nextgen/data/retrieval/product_index.npy")
    parser.add_argument("--metadata", default="backend_nextgen/data/retrieval/product_metadata.npy")
    parser.add_argument("--output",   default="results/kg_ablation.json")
    parser.add_argument("--top_k",    type=int, default=20)
    parser.add_argument("--device",   default=None)
    args = parser.parse_args()

    import torch
    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")

    # Load qrels
    qrels: Dict[str, Set[str]] = {}
    with open(args.qrels, encoding="utf-8") as f:
        for line in f:
            o = json.loads(line.strip())
            qrels[o["query"]] = set(o["relevant_ids"])
    print(f"Loaded {len(qrels)} qrels from {args.qrels}")

    # Load KG neighbours
    kg = load_kg_neighbours(Path(args.triples))
    print(f"Loaded KG: {len(kg)} brands with outbound edges")

    # Load test queries (need entity annotations)
    df = pd.read_csv(args.test_csv)
    print(f"Test queries: {len(df)}")

    # Load retriever
    from backend_nextgen.config.loader import load_config
    cfg = load_config()
    ret_cfg = cfg.section("retrieval")

    from backend_nextgen.retrieval.dual_encoder import DualEncoderRetriever
    index = np.load(args.index, allow_pickle=False)
    metadata = list(np.load(args.metadata, allow_pickle=True))
    retriever = DualEncoderRetriever(
        model_name=ret_cfg["encoder_name"],
        index=index, metadata=metadata, device=device,
    )

    # Warmup
    for _ in range(2):
        retriever.retrieve(df["query"].iloc[0], top_k=args.top_k)

    # Run ablation
    baseline_mrr, expanded_mrr = [], []
    baseline_r10, expanded_r10 = [], []
    baseline_ndcg10, expanded_ndcg10 = [], []
    n_expansions_applied = 0
    n_evaluated = 0
    n_brand_in_kg = 0

    for _, row in df.iterrows():
        q = row["query"]
        rel = qrels.get(q)
        if not rel:
            continue
        ents = parse_entities(row["entities"], q)
        n_evaluated += 1

        # Baseline retrieval (original query)
        base = retriever.retrieve(q, top_k=args.top_k)
        base_ids = [r.item_id for r in base]
        baseline_mrr.append(reciprocal_rank(base_ids, rel))
        baseline_r10.append(recall_at_k(base_ids, rel, 10))
        baseline_ndcg10.append(ndcg_at_k(base_ids, rel, 10))

        # Expanded retrieval (with KG terms)
        q_exp = expand_query(q, ents, kg)
        was_expanded = q_exp != q
        if was_expanded:
            n_expansions_applied += 1
        if any(b.lower() in kg for b in ents.get("BRAND", [])):
            n_brand_in_kg += 1
        exp = retriever.retrieve(q_exp, top_k=args.top_k)
        exp_ids = [r.item_id for r in exp]
        expanded_mrr.append(reciprocal_rank(exp_ids, rel))
        expanded_r10.append(recall_at_k(exp_ids, rel, 10))
        expanded_ndcg10.append(ndcg_at_k(exp_ids, rel, 10))

    def agg(label, base, exp):
        bm, em = float(np.mean(base)), float(np.mean(exp))
        b_lo, b_hi = bootstrap_ci(base)
        e_lo, e_hi = bootstrap_ci(exp)
        return {
            "metric": label,
            "baseline": round(bm, 4),
            "baseline_95CI": [round(b_lo, 4), round(b_hi, 4)],
            "with_kg_expansion": round(em, 4),
            "with_kg_95CI": [round(e_lo, 4), round(e_hi, 4)],
            "delta": round(em - bm, 4),
            "delta_pct": round((em - bm) / bm * 100, 2) if bm > 0 else 0.0,
        }

    out = {
        "n_evaluated": n_evaluated,
        "n_expansions_applied": n_expansions_applied,
        "expansion_applicability_pct": round(n_expansions_applied / n_evaluated * 100, 2),
        "n_brand_in_kg": n_brand_in_kg,
        "metrics": {
            "MRR":       agg("MRR", baseline_mrr, expanded_mrr),
            "Recall@10": agg("Recall@10", baseline_r10, expanded_r10),
            "NDCG@10":   agg("NDCG@10", baseline_ndcg10, expanded_ndcg10),
        },
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)

    print()
    print("=" * 60)
    print("Knowledge-Graph Ablation Study")
    print("=" * 60)
    print(f"Queries evaluated:        {n_evaluated}")
    print(f"Queries with KG match:    {n_brand_in_kg} "
          f"({n_brand_in_kg / n_evaluated * 100:.1f}%)")
    print(f"Expansions actually applied: {n_expansions_applied} "
          f"({out['expansion_applicability_pct']}%)")
    print()
    print(f"{'Metric':<10} {'Baseline':>10} {'+KG':>10} {'Delta':>10} {'%':>8}")
    for k, m in out["metrics"].items():
        print(f"{m['metric']:<10} {m['baseline']:>10.4f} {m['with_kg_expansion']:>10.4f} "
              f"{m['delta']:>+10.4f} {m['delta_pct']:>+7.1f}%")
    print()
    print(f"Saved to {out_path}")


if __name__ == "__main__":
    main()
