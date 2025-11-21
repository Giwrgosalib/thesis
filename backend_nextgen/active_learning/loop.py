"""
Uncertainty-driven active learning loop for continuous model improvement.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any

import numpy as np


@dataclass
class ActiveLearningExample:
    query: str
    tokens: List[str]
    predicted_tags: List[str]
    confidence: float


class UncertaintySampler:
    """
    Scores examples by entropy to surface low-confidence predictions.
    """

    def __init__(self, threshold: float = 0.25, batch_size: int = 128) -> None:
        self.threshold = threshold
        self.batch_size = batch_size

    @staticmethod
    def entropy(probabilities: np.ndarray) -> float:
        clipped = np.clip(probabilities, 1e-9, 1.0)
        return float(-np.sum(clipped * np.log(clipped)))

    def sample(self, logits: np.ndarray, tokens: List[str], query: str) -> ActiveLearningExample | None:
        probs = np.exp(logits) / np.sum(np.exp(logits), axis=-1, keepdims=True)
        example_entropy = np.mean([self.entropy(token_probs) for token_probs in probs])
        if example_entropy >= self.threshold:
            predicted_tags = np.argmax(probs, axis=-1)
            return ActiveLearningExample(
                query=query,
                tokens=tokens,
                predicted_tags=[str(tag) for tag in predicted_tags],
                confidence=1.0 - example_entropy,
            )
        return None
