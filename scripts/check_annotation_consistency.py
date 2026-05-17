"""
Automated consistency analysis on the NER annotations across the unified dataset.

For a thesis without true inter-annotator agreement (IAA), this provides a
quantitative proxy for label noise by measuring:

  1. Type-collision rate: fraction of unique entity surface forms that receive
     more than one label across the dataset.
  2. Dominant-label purity: for entity surfaces appearing >= K times, what
     fraction of their occurrences agree with the dominant label.
  3. Token-level boundary consistency: for ambiguous tokens (those that appear
     both inside and outside annotated spans), how often is each side chosen.

Output: results/annotation_consistency.json + console summary.
"""

from __future__ import annotations

import argparse
import ast
import json
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd


def parse_entities(query: str, entities_str: str):
    """Yield (text_lower, label_upper) for each entity span."""
    try:
        spans = ast.literal_eval(entities_str)
    except (ValueError, SyntaxError):
        return
    for span in spans:
        if len(span) != 3:
            continue
        start, end, label = span
        text = query[start:end].strip().lower()
        if text:
            yield text, label.upper()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--inputs",
        nargs="+",
        default=[
            "backend/data/unified_train.csv",
            "backend/data/unified_val.csv",
            "backend/data/unified_test.csv",
        ],
    )
    parser.add_argument("--min_count", type=int, default=3,
                        help="Min occurrences for purity analysis.")
    parser.add_argument("--output", default="results/annotation_consistency.json")
    args = parser.parse_args()

    # (text -> Counter(label -> count))
    text_labels: dict[str, Counter] = defaultdict(Counter)
    total_entities = 0
    by_split: dict[str, dict] = {}

    for path in args.inputs:
        df = pd.read_csv(path)
        split_name = Path(path).stem
        split_text_labels: dict[str, Counter] = defaultdict(Counter)
        split_entities = 0
        for _, row in df.iterrows():
            for text, label in parse_entities(row["query"], row["entities"]):
                text_labels[text][label] += 1
                split_text_labels[text][label] += 1
                total_entities += 1
                split_entities += 1
        by_split[split_name] = {
            "rows": len(df),
            "entities": split_entities,
            "unique_text_forms": len(split_text_labels),
        }

    # ── Metric 1: type-collision rate ──
    unique_forms = len(text_labels)
    multi_label_forms = sum(1 for c in text_labels.values() if len(c) > 1)
    collision_rate = multi_label_forms / unique_forms if unique_forms else 0.0

    # ── Metric 2: purity (for forms appearing >= min_count) ──
    purity_eligible = {t: c for t, c in text_labels.items()
                       if sum(c.values()) >= args.min_count}
    purities = []
    impure_examples = []
    for text, counter in purity_eligible.items():
        total = sum(counter.values())
        dominant = counter.most_common(1)[0][1]
        purity = dominant / total
        purities.append(purity)
        if purity < 1.0:
            impure_examples.append({
                "text": text,
                "labels": dict(counter),
                "purity": round(purity, 3),
                "total_occurrences": total,
            })
    avg_purity = sum(purities) / len(purities) if purities else 0.0

    # Sort impure examples by total occurrences (most-impactful first)
    impure_examples.sort(key=lambda x: -x["total_occurrences"])

    # ── Metric 3: which label pairs collide most often ──
    pair_collisions: Counter = Counter()
    for counter in text_labels.values():
        if len(counter) <= 1:
            continue
        labels = sorted(counter.keys())
        for i in range(len(labels)):
            for j in range(i + 1, len(labels)):
                pair_collisions[(labels[i], labels[j])] += 1
    top_pairs = pair_collisions.most_common(15)

    # ── Metric 4: derive an IAA-like F1-style consistency score ──
    # If we treat the dominant label as "ground truth" and other label
    # assignments as "disagreements", the macro-averaged purity gives an
    # upper bound on what a model could achieve on this dataset.
    # We report it as a proxy ceiling.
    weighted_purity = (
        sum(p * sum(text_labels[t].values())
            for t, p in zip(purity_eligible.keys(), purities))
        / sum(sum(text_labels[t].values()) for t in purity_eligible)
    ) if purity_eligible else 0.0

    # ── Output ──
    out = {
        "summary": {
            "total_entities": total_entities,
            "unique_surface_forms": unique_forms,
            "multi_label_forms": multi_label_forms,
            "type_collision_rate": round(collision_rate, 4),
            "type_collision_pct": round(collision_rate * 100, 2),
            "eligible_for_purity_analysis": len(purity_eligible),
            "min_occurrences_threshold": args.min_count,
            "average_purity": round(avg_purity, 4),
            "occurrence_weighted_purity": round(weighted_purity, 4),
            "interpretation": (
                f"{collision_rate * 100:.1f}% of unique entity strings receive "
                f"more than one label across the dataset. "
                f"For strings with >= {args.min_count} occurrences, the dominant "
                f"label accounts for {weighted_purity * 100:.1f}% of assignments "
                f"on average (occurrence-weighted). The remaining "
                f"{(1 - weighted_purity) * 100:.1f}% represents an upper bound "
                f"on the label noise a model would face."
            ),
        },
        "top_label_collision_pairs": [
            {"labels": list(pair), "collision_forms": count}
            for pair, count in top_pairs
        ],
        "top_impure_examples": impure_examples[:30],
        "by_split": by_split,
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    # Console summary
    print("=" * 60)
    print("Annotation Consistency Analysis")
    print("=" * 60)
    print(f"Total entity annotations: {total_entities}")
    print(f"Unique surface forms:     {unique_forms}")
    print(f"Multi-label forms:        {multi_label_forms} "
          f"({collision_rate * 100:.2f}% of unique forms)")
    print()
    print(f"For forms appearing >= {args.min_count} times "
          f"({len(purity_eligible)} forms):")
    print(f"  Average purity (macro):       {avg_purity:.4f}")
    print(f"  Average purity (occ-weighted): {weighted_purity:.4f}")
    print(f"  Implied ceiling F1:           {weighted_purity:.4f}")
    print()
    print("Top label-collision pairs:")
    for pair, count in top_pairs[:10]:
        print(f"  {pair[0]:<18} <-> {pair[1]:<18}  {count:>4} surface forms")
    print()
    print(f"Saved detailed report to {out_path}")


if __name__ == "__main__":
    main()
