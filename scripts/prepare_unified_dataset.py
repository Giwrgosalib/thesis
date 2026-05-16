"""
Prepare a unified dataset for both Legacy (BiLSTM-CRF) and NextGen (DeBERTa)
NER engines.

Merges all existing CSVs, normalises entity labels, generates synthetic
examples to reach the target training size, and writes 80/10/10 splits.

Usage:
    python scripts/prepare_unified_dataset.py
    python scripts/prepare_unified_dataset.py --target_train 3000
"""

from __future__ import annotations

import argparse
import ast
import itertools
import random
import re
import sys
import os
from pathlib import Path
from typing import List, Tuple

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend_nextgen.config.entity_schema import normalise_label, CANONICAL_LABELS

random.seed(42)

DATA_DIR = Path("backend/data")

EXISTING_CSVS = [
    DATA_DIR / "train_enriched.csv",
    DATA_DIR / "refined_balanced_dataset_train.csv",
    DATA_DIR / "refined_balanced_dataset_val.csv",
    DATA_DIR / "test_dataset_fixed.csv",
]

# ---------------------------------------------------------------------------
# Entity label normalisation
# ---------------------------------------------------------------------------

def normalise_entities_str(entities_str: str) -> str:
    try:
        entities = ast.literal_eval(entities_str)
    except (ValueError, SyntaxError):
        return entities_str
    normalised = []
    for ent in entities:
        if len(ent) == 3:
            start, end, label = ent
            canon = normalise_label(label)
            if canon is None:
                canon = label.upper().strip()
            normalised.append((start, end, canon))
        else:
            normalised.append(ent)
    return str(normalised)


# ---------------------------------------------------------------------------
# Value pools for synthetic augmentation (from enrich_dataset.py)
# ---------------------------------------------------------------------------

COLORS = [
    "red", "blue", "green", "black", "white", "gray", "navy", "brown",
    "silver", "gold", "pink", "purple", "orange", "yellow", "beige",
    "teal", "rose gold", "midnight blue", "forest green", "charcoal",
    "olive", "coral", "turquoise", "cream", "burgundy", "ivory",
]

MATERIALS = [
    "stainless steel", "leather", "aluminum", "titanium", "carbon fiber",
    "wood", "bamboo", "plastic", "cotton", "wool", "polyester", "nylon",
    "silicone", "rubber", "ceramic", "glass", "brass", "copper",
    "fleece", "canvas", "denim", "linen", "velvet", "suede", "mesh",
]

CONDITIONS = [
    "brand new", "used", "refurbished", "open box", "like new",
    "certified refurbished", "pre-owned", "excellent condition",
    "good condition",
]

USAGES = [
    "gaming", "professional", "outdoor", "travel", "home office",
    "studio", "workout", "hiking", "camping", "everyday",
    "photography", "streaming", "recording", "running", "cycling",
    "training", "kids", "beginner", "advanced", "school",
]

CONNECTIVITIES = [
    "bluetooth", "wireless", "wifi", "wired", "USB-C",
    "HDMI", "Thunderbolt", "ethernet", "NFC",
]

SIZES = [
    "small", "medium", "large", "XS", "S", "M", "L", "XL", "XXL",
    "size 8", "size 9", "size 10", "size 11", "size 12",
    "27 inch", "32 inch", "43 inch", "55 inch",
    "6 feet", "queen", "king", "twin", "compact",
]

PRICE_RANGES = [
    "under $50", "under $100", "under $200", "under $500",
    "below $30", "less than $150", "between $50 and $100",
    "between $100 and $300", "$50 to $200", "over $1000",
    "under $75", "under $25", "less than $80",
]

PRODUCT_TYPES = [
    "running shoes", "sneakers", "boots", "sandals",
    "laptop", "gaming laptop", "notebook", "tablet",
    "headphones", "earbuds", "wireless headphones", "gaming headset",
    "smartphone", "phone case", "smartwatch", "fitness tracker",
    "backpack", "handbag", "wallet", "sunglasses",
    "t-shirt", "hoodie", "jeans", "jacket", "leggings", "dress",
    "coffee maker", "blender", "air fryer", "vacuum cleaner",
    "camera", "drone", "keyboard", "mouse", "monitor", "webcam",
    "guitar", "headset", "microphone", "speaker", "soundbar",
    "bicycle", "treadmill", "yoga mat", "dumbbells",
    "desk lamp", "pillow", "mattress", "blanket", "desk chair",
    "router", "hard drive", "SSD", "power bank", "charger",
]

BRANDS = [
    "Nike", "Adidas", "Apple", "Samsung", "Sony", "Bose", "JBL",
    "Logitech", "Razer", "Dell", "HP", "Lenovo", "ASUS",
    "Canon", "Nikon", "GoPro", "DJI", "Anker", "Corsair",
    "Dyson", "KitchenAid", "Ninja", "Vitamix",
    "The North Face", "Columbia", "Patagonia", "Under Armour",
    "LG", "MSI", "Acer", "Google", "Microsoft",
]

BRAND_MODELS = [
    ("Samsung", "Galaxy S23"),
    ("Samsung", "Galaxy S24 Ultra"),
    ("Samsung", "Galaxy Tab S9"),
    ("Samsung", "Galaxy Watch 6"),
    ("Samsung", "Galaxy Buds FE"),
    ("Apple", "iPhone 15 Pro"),
    ("Apple", "iPhone 14"),
    ("Apple", "MacBook Air M2"),
    ("Apple", "MacBook Pro M3"),
    ("Apple", "iPad Pro"),
    ("Apple", "AirPods Pro"),
    ("Apple", "Apple Watch Ultra"),
    ("Sony", "WH-1000XM5"),
    ("Sony", "WF-1000XM5"),
    ("Sony", "PlayStation 5"),
    ("Sony", "Alpha A7 IV"),
    ("Bose", "QuietComfort Ultra"),
    ("Bose", "SoundLink Flex"),
    ("Nike", "Air Max 90"),
    ("Nike", "Air Force 1"),
    ("Nike", "Dunk Low"),
    ("Nike", "Pegasus 40"),
    ("Adidas", "Ultraboost 23"),
    ("Adidas", "Stan Smith"),
    ("Adidas", "Samba OG"),
    ("Dell", "XPS 15"),
    ("Dell", "Inspiron 16"),
    ("Lenovo", "ThinkPad X1 Carbon"),
    ("Lenovo", "IdeaPad Slim 5"),
    ("HP", "Spectre x360"),
    ("HP", "Pavilion 15"),
    ("ASUS", "ROG Zephyrus G14"),
    ("ASUS", "ZenBook 14"),
    ("Logitech", "MX Master 3S"),
    ("Logitech", "G Pro X"),
    ("Razer", "DeathAdder V3"),
    ("Razer", "BlackWidow V4"),
    ("Canon", "EOS R6 Mark II"),
    ("Canon", "PowerShot G7X"),
    ("Nikon", "Z6 III"),
    ("DJI", "Mavic Air 3"),
    ("DJI", "Mini 4 Pro"),
    ("Dyson", "V15 Detect"),
    ("Dyson", "Airwrap"),
    ("GoPro", "Hero 12"),
    ("JBL", "Flip 6"),
    ("JBL", "Charge 5"),
    ("Google", "Pixel 8 Pro"),
    ("Google", "Pixel Watch 2"),
    ("Microsoft", "Surface Pro 9"),
    ("Corsair", "K100 RGB"),
    ("Anker", "PowerCore 26800"),
    ("The North Face", "Nuptse 700"),
    ("Columbia", "Bugaboo II"),
    ("Patagonia", "Nano Puff"),
    ("Under Armour", "Curry 11"),
    ("LG", "C3 OLED"),
    ("MSI", "Stealth 16"),
    ("Vitamix", "A3500"),
    ("KitchenAid", "Artisan 5-Quart"),
]

FEATURES = [
    "waterproof", "noise cancelling", "fast charging", "foldable",
    "portable", "lightweight", "ergonomic", "adjustable",
    "rechargeable", "solar powered", "anti-slip", "breathable",
    "scratch resistant", "shockproof", "dual motor",
]

CONV_PREFIXES = [
    "I'm looking for a ", "I'm looking for ", "Looking for a ",
    "I need a ", "I want a ", "I want to buy a ",
    "Help me find a ", "Can you find me a ", "Can you show me a ",
    "Searching for a ", "Please find me a ", "Show me a ",
    "Anyone selling a ", "We need a ", "My friend wants a ",
    "Do you have a ", "I'd like to get a ", "Can I see a ",
    "My wife wants a ", "My daughter wants a ", "I'm interested in a ",
    "Does anyone sell a ", "Where can I find a ",
    "I've been looking for a ", "Could you help me find a ",
    "I really need a ", "I'm searching for a ",
]

CONV_SUFFIXES = [
    "", "",
    " please", " for sale", " any suggestions?",
    " recommendations?", " if possible",
]


def _rand_prefix() -> str:
    return random.choice(CONV_PREFIXES)


def _rand_suffix() -> str:
    return random.choice(CONV_SUFFIXES)


def _find_spans(query: str, *tagged_phrases) -> List[Tuple[int, int, str]]:
    result = []
    for phrase, label in tagged_phrases:
        m = re.search(re.escape(phrase), query, re.IGNORECASE)
        if m:
            result.append((m.start(), m.end(), label))
    return result


def _make_row(q: str, *tagged_phrases) -> dict | None:
    ents = _find_spans(q, *tagged_phrases)
    if len(ents) == len(tagged_phrases):
        return {"query": q, "intent": "search_product", "entities": str(ents)}
    return None


def generate_synthetic(n: int, existing_queries: set) -> List[dict]:
    rows = []

    generators = [
        _gen_brand_product,
        _gen_brand_model,
        _gen_color_product,
        _gen_color_brand_product,
        _gen_material_product,
        _gen_condition_product,
        _gen_usage_product,
        _gen_connectivity_product,
        _gen_size_product,
        _gen_price_product,
        _gen_feature_product,
        _gen_multi_entity,
    ]

    per_gen = (n // len(generators)) + 1
    for gen in generators:
        batch = gen(per_gen)
        for row in batch:
            if row["query"].lower().strip() not in existing_queries:
                rows.append(row)
                existing_queries.add(row["query"].lower().strip())

    random.shuffle(rows)
    return rows[:n]


def _gen_brand_product(n: int) -> List[dict]:
    rows = []
    combos = list(itertools.product(BRANDS, PRODUCT_TYPES))
    random.shuffle(combos)
    for brand, product in combos:
        q = f"{_rand_prefix()}{brand} {product}{_rand_suffix()}"
        row = _make_row(q, (brand, "BRAND"), (product, "PRODUCT_TYPE"))
        if row:
            rows.append(row)
        if len(rows) >= n:
            break
    return rows[:n]


def _gen_brand_model(n: int) -> List[dict]:
    rows = []
    pool = BRAND_MODELS[:]
    random.shuffle(pool)
    for brand, model in itertools.cycle(pool):
        templates = [
            (f"{_rand_prefix()}{brand} {model}{_rand_suffix()}",
             [(brand, "BRAND"), (model, "MODEL")]),
            (f"{_rand_prefix()}{brand} {model} {random.choice(PRICE_RANGES)}{_rand_suffix()}",
             [(brand, "BRAND"), (model, "MODEL"), (None, "PRICE_RANGE")]),
            (f"{_rand_prefix()}{random.choice(CONDITIONS[:5])} {brand} {model}{_rand_suffix()}",
             [(None, "CONDITION"), (brand, "BRAND"), (model, "MODEL")]),
            (f"{_rand_prefix()}{brand} {model} in {random.choice(COLORS[:15])}{_rand_suffix()}",
             [(brand, "BRAND"), (model, "MODEL"), (None, "COLOR")]),
        ]
        q_raw, tagged_raw = random.choice(templates)
        tagged = []
        for phrase, label in tagged_raw:
            if phrase is not None:
                tagged.append((phrase, label))
            else:
                for val_list, lbl in [(PRICE_RANGES, "PRICE_RANGE"), (CONDITIONS[:5], "CONDITION"), (COLORS[:15], "COLOR")]:
                    if label == lbl:
                        for v in val_list:
                            if v in q_raw:
                                tagged.append((v, label))
                                break
                        break
        ents = _find_spans(q_raw, *tagged)
        if len(ents) >= 2:
            rows.append({"query": q_raw, "intent": "search_product", "entities": str(ents)})
        if len(rows) >= n:
            break
    return rows[:n]


def _gen_color_product(n: int) -> List[dict]:
    rows = []
    combos = list(itertools.product(COLORS, PRODUCT_TYPES))
    random.shuffle(combos)
    for color, product in combos:
        templates = [
            f"{_rand_prefix()}{color} {product}{_rand_suffix()}",
            f"{_rand_prefix()}{product} in {color}{_rand_suffix()}",
        ]
        for q in templates:
            row = _make_row(q, (color, "COLOR"), (product, "PRODUCT_TYPE"))
            if row:
                rows.append(row)
                break
        if len(rows) >= n:
            break
    return rows[:n]


def _gen_color_brand_product(n: int) -> List[dict]:
    rows = []
    combos = list(itertools.product(COLORS, BRANDS, PRODUCT_TYPES))
    random.shuffle(combos)
    for color, brand, product in combos:
        q = f"{_rand_prefix()}{color} {brand} {product}{_rand_suffix()}"
        row = _make_row(q, (color, "COLOR"), (brand, "BRAND"), (product, "PRODUCT_TYPE"))
        if row:
            rows.append(row)
        if len(rows) >= n:
            break
    return rows[:n]


def _gen_material_product(n: int) -> List[dict]:
    rows = []
    combos = list(itertools.product(MATERIALS, PRODUCT_TYPES))
    random.shuffle(combos)
    for material, product in combos:
        templates = [
            f"{_rand_prefix()}{material} {product}{_rand_suffix()}",
            f"{_rand_prefix()}{product} made of {material}{_rand_suffix()}",
        ]
        for q in templates:
            row = _make_row(q, (material, "MATERIAL"), (product, "PRODUCT_TYPE"))
            if row:
                rows.append(row)
                break
        if len(rows) >= n:
            break
    return rows[:n]


def _gen_condition_product(n: int) -> List[dict]:
    rows = []
    combos = list(itertools.product(CONDITIONS, PRODUCT_TYPES))
    random.shuffle(combos)
    for cond, product in combos:
        q = f"{_rand_prefix()}{cond} {product}{_rand_suffix()}"
        row = _make_row(q, (cond, "CONDITION"), (product, "PRODUCT_TYPE"))
        if row:
            rows.append(row)
        if len(rows) >= n:
            break
    return rows[:n]


def _gen_usage_product(n: int) -> List[dict]:
    rows = []
    combos = list(itertools.product(USAGES, PRODUCT_TYPES))
    random.shuffle(combos)
    for usage, product in combos:
        templates = [
            f"{_rand_prefix()}{usage} {product}{_rand_suffix()}",
            f"{_rand_prefix()}{product} for {usage}{_rand_suffix()}",
        ]
        for q in templates:
            row = _make_row(q, (usage, "USAGE"), (product, "PRODUCT_TYPE"))
            if row:
                rows.append(row)
                break
        if len(rows) >= n:
            break
    return rows[:n]


def _gen_connectivity_product(n: int) -> List[dict]:
    rows = []
    combos = list(itertools.product(CONNECTIVITIES, PRODUCT_TYPES))
    random.shuffle(combos)
    for conn, product in combos:
        q = f"{_rand_prefix()}{conn} {product}{_rand_suffix()}"
        row = _make_row(q, (conn, "CONNECTIVITY"), (product, "PRODUCT_TYPE"))
        if row:
            rows.append(row)
        if len(rows) >= n:
            break
    return rows[:n]


def _gen_size_product(n: int) -> List[dict]:
    rows = []
    combos = list(itertools.product(SIZES, PRODUCT_TYPES))
    random.shuffle(combos)
    for size, product in combos:
        templates = [
            f"{_rand_prefix()}{product} {size}{_rand_suffix()}",
            f"{_rand_prefix()}{size} {product}{_rand_suffix()}",
        ]
        for q in templates:
            row = _make_row(q, (product, "PRODUCT_TYPE"), (size, "SIZE"))
            if row:
                rows.append(row)
                break
        if len(rows) >= n:
            break
    return rows[:n]


def _gen_price_product(n: int) -> List[dict]:
    rows = []
    combos = list(itertools.product(PRICE_RANGES, PRODUCT_TYPES))
    random.shuffle(combos)
    for price_str, product in combos:
        q = f"{_rand_prefix()}{product} {price_str}{_rand_suffix()}"
        row = _make_row(q, (product, "PRODUCT_TYPE"), (price_str, "PRICE_RANGE"))
        if row:
            rows.append(row)
        if len(rows) >= n:
            break
    return rows[:n]


def _gen_feature_product(n: int) -> List[dict]:
    rows = []
    combos = list(itertools.product(FEATURES, PRODUCT_TYPES))
    random.shuffle(combos)
    for feat, product in combos:
        templates = [
            f"{_rand_prefix()}{feat} {product}{_rand_suffix()}",
            f"{_rand_prefix()}{product} with {feat}{_rand_suffix()}",
        ]
        for q in templates:
            row = _make_row(q, (feat, "FEATURE"), (product, "PRODUCT_TYPE"))
            if row:
                rows.append(row)
                break
        if len(rows) >= n:
            break
    return rows[:n]


def _gen_multi_entity(n: int) -> List[dict]:
    rows = []
    for _ in range(n * 4):
        color = random.choice(COLORS)
        brand = random.choice(BRANDS)
        product = random.choice(PRODUCT_TYPES)
        material = random.choice(MATERIALS)
        cond = random.choice(CONDITIONS[:5])
        usage = random.choice(USAGES)
        price = random.choice(PRICE_RANGES)
        feat = random.choice(FEATURES)

        templates = [
            (f"{_rand_prefix()}{color} {brand} {product} {price}",
             [(color, "COLOR"), (brand, "BRAND"), (product, "PRODUCT_TYPE"), (price, "PRICE_RANGE")]),
            (f"{_rand_prefix()}{cond} {brand} {product} for {usage}",
             [(cond, "CONDITION"), (brand, "BRAND"), (product, "PRODUCT_TYPE"), (usage, "USAGE")]),
            (f"{_rand_prefix()}{color} {material} {product}",
             [(color, "COLOR"), (material, "MATERIAL"), (product, "PRODUCT_TYPE")]),
            (f"{_rand_prefix()}{brand} {product} {feat} {price}",
             [(brand, "BRAND"), (product, "PRODUCT_TYPE"), (feat, "FEATURE"), (price, "PRICE_RANGE")]),
            (f"{_rand_prefix()}{cond} {color} {product} for {usage}",
             [(cond, "CONDITION"), (color, "COLOR"), (product, "PRODUCT_TYPE"), (usage, "USAGE")]),
        ]

        q, tagged = random.choice(templates)
        ents = _find_spans(q, *tagged)
        if len(ents) >= 2:
            rows.append({"query": q, "intent": "search_product", "entities": str(ents)})
        if len(rows) >= n:
            break
    return rows[:n]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Prepare unified NER dataset")
    parser.add_argument("--target_train", type=int, default=2800,
                        help="Target number of training rows (default: 2800)")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)

    # --- 1. Load and merge all existing CSVs ---
    frames = []
    for csv_path in EXISTING_CSVS:
        if csv_path.exists():
            df = pd.read_csv(csv_path)
            print(f"  Loaded {len(df):>5} rows from {csv_path.name}")
            frames.append(df)
        else:
            print(f"  SKIP (not found): {csv_path}")

    if not frames:
        print("ERROR: No CSVs found. Aborting.")
        sys.exit(1)

    combined = pd.concat(frames, ignore_index=True)
    combined.drop_duplicates(subset=["query"], keep="last", inplace=True)
    combined.reset_index(drop=True, inplace=True)
    print(f"\nMerged & deduplicated: {len(combined)} unique rows")

    # --- 2. Normalise entity labels ---
    combined["entities"] = combined["entities"].apply(normalise_entities_str)
    print("Entity labels normalised.")

    # --- 3. Generate synthetic examples if needed ---
    total_target = int(args.target_train / 0.8)  # 80/10/10 split
    shortfall = max(0, total_target - len(combined))

    if shortfall > 0:
        print(f"\nNeed {shortfall} synthetic examples to reach ~{total_target} total...")
        existing_queries = {q.lower().strip() for q in combined["query"]}
        synthetic = generate_synthetic(shortfall, existing_queries)
        syn_df = pd.DataFrame(synthetic)
        combined = pd.concat([combined, syn_df], ignore_index=True)
        combined.drop_duplicates(subset=["query"], keep="last", inplace=True)
        combined.reset_index(drop=True, inplace=True)
        print(f"After augmentation: {len(combined)} total rows")
    else:
        print(f"\nAlready have {len(combined)} rows (target total ~{total_target}). No augmentation needed.")

    # --- 4. Split 80/10/10 ---
    from sklearn.model_selection import train_test_split

    combined = combined.sample(frac=1, random_state=args.seed).reset_index(drop=True)

    train_df, temp_df = train_test_split(
        combined, test_size=0.2, random_state=args.seed
    )
    val_df, test_df = train_test_split(
        temp_df, test_size=0.5, random_state=args.seed
    )

    # --- 5. Write output files ---
    out_train = DATA_DIR / "unified_train.csv"
    out_val = DATA_DIR / "unified_val.csv"
    out_test = DATA_DIR / "unified_test.csv"

    train_df.to_csv(out_train, index=False)
    val_df.to_csv(out_val, index=False)
    test_df.to_csv(out_test, index=False)

    # --- 6. Summary ---
    print(f"\n{'='*50}")
    print(f"UNIFIED DATASET CREATED")
    print(f"{'='*50}")
    print(f"  Train: {len(train_df):>5} rows  ->  {out_train}")
    print(f"  Val:   {len(val_df):>5} rows  ->  {out_val}")
    print(f"  Test:  {len(test_df):>5} rows  ->  {out_test}")
    print(f"  Total: {len(combined):>5} rows")

    # Label distribution
    all_labels = set()
    for ent_str in combined["entities"]:
        try:
            for ent in ast.literal_eval(ent_str):
                if len(ent) == 3:
                    all_labels.add(ent[2])
        except (ValueError, SyntaxError):
            pass
    print(f"\n  Entity types: {len(all_labels)}")
    for label in sorted(all_labels):
        canonical = "Y" if label in CANONICAL_LABELS else "n"
        print(f"    [{canonical}] {label}")


if __name__ == "__main__":
    main()
