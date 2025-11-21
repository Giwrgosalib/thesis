"""
Lightweight product knowledge graph utilities.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Tuple

import networkx as nx


@dataclass
class KGNode:
    node_id: str
    label: str
    attributes: Dict[str, str]


class KnowledgeGraph:
    """
    Maintains a heterogeneous graph for products, brands, and attributes.
    """

    def __init__(self) -> None:
        self.graph = nx.MultiDiGraph()

    def load(self, triples: Iterable[Tuple[str, str, str]]) -> None:
        for head, relation, tail in triples:
            self.graph.add_edge(head, tail, relation=relation)

    def add_node(self, node: KGNode) -> None:
        self.graph.add_node(node.node_id, label=node.label, **node.attributes)

    def neighbors(self, node_id: str) -> Iterable[str]:
        return self.graph.neighbors(node_id)

    def find_related_products(self, brand: str, limit: int = 10) -> Iterable[str]:
        matches = []
        for node, data in self.graph.nodes(data=True):
            if data.get("label") == "product" and data.get("brand") == brand:
                matches.append(node)
            if len(matches) >= limit:
                break
        return matches
