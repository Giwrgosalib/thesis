"""
Fine-tune the transformer-based NER model on the refined dataset.

This script provides a reproducible entry point for thesis experiments.

Key fixes vs original:
- Supports all entity types (not just BRAND) — label_list built from dataset
- Proper BIO alignment: B- for first token in span, I- for continuation, O outside
- Uses ast.literal_eval instead of eval for safe entity parsing
- Adds seqeval F1 evaluation after each epoch
- Saves label mapping alongside model for consistent inference
"""

from __future__ import annotations

import argparse
import ast
import json
import logging
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForTokenClassification,
    Trainer,
    TrainingArguments,
    DataCollatorForTokenClassification,
    EvalPrediction,
)

from backend_nextgen.config.loader import load_config

logger = logging.getLogger(__name__)

REQUIRED_MODULES = {
    "sentencepiece": "sentencepiece",
    "protobuf": "google.protobuf",
}

# Canonical entity label normalization.
# Must stay in sync with scripts/evaluate_ai_engines.py :: LABEL_NORMALIZATION.
# Raw dataset labels → canonical names used throughout the pipeline.
ENTITY_NORMALIZATION = {
    # Brand / manufacturer
    "BRAND": "BRAND", "MANUFACTURER": "BRAND", "MAKER": "BRAND",
    # Product / item type
    "PRODUCT_TYPE": "PRODUCT_TYPE", "PRODUCT": "PRODUCT_TYPE",
    "TYPE": "PRODUCT_TYPE", "ITEM": "PRODUCT_TYPE",
    # Category
    "CATEGORY": "CATEGORY",
    # Model
    "MODEL": "MODEL", "MODEL_NAME": "MODEL", "MODEL_NUMBER": "MODEL",
    "VERSION": "MODEL", "VARIANT": "MODEL",
    # Color
    "COLOR": "COLOR", "COLOUR": "COLOR", "HUE": "COLOR",
    # Size / dimensions
    "SIZE": "SIZE", "DIMENSION": "SIZE", "MEASUREMENT": "SIZE",
    # Price
    "PRICE_RANGE": "PRICE_RANGE", "PRICE": "PRICE_RANGE",
    "PRICE_TOKEN": "PRICE_RANGE", "PRICE_QUALIFIER": "PRICE_RANGE",
    "PRICE_PREFERENCE": "PRICE_RANGE", "BUDGET": "PRICE_RANGE", "COST": "PRICE_RANGE",
    # Condition
    "CONDITION": "CONDITION", "STATE": "CONDITION",
    # Material / fabric
    "MATERIAL": "MATERIAL", "FABRIC": "MATERIAL", "COMPOSITION": "MATERIAL",
    # Feature / spec
    "FEATURE": "FEATURE", "SPECIFICATION": "FEATURE", "SPEC": "FEATURE",
    # Technology
    "TECH": "TECH", "TECHNOLOGY": "TECH",
    # Shipping
    "SHIPPING": "SHIPPING",
    # Usage / purpose
    "USAGE": "USAGE",
    # Quality / tier (kept distinct)
    "QUALITY": "QUALITY", "TIER": "TIER",
    # Storage / RAM / GPU (hardware)
    "STORAGE": "STORAGE", "RAM": "RAM", "GPU": "GPU",
    # Connectivity
    "CONNECTIVITY": "CONNECTIVITY",
}


def ensure_dependencies() -> None:
    missing = []
    for package, module in REQUIRED_MODULES.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(package)
    if missing:
        raise ImportError(
            "Missing tokenizer dependencies: "
            + ", ".join(missing)
            + ". Install with: pip install "
            + " ".join(missing)
        )


def _safe_parse_entities(raw) -> List:
    """Safely parse entity field — never uses eval()."""
    if pd.isna(raw) if not isinstance(raw, list) else False:
        return []
    if isinstance(raw, list):
        return [tuple(e) for e in raw if isinstance(e, (list, tuple)) and len(e) == 3]
    if isinstance(raw, str):
        try:
            parsed = ast.literal_eval(raw)
            if isinstance(parsed, list):
                return [tuple(e) for e in parsed if isinstance(e, (list, tuple)) and len(e) == 3]
        except (ValueError, SyntaxError):
            pass
    return []


def _normalize_label(label: str) -> str:
    """Map raw dataset labels to canonical entity type names."""
    return ENTITY_NORMALIZATION.get(label.upper(), label.upper())


def _build_bio_labels(tokens: List[str], entities: List, query: str) -> List[str]:
    """
    Assign BIO tags to whitespace-split tokens using character-span entity annotations.

    Args:
        tokens: query.split() tokens
        entities: list of (char_start, char_end, label) tuples
        query: original query string for char-position reconstruction

    Returns:
        List of BIO tag strings, one per token.
    """
    labels = ["O"] * len(tokens)

    # Build a map from character position → token index
    char_to_token = {}
    char_pos = 0
    for token_idx, token in enumerate(tokens):
        for c in range(char_pos, char_pos + len(token)):
            char_to_token[c] = token_idx
        char_pos += len(token) + 1  # +1 for the space between tokens

    for raw_start, raw_end, raw_label in entities:
        try:
            start, end = int(raw_start), int(raw_end)
        except (TypeError, ValueError):
            continue
        label = _normalize_label(str(raw_label))

        first_in_span = True
        visited_tokens: set = set()
        for c in range(start, min(end, len(query))):
            token_idx = char_to_token.get(c)
            if token_idx is None or token_idx in visited_tokens:
                continue
            visited_tokens.add(token_idx)
            if first_in_span:
                labels[token_idx] = f"B-{label}"
                first_in_span = False
            else:
                # Only overwrite if not already a B- (preserve first-encounter priority)
                if not labels[token_idx].startswith("B-"):
                    labels[token_idx] = f"I-{label}"

    return labels


def build_label_list(dataframes: List[pd.DataFrame]) -> List[str]:
    """
    Scan all entity annotations and build a sorted BIO label list.
    Always includes "O" as the first element.
    """
    entity_types: set = set()
    for df in dataframes:
        for raw in df["entities"].dropna():
            for entry in _safe_parse_entities(raw):
                if len(entry) == 3:
                    entity_types.add(_normalize_label(str(entry[2])))

    label_list = ["O"]
    for etype in sorted(entity_types):
        label_list.append(f"B-{etype}")
        label_list.append(f"I-{etype}")
    return label_list


class NERDataset(Dataset):
    def __init__(
        self,
        dataframe: pd.DataFrame,
        tokenizer,
        label_to_id: dict,
        max_length: int = 256,
    ):
        self.df = dataframe
        self.tokenizer = tokenizer
        self.label_to_id = label_to_id
        self.max_length = max_length

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        query = str(row["query"])
        tokens = query.split()

        entities = _safe_parse_entities(row["entities"])
        # Assign proper BIO labels using character-span alignment
        word_labels = _build_bio_labels(tokens, entities, query)

        encoding = self.tokenizer(
            tokens,
            is_split_into_words=True,
            return_tensors="pt",
            truncation=True,
            padding="max_length",
            max_length=self.max_length,
        )

        word_ids = encoding.word_ids(batch_index=0)
        label_ids = []
        prev_word_id: Optional[int] = None
        for word_id in word_ids:
            if word_id is None:
                # Special token ([CLS], [SEP], padding) → ignored in loss
                label_ids.append(-100)
            elif word_id != prev_word_id:
                # First sub-token of a word → use its word label
                label_ids.append(self.label_to_id.get(word_labels[word_id], self.label_to_id["O"]))
            else:
                # Continuation sub-token → use I- variant or -100 to ignore
                word_label = word_labels[word_id]
                if word_label.startswith("B-"):
                    continuation = "I-" + word_label[2:]
                    label_ids.append(self.label_to_id.get(continuation, self.label_to_id["O"]))
                else:
                    label_ids.append(-100)
            prev_word_id = word_id

        encoding["labels"] = torch.tensor(label_ids)
        return {k: v.squeeze(0) for k, v in encoding.items()}


def make_compute_metrics(label_list: List[str]):
    """Return a compute_metrics function compatible with Hugging Face Trainer."""

    id_to_label = {i: l for i, l in enumerate(label_list)}

    def compute_metrics(p: EvalPrediction):
        predictions = np.argmax(p.predictions, axis=2)
        true_labels = p.label_ids

        true_seqs, pred_seqs = [], []
        for pred_row, label_row in zip(predictions, true_labels):
            true_seq, pred_seq = [], []
            for pred_id, label_id in zip(pred_row, label_row):
                if label_id == -100:
                    continue
                true_seq.append(id_to_label.get(int(label_id), "O"))
                pred_seq.append(id_to_label.get(int(pred_id), "O"))
            true_seqs.append(true_seq)
            pred_seqs.append(pred_seq)

        # Compute entity-level precision / recall / F1 without seqeval dependency
        tp = fp = fn = 0
        for true_seq, pred_seq in zip(true_seqs, pred_seqs):
            true_spans = _extract_spans(true_seq)
            pred_spans = _extract_spans(pred_seq)
            tp += len(true_spans & pred_spans)
            fp += len(pred_spans - true_spans)
            fn += len(true_spans - pred_spans)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
        return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}

    return compute_metrics


def _extract_spans(tag_seq: List[str]) -> set:
    """Convert a BIO tag sequence to a set of (start, end, label) span tuples."""
    spans = set()
    start = None
    current_label = None
    for i, tag in enumerate(tag_seq):
        if tag.startswith("B-"):
            if start is not None:
                spans.add((start, i - 1, current_label))
            start = i
            current_label = tag[2:]
        elif tag.startswith("I-") and current_label == tag[2:]:
            pass  # continue current span
        else:
            if start is not None:
                spans.add((start, i - 1, current_label))
            start = None
            current_label = None
    if start is not None:
        spans.add((start, len(tag_seq) - 1, current_label))
    return spans


def main() -> None:
    parser = argparse.ArgumentParser(description="Train transformer NER for eBay product search")
    parser.add_argument("--train", default="backend/data/refined_balanced_dataset_train.csv")
    parser.add_argument("--val", default="backend/data/refined_balanced_dataset_val.csv")
    parser.add_argument("--output_dir", default="backend_nextgen/models/ner")
    parser.add_argument(
        "--max_samples",
        type=int,
        default=None,
        help="Limit training samples for quick iterations. Default: use all.",
    )
    parser.add_argument("--epochs", type=int, default=3, help="Number of training epochs.")
    parser.add_argument("--batch_size", type=int, default=8)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--max_length", type=int, default=128, help="Max token sequence length.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    config = load_config()
    model_name = config.section("nlp")["model_name"]
    ensure_dependencies()

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    if not getattr(tokenizer, "is_fast", False):
        raise RuntimeError(
            "The selected tokenizer does not expose a fast implementation. "
            "Switch to a model with a fast tokenizer (e.g. deberta-v3-base)."
        )

    train_df = pd.read_csv(Path(args.train))
    val_df = pd.read_csv(Path(args.val))

    if args.max_samples and len(train_df) > args.max_samples:
        train_df = train_df.sample(n=args.max_samples, random_state=42).reset_index(drop=True)
    if args.max_samples and len(val_df) > max(args.max_samples // 4, 1):
        val_df = val_df.sample(n=max(args.max_samples // 4, 1), random_state=42).reset_index(drop=True)

    logger.info(f"Train size: {len(train_df)}, Val size: {len(val_df)}")

    # Build label list from the actual data — covers ALL entity types
    label_list = build_label_list([train_df, val_df])
    label_to_id = {label: idx for idx, label in enumerate(label_list)}
    id_to_label = {idx: label for label, idx in label_to_id.items()}
    logger.info(f"Label list ({len(label_list)} labels): {label_list}")

    max_length = args.max_length or config.section("nlp").get("max_sequence_length", 256)
    train_dataset = NERDataset(train_df, tokenizer, label_to_id, max_length=max_length)
    val_dataset = NERDataset(val_df, tokenizer, label_to_id, max_length=max_length)

    model = AutoModelForTokenClassification.from_pretrained(
        model_name,
        num_labels=len(label_list),
        id2label=id_to_label,
        label2id=label_to_id,
        ignore_mismatched_sizes=True,
    )

    output_path = Path(args.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # `evaluation_strategy` was renamed to `eval_strategy` in Transformers ≥4.46
    import transformers as _tfm
    _tfm_major, _tfm_minor = (int(x) for x in _tfm.__version__.split(".")[:2])
    _eval_strategy_key = "eval_strategy" if (_tfm_major, _tfm_minor) >= (4, 46) else "evaluation_strategy"

    training_kwargs = {
        "output_dir": str(output_path),
        "logging_steps": 20,
        "per_device_train_batch_size": args.batch_size,
        "per_device_eval_batch_size": args.batch_size,
        "num_train_epochs": args.epochs,
        "learning_rate": args.lr,
        "weight_decay": 0.01,
        "warmup_ratio": 0.1,
        "lr_scheduler_type": "cosine",
        _eval_strategy_key: "epoch",
        "save_strategy": "epoch",
        "load_best_model_at_end": True,
        "metric_for_best_model": "f1",
        "save_total_limit": 2,
        "fp16": torch.cuda.is_available(),
        "report_to": "none",
    }

    training_args = TrainingArguments(**training_kwargs)
    data_collator = DataCollatorForTokenClassification(tokenizer, padding="max_length", max_length=max_length)
    compute_metrics = make_compute_metrics(label_list)

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        tokenizer=tokenizer,
        data_collator=data_collator,
        compute_metrics=compute_metrics,
    )

    trainer.train()
    trainer.save_model(str(output_path))

    # Persist label mapping so inference always uses the same schema
    label_map_path = output_path / "label_map.json"
    with open(label_map_path, "w", encoding="utf-8") as f:
        json.dump({"label_list": label_list, "label_to_id": label_to_id, "id_to_label": {str(k): v for k, v in id_to_label.items()}}, f, indent=2)
    logger.info(f"Label map saved to {label_map_path}")
    logger.info("Training complete.")


if __name__ == "__main__":
    main()
