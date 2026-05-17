"""
Expand the runtime knowledge graph using real co-occurrence data from the
unified training set, replacing the hard-coded whitelist of 10 electronics
brands with data-driven brand <-> category links and adding additional node
and edge types.

Writes:
  - backend_nextgen/data/knowledge_graph/expanded_triples.tsv
  - backend_nextgen/data/knowledge_graph/expanded_kg_stats.json

The orchestrator's _seed_knowledge_graph() can be modified to load this
expanded file instead of (or in addition to) the hard-coded seed.
"""

from __future__ import annotations

import argparse
import ast
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

import pandas as pd


STOPWORDS = {
    "the", "a", "an", "for", "with", "in", "on", "and", "or", "of", "to",
    "any", "some", "new", "good", "best",
}


def parse_entities(query: str, entities_str: str) -> dict[str, list[str]]:
    """Return {label_upper: [values_lower]} for one query."""
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
        if text and text not in STOPWORDS:
            out.setdefault(label.upper(), []).append(text)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--inputs",
        nargs="+",
        default=[
            "backend/data/unified_train.csv",
            "backend/data/unified_val.csv",
        ],
        help="Sources for co-occurrence statistics (excludes test by default).",
    )
    parser.add_argument(
        "--output_triples",
        default="backend_nextgen/data/knowledge_graph/expanded_triples.tsv",
    )
    parser.add_argument(
        "--output_stats",
        default="backend_nextgen/data/knowledge_graph/expanded_kg_stats.json",
    )
    parser.add_argument(
        "--min_cooccurrence", type=int, default=2,
        help="Minimum co-occurrence count to keep an edge.",
    )
    args = parser.parse_args()

    rows: list[dict] = []
    for path in args.inputs:
        df = pd.read_csv(path)
        for _, row in df.iterrows():
            ents = parse_entities(row["query"], row["entities"])
            if ents:
                rows.append(ents)

    print(f"Loaded {len(rows)} annotated queries from {len(args.inputs)} files.")

    # ── Aggregate co-occurrences ──
    brand_category: Counter = Counter()           # (brand, category)
    brand_ptype: Counter = Counter()              # (brand, product_type)
    ptype_color: Counter = Counter()              # (product_type, color)
    ptype_material: Counter = Counter()           # (product_type, material)
    ptype_feature: Counter = Counter()            # (product_type, feature)
    ptype_size: Counter = Counter()               # (product_type, size)
    ptype_usage: Counter = Counter()              # (product_type, usage)
    brand_set: set[str] = set()
    category_set: set[str] = set()
    ptype_set: set[str] = set()
    color_set: set[str] = set()
    material_set: set[str] = set()
    feature_set: set[str] = set()
    size_set: set[str] = set()
    usage_set: set[str] = set()

    for ents in rows:
        brands = ents.get("BRAND", [])
        cats = ents.get("CATEGORY", [])
        ptypes = ents.get("PRODUCT_TYPE", [])
        colors = ents.get("COLOR", [])
        materials = ents.get("MATERIAL", [])
        features = ents.get("FEATURE", [])
        sizes = ents.get("SIZE", [])
        usages = ents.get("USAGE", [])

        brand_set.update(brands)
        category_set.update(cats)
        ptype_set.update(ptypes)
        color_set.update(colors)
        material_set.update(materials)
        feature_set.update(features)
        size_set.update(sizes)
        usage_set.update(usages)

        for b in brands:
            for c in cats:
                brand_category[(b, c)] += 1
            for p in ptypes:
                brand_ptype[(b, p)] += 1
        for p in ptypes:
            for col in colors:
                ptype_color[(p, col)] += 1
            for m in materials:
                ptype_material[(p, m)] += 1
            for f in features:
                ptype_feature[(p, f)] += 1
            for s in sizes:
                ptype_size[(p, s)] += 1
            for u in usages:
                ptype_usage[(p, u)] += 1

    def keep(c: Counter) -> dict[tuple[str, str], int]:
        return {k: v for k, v in c.items() if v >= args.min_cooccurrence}

    brand_category_kept = keep(brand_category)
    brand_ptype_kept = keep(brand_ptype)
    ptype_color_kept = keep(ptype_color)
    ptype_material_kept = keep(ptype_material)
    ptype_feature_kept = keep(ptype_feature)
    ptype_size_kept = keep(ptype_size)
    ptype_usage_kept = keep(ptype_usage)

    # ── Write triples ──
    out_path = Path(args.output_triples)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    def write_triples(handle, edges: dict, relation: str, head_type: str, tail_type: str):
        for (h, t), w in sorted(edges.items(), key=lambda x: -x[1]):
            handle.write(f"{head_type}:{h}\t{relation}\t{tail_type}:{t}\t{w}\n")

    with out_path.open("w", encoding="utf-8") as f:
        f.write("# head\trelation\ttail\tweight\n")
        write_triples(f, brand_category_kept, "sold_in", "brand", "category")
        write_triples(f, brand_ptype_kept, "makes", "brand", "product_type")
        write_triples(f, ptype_color_kept, "has_color", "product_type", "color")
        write_triples(f, ptype_material_kept, "has_material", "product_type", "material")
        write_triples(f, ptype_feature_kept, "has_feature", "product_type", "feature")
        write_triples(f, ptype_size_kept, "has_size", "product_type", "size")
        write_triples(f, ptype_usage_kept, "has_usage", "product_type", "usage")

    # ── Stats ──
    n_nodes = (len(brand_set) + len(category_set) + len(ptype_set)
               + len(color_set) + len(material_set) + len(feature_set)
               + len(size_set) + len(usage_set))
    n_edges = sum(len(d) for d in (
        brand_category_kept, brand_ptype_kept, ptype_color_kept,
        ptype_material_kept, ptype_feature_kept, ptype_size_kept,
        ptype_usage_kept,
    ))

    stats = {
        "source_queries": len(rows),
        "min_cooccurrence_kept": args.min_cooccurrence,
        "nodes": {
            "brand": len(brand_set),
            "category": len(category_set),
            "product_type": len(ptype_set),
            "color": len(color_set),
            "material": len(material_set),
            "feature": len(feature_set),
            "size": len(size_set),
            "usage": len(usage_set),
            "total": n_nodes,
        },
        "edges": {
            "sold_in (brand->category)": len(brand_category_kept),
            "makes (brand->product_type)": len(brand_ptype_kept),
            "has_color (product_type->color)": len(ptype_color_kept),
            "has_material (product_type->material)": len(ptype_material_kept),
            "has_feature (product_type->feature)": len(ptype_feature_kept),
            "has_size (product_type->size)": len(ptype_size_kept),
            "has_usage (product_type->usage)": len(ptype_usage_kept),
            "total": n_edges,
        },
        "relationship_types": 7,
        "comparison_to_seed": {
            "seed_nodes": 70,          # 39 brand + 31 category
            "seed_edges": 10,          # whitelist of electronics brands
            "seed_relationship_types": 1,
        },
    }

    stats_path = Path(args.output_stats)
    with stats_path.open("w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

    # ── Console summary ──
    print("=" * 60)
    print("Knowledge Graph Expansion Summary")
    print("=" * 60)
    print(f"Source queries:  {len(rows)}")
    print(f"Min co-occurrence threshold: {args.min_cooccurrence}")
    print()
    print("Nodes by type:")
    for k, v in stats["nodes"].items():
        if k != "total":
            print(f"  {k:<14}  {v:>5}")
    print(f"  {'TOTAL':<14}  {stats['nodes']['total']:>5}")
    print()
    print("Edges by relation:")
    for k, v in stats["edges"].items():
        if k != "total":
            print(f"  {k:<40}  {v:>5}")
    print(f"  {'TOTAL EDGES':<40}  {stats['edges']['total']:>5}")
    print()
    print("Comparison to seed graph:")
    print(f"  Seed:     70 nodes,  10 edges, 1 relationship type")
    print(f"  Expanded: {n_nodes} nodes, {n_edges} edges, 7 relationship types")
    print()
    print(f"Saved triples to {out_path}")
    print(f"Saved stats   to {stats_path}")


if __name__ == "__main__":
    main()
