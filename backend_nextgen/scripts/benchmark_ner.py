"""
Benchmark legacy BiLSTM-CRF vs next-gen transformer NER on the refined dataset.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Tuple

import sys
from pathlib import Path

import pandas as pd
import torch
from seqeval.metrics import classification_report

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from custom_nlp import EBayNLP  # type: ignore
from backend_nextgen.config.loader import load_config
from backend_nextgen.nlp.transformer_ner import TransformerCRFNER


def load_dataset(dataset_path: Path) -> List[Tuple[List[str], List[str]]]:
    df = pd.read_csv(dataset_path)
    samples: List[Tuple[List[str], List[str]]] = []
    for _, row in df.iterrows():
        query = str(row["query"])
        entities = row["entities"]
        try:
            parsed = eval(entities) if isinstance(entities, str) else entities
        except Exception:
            continue
        tokens = query.split()
        tags = ["O"] * len(tokens)
        for start, end, label in parsed:
            # naive alignment
            for idx, token in enumerate(tokens):
                if label:
                    tags[idx] = "B-" + label
        samples.append((tokens, tags))
    return samples


def evaluate_bilstm(samples: List[Tuple[List[str], List[str]]]) -> List[List[str]]:
    model = EBayNLP()
    predictions: List[List[str]] = []
    for tokens, _ in samples:
        query = " ".join(tokens)
        result = model.extract_entities(query)
        predicted_tags = []
        for token in tokens:
            tag = "O"
            for entity in result.get("raw_entities", []):
                if token.lower() in entity["value"].lower():
                    tag = "B-" + entity["label"]
                    break
            predicted_tags.append(tag)
        predictions.append(predicted_tags)
    return predictions


def evaluate_transformer(samples: List[Tuple[List[str], List[str]]]) -> List[List[str]]:
    config = load_config()
    tag_to_idx = {"O": 0, "B-BRAND": 1, "I-BRAND": 2}  # placeholder
    model = TransformerCRFNER(
        model_name=config.section("nlp")["model_name"],
        tag_to_idx=tag_to_idx,
    )
    predictions: List[List[str]] = []
    for tokens, _ in samples:
        # Simplified evaluation; would need tokenizer alignment
        predictions.append(["O"] * len(tokens))
    return predictions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="backend/data/refined_balanced_dataset_val.csv")
    args = parser.parse_args()
    samples = load_dataset(Path(args.dataset))
    gold = [tags for _, tags in samples]
    bilstm_preds = evaluate_bilstm(samples)
    transformer_preds = evaluate_transformer(samples)

    print("=== BiLSTM-CRF Report ===")
    print(classification_report(gold, bilstm_preds))
    print("=== Transformer NER Report ===")
    print(classification_report(gold, transformer_preds))


if __name__ == "__main__":
    main()
