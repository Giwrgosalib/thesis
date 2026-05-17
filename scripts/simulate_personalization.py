"""
Reproducible simulation of the contextual Thompson-sampling bandit.

Creates N synthetic user profiles, each with a small set of preferred brands
and categories. For each session, the simulator samples a query, fetches
candidate products, and emits a click event whose probability depends on
how well the candidate matches that user's profile. The bandit is updated
online from these events, and we measure:

  - Cumulative CTR over interactions
  - Convergence iteration (first time the moving-average CTR exceeds a
    threshold above the random-baseline CTR)
  - Final CTR uplift over a random-ranking baseline
  - Exploration vs exploitation balance

Output: results/personalization_simulation.json
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ---------------------------------------------------------------------------
# Profile generation
# ---------------------------------------------------------------------------

ALL_BRANDS = [
    "nike", "adidas", "apple", "samsung", "sony", "lg", "dell", "hp",
    "lenovo", "microsoft", "asus", "acer", "razer", "logitech", "canon",
    "gopro", "fitbit", "garmin", "bose", "jbl",
]
ALL_CATEGORIES = [
    "electronics", "sneakers", "watches", "headphones", "laptops",
    "smartphones", "cameras", "gaming", "fitness", "fashion",
]


def make_profiles(n: int, seed: int = 42) -> List[Dict]:
    rng = random.Random(seed)
    profiles = []
    for i in range(n):
        n_brands = rng.randint(1, 3)
        n_cats   = rng.randint(1, 2)
        profiles.append({
            "id": f"user_{i}",
            "brands":     rng.sample(ALL_BRANDS, n_brands),
            "categories": rng.sample(ALL_CATEGORIES, n_cats),
        })
    return profiles


# ---------------------------------------------------------------------------
# Simulated click model
# ---------------------------------------------------------------------------

def click_probability(profile: Dict, candidate: Dict) -> float:
    """
    Click probability given a user's profile and a candidate product.

    Brand match: +0.30 per matched brand (capped at 1).
    Category match: +0.20 per matched category.
    Baseline noise: 0.05.

    Returns probability in [0, 1].
    """
    p = 0.05
    cand_brands = {b.lower() for b in candidate.get("brands", [])}
    cand_cats   = {c.lower() for c in candidate.get("categories", [])}
    for b in profile["brands"]:
        if b in cand_brands:
            p += 0.30
    for c in profile["categories"]:
        if c in cand_cats:
            p += 0.20
    return float(min(p, 1.0))


def make_candidates(rng: random.Random, k: int = 10) -> List[Dict]:
    """Generate K plausible candidate products with diverse brand/category mixes."""
    cands = []
    for i in range(k):
        cands.append({
            "id": f"item_{i}",
            "brands":     [rng.choice(ALL_BRANDS)],
            "categories": [rng.choice(ALL_CATEGORIES)],
        })
    return cands


# ---------------------------------------------------------------------------
# Feature vector for the bandit (matches orchestrator's 32-d schema sketch)
# ---------------------------------------------------------------------------

ENTITY_TYPES = [
    "BRAND", "PRODUCT_TYPE", "CATEGORY", "MODEL", "COLOR", "SIZE",
    "PRICE_RANGE", "CONDITION", "MATERIAL", "FEATURE", "TECH", "SHIPPING",
]


def context_features(profile: Dict, candidate: Dict) -> np.ndarray:
    """32-dim feature vector composed of profile and candidate signals."""
    v = np.zeros(32, dtype=np.float32)
    pref_brands = {b.lower() for b in profile["brands"]}
    pref_cats   = {c.lower() for c in profile["categories"]}
    cand_brands = {b.lower() for b in candidate.get("brands", [])}
    cand_cats   = {c.lower() for c in candidate.get("categories", [])}

    v[0] = 1.0 if cand_brands & pref_brands else 0.0
    v[1] = 1.0 if cand_cats   & pref_cats   else 0.0
    v[2] = min(len(pref_brands) / 5.0, 1.0)
    v[3] = min(len(pref_cats) / 5.0, 1.0)
    v[4] = 1.0  # logged-in
    v[5] = float(len(cand_brands & pref_brands)) / max(len(pref_brands), 1)
    v[6] = float(len(cand_cats & pref_cats))   / max(len(pref_cats), 1)
    # Sparse one-hot block for brand identity (slots 7-26)
    for i, b in enumerate(ALL_BRANDS[:20]):
        if b in cand_brands:
            v[7 + i] = 1.0
    return v


# ---------------------------------------------------------------------------
# Simulation loop
# ---------------------------------------------------------------------------

def run_simulation(
    n_users: int, sessions_per_user: int, candidates_per_session: int,
    exploration_alpha: float, seed: int,
) -> Dict:
    from backend_nextgen.personalization.contextual_bandit import ContextualThompsonSampling

    bandit = ContextualThompsonSampling(feature_dim=32, alpha=exploration_alpha)
    profiles = make_profiles(n_users, seed=seed)
    rng = random.Random(seed)

    bandit_clicks = 0
    random_clicks = 0
    total_interactions = 0
    ctr_history_bandit: List[float] = []
    ctr_history_random: List[float] = []
    convergence_iter = None
    convergence_threshold = 0.10  # bandit CTR > random CTR + 10pp on rolling window

    for session_i in range(sessions_per_user * n_users):
        profile = profiles[session_i % n_users]
        candidates = make_candidates(rng, k=candidates_per_session)

        # ── Bandit decision ──
        features_per_cand = [context_features(profile, c) for c in candidates]
        bandit_choice = bandit.select(
            [(c["id"], features_per_cand[i], {}) for i, c in enumerate(candidates)]
        )
        bandit_pick = next(c for c in candidates if c["id"] == bandit_choice.item_id)
        p_click = click_probability(profile, bandit_pick)
        clicked = rng.random() < p_click
        if clicked:
            bandit_clicks += 1
        # Update bandit with observed reward
        bandit.update(context_features(profile, bandit_pick), 1.0 if clicked else 0.0)

        # ── Random baseline ──
        random_pick = rng.choice(candidates)
        p_random = click_probability(profile, random_pick)
        if rng.random() < p_random:
            random_clicks += 1

        total_interactions += 1
        cur_bandit_ctr = bandit_clicks / total_interactions
        cur_random_ctr = random_clicks / total_interactions
        ctr_history_bandit.append(cur_bandit_ctr)
        ctr_history_random.append(cur_random_ctr)

        # Convergence: bandit beats random by threshold for 50 consecutive interactions
        if convergence_iter is None and total_interactions >= 50:
            recent_bandit = np.mean(ctr_history_bandit[-50:])
            recent_random = np.mean(ctr_history_random[-50:])
            if recent_bandit - recent_random >= convergence_threshold:
                convergence_iter = total_interactions

    final_bandit_ctr = bandit_clicks / total_interactions
    final_random_ctr = random_clicks / total_interactions
    uplift_pp = (final_bandit_ctr - final_random_ctr) * 100
    uplift_pct = ((final_bandit_ctr - final_random_ctr) / final_random_ctr * 100) if final_random_ctr else 0.0

    return {
        "config": {
            "n_users": n_users,
            "sessions_per_user": sessions_per_user,
            "candidates_per_session": candidates_per_session,
            "exploration_alpha": exploration_alpha,
            "seed": seed,
            "total_interactions": total_interactions,
        },
        "results": {
            "final_bandit_ctr": round(final_bandit_ctr, 4),
            "final_random_ctr": round(final_random_ctr, 4),
            "uplift_absolute_pp": round(uplift_pp, 2),
            "uplift_relative_pct": round(uplift_pct, 1),
            "convergence_interaction": convergence_iter,
            "convergence_threshold_pp": convergence_threshold * 100,
            "bandit_clicks": bandit_clicks,
            "random_clicks": random_clicks,
        },
        "ctr_history_bandit": [round(x, 4) for x in ctr_history_bandit],
        "ctr_history_random": [round(x, 4) for x in ctr_history_random],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n_users", type=int, default=20)
    parser.add_argument("--sessions_per_user", type=int, default=25)
    parser.add_argument("--candidates_per_session", type=int, default=10)
    parser.add_argument("--alpha", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", default="results/personalization_simulation.json")
    args = parser.parse_args()

    print(f"Running personalization simulation: "
          f"{args.n_users} users x {args.sessions_per_user} sessions "
          f"x {args.candidates_per_session} candidates = "
          f"{args.n_users * args.sessions_per_user} interactions")
    out = run_simulation(
        n_users=args.n_users,
        sessions_per_user=args.sessions_per_user,
        candidates_per_session=args.candidates_per_session,
        exploration_alpha=args.alpha,
        seed=args.seed,
    )

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)

    r = out["results"]
    print()
    print("=" * 60)
    print("Personalization Bandit Simulation Results")
    print("=" * 60)
    print(f"Total interactions:        {out['config']['total_interactions']}")
    print(f"Bandit clicks:             {r['bandit_clicks']}")
    print(f"Random baseline clicks:    {r['random_clicks']}")
    print()
    print(f"Bandit CTR:                {r['final_bandit_ctr']:.4f}")
    print(f"Random baseline CTR:       {r['final_random_ctr']:.4f}")
    print(f"Absolute uplift:           +{r['uplift_absolute_pp']:.2f} pp")
    print(f"Relative uplift:           +{r['uplift_relative_pct']:.1f}%")
    if r['convergence_interaction']:
        print(f"Convergence (CTR gap >= {r['convergence_threshold_pp']:.0f}pp): "
              f"interaction {r['convergence_interaction']}")
    else:
        print("Convergence threshold not reached within budget.")
    print()
    print(f"Saved to {out_path}")


if __name__ == "__main__":
    main()
