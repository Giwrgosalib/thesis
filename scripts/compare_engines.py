"""
Side-by-side A/B comparison of the Legacy (BiLSTM-CRF) and NextGen (DeBERTa)
NER engines for a diploma thesis.

For each query the script reports:
  - Entities extracted by each engine
  - Which entity types each engine found / missed
  - Wall-clock inference latency for each engine
  - Optional: save a JSON comparison table for offline analysis

Usage (interactive mode):
    python scripts/compare_engines.py

Usage (batch mode — queries from a CSV/JSONL file):
    python scripts/compare_engines.py \
        --input  backend/data/test_dataset.csv \
        --output results/ab_comparison.json

Usage (single query):
    python scripts/compare_engines.py --query "red Nike running shoes under 100"
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend_nextgen.config.entity_schema import normalise_label  # noqa: E402


# ---------------------------------------------------------------------------
# Engine loaders (lazy — only import what's needed)
# ---------------------------------------------------------------------------

def load_legacy_engine():
    """Load the legacy BiLSTM-CRF engine."""
    from backend.custom_nlp import EBayNLP
    nlp = EBayNLP()
    return nlp


def load_nextgen_engine(model_dir: str = "backend_nextgen/models/ner"):
    """Load the NextGen DeBERTa NER engine directly (no full orchestrator needed)."""
    import torch
    from transformers import AutoTokenizer, AutoModelForTokenClassification

    model_path = Path(model_dir)
    label_map_path = model_path / "label_map.json"
    if not label_map_path.exists():
        raise FileNotFoundError(f"label_map.json not found in {model_path}")

    with open(label_map_path, encoding="utf-8") as f:
        lmap = json.load(f)

    id2label = {int(k): v for k, v in lmap["id_to_label"].items()}
    tokenizer = AutoTokenizer.from_pretrained(str(model_path))
    model = AutoModelForTokenClassification.from_pretrained(str(model_path))
    model.eval()
    if torch.cuda.is_available():
        model = model.cuda()

    def predict(query: str) -> List[Dict[str, Any]]:
        """Return list of {text, label, start, end}."""
        tokens = query.split()
        enc = tokenizer(
            tokens, is_split_into_words=True, return_tensors="pt",
            truncation=True, max_length=128,
        )
        # Save word_ids before moving tensors to GPU (BatchEncoding loses this on dict conversion)
        word_ids = enc.word_ids(batch_index=0)
        if torch.cuda.is_available():
            enc = {k: v.cuda() for k, v in enc.items()}
        with torch.no_grad():
            logits = model(**enc).logits[0]
        preds = logits.argmax(-1).tolist()

        word_labels: Dict[int, str] = {}
        prev_wid = None
        for i, wid in enumerate(word_ids):
            if wid is None or wid == prev_wid:
                prev_wid = wid
                continue
            lbl = id2label.get(preds[i], "O")
            if lbl != "O":
                word_labels[wid] = lbl
            prev_wid = wid

        entities = []
        cur_lbl = cur_start = cur_end = None
        char_pos = 0
        for idx, tok in enumerate(tokens):
            raw = word_labels.get(idx, "O")
            base = raw[2:] if raw.startswith(("B-", "I-")) else raw
            if raw.startswith("B-"):
                if cur_lbl:
                    entities.append({"text": query[cur_start:cur_end], "label": cur_lbl,
                                     "start": cur_start, "end": cur_end})
                cur_lbl, cur_start, cur_end = base, char_pos, char_pos + len(tok)
            elif raw.startswith("I-") and cur_lbl == base:
                cur_end = char_pos + len(tok)
            else:
                if cur_lbl:
                    entities.append({"text": query[cur_start:cur_end], "label": cur_lbl,
                                     "start": cur_start, "end": cur_end})
                cur_lbl = None
            char_pos += len(tok) + 1
        if cur_lbl:
            entities.append({"text": query[cur_start:cur_end], "label": cur_lbl,
                              "start": cur_start, "end": cur_end})
        return entities

    return predict


# ---------------------------------------------------------------------------
# Per-query comparison
# ---------------------------------------------------------------------------

def compare_query(
    query: str,
    legacy_fn,
    nextgen_fn,
    gold_entities: Optional[List] = None,
) -> Dict[str, Any]:
    """Run both engines on one query and return a structured comparison."""

    # Legacy inference
    t0 = time.perf_counter()
    try:
        legacy_raw = legacy_fn.extract_entities(query)
        # Legacy engine returns entity labels as TOP-LEVEL keys (not nested under "entities").
        # Skip bookkeeping keys; pick up any key that maps to a canonical entity label.
        _SKIP = {"intent", "raw_query", "raw_entities", "entities"}
        legacy_ents = []
        for label, values in legacy_raw.items():
            if label in _SKIP or not values:
                continue
            canon = normalise_label(label) or label
            # values may be a list of strings or a list with mixed types (e.g. price tuples)
            if isinstance(values, list):
                text = ", ".join(str(v) for v in values if v is not None and str(v).strip())
            else:
                text = str(values).strip()
            if text:
                legacy_ents.append({"text": text, "label": canon})
    except Exception as exc:
        legacy_ents = [{"error": str(exc)}]
    legacy_ms = round((time.perf_counter() - t0) * 1000, 1)

    # NextGen inference
    t0 = time.perf_counter()
    try:
        raw_nextgen = nextgen_fn(query)
        # Normalise NextGen labels to canonical schema as well
        nextgen_ents = []
        for e in raw_nextgen:
            if "label" not in e:
                nextgen_ents.append(e)
                continue
            canon = normalise_label(e["label"]) or e["label"]
            nextgen_ents.append({**e, "label": canon})
    except Exception as exc:
        nextgen_ents = [{"error": str(exc)}]
    nextgen_ms = round((time.perf_counter() - t0) * 1000, 1)

    legacy_labels = {e["label"] for e in legacy_ents if "label" in e}
    nextgen_labels = {e["label"] for e in nextgen_ents if "label" in e}

    result = {
        "query": query,
        "legacy": {
            "entities": legacy_ents,
            "labels_found": sorted(legacy_labels),
            "latency_ms": legacy_ms,
        },
        "nextgen": {
            "entities": nextgen_ents,
            "labels_found": sorted(nextgen_labels),
            "latency_ms": nextgen_ms,
        },
        "agreement": sorted(legacy_labels & nextgen_labels),
        "legacy_only": sorted(legacy_labels - nextgen_labels),
        "nextgen_only": sorted(nextgen_labels - legacy_labels),
    }

    if gold_entities is not None:
        gold_labels = {e[2] for e in gold_entities if isinstance(e, (list, tuple)) and len(e) == 3}
        result["gold"] = {"labels": sorted(gold_labels)}
        result["legacy"]["tp"] = sorted(legacy_labels & gold_labels)
        result["legacy"]["fp"] = sorted(legacy_labels - gold_labels)
        result["legacy"]["fn"] = sorted(gold_labels - legacy_labels)
        result["nextgen"]["tp"] = sorted(nextgen_labels & gold_labels)
        result["nextgen"]["fp"] = sorted(nextgen_labels - gold_labels)
        result["nextgen"]["fn"] = sorted(gold_labels - nextgen_labels)

    return result


def print_comparison(result: Dict[str, Any]) -> None:
    q = result["query"]
    sep = "=" * 70
    dash = "-" * 70
    print(f"\n{sep}")
    print(f"Query: {q}")
    print(dash)

    L = result["legacy"]
    N = result["nextgen"]
    print(f"  {'LEGACY (BiLSTM-CRF)':<35} {'NEXTGEN (DeBERTa)':<35}")
    print(f"  Latency: {L['latency_ms']:.1f} ms{'':<20} Latency: {N['latency_ms']:.1f} ms")

    all_labels = sorted(set(L["labels_found"]) | set(N["labels_found"]))
    legacy_ent_map = {e.get("label"): e.get("text", "") for e in L["entities"] if "label" in e}
    nextgen_ent_map = {e.get("label"): e.get("text", "") for e in N["entities"] if "label" in e}

    if all_labels:
        print(f"\n  {'Label':<20} {'Legacy':<25} {'NextGen':<25}")
        print(f"  {'-'*20} {'-'*25} {'-'*25}")
        for lbl in all_labels:
            l_text = (legacy_ent_map.get(lbl) or "-")[:24]
            n_text = (nextgen_ent_map.get(lbl) or "-")[:24]
            print(f"  {lbl:<20} {l_text:<25} {n_text:<25}")
    else:
        print("  (no entities found by either engine)")

    if result.get("agreement"):
        print(f"\n  [OK] Agreement: {', '.join(result['agreement'])}")
    if result.get("legacy_only"):
        print(f"  [L]  Legacy only: {', '.join(result['legacy_only'])}")
    if result.get("nextgen_only"):
        print(f"  [N]  NextGen only: {', '.join(result['nextgen_only'])}")

    if "gold" in result:
        print(f"\n  Gold labels:     {', '.join(result['gold']['labels']) or '(none)'}")
        print(f"  Legacy   TP/FP/FN: {result['legacy']['tp']} / {result['legacy']['fp']} / {result['legacy']['fn']}")
        print(f"  NextGen  TP/FP/FN: {result['nextgen']['tp']} / {result['nextgen']['fp']} / {result['nextgen']['fn']}")


def aggregate_stats(results: List[Dict]) -> Dict[str, Any]:
    """Compute aggregate latency and win-rate stats across all queries."""
    legacy_lat = [r["legacy"]["latency_ms"] for r in results]
    nextgen_lat = [r["nextgen"]["latency_ms"] for r in results]

    legacy_wins = nextgen_wins = ties = 0
    legacy_tp = legacy_fp = legacy_fn = 0
    nextgen_tp = nextgen_fp = nextgen_fn = 0

    for r in results:
        n_l = len(r["legacy"]["labels_found"])
        n_n = len(r["nextgen"]["labels_found"])
        if n_n > n_l:
            nextgen_wins += 1
        elif n_l > n_n:
            legacy_wins += 1
        else:
            ties += 1

        if "gold" in r:
            legacy_tp  += len(r["legacy"]["tp"])
            legacy_fp  += len(r["legacy"]["fp"])
            legacy_fn  += len(r["legacy"]["fn"])
            nextgen_tp += len(r["nextgen"]["tp"])
            nextgen_fp += len(r["nextgen"]["fp"])
            nextgen_fn += len(r["nextgen"]["fn"])

    def f1(tp, fp, fn):
        p = tp / (tp + fp) if tp + fp else 0
        r = tp / (tp + fn) if tp + fn else 0
        return round(2 * p * r / (p + r), 4) if (p + r) else 0

    stats: Dict[str, Any] = {
        "num_queries": len(results),
        "legacy_avg_latency_ms": round(sum(legacy_lat) / len(legacy_lat), 1) if legacy_lat else 0,
        "nextgen_avg_latency_ms": round(sum(nextgen_lat) / len(nextgen_lat), 1) if nextgen_lat else 0,
        "entity_count_wins": {
            "legacy": legacy_wins, "nextgen": nextgen_wins, "tie": ties,
        },
    }
    if legacy_tp + legacy_fp + legacy_fn + nextgen_tp + nextgen_fp + nextgen_fn > 0:
        stats["legacy_macro_f1_vs_gold"]  = f1(legacy_tp, legacy_fp, legacy_fn)
        stats["nextgen_macro_f1_vs_gold"] = f1(nextgen_tp, nextgen_fp, nextgen_fn)
    return stats


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="A/B comparison of Legacy vs NextGen NER engines")
    parser.add_argument("--query",   default=None, help="Single query to compare")
    parser.add_argument("--input",   default=None, help="CSV/JSONL with queries (and optional entities column)")
    parser.add_argument("--output",  default=None, help="Save full comparison JSON to this path")
    parser.add_argument("--nextgen_model", default="backend_nextgen/models/ner")
    parser.add_argument("--max_samples", type=int, default=None)
    parser.add_argument("--no_legacy", action="store_true", help="Skip legacy engine (faster)")
    args = parser.parse_args()

    print("Loading engines…")
    legacy_fn = None if args.no_legacy else load_legacy_engine()
    nextgen_fn = load_nextgen_engine(args.nextgen_model)
    print("Engines ready.\n")

    queries_with_gold: List[tuple] = []

    if args.query:
        queries_with_gold = [(args.query, None)]

    elif args.input:
        input_path = Path(args.input)
        if input_path.suffix == ".csv":
            import pandas as pd
            df = pd.read_csv(input_path)
            if args.max_samples:
                df = df.head(args.max_samples)
            for _, row in df.iterrows():
                gold = None
                if "entities" in df.columns:
                    try:
                        gold = ast.literal_eval(str(row["entities"]))
                    except Exception:
                        gold = None
                queries_with_gold.append((str(row["query"]), gold))
        else:
            with open(input_path, encoding="utf-8") as f:
                for line in f:
                    obj = json.loads(line.strip())
                    queries_with_gold.append((obj["query"], obj.get("entities")))
                    if args.max_samples and len(queries_with_gold) >= args.max_samples:
                        break
    else:
        # Interactive mode
        print("Interactive A/B comparison mode. Type a query and press Enter.")
        print("Empty input exits.\n")
        while True:
            try:
                query = input("Query> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not query:
                break
            result = compare_query(query, legacy_fn, nextgen_fn)
            print_comparison(result)
        return

    # Batch mode
    all_results = []
    for i, (query, gold) in enumerate(queries_with_gold, 1):
        print(f"[{i}/{len(queries_with_gold)}] {query[:80]}")
        result = compare_query(query, legacy_fn, nextgen_fn, gold_entities=gold)
        print_comparison(result)
        all_results.append(result)

    if all_results:
        stats = aggregate_stats(all_results)
        print(f"\n{'='*70}")
        print("  Aggregate Statistics")
        print(f"{'='*70}")
        print(f"  Queries:           {stats['num_queries']}")
        print(f"  Legacy avg latency:  {stats['legacy_avg_latency_ms']} ms")
        print(f"  NextGen avg latency: {stats['nextgen_avg_latency_ms']} ms")
        wins = stats["entity_count_wins"]
        print(f"  Entity count wins: Legacy={wins['legacy']} | NextGen={wins['nextgen']} | Tie={wins['tie']}")
        if "legacy_macro_f1_vs_gold" in stats:
            print(f"  Legacy vs gold F1:  {stats['legacy_macro_f1_vs_gold']}")
            print(f"  NextGen vs gold F1: {stats['nextgen_macro_f1_vs_gold']}")

        if args.output:
            out = Path(args.output)
            out.parent.mkdir(parents=True, exist_ok=True)
            with open(out, "w", encoding="utf-8") as f:
                json.dump({"stats": stats, "results": all_results}, f, indent=2)
            print(f"\n  Full comparison saved to {out}")


if __name__ == "__main__":
    main()
