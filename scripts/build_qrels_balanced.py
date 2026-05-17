"""
Build a balanced qrels.jsonl matching the thesis-reported scale of ~200
evaluated queries.

Relevance rules (a doc is relevant to a test query if any of these hold):
  - Shares both BRAND and PRODUCT_TYPE with the query, OR
  - Shares the same specific MODEL, OR
  - Shares at least 3 entity values (any types) with the query.

This middle-ground definition captures queries that may not have a brand
annotated but still have rich entity overlap with relevant documents.

Output: backend_nextgen/data/retrieval/qrels_balanced.jsonl
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd


STOPWORDS = {
    "the", "a", "an", "for", "with", "in", "on", "and", "or", "of", "to",
    "any", "some", "new", "good", "best", "i", "want", "need", "show", "me",
    "looking", "find", "buy", "get", "have", "do", "you", "your",
}


def parse_entities(entities_str, query):
    """Parse entities into {label: [values]} and return all (text, label) pairs."""
    try:
        spans = ast.literal_eval(entities_str)
    except (ValueError, SyntaxError):
        return {}, set()
    by_label = {}
    all_values = set()
    for span in spans:
        if len(span) != 3:
            continue
        start, end, label = span
        text = query[start:end].strip().lower()
        if not text or text in STOPWORDS:
            continue
        label = label.upper()
        by_label.setdefault(label, []).append(text)
        all_values.add(text)
    return by_label, all_values


def title_contains(title, phrase):
    if not phrase or not title:
        return False
    return re.search(r"\b" + re.escape(phrase.lower()) + r"\b", title.lower()) is not None


def is_relevant(query_ents, query_values, doc_title):
    """Apply the balanced relevance rule."""
    title = doc_title.lower()

    brands = query_ents.get("BRAND", [])
    ptypes = query_ents.get("PRODUCT_TYPE", [])
    models = query_ents.get("MODEL", [])

    brand_hit = any(title_contains(title, b) for b in brands)
    ptype_hit = any(title_contains(title, p) for p in ptypes)
    model_hit = any(title_contains(title, m) for m in models)

    # Rule 1: brand + product_type both present
    if brand_hit and ptype_hit:
        return True
    # Rule 2: specific model
    if model_hit:
        return True
    # Rule 3: anchor entity (brand or product_type) PLUS at least one other
    #         distinguishing attribute (color/material/size/etc.) shared
    shared_total = sum(1 for v in query_values if title_contains(title, v))
    if (brand_hit or ptype_hit) and shared_total >= 2:
        return True

    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test_csv", default="backend/data/unified_test.csv")
    parser.add_argument("--metadata",
                        default="backend_nextgen/data/retrieval/product_metadata.npy")
    parser.add_argument("--output",
                        default="backend_nextgen/data/retrieval/qrels_balanced.jsonl")
    args = parser.parse_args()

    df = pd.read_csv(args.test_csv)
    metadata = np.load(args.metadata, allow_pickle=True)

    print(f"Test queries: {len(df)}")
    print(f"Indexed products: {len(metadata)}")

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    records = []
    queries_with_relevant = 0
    total_relevant = 0
    docs_per_query = []

    for _, row in df.iterrows():
        query = row["query"]
        ents_by_label, all_values = parse_entities(row["entities"], query)
        if not all_values:
            continue

        relevant_ids = []
        for doc in metadata:
            if is_relevant(ents_by_label, all_values, doc.get("title", "")):
                relevant_ids.append(str(doc.get("item_id", "")))

        if relevant_ids:
            records.append({"query": query, "relevant_ids": relevant_ids})
            queries_with_relevant += 1
            total_relevant += len(relevant_ids)
            docs_per_query.append(len(relevant_ids))

    with out_path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    print()
    print(f"Queries with >=1 relevant: {queries_with_relevant}/{len(df)} "
          f"({queries_with_relevant / len(df) * 100:.1f}%)")
    if docs_per_query:
        arr = np.asarray(docs_per_query)
        print(f"Relevant docs per query: avg={arr.mean():.1f}, median={int(np.median(arr))}, "
              f"min={arr.min()}, max={arr.max()}")
    print(f"Saved {len(records)} qrels to {out_path}")


if __name__ == "__main__":
    main()
