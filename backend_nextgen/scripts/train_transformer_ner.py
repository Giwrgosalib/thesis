"""
Fine-tune the transformer-based NER model on the refined dataset.

This script provides a reproducible entry point for thesis experiments.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import torch
from torch.utils.data import Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForTokenClassification,
    Trainer,
    TrainingArguments,
    DataCollatorForTokenClassification,
)
import inspect

from backend_nextgen.config.loader import load_config


REQUIRED_MODULES = {
    "sentencepiece": "sentencepiece",
    "protobuf": "google.protobuf",
    "tiktoken": "tiktoken",
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


class NERDataset(Dataset):
    def __init__(self, dataframe: pd.DataFrame, tokenizer, label_to_id: dict, max_length: int = 256):
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
        labels = ["O"] * len(tokens)
        entities = row["entities"]
        try:
            parsed = eval(entities) if isinstance(entities, str) else entities
        except Exception:
            parsed = []
        for start, end, label in parsed:
            for i in range(len(tokens)):
                labels[i] = "B-" + label

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
        for word_id in word_ids:
            if word_id is None:
                label_ids.append(-100)
            else:
                label_ids.append(self.label_to_id.get(labels[word_id], self.label_to_id["O"]))

        encoding["labels"] = torch.tensor(label_ids)
        return {k: v.squeeze(0) for k, v in encoding.items()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", default="backend/data/refined_balanced_dataset_train.csv")
    parser.add_argument("--val", default="backend/data/refined_balanced_dataset_val.csv")
    parser.add_argument("--output_dir", default="backend_nextgen/models/ner")
    parser.add_argument("--max_samples", type=int, default=512, help="Limit number of training samples for quick iterations.")
    args = parser.parse_args()

    config = load_config()
    model_name = config.section("nlp")["model_name"]
    ensure_dependencies()
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    if not getattr(tokenizer, "is_fast", False):
        raise RuntimeError(
            "The selected tokenizer does not expose a fast implementation. "
            "Install `tiktoken` and ensure the model has a fast tokenizer, or "
            "switch to a model with fast tokenizer support."
        )
    label_list = ["O", "B-BRAND", "I-BRAND"]
    label_to_id = {label: idx for idx, label in enumerate(label_list)}

    train_df = pd.read_csv(Path(args.train))
    val_df = pd.read_csv(Path(args.val))

    if args.max_samples and len(train_df) > args.max_samples:
        train_df = train_df.sample(n=args.max_samples, random_state=42).reset_index(drop=True)

    if args.max_samples and len(val_df) > max(args.max_samples // 4, 1):
        val_df = val_df.sample(n=max(args.max_samples // 4, 1), random_state=42).reset_index(drop=True)

    max_length = config.section("nlp").get("max_sequence_length", 256)
    train_dataset = NERDataset(train_df, tokenizer, label_to_id, max_length=max_length)
    val_dataset = NERDataset(val_df, tokenizer, label_to_id, max_length=max_length)

    model = AutoModelForTokenClassification.from_pretrained(model_name, num_labels=len(label_list), id2label={i: l for i, l in enumerate(label_list)}, label2id=label_to_id)

    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    training_kwargs = {
        "output_dir": args.output_dir,
        "logging_steps": 10,
        "per_device_train_batch_size": 4,
        "per_device_eval_batch_size": 4,
        "num_train_epochs": 1,
        "learning_rate": 5e-5,
        "weight_decay": 0.01,
        "save_total_limit": 1,
        "save_steps": 500,
    }

    training_args = TrainingArguments(**training_kwargs)

    data_collator = DataCollatorForTokenClassification(tokenizer, padding="max_length", max_length=max_length)

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        tokenizer=tokenizer,
        data_collator=data_collator,
    )

    trainer.train()
    trainer.save_model(args.output_dir)


if __name__ == "__main__":
    main()
