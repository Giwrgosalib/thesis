"""
Dataset enrichment script for under-represented NER entity types.

Generates template-based synthetic training examples for entity types
that have too few examples in the original dataset:
  COLOR, MATERIAL, CONDITION, USAGE, CONNECTIVITY, SIZE, PRICE_RANGE

Each example has:
  - query: natural-language product search string
  - intent: "search_product"
  - entities: [(char_start, char_end, label), ...] tuples

Usage:
    python scripts/enrich_dataset.py \
        --output backend/data/train_enriched.csv \
        --base backend/data/train_combined.csv
"""

from __future__ import annotations

import argparse
import csv
import itertools
import random
import re
from pathlib import Path
from typing import List, Tuple

random.seed(42)

# ---------------------------------------------------------------------------
# Value pools for each entity type
# ---------------------------------------------------------------------------

COLORS = [
    "red", "blue", "green", "black", "white", "gray", "grey", "navy",
    "brown", "silver", "gold", "pink", "purple", "orange", "yellow",
    "beige", "cream", "teal", "rose gold", "midnight blue", "forest green",
    "charcoal", "olive", "coral", "turquoise",
]

MATERIALS = [
    "stainless steel", "leather", "aluminum", "titanium", "carbon fiber",
    "wood", "bamboo", "plastic", "cotton", "wool", "polyester", "nylon",
    "silicone", "rubber", "ceramic", "glass", "brass", "copper",
    "fleece", "canvas", "denim", "linen", "velvet", "suede",
]

CONDITIONS = [
    "brand new", "used", "refurbished", "open box", "like new",
    "certified refurbished", "pre-owned", "excellent condition",
    "good condition", "for parts",
]

USAGES = [
    "gaming", "professional", "outdoor", "travel", "home office",
    "studio", "workout", "hiking", "camping", "everyday",
    "photography", "streaming", "recording", "running", "cycling",
    "training", "kids", "beginner", "advanced",
]

CONNECTIVITIES = [
    "bluetooth", "wireless", "wifi", "wired", "USB-C",
    "HDMI", "Thunderbolt", "ethernet", "NFC",
]

SIZES = [
    "small", "medium", "large", "XS", "S", "M", "L", "XL", "XXL",
    "size 8", "size 9", "size 10", "size 11", "size 12",
    "27 inch", "32 inch", "43 inch", "55 inch",
    "6 feet", "queen", "king", "twin",
]

PRICE_RANGES = [
    ("under $50", 0, 50),
    ("under $100", 0, 100),
    ("under $200", 0, 200),
    ("under $500", 0, 500),
    ("below $30", 0, 30),
    ("less than $150", 0, 150),
    ("between $50 and $100", 50, 100),
    ("between $100 and $300", 100, 300),
    ("$50 to $200", 50, 200),
    ("over $1000", 1000, 9999),
]

PRODUCT_TYPES = [
    "running shoes", "sneakers", "boots", "sandals",
    "laptop", "gaming laptop", "notebook", "tablet",
    "headphones", "earbuds", "wireless headphones", "gaming headset",
    "smartphone", "phone case", "smartwatch", "fitness tracker",
    "backpack", "handbag", "wallet", "sunglasses",
    "t-shirt", "hoodie", "jeans", "jacket", "leggings",
    "coffee maker", "blender", "air fryer", "vacuum cleaner",
    "camera", "drone", "keyboard", "mouse", "monitor",
    "guitar", "headset", "microphone", "speaker", "soundbar",
    "bicycle", "treadmill", "yoga mat", "dumbbells",
    "desk lamp", "pillow", "mattress", "blanket",
]

BRANDS = [
    "Nike", "Adidas", "Apple", "Samsung", "Sony", "Bose", "JBL",
    "Logitech", "Razer", "Dell", "HP", "Lenovo", "ASUS",
    "Canon", "Nikon", "GoPro", "DJI",
    "Dyson", "KitchenAid", "Ninja", "Vitamix",
    "The North Face", "Columbia", "Patagonia",
]


# ---------------------------------------------------------------------------
# Conversational prefixes / suffixes that mirror real eBay search queries
# ---------------------------------------------------------------------------

CONV_PREFIXES = [
    "",  # bare query (no prefix)
    "",  # bare query (weight it more)
    "I'm looking for a ",
    "I'm looking for ",
    "Looking for a ",
    "Looking for ",
    "I need a ",
    "I need ",
    "I want a ",
    "I want ",
    "Help me find a ",
    "Help me find ",
    "Can you find me a ",
    "Can anyone find a ",
    "Does anyone have a ",
    "Does anyone sell a ",
    "Anyone selling a ",
    "Searching for a ",
    "Searching for ",
    "I have been looking for a ",
    "I have been searching for a ",
    "Please find me a ",
    "Please show me a ",
    "Can I please see a ",
    "My wife wants a ",
    "My husband is looking for a ",
    "My son wants a ",
    "My daughter wants a ",
    "We are searching for a ",
    "We want to find a ",
    "We need a ",
]

CONV_SUFFIXES = [
    "",  # no suffix (weight more)
    "",
    " please",
    " for sale",
    " anyone?",
    " any suggestions?",
    " recommendations?",
    " in good condition",
]


def _rand_prefix() -> str:
    return random.choice(CONV_PREFIXES)


def _rand_suffix() -> str:
    return random.choice(CONV_SUFFIXES)


# ---------------------------------------------------------------------------
# Template definitions
# Each template is a callable(values) -> (query_str, entities_list)
# ---------------------------------------------------------------------------

def _spans(query: str, *phrases: str) -> List[Tuple[int, int, str]]:
    """Find char spans for each (phrase, label) pair in query."""
    result = []
    for phrase, label in phrases:
        m = re.search(re.escape(phrase), query, re.IGNORECASE)
        if m:
            result.append((m.start(), m.end(), label))
    return result


def _make_row(q: str, *tagged_phrases) -> dict:
    """Build a dataset row, returning None if any phrase is missing."""
    ents = _spans(q, *tagged_phrases)
    if len(ents) == len(tagged_phrases):
        return {"query": q, "intent": "search_product", "entities": str(ents)}
    return None


def make_color_examples(n: int) -> List[dict]:
    rows = []
    combos = list(itertools.product(COLORS, PRODUCT_TYPES))
    random.shuffle(combos)
    for color, product in combos * 2:  # allow repeats with different prefixes
        templates = [
            f"{_rand_prefix()}{color} {product}{_rand_suffix()}",
            f"{_rand_prefix()}{product} in {color}{_rand_suffix()}",
            f"{_rand_prefix()}{product} {color} color{_rand_suffix()}",
            f"{_rand_prefix()}{product} color {color}{_rand_suffix()}",
        ]
        for q in templates:
            row = _make_row(q, (color, "COLOR"), (product, "PRODUCT_TYPE"))
            if row:
                rows.append(row)
                break
        if len(rows) >= n:
            break
    return rows[:n]


def make_color_brand_examples(n: int) -> List[dict]:
    rows = []
    combos = list(itertools.product(COLORS, BRANDS, PRODUCT_TYPES))
    random.shuffle(combos)
    for color, brand, product in combos:
        templates = [
            f"{_rand_prefix()}{color} {brand} {product}{_rand_suffix()}",
            f"{_rand_prefix()}{brand} {product} in {color}{_rand_suffix()}",
            f"{_rand_prefix()}{brand} {color} {product}{_rand_suffix()}",
        ]
        for q in templates:
            row = _make_row(q, (color, "COLOR"), (brand, "BRAND"), (product, "PRODUCT_TYPE"))
            if row:
                rows.append(row)
                break
        if len(rows) >= n:
            break
    return rows[:n]


def make_material_examples(n: int) -> List[dict]:
    rows = []
    combos = list(itertools.product(MATERIALS, PRODUCT_TYPES))
    random.shuffle(combos)
    for material, product in combos * 2:
        templates = [
            f"{_rand_prefix()}{material} {product}{_rand_suffix()}",
            f"{_rand_prefix()}{product} {material}{_rand_suffix()}",
            f"{_rand_prefix()}{product} made of {material}{_rand_suffix()}",
            f"{_rand_prefix()}{product} {material} material{_rand_suffix()}",
        ]
        for q in templates:
            row = _make_row(q, (material, "MATERIAL"), (product, "PRODUCT_TYPE"))
            if row:
                rows.append(row)
                break
        if len(rows) >= n:
            break
    return rows[:n]


def make_condition_examples(n: int) -> List[dict]:
    rows = []
    combos = list(itertools.product(CONDITIONS, PRODUCT_TYPES))
    random.shuffle(combos)
    for cond, product in combos * 2:
        templates = [
            f"{_rand_prefix()}{cond} {product}{_rand_suffix()}",
            f"{_rand_prefix()}{product} {cond}{_rand_suffix()}",
            f"{_rand_prefix()}{product} in {cond} condition{_rand_suffix()}",
            f"Does anyone sell a {cond} {product}",
            f"Anyone selling a {cond} {product}",
        ]
        for q in templates:
            row = _make_row(q, (cond, "CONDITION"), (product, "PRODUCT_TYPE"))
            if row:
                rows.append(row)
                break
        if len(rows) >= n:
            break
    return rows[:n]


def make_condition_brand_examples(n: int) -> List[dict]:
    rows = []
    combos = list(itertools.product(CONDITIONS, BRANDS, PRODUCT_TYPES))
    random.shuffle(combos)
    for cond, brand, product in combos:
        templates = [
            f"{_rand_prefix()}{cond} {brand} {product}{_rand_suffix()}",
            f"Does anyone sell a {cond} {brand} {product}",
            f"Anyone selling a {cond} {brand} {product}",
        ]
        for q in templates:
            row = _make_row(q, (cond, "CONDITION"), (brand, "BRAND"), (product, "PRODUCT_TYPE"))
            if row:
                rows.append(row)
                break
        if len(rows) >= n:
            break
    return rows[:n]


def make_usage_examples(n: int) -> List[dict]:
    rows = []
    combos = list(itertools.product(USAGES, PRODUCT_TYPES))
    random.shuffle(combos)
    for usage, product in combos * 2:
        templates = [
            f"{_rand_prefix()}{usage} {product}{_rand_suffix()}",
            f"{_rand_prefix()}{product} for {usage}{_rand_suffix()}",
            f"{_rand_prefix()}{product} for {usage} use{_rand_suffix()}",
            f"I need a {product} for {usage}",
            f"Looking for a {product} for {usage}",
        ]
        for q in templates:
            row = _make_row(q, (usage, "USAGE"), (product, "PRODUCT_TYPE"))
            if row:
                rows.append(row)
                break
        if len(rows) >= n:
            break
    return rows[:n]


def make_connectivity_examples(n: int) -> List[dict]:
    rows = []
    combos = list(itertools.product(CONNECTIVITIES, PRODUCT_TYPES))
    random.shuffle(combos)
    for conn, product in combos * 2:
        templates = [
            f"{_rand_prefix()}{conn} {product}{_rand_suffix()}",
            f"{_rand_prefix()}{product} with {conn}{_rand_suffix()}",
            f"{_rand_prefix()}{product} {conn} connection{_rand_suffix()}",
            f"I need a {product} with {conn}",
            f"Looking for a {product} with {conn} connectivity",
        ]
        for q in templates:
            row = _make_row(q, (conn, "CONNECTIVITY"), (product, "PRODUCT_TYPE"))
            if row:
                rows.append(row)
                break
        if len(rows) >= n:
            break
    return rows[:n]


def make_size_examples(n: int) -> List[dict]:
    rows = []
    combos = list(itertools.product(SIZES, PRODUCT_TYPES))
    random.shuffle(combos)
    for size, product in combos * 2:
        templates = [
            f"{_rand_prefix()}{product} {size}{_rand_suffix()}",
            f"{_rand_prefix()}{product} size {size}{_rand_suffix()}",
            f"{_rand_prefix()}{product} in size {size}{_rand_suffix()}",
            f"I need a {product} size {size}",
            f"Looking for a {size} {product}",
        ]
        for q in templates:
            row = _make_row(q, (product, "PRODUCT_TYPE"), (size, "SIZE"))
            if row:
                rows.append(row)
                break
        if len(rows) >= n:
            break
    return rows[:n]


def make_price_examples(n: int) -> List[dict]:
    rows = []
    combos = list(itertools.product(PRICE_RANGES, PRODUCT_TYPES))
    random.shuffle(combos)
    for (price_str, lo, hi), product in combos * 2:
        templates = [
            f"{_rand_prefix()}{product} {price_str}{_rand_suffix()}",
            f"{_rand_prefix()}{product} {price_str} please",
            f"I need a {product} {price_str}",
            f"Looking for a {product} {price_str}",
            f"Help me find a {product} {price_str}",
        ]
        for q in templates:
            row = _make_row(q, (product, "PRODUCT_TYPE"), (price_str, "PRICE_RANGE"))
            if row:
                rows.append(row)
                break
        if len(rows) >= n:
            break
    return rows[:n]


def make_multi_entity_examples(n: int) -> List[dict]:
    """Combine color + material + condition + usage in richer conversational queries."""
    rows = []
    for _ in range(n * 4):
        color = random.choice(COLORS)
        material = random.choice(MATERIALS)
        product = random.choice(PRODUCT_TYPES)
        cond = random.choice(CONDITIONS[:5])  # top 5 most natural
        usage = random.choice(USAGES)
        prefix = _rand_prefix()

        templates = [
            f"{prefix}{color} {material} {product} {cond}",
            f"{prefix}{cond} {color} {product}",
            f"{prefix}{material} {product} in {color}",
            f"{prefix}{cond} {material} {product}",
            f"{prefix}{product} {material} {color} color",
            f"I'm looking for a {color} {product} in {cond} condition",
            f"Does anyone have a {cond} {color} {product}",
            f"I need a {material} {product} in {color}",
            f"Looking for a {product} for {usage} in {color}",
            f"Help me find a {cond} {product} for {usage}",
        ]
        q = random.choice(templates)
        ents = []
        for phrase, label in [(color, "COLOR"), (material, "MATERIAL"),
                               (product, "PRODUCT_TYPE"), (cond, "CONDITION"),
                               (usage, "USAGE")]:
            m = re.search(re.escape(phrase), q, re.IGNORECASE)
            if m:
                ents.append((m.start(), m.end(), label))

        if len(ents) >= 2:
            rows.append({"query": q, "intent": "search_product", "entities": str(ents)})
        if len(rows) >= n:
            break
    return rows[:n]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Enrich NER training dataset with synthetic examples")
    parser.add_argument("--output", default="backend/data/train_enriched.csv")
    parser.add_argument("--base", default="backend/data/train_combined.csv")
    parser.add_argument("--per_type", type=int, default=80,
                        help="Synthetic examples per entity type")
    args = parser.parse_args()

    all_new = []
    all_new += make_color_examples(args.per_type)
    all_new += make_color_brand_examples(args.per_type // 2)
    all_new += make_material_examples(args.per_type)
    all_new += make_condition_examples(args.per_type)
    all_new += make_condition_brand_examples(args.per_type // 2)
    all_new += make_usage_examples(args.per_type)
    all_new += make_connectivity_examples(args.per_type)
    all_new += make_size_examples(args.per_type)
    all_new += make_price_examples(args.per_type)
    all_new += make_multi_entity_examples(args.per_type)

    random.shuffle(all_new)
    print(f"Generated {len(all_new)} synthetic examples")

    # Load base dataset
    base_path = Path(args.base)
    base_rows = []
    if base_path.exists():
        with base_path.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            base_rows = list(reader)
        print(f"Base dataset: {len(base_rows)} rows")

    # Deduplicate by query
    existing_queries = {r["query"].lower().strip() for r in base_rows}
    unique_new = [r for r in all_new if r["query"].lower().strip() not in existing_queries]
    print(f"Unique new examples after dedup: {len(unique_new)}")

    combined = base_rows + unique_new
    print(f"Combined total: {len(combined)} rows")

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["query", "intent", "entities"])
        writer.writeheader()
        writer.writerows(combined)

    print(f"Saved to {out_path}")


if __name__ == "__main__":
    main()
