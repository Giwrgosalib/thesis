"""
Contextual Thompson Sampling for personalization.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np


@dataclass
class Recommendation:
    item_id: str
    score: float
    metadata: Dict[str, str]


class ContextualThompsonSampling:
    """
    Simple linear contextual bandit using Bayesian updates.
    """

    def __init__(self, feature_dim: int, alpha: float = 1.0) -> None:
        self.feature_dim = feature_dim
        self.alpha = alpha
        self.A = np.eye(feature_dim)
        self.b = np.zeros(feature_dim)

    def select(self, candidates: List[Tuple[str, np.ndarray, Dict[str, str]]]) -> Recommendation:
        A_inv = np.linalg.inv(self.A)
        theta = A_inv @ self.b

        best_id = ""
        best_score = float("-inf")
        best_meta: Dict[str, str] = {}

        for item_id, features, metadata in candidates:
            mean = theta @ features
            variance = features @ A_inv @ features
            sampled_reward = np.random.normal(mean, self.alpha * variance)
            if sampled_reward > best_score:
                best_score = sampled_reward
                best_id = item_id
                best_meta = metadata

        return Recommendation(item_id=best_id, score=best_score, metadata=best_meta)

    def update(self, features: np.ndarray, reward: float) -> None:
        self.A += np.outer(features, features)
        self.b += reward * features
