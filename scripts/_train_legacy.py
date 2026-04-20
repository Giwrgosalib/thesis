"""Standalone training script for legacy BiLSTM-CRF on enriched dataset."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.custom_nlp import EBayNLP

nlp = EBayNLP()
nlp.train(dataset_path="backend/data/train_enriched.csv", iterations=25)
print("Training complete.")
