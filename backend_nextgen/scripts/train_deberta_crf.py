"""
Fine-tune DeBERTa-v3-base + CRF for NER on the unified dataset.

Uses the TransformerCRFNER model class (backend_nextgen/nlp/transformer_ner.py)
which adds a CRF decoding layer on top of the transformer encoder. This ensures
valid BIO transition sequences and matches the thesis architecture description.

Training uses a custom PyTorch loop (not HF Trainer) because CRF loss/decode
is not directly compatible with the standard Trainer API.
"""

from __future__ import annotations

import argparse
import ast
import json
import logging
import time
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd
import torch
from torch.optim import AdamW
from torch.utils.data import DataLoader, Dataset
from transformers import AutoTokenizer, get_cosine_schedule_with_warmup

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend_nextgen.nlp.transformer_ner import TransformerCRFNER

logger = logging.getLogger(__name__)

# ─── Label normalization (same as train_transformer_ner.py) ───
ENTITY_NORMALIZATION = {
    "BRAND": "BRAND", "MANUFACTURER": "BRAND", "MAKER": "BRAND",
    "PRODUCT_TYPE": "PRODUCT_TYPE", "PRODUCT": "PRODUCT_TYPE",
    "TYPE": "PRODUCT_TYPE", "ITEM": "PRODUCT_TYPE",
    "CATEGORY": "CATEGORY",
    "MODEL": "MODEL", "MODEL_NAME": "MODEL", "MODEL_NUMBER": "MODEL",
    "VERSION": "MODEL", "VARIANT": "MODEL",
    "COLOR": "COLOR", "COLOUR": "COLOR", "HUE": "COLOR",
    "SIZE": "SIZE", "DIMENSION": "SIZE", "MEASUREMENT": "SIZE",
    "PRICE_RANGE": "PRICE_RANGE", "PRICE": "PRICE_RANGE",
    "PRICE_TOKEN": "PRICE_RANGE", "PRICE_QUALIFIER": "PRICE_RANGE",
    "PRICE_PREFERENCE": "PRICE_RANGE", "BUDGET": "PRICE_RANGE", "COST": "PRICE_RANGE",
    "CONDITION": "CONDITION", "STATE": "CONDITION",
    "MATERIAL": "MATERIAL", "FABRIC": "MATERIAL", "COMPOSITION": "MATERIAL",
    "FEATURE": "FEATURE", "SPECIFICATION": "FEATURE", "SPEC": "FEATURE",
    "TECH": "TECH", "TECHNOLOGY": "TECH",
    "SHIPPING": "SHIPPING",
    "USAGE": "USAGE",
    "QUALITY": "QUALITY", "TIER": "TIER",
    "STORAGE": "STORAGE", "RAM": "RAM", "GPU": "GPU",
    "CONNECTIVITY": "CONNECTIVITY",
}


def _safe_parse_entities(raw) -> List:
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
    return ENTITY_NORMALIZATION.get(label.upper(), label.upper())


def _build_bio_labels(tokens: List[str], entities: List, query: str) -> List[str]:
    labels = ["O"] * len(tokens)
    char_to_token = {}
    char_pos = 0
    for token_idx, token in enumerate(tokens):
        for c in range(char_pos, char_pos + len(token)):
            char_to_token[c] = token_idx
        char_pos += len(token) + 1

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
                if not labels[token_idx].startswith("B-"):
                    labels[token_idx] = f"I-{label}"
    return labels


def build_label_list(dataframes: List[pd.DataFrame]) -> List[str]:
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
    """
    Dataset that produces:
      - input_ids, attention_mask: standard transformer inputs
      - labels: BIO tag IDs for each subtoken position
      - crf_mask: True only for positions that are real word subtokens
                  (False for [CLS], [SEP], and padding)
      - first_subtoken_mask: True only for the FIRST subtoken of each word
                             (used in evaluation to avoid double-counting)
    """

    def __init__(self, dataframe: pd.DataFrame, tokenizer, label_to_id: dict, max_length: int = 128):
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
        crf_mask = []
        first_subtoken_mask = []
        prev_word_id: Optional[int] = None

        for word_id in word_ids:
            if word_id is None:
                # Special token ([CLS], [SEP], padding)
                label_ids.append(self.label_to_id["O"])  # placeholder for CRF
                crf_mask.append(False)
                first_subtoken_mask.append(False)
            elif word_id != prev_word_id:
                # First subtoken of a new word
                label_ids.append(self.label_to_id.get(word_labels[word_id], self.label_to_id["O"]))
                crf_mask.append(True)
                first_subtoken_mask.append(True)
            else:
                # Continuation subtoken of the same word
                word_label = word_labels[word_id]
                if word_label.startswith("B-"):
                    continuation = "I-" + word_label[2:]
                    label_ids.append(self.label_to_id.get(continuation, self.label_to_id["O"]))
                else:
                    label_ids.append(self.label_to_id.get(word_label, self.label_to_id["O"]))
                crf_mask.append(True)
                first_subtoken_mask.append(False)
            prev_word_id = word_id

        result = {k: v.squeeze(0) for k, v in encoding.items()}
        result["labels"] = torch.tensor(label_ids, dtype=torch.long)
        result["crf_mask"] = torch.tensor(crf_mask, dtype=torch.bool)
        result["first_subtoken_mask"] = torch.tensor(first_subtoken_mask, dtype=torch.bool)
        return result


def collate_fn(batch):
    keys = batch[0].keys()
    return {k: torch.stack([item[k] for item in batch]) for k in keys}


def _extract_spans(tag_seq: List[str]) -> set:
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
            pass
        else:
            if start is not None:
                spans.add((start, i - 1, current_label))
            start = None
            current_label = None
    if start is not None:
        spans.add((start, len(tag_seq) - 1, current_label))
    return spans


def evaluate(model, dataloader, id_to_label, device):
    """Compute entity-level P/R/F1 using first-subtoken predictions only."""
    model.eval()
    tp = fp = fn = 0

    with torch.no_grad():
        for batch in dataloader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            crf_mask = batch["crf_mask"].to(device)
            labels = batch["labels"].to(device)
            first_subtoken_mask = batch["first_subtoken_mask"].to(device)

            # CRF decode — returns packed predictions (one per word token in crf_mask)
            _, tag_seqs = model(input_ids, attention_mask, labels=None, crf_mask=crf_mask)

            for i in range(input_ids.size(0)):
                cm = crf_mask[i]  # [max_length] bool
                fsm = first_subtoken_mask[i]  # [max_length] bool
                gt_labels = labels[i]  # [max_length] long

                # tag_seqs[i] has one prediction per crf_mask=True position (packed)
                preds = tag_seqs[i]

                # Get positions where crf_mask is True (in original sequence order)
                crf_positions = cm.nonzero(as_tuple=True)[0]
                first_sub_set = set(fsm.nonzero(as_tuple=True)[0].tolist())

                # Only evaluate at first-subtoken positions
                pred_tags = []
                true_tags = []
                for crf_idx, pos in enumerate(crf_positions):
                    if pos.item() in first_sub_set:
                        pred_tags.append(id_to_label.get(preds[crf_idx], "O"))
                        true_tags.append(id_to_label.get(gt_labels[pos].item(), "O"))

                true_spans = _extract_spans(true_tags)
                pred_spans = _extract_spans(pred_tags)
                tp += len(true_spans & pred_spans)
                fp += len(pred_spans - true_spans)
                fn += len(true_spans - pred_spans)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    model.train()
    return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4),
            "tp": tp, "fp": fp, "fn": fn}


def main():
    parser = argparse.ArgumentParser(description="Train DeBERTa+CRF NER model")
    parser.add_argument("--train", default="backend/data/unified_train.csv")
    parser.add_argument("--val", default="backend/data/unified_val.csv")
    parser.add_argument("--output_dir", default="backend_nextgen/models/deberta_crf/best_model")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch_size", type=int, default=8)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--max_length", type=int, default=128)
    parser.add_argument("--warmup_ratio", type=float, default=0.1)
    parser.add_argument("--weight_decay", type=float, default=0.01)
    parser.add_argument("--max_samples", type=int, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--patience", type=int, default=3, help="Early stopping patience")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Device: {device}")

    # Load data
    model_name = "microsoft/deberta-v3-base"
    tokenizer = AutoTokenizer.from_pretrained(model_name)

    train_df = pd.read_csv(Path(args.train))
    val_df = pd.read_csv(Path(args.val))

    if args.max_samples:
        train_df = train_df.sample(n=min(args.max_samples, len(train_df)), random_state=42).reset_index(drop=True)
        val_df = val_df.sample(n=min(args.max_samples // 4, len(val_df)), random_state=42).reset_index(drop=True)

    logger.info(f"Train: {len(train_df)} rows, Val: {len(val_df)} rows")

    # Build labels
    label_list = build_label_list([train_df, val_df])
    label_to_id = {label: idx for idx, label in enumerate(label_list)}
    id_to_label = {idx: label for label, idx in label_to_id.items()}
    logger.info(f"Labels: {len(label_list)} tags ({(len(label_list)-1)//2} entity types + O)")

    # Build datasets
    train_dataset = NERDataset(train_df, tokenizer, label_to_id, max_length=args.max_length)
    val_dataset = NERDataset(val_df, tokenizer, label_to_id, max_length=args.max_length)

    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True, collate_fn=collate_fn)
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size, shuffle=False, collate_fn=collate_fn)

    # Build model
    model = TransformerCRFNER(
        model_name=model_name,
        tag_to_idx=label_to_id,
        use_crf=True,
        dropout=0.1,
    )
    model.to(device)
    total_params = sum(p.numel() for p in model.parameters())
    logger.info(f"Model: DeBERTa-v3-base + CRF ({total_params:,} params)")
    logger.info(f"CRF active: {model.use_crf}")

    # Optimizer + scheduler
    no_decay = ["bias", "LayerNorm.weight"]
    optimizer_grouped_parameters = [
        {"params": [p for n, p in model.named_parameters() if not any(nd in n for nd in no_decay)],
         "weight_decay": args.weight_decay},
        {"params": [p for n, p in model.named_parameters() if any(nd in n for nd in no_decay)],
         "weight_decay": 0.0},
    ]
    optimizer = AdamW(optimizer_grouped_parameters, lr=args.lr)

    total_steps = len(train_loader) * args.epochs
    warmup_steps = int(total_steps * args.warmup_ratio)
    scheduler = get_cosine_schedule_with_warmup(optimizer, warmup_steps, total_steps)

    # Training loop with early stopping
    best_f1 = 0.0
    patience_counter = 0
    output_path = Path(args.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    for epoch in range(1, args.epochs + 1):
        model.train()
        epoch_loss = 0.0
        t0 = time.time()

        for step, batch in enumerate(train_loader, 1):
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)
            crf_mask = batch["crf_mask"].to(device)

            loss, _ = model(input_ids, attention_mask, labels=labels, crf_mask=crf_mask)

            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            scheduler.step()
            optimizer.zero_grad()

            epoch_loss += loss.item()
            if step % 50 == 0:
                logger.info(f"  Epoch {epoch} Step {step}/{len(train_loader)} loss={loss.item():.4f}")

        avg_loss = epoch_loss / len(train_loader)
        elapsed = time.time() - t0

        # Evaluate
        metrics = evaluate(model, val_loader, id_to_label, device)
        logger.info(
            f"Epoch {epoch}/{args.epochs} -- loss={avg_loss:.4f}, "
            f"P={metrics['precision']:.4f} R={metrics['recall']:.4f} F1={metrics['f1']:.4f} "
            f"({elapsed:.1f}s)"
        )

        if metrics["f1"] > best_f1:
            best_f1 = metrics["f1"]
            patience_counter = 0
            # Save best model
            torch.save(model.state_dict(), output_path / "model.pt")
            config_data = {
                "model_name": model_name,
                "tag_to_idx": label_to_id,
                "use_crf": True,
                "dropout": 0.1,
                "label_list": label_list,
                "id_to_label": {str(k): v for k, v in id_to_label.items()},
                "num_params": total_params,
            }
            with open(output_path / "config.json", "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=2)
            tokenizer.save_pretrained(str(output_path / "tokenizer"))
            logger.info(f"  -> Best model saved (F1={best_f1:.4f})")
        else:
            patience_counter += 1
            if patience_counter >= args.patience:
                logger.info(f"Early stopping at epoch {epoch} (no improvement for {args.patience} epochs)")
                break

    logger.info(f"\nTraining complete. Best val F1: {best_f1:.4f}")
    logger.info(f"Model saved to: {output_path}")


if __name__ == "__main__":
    main()
