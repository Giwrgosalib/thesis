"""
Fine-tune a cross-encoder reranker using click log data.
"""

from __future__ import annotations

import argparse
import pandas as pd
from pathlib import Path

from torch.utils.data import Dataset
from transformers import AutoTokenizer, AutoModelForSequenceClassification, Trainer, TrainingArguments
import torch


class RerankDataset(Dataset):
    def __init__(self, dataframe: pd.DataFrame, tokenizer, max_length: int = 256):
        self.df = dataframe
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        encoding = self.tokenizer(
            row["query"],
            row["document"],
            truncation=True,
            padding="max_length",
            max_length=self.max_length,
            return_tensors="pt",
        )
        encoding = {k: v.squeeze(0) for k, v in encoding.items()}
        encoding["labels"] = torch.tensor(row["label"], dtype=torch.float)
        return encoding


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="backend/data/rerank_training.csv")
    parser.add_argument("--model", default="cross-encoder/ms-marco-MiniLM-L-6-v2")
    parser.add_argument("--output_dir", default="backend_nextgen/models/reranker")
    args = parser.parse_args()

    df = pd.read_csv(Path(args.dataset))
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    dataset = RerankDataset(df, tokenizer)

    model = AutoModelForSequenceClassification.from_pretrained(args.model, num_labels=1)
    training_args = TrainingArguments(
        output_dir=args.output_dir,
        per_device_train_batch_size=16,
        num_train_epochs=3,
        learning_rate=2e-5,
        evaluation_strategy="no",
    )

    trainer = Trainer(model=model, args=training_args, train_dataset=dataset, tokenizer=tokenizer)
    trainer.train()
    trainer.save_model(args.output_dir)


if __name__ == "__main__":
    main()
