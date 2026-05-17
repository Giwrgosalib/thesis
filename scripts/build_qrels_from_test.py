"""
Build a qrels.jsonl file from unified_test.csv + product_metadata.npy.

For each test query, identify which "products" (training queries indexed in
the FAISS store) share entity values with the test query, and assign
multi-graded relevance based on the strength of overlap:

  - relevance 3: shares BRAND + PRODUCT_TYPE (strong topical match)
  - relevance 2: shares BRAND or PRODUCT_TYPE alone (partial topical match)
  - relevance 1: shares any non-trivial entity value (loose match)
  - relevance 0: no overlap (not in qrels)

The strict eval cutoff (used by evaluate_retrieval.py) is relevance >= 2.

Output: backend_nextgen/data/retrieval/qrels.jsonl
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd


# Tokens too generic to use as relevance signal on their own.
STOPWORDS = {
    "the", "a", "an", "for", "with", "in", "on", "and", "or", "of", "to",
    "any", "some", "new", "good", "best", "i", "want", "need", "show", "me",
    "looking", "for", "find", "buy", "get", "have", "do", "you", "your",
}


def parse_entities(entities_str: str, query: str) -> dict[str, list[str]]:
    """Parse entity span list into label -> [text values]."""
    try:
        spans = ast.literal_eval(entities_str)
    except (ValueError, SyntaxError):
        return {}
    out: dict[str, list[str]] = {}
    for span in spans:
        if len(span) != 3:
            continue
        start, end, label = span
        text = query[start:end].strip().lower()
        if not text or text in STOPWORDS:
            continue
        out.setdefault(label.upper(), []).append(text)
    return out


def title_contains(title: str, phrase: str) -> bool:
    """Check whether `phrase` occurs as a word/phrase in `title`."""
    if not phrase or not title:
        return False
    pattern = r"\b" + re.escape(phrase.lower()) + r"\b"
    return re.search(pattern, title.lower()) is not None


def relevance_score(query_ents: dict[str, list[str]], doc_title: str) -> int:
    """Score how relevant doc_title is to a test query's entities."""
    title = doc_title.lower()

    brand_hit = any(title_contains(title, b) for b in query_ents.get("BRAND", []))
    ptype_hit = any(title_contains(title, p) for p in query_ents.get("PRODUCT_TYPE", []))
    model_hit = any(title_contains(title, m) for m in query_ents.get("MODEL", []))

    # Strong: brand + product type both present, OR specific model present
    if (brand_hit and ptype_hit) or model_hit:
        return 3

    # Partial: brand alone or product type alone
    if brand_hit or ptype_hit:
        return 2

    # Loose: any other entity value present
    for label, vals in query_ents.items():
        if label in ("BRAND", "PRODUCT_TYPE", "MODEL"):
            continue
        for v in vals:
            if title_contains(title, v):
                return 1

    return 0


def main():
    parser = argparse.ArgumentParser(description="Build qrels.jsonl from test entities")
    parser.add_argument("--test_csv", default="backend/data/unified_test.csv")
    parser.add_argument("--metadata",
                        default="backend_nextgen/data/retrieval/product_metadata.npy")
    parser.add_argument("--output",
                        default="backend_nextgen/data/retrieval/qrels.jsonl")
    parser.add_argument("--min_relevance", type=int, default=2,
                        help="Minimum relevance grade for a doc to appear in qrels")
    args = parser.parse_args()

    df = pd.read_csv(args.test_csv)
    metadata = np.load(args.metadata, allow_pickle=True)

    print(f"Test queries: {len(df)}")
    print(f"Indexed products: {len(metadata)}")

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    qrels_records = []
    queries_with_relevant = 0
    total_relevant = 0

    for _, row in df.iterrows():
        query = row["query"]
        ents = parse_entities(row["entities"], query)
        if not ents:
            continue

        relevant_ids: list[str] = []
        for doc in metadata:
            score = relevance_score(ents, doc.get("title", ""))
            if score >= args.min_relevance:
                relevant_ids.append(str(doc.get("item_id", "")))

        if relevant_ids:
            qrels_records.append({"query": query, "relevant_ids": relevant_ids})
            queries_with_relevant += 1
            total_relevant += len(relevant_ids)

    with out_path.open("w", encoding="utf-8") as f:
        for r in qrels_records:
            f.write(json.dumps(r) + "\n")

    print()
    print(f"Queries with >=1 relevant doc: {queries_with_relevant}/{len(df)} "
          f"({queries_with_relevant / len(df) * 100:.1f}%)")
    if queries_with_relevant > 0:
        print(f"Avg relevant docs per query: "
              f"{total_relevant / queries_with_relevant:.1f}")
    print(f"Saved {len(qrels_records)} qrels records to {out_path}")


if __name__ == "__main__":
    main()
