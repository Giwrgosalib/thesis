"""
Inference helpers for the fine-tuned transformer NER model.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Any

import torch
from transformers import AutoTokenizer, AutoModelForTokenClassification


@dataclass
class NERPrediction:
    label: str
    value: str
    score: float


class TransformerNERInference:
    """
    Wraps a fine-tuned Hugging Face token classification model for runtime NER.
    """

    def __init__(
        self,
        model_path: str | Path,
        device: str | torch.device = "cpu",
        confidence_threshold: float = 0.5,
    ) -> None:
        resolved_path = Path(model_path).resolve()
        if not resolved_path.exists():
            raise FileNotFoundError(f"NER model directory not found: {resolved_path}")

        self.device = torch.device(device)
        self.tokenizer = AutoTokenizer.from_pretrained(resolved_path)
        self.model = AutoModelForTokenClassification.from_pretrained(resolved_path)
        self.model.to(self.device)
        self.model.eval()
        self.id2label = self.model.config.id2label
        self.confidence_threshold = confidence_threshold

    def predict(self, text: str) -> List[NERPrediction]:
        # Normalize text to lowercase for robust extraction
        text = text.lower()
        encoded = self.tokenizer(text, return_tensors="pt")
        encoded = {k: v.to(self.device) for k, v in encoded.items()}

        with torch.no_grad():
            outputs = self.model(**encoded)
            logits = outputs.logits.squeeze(0)
            probs = torch.softmax(logits, dim=-1)
            scores, indices = torch.max(probs, dim=-1)

        tokens = self.tokenizer.convert_ids_to_tokens(encoded["input_ids"].squeeze(0))
        predictions: List[NERPrediction] = []

        current_tokens: List[str] = []
        current_label = None
        current_score = []

        for token, idx, score in zip(tokens, indices.tolist(), scores.tolist()):
            label = self.id2label.get(idx, "O")
            if token in self.tokenizer.all_special_tokens:
                continue
            if label.startswith("B-"):
                if current_tokens and current_label:
                    predictions.append(
                        NERPrediction(label=current_label, value=self._tokens_to_text(current_tokens), score=sum(current_score) / len(current_score))
                    )
                current_tokens = [token]
                current_label = label[2:]
                current_score = [score]
            elif label.startswith("I-") and current_label == label[2:]:
                current_tokens.append(token)
                current_score.append(score)
            else:
                if current_tokens and current_label:
                    predictions.append(
                        NERPrediction(label=current_label, value=self._tokens_to_text(current_tokens), score=sum(current_score) / len(current_score))
                    )
                current_tokens = []
                current_label = None
                current_score = []

        if current_tokens and current_label:
            predictions.append(
                NERPrediction(label=current_label, value=self._tokens_to_text(current_tokens), score=sum(current_score) / len(current_score))
            )

        filtered = [pred for pred in predictions if pred.score >= self.confidence_threshold]
        return filtered

    def extract_entities(self, text: str) -> Dict[str, Any]:
        predictions = self.predict(text)
        grouped: Dict[str, List[str]] = {}
        raw = []
        for pred in predictions:
            grouped.setdefault(pred.label, []).append(pred.value)
            raw.append({"label": pred.label, "value": pred.value, "score": pred.score})
        return {
            "intent": "search_product",
            "raw_query": text,
            "entities": grouped,
            "raw_entities": raw,
        }

    def _tokens_to_text(self, tokens: List[str]) -> str:
        # Improved decoding for both WordPiece (##) and SentencePiece ( )
        # Using the tokenizer's method is safest if available, but manual fallback below:
        if hasattr(self.tokenizer, "convert_tokens_to_string"):
            return self.tokenizer.convert_tokens_to_string(tokens).strip()
            
        # Fallback manual reconstruction
        clean_tokens: List[str] = []
        for token in tokens:
            # Handle SentencePiece underscore
            token = token.replace(" ", " ")
            
            if token.startswith("##"):
                if clean_tokens:
                    clean_tokens[-1] += token[2:]
                else:
                    clean_tokens.append(token[2:])
            else:
                clean_tokens.append(token)
        return " ".join(clean_tokens).strip()
