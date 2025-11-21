"""
Pipeline for constructing a product knowledge graph from structured CSV/JSON data.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, Tuple

from backend_nextgen.knowledge.graph_builder import KnowledgeGraph, KGNode


def load_product_rows(csv_path: Path) -> Iterable[dict]:
    with csv_path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            yield row


def build_triples(rows: Iterable[dict]) -> Iterable[Tuple[str, str, str]]:
    for row in rows:
        product_id = row.get("item_id") or row.get("sku") or row.get("id")
        brand = row.get("brand")
        category = row.get("category")
        if product_id and brand:
            yield (product_id, "has_brand", brand)
        if product_id and category:
            yield (product_id, "has_category", category)


def run_knowledge_graph_pipeline(csv_path: Path | None = None, output_path: Path | None = None) -> None:
    if csv_path is None:
        csv_path = Path("data/products.csv")
    if output_path is None:
        output_path = Path("data/knowledge_graph/triples.txt")
    kg = KnowledgeGraph()
    rows = list(load_product_rows(csv_path))
    triples = list(build_triples(rows))
    kg.load(triples)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for head, relation, tail in triples:
            handle.write(f"{head}\t{relation}\t{tail}\n")
