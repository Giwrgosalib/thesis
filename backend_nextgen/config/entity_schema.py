"""
Canonical entity schema shared by both the Legacy (BiLSTM-CRF) and NextGen
(DeBERTa) NER engines.

All entity labels extracted by either engine should be normalised to the
types defined here before being compared, logged, or passed downstream.

Usage
-----
>>> from backend_nextgen.config.entity_schema import CANONICAL_LABELS, normalise_label
>>> normalise_label("PRODUCT")          # → "PRODUCT_TYPE"
>>> normalise_label("PRICE")            # → "PRICE_RANGE"
>>> normalise_label("COLOR")            # → "COLOR"
>>> normalise_label("unknown_type")     # → None   (unrecognised label)
"""

from __future__ import annotations

from typing import Optional

# ---------------------------------------------------------------------------
# Canonical label set
# ---------------------------------------------------------------------------

CANONICAL_LABELS: frozenset[str] = frozenset({
    # Core product identification
    "BRAND",            # Manufacturer / brand name  (e.g. "Nike", "Apple")
    "PRODUCT_TYPE",     # Generic product category   (e.g. "running shoes", "laptop")
    "CATEGORY",         # High-level eBay category   (e.g. "Electronics", "Clothing")
    "MODEL",            # Specific model / variant   (e.g. "iPhone 15 Pro", "RTX 4090")

    # Physical attributes
    "COLOR",            # Colour descriptor          (e.g. "red", "midnight blue")
    "SIZE",             # Size / dimensions          (e.g. "XL", '8 foot', "256 GB")
    "MATERIAL",         # Material / fabric          (e.g. "leather", "slate")

    # Commercial attributes
    "PRICE_RANGE",      # Price or budget constraint (e.g. "under $100", "£50-£80")
    "CONDITION",        # Item condition             (e.g. "brand new", "used", "refurbished")
    "SHIPPING",         # Shipping preference        (e.g. "free shipping", "next day")

    # Functional / feature attributes
    "FEATURE",          # Highlighted feature        (e.g. "noise cancellation", "waterproof")
    "TECH",             # Technology spec            (e.g. "Bluetooth 5.0", "4K OLED")
    "STORAGE",          # Storage capacity           (e.g. "256 GB", "1 TB")
    "CONNECTIVITY",     # Connectivity type          (e.g. "WiFi", "USB-C")
    "USAGE",            # Use-case / activity        (e.g. "gaming", "hiking")

    # Miscellaneous
    "INCLUSIONS",       # Bundled accessories        (e.g. "with charger", "accessories")
    "BRAND_EXCLUSION",  # Brands to exclude          (e.g. "not Dell")
})

# ---------------------------------------------------------------------------
# Alias / synonym mapping  (legacy labels → canonical)
# ---------------------------------------------------------------------------

_ALIAS_MAP: dict[str, str] = {
    # Legacy BiLSTM-CRF engine aliases
    "PRODUCT":          "PRODUCT_TYPE",
    "PRODUCT_CATEGORY": "CATEGORY",
    "PRICE":            "PRICE_RANGE",
    "PRICE_CONSTRAINT": "PRICE_RANGE",
    "COND":             "CONDITION",
    "TECH_SPEC":        "TECH",
    "SPEC":             "TECH",
    "STORAGE_CAPACITY": "STORAGE",
    "CONN":             "CONNECTIVITY",
    "EXCLUSION":        "BRAND_EXCLUSION",
    "NOT_BRAND":        "BRAND_EXCLUSION",
    "INCLUDE":          "INCLUSIONS",
    "ACCESSORY":        "INCLUSIONS",
}


def normalise_label(raw_label: str) -> Optional[str]:
    """
    Map a raw entity label from either engine to the canonical schema.

    Returns the canonical label string, or ``None`` if the label is
    not recognised (caller should treat it as an "O" / unknown token).
    """
    if not raw_label:
        return None
    upper = raw_label.upper().strip()
    if upper in CANONICAL_LABELS:
        return upper
    mapped = _ALIAS_MAP.get(upper)
    if mapped and mapped in CANONICAL_LABELS:
        return mapped
    return None


def normalise_entity_dict(entities: dict[str, object]) -> dict[str, object]:
    """
    Normalise a {label: value} entity dictionary in-place (returns a new dict).

    Labels that don't map to the canonical schema are dropped and a debug
    message is emitted.  Useful for aligning legacy engine output before
    comparison.
    """
    import logging
    _log = logging.getLogger(__name__)
    normalised: dict[str, object] = {}
    for raw_lbl, value in entities.items():
        canon = normalise_label(raw_lbl)
        if canon is None:
            _log.debug("Dropping unrecognised entity label: %r", raw_lbl)
            continue
        if canon in normalised:
            # Merge list values; prefer existing for scalar conflicts
            existing = normalised[canon]
            if isinstance(existing, list) and isinstance(value, list):
                normalised[canon] = existing + value
            elif isinstance(existing, list):
                normalised[canon] = existing + [value]
            else:
                normalised[canon] = [existing, value]
        else:
            normalised[canon] = value
    return normalised
