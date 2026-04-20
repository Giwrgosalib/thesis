"""
Offline evaluation harness for both AI engines.

Metrics computed
----------------
NER (both engines):
  - Entity-level precision / recall / F1  (per entity type + macro average)

Retrieval (nextgen dual encoder):
  - Recall@K (K = 1, 5, 10)
  - Mean Reciprocal Rank (MRR)

Ranking (nextgen neural reranker):
  - NDCG@5 / NDCG@10

Usage
-----
    # Quick test on sample queries (no datasets required)
    python scripts/evaluate_ai_engines.py --quick

    # Full evaluation against a CSV test file
    python scripts/evaluate_ai_engines.py \
        --ner_test backend/data/refined_balanced_dataset_val.csv \
        --retrieval_test scripts/eval_retrieval_queries.json \
        --engine both
"""

from __future__ import annotations

import argparse
import ast
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("evaluate_ai_engines")


# ---------------------------------------------------------------------------
# Canonical entity label normalization
# Must stay in sync with backend_nextgen/scripts/train_transformer_ner.py
# ---------------------------------------------------------------------------

LABEL_NORMALIZATION: Dict[str, str] = {
    # Brand / manufacturer
    "BRAND": "BRAND", "MANUFACTURER": "BRAND", "MAKER": "BRAND",
    # Product / item type
    "PRODUCT_TYPE": "PRODUCT_TYPE", "PRODUCT": "PRODUCT_TYPE",
    "TYPE": "PRODUCT_TYPE", "ITEM": "PRODUCT_TYPE",
    # Category
    "CATEGORY": "CATEGORY",
    # Model
    "MODEL": "MODEL", "MODEL_NAME": "MODEL", "MODEL_NUMBER": "MODEL",
    "VERSION": "MODEL", "VARIANT": "MODEL",
    # Color
    "COLOR": "COLOR", "COLOUR": "COLOR", "HUE": "COLOR",
    # Size / dimensions
    "SIZE": "SIZE", "DIMENSION": "SIZE", "MEASUREMENT": "SIZE",
    # Price
    "PRICE_RANGE": "PRICE_RANGE", "PRICE": "PRICE_RANGE",
    "PRICE_TOKEN": "PRICE_RANGE", "PRICE_QUALIFIER": "PRICE_RANGE",
    "PRICE_PREFERENCE": "PRICE_RANGE", "BUDGET": "PRICE_RANGE", "COST": "PRICE_RANGE",
    # Condition
    "CONDITION": "CONDITION", "STATE": "CONDITION",
    # Material / fabric
    "MATERIAL": "MATERIAL", "FABRIC": "MATERIAL", "COMPOSITION": "MATERIAL",
    # Feature / spec
    "FEATURE": "FEATURE", "SPECIFICATION": "FEATURE", "SPEC": "FEATURE",
    # Technology
    "TECH": "TECH", "TECHNOLOGY": "TECH",
    # Shipping
    "SHIPPING": "SHIPPING",
    # Usage / purpose
    "USAGE": "USAGE",
    # Quality / tier (kept distinct so per-type metrics are meaningful)
    "QUALITY": "QUALITY", "TIER": "TIER",
    # Storage / RAM (hardware)
    "STORAGE": "STORAGE", "RAM": "RAM", "GPU": "GPU",
    # Connectivity
    "CONNECTIVITY": "CONNECTIVITY",
    # Remaining pass-through — kept as-is (no mapping needed)
}


def normalize_label(lbl: str) -> str:
    """Return the canonical entity label, upper-cased and de-aliased."""
    return LABEL_NORMALIZATION.get(lbl.upper(), lbl.upper())


# ---------------------------------------------------------------------------
# BIO span extraction helper (shared by both engines)
# ---------------------------------------------------------------------------

def bio_to_spans(tags: List[str]) -> set:
    """Convert BIO tag sequence to set of (start_idx, end_idx, label) tuples."""
    spans: set = set()
    start: Optional[int] = None
    label: Optional[str] = None
    for i, tag in enumerate(tags):
        if tag.startswith("B-"):
            if start is not None:
                spans.add((start, i - 1, label))
            start, label = i, tag[2:]
        elif tag.startswith("I-") and label == tag[2:]:
            pass  # continue span
        else:
            if start is not None:
                spans.add((start, i - 1, label))
            start, label = None, None
    if start is not None:
        spans.add((start, len(tags) - 1, label))
    return spans


def safe_parse_entities(raw) -> List[Tuple]:
    """Parse entity field safely without eval()."""
    import pandas as pd
    if isinstance(raw, float) or (hasattr(pd, "isna") and pd.isna(raw)):
        return []
    if isinstance(raw, list):
        return [tuple(e) for e in raw if isinstance(e, (list, tuple)) and len(e) == 3]
    if isinstance(raw, str):
        try:
            parsed = ast.literal_eval(raw)
            if isinstance(parsed, list):
                return [tuple(e) for e in parsed if isinstance(e, (list, tuple)) and len(e) == 3]
        except (ValueError, SyntaxError):
            pass
    return []


# ---------------------------------------------------------------------------
# NER evaluation helpers
# ---------------------------------------------------------------------------

def compute_ner_metrics(predictions: List[List[str]], references: List[List[str]]) -> Dict[str, Any]:
    """
    Compute entity-level precision / recall / F1 by type and overall.

    Args:
        predictions: list of predicted BIO tag sequences
        references:  list of gold BIO tag sequences (same length)

    Returns:
        dict with per-type and macro P/R/F1
    """
    from collections import defaultdict
    tp_by_type: Dict[str, int] = defaultdict(int)
    fp_by_type: Dict[str, int] = defaultdict(int)
    fn_by_type: Dict[str, int] = defaultdict(int)

    for pred_tags, true_tags in zip(predictions, references):
        length = min(len(pred_tags), len(true_tags))
        pred_spans = bio_to_spans(pred_tags[:length])
        true_spans = bio_to_spans(true_tags[:length])
        for span in pred_spans:
            if span in true_spans:
                tp_by_type[span[2]] += 1
            else:
                fp_by_type[span[2]] += 1
        for span in true_spans:
            if span not in pred_spans:
                fn_by_type[span[2]] += 1

    all_types = sorted(set(list(tp_by_type) + list(fp_by_type) + list(fn_by_type)))
    results: Dict[str, Any] = {}
    macro_p = macro_r = macro_f1 = 0.0

    for etype in all_types:
        tp = tp_by_type[etype]
        fp = fp_by_type[etype]
        fn = fn_by_type[etype]
        p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f = (2 * p * r / (p + r)) if (p + r) > 0 else 0.0
        results[etype] = {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f, 4), "support": tp + fn}
        macro_p += p
        macro_r += r
        macro_f1 += f

    n = max(len(all_types), 1)
    results["MACRO"] = {
        "precision": round(macro_p / n, 4),
        "recall": round(macro_r / n, 4),
        "f1": round(macro_f1 / n, 4),
    }
    return results


# ---------------------------------------------------------------------------
# Legacy NER evaluation
# ---------------------------------------------------------------------------

def evaluate_legacy_ner(test_csv: Path, max_samples: int = 200) -> Dict[str, Any]:
    """Evaluate the legacy BiLSTM-CRF NER model on a test CSV."""
    import pandas as pd

    logger.info("--- Evaluating Legacy NER (BiLSTM-CRF) ---")
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from backend.custom_nlp import EBayNLP
    except Exception as e:
        return {"error": f"Could not import legacy NLP: {e}"}

    try:
        nlp = EBayNLP()
    except Exception as e:
        return {"error": f"Could not instantiate EBayNLP: {e}"}

    if nlp.ner_model is None:
        return {"error": "Legacy NER model not loaded (run training first)."}

    df = pd.read_csv(test_csv)
    if max_samples and len(df) > max_samples:
        df = df.sample(n=max_samples, random_state=42).reset_index(drop=True)

    predictions, references = [], []
    latencies = []

    for _, row in df.iterrows():
        query = str(row.get("query", ""))
        if not query.strip():
            continue

        entities = safe_parse_entities(row.get("entities", "[]"))
        tokens = query.split()

        # Build gold BIO tags
        gold_tags = ["O"] * len(tokens)
        char_to_tok: Dict[int, int] = {}
        pos = 0
        for ti, tok in enumerate(tokens):
            for c in range(pos, pos + len(tok)):
                char_to_tok[c] = ti
            pos += len(tok) + 1

        for s, e, lbl in entities:
            canon = normalize_label(lbl)
            first = True
            seen: set = set()
            for c in range(int(s), min(int(e), len(query))):
                ti = char_to_tok.get(c)
                if ti is None or ti in seen:
                    continue
                seen.add(ti)
                gold_tags[ti] = f"B-{canon}" if first else f"I-{canon}"
                first = False

        # Predict
        t0 = time.perf_counter()
        try:
            result = nlp.extract_entities(query)
        except Exception:
            result = {}
        latencies.append((time.perf_counter() - t0) * 1000)

        # Convert predicted entities back to BIO tags over the same token list
        pred_tags = ["O"] * len(tokens)
        for etype, values in result.items():
            if etype in ("intent", "raw_query", "raw_entities"):
                continue
            canon_etype = normalize_label(etype)
            for val in (values if isinstance(values, list) else [values]):
                val_str = str(val).lower()
                # Greedy token-level match
                val_tokens = val_str.split()
                for ti in range(len(tokens) - len(val_tokens) + 1):
                    window = [tokens[ti + j].lower() for j in range(len(val_tokens))]
                    if window == val_tokens:
                        pred_tags[ti] = f"B-{canon_etype}"
                        for j in range(1, len(val_tokens)):
                            pred_tags[ti + j] = f"I-{canon_etype}"
                        break

        predictions.append(pred_tags)
        references.append(gold_tags)

    metrics = compute_ner_metrics(predictions, references)
    metrics["latency_ms_avg"] = round(float(np.mean(latencies)), 2) if latencies else 0.0
    metrics["samples_evaluated"] = len(predictions)
    return metrics


# ---------------------------------------------------------------------------
# NextGen NER evaluation
# ---------------------------------------------------------------------------

def evaluate_nextgen_ner(test_csv: Path, model_path: Path, max_samples: int = 200) -> Dict[str, Any]:
    """Evaluate the transformer NER model on a test CSV."""
    import pandas as pd

    logger.info("--- Evaluating NextGen NER (Transformer) ---")

    if not model_path.exists():
        return {"error": f"NextGen NER model not found at {model_path}. Run train_transformer_ner.py first."}

    try:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from backend_nextgen.nlp.inference import TransformerNERInference
    except Exception as e:
        return {"error": f"Could not import TransformerNERInference: {e}"}

    try:
        ner = TransformerNERInference(model_path=model_path, confidence_threshold=0.3)
    except Exception as e:
        return {"error": f"Could not load NextGen NER model: {e}"}

    df = pd.read_csv(test_csv)
    if max_samples and len(df) > max_samples:
        df = df.sample(n=max_samples, random_state=42).reset_index(drop=True)

    predictions, references = [], []
    latencies = []

    for _, row in df.iterrows():
        query = str(row.get("query", ""))
        if not query.strip():
            continue

        entities = safe_parse_entities(row.get("entities", "[]"))
        tokens = query.split()

        # Build gold BIO tags
        gold_tags = ["O"] * len(tokens)
        char_to_tok: Dict[int, int] = {}
        pos = 0
        for ti, tok in enumerate(tokens):
            for c in range(pos, pos + len(tok)):
                char_to_tok[c] = ti
            pos += len(tok) + 1

        for s, e, lbl in entities:
            canon = normalize_label(lbl)
            first = True
            seen: set = set()
            for c in range(int(s), min(int(e), len(query))):
                ti = char_to_tok.get(c)
                if ti is None or ti in seen:
                    continue
                seen.add(ti)
                gold_tags[ti] = f"B-{canon}" if first else f"I-{canon}"
                first = False

        # Predict
        t0 = time.perf_counter()
        try:
            preds = ner.predict(query)
        except Exception:
            preds = []
        latencies.append((time.perf_counter() - t0) * 1000)

        # Convert predictions back to word-level BIO tags (normalize predicted labels too)
        pred_tags = ["O"] * len(tokens)
        for pred in preds:
            canon_label = normalize_label(pred.label)
            val_tokens = pred.value.split()
            for ti in range(len(tokens) - len(val_tokens) + 1):
                window = [tokens[ti + j].lower() for j in range(len(val_tokens))]
                if window == val_tokens:
                    pred_tags[ti] = f"B-{canon_label}"
                    for j in range(1, len(val_tokens)):
                        pred_tags[ti + j] = f"I-{canon_label}"
                    break

        predictions.append(pred_tags)
        references.append(gold_tags)

    metrics = compute_ner_metrics(predictions, references)
    metrics["latency_ms_avg"] = round(float(np.mean(latencies)), 2) if latencies else 0.0
    metrics["samples_evaluated"] = len(predictions)
    return metrics


# ---------------------------------------------------------------------------
# Retrieval evaluation
# ---------------------------------------------------------------------------

def evaluate_retrieval(
    queries_file: Path,
    model_name: str,
    index_path: Path,
    metadata_path: Path,
    k_values: List[int] = None,
) -> Dict[str, Any]:
    """
    Evaluate dual-encoder retrieval using recall@K and MRR.

    queries_file: JSON file with a list of {"query": "...", "relevant_ids": ["id1", ...]}
    """
    if k_values is None:
        k_values = [1, 5, 10]

    logger.info("--- Evaluating Retrieval (Dual Encoder) ---")

    if not queries_file.exists():
        return {"error": f"Retrieval queries file not found: {queries_file}"}
    if not index_path.exists():
        return {"error": f"Retrieval index not found: {index_path}. Build the index first."}

    try:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from backend_nextgen.retrieval.dual_encoder import DualEncoderRetriever
    except Exception as e:
        return {"error": f"Could not import DualEncoderRetriever: {e}"}

    try:
        retriever = DualEncoderRetriever.from_disk(
            model_name=model_name,
            index_path=index_path,
            metadata_path=metadata_path,
        )
    except Exception as e:
        return {"error": f"Could not load retriever: {e}"}

    with open(queries_file, encoding="utf-8") as f:
        eval_queries = json.load(f)

    recall_at_k = {k: [] for k in k_values}
    mrr_scores = []

    for item in eval_queries:
        query = item["query"]
        relevant = set(str(rid) for rid in item.get("relevant_ids", []))
        if not relevant:
            continue

        max_k = max(k_values)
        results = retriever.retrieve(query, top_k=max_k)
        retrieved_ids = [r.item_id for r in results]

        # Recall@K
        for k in k_values:
            top_ids = set(retrieved_ids[:k])
            hit = len(relevant & top_ids) / len(relevant)
            recall_at_k[k].append(hit)

        # MRR
        rr = 0.0
        for rank, rid in enumerate(retrieved_ids, 1):
            if rid in relevant:
                rr = 1.0 / rank
                break
        mrr_scores.append(rr)

    metrics: Dict[str, Any] = {
        f"recall@{k}": round(float(np.mean(vals)), 4) if vals else 0.0
        for k, vals in recall_at_k.items()
    }
    metrics["mrr"] = round(float(np.mean(mrr_scores)), 4) if mrr_scores else 0.0
    metrics["queries_evaluated"] = len(mrr_scores)
    return metrics


# ---------------------------------------------------------------------------
# Ranking evaluation (NDCG)
# ---------------------------------------------------------------------------

def ndcg_at_k(relevances: List[float], k: int) -> float:
    """Compute NDCG@K."""
    def dcg(rels: List[float], k: int) -> float:
        return sum(r / np.log2(i + 2) for i, r in enumerate(rels[:k]))

    ideal = sorted(relevances, reverse=True)
    dcg_val = dcg(relevances, k)
    idcg_val = dcg(ideal, k)
    return dcg_val / idcg_val if idcg_val > 0 else 0.0


def evaluate_ranking(
    ranking_test_file: Path,
    model_name: str,
    k_values: List[int] = None,
) -> Dict[str, Any]:
    """
    Evaluate the neural reranker using NDCG@K.

    ranking_test_file: JSON list of {"query": "...", "items": [{"text": "...", "relevance": 1.0}, ...]}
      relevance should be in [0, 1] where 1 = most relevant.
    """
    if k_values is None:
        k_values = [5, 10]

    logger.info("--- Evaluating Ranking (Neural Reranker) ---")

    if not ranking_test_file.exists():
        return {"error": f"Ranking test file not found: {ranking_test_file}"}

    try:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from backend_nextgen.ranking.neural_reranker import NeuralReRanker
    except Exception as e:
        return {"error": f"Could not import NeuralReRanker: {e}"}

    try:
        reranker = NeuralReRanker(model_name=model_name)
    except Exception as e:
        return {"error": f"Could not load reranker: {e}"}

    with open(ranking_test_file, encoding="utf-8") as f:
        eval_cases = json.load(f)

    ndcg_by_k: Dict[int, List[float]] = {k: [] for k in k_values}

    for case in eval_cases:
        query = case["query"]
        items = case["items"]
        if not items:
            continue

        # Build item dicts for reranker
        item_dicts = [
            {"item_id": f"item_{i}", "title": it.get("text", ""), "description": ""}
            for i, it in enumerate(items)
        ]
        gold_relevances = [float(it.get("relevance", 0)) for it in items]

        try:
            reranked = reranker.rerank(query, item_dicts, top_k=len(item_dicts))
        except Exception:
            continue

        # Map reranker output order back to gold relevance scores
        id_to_rel = {f"item_{i}": r for i, r in enumerate(gold_relevances)}
        reranked_relevances = [id_to_rel.get(r.item_id, 0.0) for r in reranked]

        for k in k_values:
            ndcg_by_k[k].append(ndcg_at_k(reranked_relevances, k))

    return {
        f"ndcg@{k}": round(float(np.mean(vals)), 4) if vals else 0.0
        for k, vals in ndcg_by_k.items()
    } | {"cases_evaluated": sum(len(v) for v in ndcg_by_k.values()) // max(len(k_values), 1)}


# ---------------------------------------------------------------------------
# Quick smoke-test (no datasets required)
# ---------------------------------------------------------------------------

QUICK_QUERIES = [
    ("red Nike running shoes under $100", {"BRAND": ["Nike"], "COLOR": ["red"], "PRODUCT_TYPE": ["running shoes"], "PRICE_RANGE": ["under $100"]}),
    ("Sony WH-1000XM5 headphones", {"BRAND": ["Sony"], "MODEL": ["WH-1000XM5"], "PRODUCT_TYPE": ["headphones"]}),
    ("blue leather wallet size small", {"COLOR": ["blue"], "MATERIAL": ["leather"], "PRODUCT_TYPE": ["wallet"], "SIZE": ["small"]}),
    ("iPhone 15 Pro Max 256GB", {"BRAND": ["Apple"], "MODEL": ["iPhone 15 Pro Max"], "FEATURE": ["256GB"]}),
    ("gaming laptop under $800", {"PRODUCT_TYPE": ["gaming laptop"], "PRICE_RANGE": ["under $800"]}),
]


def run_quick_evaluation(engine: str) -> None:
    """Run a quick smoke-test on hard-coded queries without needing CSV files."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

    print("\n" + "=" * 60)
    print("QUICK EVALUATION — Entity Extraction Smoke Test")
    print("=" * 60)

    if engine in ("legacy", "both"):
        print("\n[Legacy Engine — BiLSTM-CRF]\n")
        try:
            from backend.custom_nlp import EBayNLP
            nlp = EBayNLP()
            if nlp.ner_model is None:
                print("  Legacy NER model not loaded. Run training first.")
            else:
                for query, expected in QUICK_QUERIES:
                    t0 = time.perf_counter()
                    result = nlp.extract_entities(query)
                    ms = (time.perf_counter() - t0) * 1000
                    print(f"  Query: {query!r}")
                    entities = {k: v for k, v in result.items() if k not in ("intent", "raw_query", "raw_entities") and v}
                    print(f"  Extracted: {entities}")
                    hits = sum(1 for k, vals in expected.items() if any(str(e).lower() in [str(v).lower() for v in result.get(k, [])] for e in vals))
                    print(f"  Coverage: {hits}/{len(expected)} expected entity types found  ({ms:.1f} ms)\n")
        except Exception as e:
            print(f"  Error: {e}\n")

    if engine in ("nextgen", "both"):
        print("[NextGen Engine — Transformer NER]\n")
        try:
            from backend_nextgen.nlp.inference import TransformerNERInference
            # Use the trained deberta_crf model; fall back to models/ner (from new training script)
            model_path = Path("backend_nextgen/models/deberta_crf/best_model")
            if not model_path.exists():
                model_path = Path("backend_nextgen/models/ner")
            if not model_path.exists():
                print("  NextGen NER model not found. Run train_transformer_ner.py first.\n")
            else:
                ner = TransformerNERInference(model_path=model_path, confidence_threshold=0.3)
                for query, expected in QUICK_QUERIES:
                    t0 = time.perf_counter()
                    preds = ner.predict(query)
                    ms = (time.perf_counter() - t0) * 1000
                    grouped: Dict[str, List[str]] = {}
                    for p in preds:
                        grouped.setdefault(p.label, []).append(p.value)
                    print(f"  Query: {query!r}")
                    print(f"  Extracted: {grouped}")
                    hits = sum(1 for k in expected if k in grouped)
                    print(f"  Coverage: {hits}/{len(expected)} expected entity types found  ({ms:.1f} ms)\n")
        except Exception as e:
            print(f"  Error: {e}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate AI engines (NER, retrieval, ranking)")
    parser.add_argument("--engine", choices=["legacy", "nextgen", "both"], default="both")
    parser.add_argument("--ner_test", type=Path, default=None, help="Path to NER test CSV")
    parser.add_argument("--retrieval_test", type=Path, default=None, help="Path to retrieval queries JSON")
    parser.add_argument("--ranking_test", type=Path, default=None, help="Path to ranking test JSON")
    parser.add_argument("--nextgen_ner_model", type=Path, default=Path("backend_nextgen/models/deberta_crf/best_model"))
    parser.add_argument("--retrieval_index", type=Path, default=Path("backend_nextgen/data/vector_store/faiss_index.npy"))
    parser.add_argument("--retrieval_metadata", type=Path, default=Path("backend_nextgen/data/vector_store/metadata.npy"))
    parser.add_argument("--retrieval_model", default="intfloat/e5-base-v2")
    parser.add_argument("--reranker_model", default="cross-encoder/ms-marco-MiniLM-L-6-v2")
    parser.add_argument("--max_samples", type=int, default=200)
    parser.add_argument("--quick", action="store_true", help="Run quick smoke test only (no datasets needed)")
    parser.add_argument("--output", type=Path, default=None, help="Save results JSON to this path")
    args = parser.parse_args()

    all_results: Dict[str, Any] = {}

    if args.quick:
        run_quick_evaluation(args.engine)
        return

    # --- NER ---
    if args.ner_test:
        if args.engine in ("legacy", "both"):
            legacy_ner = evaluate_legacy_ner(args.ner_test, args.max_samples)
            all_results["legacy_ner"] = legacy_ner
            print("\n[Legacy NER Results]")
            _print_ner_results(legacy_ner)

        if args.engine in ("nextgen", "both"):
            nextgen_ner = evaluate_nextgen_ner(args.ner_test, args.nextgen_ner_model, args.max_samples)
            all_results["nextgen_ner"] = nextgen_ner
            print("\n[NextGen NER Results]")
            _print_ner_results(nextgen_ner)
    else:
        logger.info("Skipping NER evaluation (--ner_test not provided).")

    # --- Retrieval ---
    if args.retrieval_test and args.engine in ("nextgen", "both"):
        retrieval_metrics = evaluate_retrieval(
            queries_file=args.retrieval_test,
            model_name=args.retrieval_model,
            index_path=args.retrieval_index,
            metadata_path=args.retrieval_metadata,
        )
        all_results["retrieval"] = retrieval_metrics
        print("\n[Retrieval Results]")
        for k, v in retrieval_metrics.items():
            print(f"  {k}: {v}")
    elif not args.retrieval_test:
        logger.info("Skipping retrieval evaluation (--retrieval_test not provided).")

    # --- Ranking ---
    if args.ranking_test and args.engine in ("nextgen", "both"):
        ranking_metrics = evaluate_ranking(
            ranking_test_file=args.ranking_test,
            model_name=args.reranker_model,
        )
        all_results["ranking"] = ranking_metrics
        print("\n[Ranking Results]")
        for k, v in ranking_metrics.items():
            print(f"  {k}: {v}")
    elif not args.ranking_test:
        logger.info("Skipping ranking evaluation (--ranking_test not provided).")

    if not args.ner_test and not args.retrieval_test and not args.ranking_test:
        print("\nNo evaluation targets specified. Use --quick for a smoke test or provide --ner_test / --retrieval_test / --ranking_test.")
        parser.print_help()
        return

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(all_results, f, indent=2)
        print(f"\nResults saved to {args.output}")


def _print_ner_results(results: Dict[str, Any]) -> None:
    if "error" in results:
        print(f"  ERROR: {results['error']}")
        return
    macro = results.get("MACRO", {})
    print(f"  Macro F1:        {macro.get('f1', 'N/A')}")
    print(f"  Macro Precision: {macro.get('precision', 'N/A')}")
    print(f"  Macro Recall:    {macro.get('recall', 'N/A')}")
    print(f"  Avg latency:     {results.get('latency_ms_avg', 'N/A')} ms")
    print(f"  Samples:         {results.get('samples_evaluated', 'N/A')}")
    print("  Per-type F1:")
    for etype, m in sorted(results.items()):
        if etype in ("MACRO", "latency_ms_avg", "samples_evaluated", "error"):
            continue
        print(f"    {etype:<20} F1={m['f1']}  P={m['precision']}  R={m['recall']}  support={m['support']}")


if __name__ == "__main__":
    main()
