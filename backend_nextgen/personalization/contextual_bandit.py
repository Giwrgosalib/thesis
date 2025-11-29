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
    explanation: Dict[str, float] = None


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
        best_explanation: Dict[str, float] = {} # Initialize best_explanation

        for item_id, features, metadata in candidates:
            mean = theta @ features
            variance = features @ A_inv @ features
            sampled_reward = np.random.normal(mean, self.alpha * variance)
            if sampled_reward > best_score:
                best_score = sampled_reward
                best_id = item_id
                best_meta = metadata
                best_explanation = {
                    "predicted_reward": float(mean),
                    "uncertainty_bonus": float(self.alpha * variance),
                    "final_score": float(sampled_reward)
                }

        return Recommendation(
            item_id=best_id, 
            score=best_score, 
            metadata=best_meta,
            explanation=best_explanation
        )

    def update(self, features: np.ndarray, reward: float) -> None:
        self.A += np.outer(features, features)
        self.b += reward * features

    def save_state(self, filepath: str) -> None:
        """Save the bandit state (A and b matrices) to disk."""
        np.savez(filepath, A=self.A, b=self.b)

    def load_state(self, filepath: str) -> None:
        """Load the bandit state from disk."""
        try:
            data = np.load(filepath)
            self.A = data["A"]
            self.b = data["b"]
        except Exception as e:
            print(f"Failed to load bandit state: {e}")
