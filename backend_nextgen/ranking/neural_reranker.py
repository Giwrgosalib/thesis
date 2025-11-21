"""
Neural re-ranking for eBay search results.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any

import torch

try:
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
except ImportError as exc:
    raise ImportError("Install transformers to use the neural re-ranker") from exc


@dataclass
class RankedItem:
    item_id: str
    score: float
    payload: Dict[str, Any]


class NeuralReRanker:
    """
    Cross-encoder scorer trained on click/satisfaction data.
    """

    def __init__(self, model_name: str, device: str | torch.device = "cpu") -> None:
        self.device = torch.device(device)
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        self.model.to(self.device)
        self.model.eval()

    def score(self, query: str, item_texts: List[str]) -> torch.Tensor:
        encoded = self.tokenizer(
            [query] * len(item_texts),
            item_texts,
            padding=True,
            truncation=True,
            return_tensors="pt",
        ).to(self.device)
        with torch.no_grad():
            outputs = self.model(**encoded)
            logits = outputs.logits.squeeze(-1)
        return logits.cpu()

    def rerank(self, query: str, items: List[Dict[str, Any]], top_k: int = 20) -> List[RankedItem]:
        item_texts = [item["title"] + " " + item.get("description", "") for item in items]
        scores = self.score(query, item_texts)
        sorted_indices = torch.argsort(scores, descending=True)[:top_k]
        return [
            RankedItem(
                item_id=items[idx]["item_id"],
                score=float(scores[idx]),
                payload=items[idx],
            )
            for idx in sorted_indices
        ]
