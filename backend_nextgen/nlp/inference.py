"""
Inference helpers for the fine-tuned transformer NER model.

Supports two model formats:
  1. Standard HuggingFace AutoModelForTokenClassification (from train_transformer_ner.py)
  2. Custom TransformerCRFNER format (config.json has 'model_name' + 'label_to_id' keys)
     — used by the original training pipeline stored at models/deberta_crf/
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import torch
from transformers import AutoTokenizer, AutoModelForTokenClassification

logger = logging.getLogger(__name__)


@dataclass
class NERPrediction:
    label: str
    value: str
    score: float


class TransformerNERInference:
    """
    Wraps a fine-tuned transformer NER model for runtime inference.

    Automatically detects whether the model directory was saved by
    - ``train_transformer_ner.py`` (standard HF format), or
    - the original ``TransformerCRFNER`` training pipeline (custom format with
      a ``model_name`` key in ``config.json`` and CRF weights in ``pytorch_model.bin``).
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
        self.confidence_threshold = confidence_threshold
        self._use_crf = False

        # Detect model format from config.json
        config_path = resolved_path / "config.json"
        if not config_path.exists():
            raise FileNotFoundError(f"config.json missing in NER model dir: {resolved_path}")

        with open(config_path, encoding="utf-8") as f:
            raw_cfg = json.load(f)

        # Custom TransformerCRFNER format: has 'model_name' + 'label_to_id'
        if "model_name" in raw_cfg and "label_to_id" in raw_cfg:
            self._load_custom_crf_model(resolved_path, raw_cfg)
        else:
            # Standard HuggingFace format
            self._load_hf_model(resolved_path)

    # ------------------------------------------------------------------
    # Loaders
    # ------------------------------------------------------------------

    def _load_hf_model(self, model_dir: Path) -> None:
        """Load a standard HuggingFace AutoModelForTokenClassification."""
        self.tokenizer = AutoTokenizer.from_pretrained(model_dir)
        self.model = AutoModelForTokenClassification.from_pretrained(model_dir)
        self.model.to(self.device)
        self.model.eval()
        self.id2label: Dict[int, str] = {int(k): v for k, v in self.model.config.id2label.items()}
        logger.info(f"Loaded HF NER model from {model_dir} ({len(self.id2label)} labels)")

    def _load_custom_crf_model(self, model_dir: Path, cfg: Dict[str, Any]) -> None:
        """
        Load a TransformerCRFNER model saved in the custom format.
        The tokenizer is loaded from the base model name (downloaded/cached by HuggingFace).
        The encoder + classifier weights are extracted from the state dict.
        """
        from backend_nextgen.nlp.transformer_ner import TransformerCRFNER

        base_model_name: str = cfg["model_name"]
        label_to_id: Dict[str, int] = cfg["label_to_id"]
        tag_to_idx = {k: int(v) for k, v in label_to_id.items()}
        self.id2label = {int(v): k for k, v in tag_to_idx.items()}

        logger.info(f"Loading custom CRF NER model (base: {base_model_name}, labels: {len(tag_to_idx)})")

        # Tokenizer: load from cache or download
        tokenizer_dir = model_dir / "tokenizer"
        if tokenizer_dir.exists():
            self.tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_dir))
        else:
            logger.info(f"Tokenizer not cached locally — downloading from {base_model_name}")
            self.tokenizer = AutoTokenizer.from_pretrained(base_model_name)
            # Cache alongside model for future offline use
            try:
                tokenizer_dir.mkdir(parents=True, exist_ok=True)
                self.tokenizer.save_pretrained(str(tokenizer_dir))
                logger.info(f"Tokenizer cached to {tokenizer_dir}")
            except Exception as e:
                logger.warning(f"Could not cache tokenizer: {e}")

        # Build TransformerCRFNER and load weights
        crf_model = TransformerCRFNER(
            model_name=base_model_name,
            tag_to_idx=tag_to_idx,
            use_crf=True,
        )
        weights_path = model_dir / "pytorch_model.bin"
        if not weights_path.exists():
            raise FileNotFoundError(f"pytorch_model.bin not found in {model_dir}")

        state_dict = torch.load(weights_path, map_location="cpu", weights_only=False)
        crf_model.load_state_dict(state_dict, strict=False)
        crf_model.to(self.device)
        crf_model.eval()

        self.model = crf_model
        self._use_crf = True
        logger.info("Custom CRF NER model loaded successfully.")

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def predict(self, text: str) -> List[NERPrediction]:
        """
        Run NER on ``text`` and return a list of entity predictions above
        the confidence threshold.
        """
        # Lowercase for robustness (consistent with training preprocessing)
        text_lower = text.lower()
        encoded = self.tokenizer(
            text_lower,
            return_tensors="pt",
            truncation=True,
            max_length=512,
        )
        encoded = {k: v.to(self.device) for k, v in encoded.items()}

        with torch.no_grad():
            if self._use_crf:
                # Custom TransformerCRFNER: forward returns (loss|None, tag_seqs)
                _, tag_seqs = self.model(
                    input_ids=encoded["input_ids"],
                    attention_mask=encoded["attention_mask"],
                )
                # tag_seqs is List[List[int]] when CRF is used
                tag_seq = tag_seqs[0] if tag_seqs else []
                tokens = self.tokenizer.convert_ids_to_tokens(encoded["input_ids"].squeeze(0))
                # CRF doesn't produce per-token probabilities; assign neutral score
                token_scores = [1.0] * len(tag_seq)
                tag_labels = [self.id2label.get(int(t), "O") for t in tag_seq]
            else:
                # Standard HF model
                outputs = self.model(**encoded)
                logits = outputs.logits.squeeze(0)
                probs = torch.softmax(logits, dim=-1)
                scores_t, indices_t = torch.max(probs, dim=-1)
                tokens = self.tokenizer.convert_ids_to_tokens(encoded["input_ids"].squeeze(0))
                tag_labels = [self.id2label.get(int(i), "O") for i in indices_t.tolist()]
                token_scores = scores_t.tolist()

        predictions: List[NERPrediction] = []
        current_tokens: List[str] = []
        current_label: Optional[str] = None
        current_scores: List[float] = []

        for token, label, score in zip(tokens, tag_labels, token_scores):
            if token in self.tokenizer.all_special_tokens:
                continue
            if label.startswith("B-"):
                if current_tokens and current_label:
                    predictions.append(NERPrediction(
                        label=current_label,
                        value=self._tokens_to_text(current_tokens),
                        score=sum(current_scores) / len(current_scores),
                    ))
                current_tokens = [token]
                current_label = label[2:]
                current_scores = [score]
            elif label.startswith("I-") and current_label == label[2:]:
                current_tokens.append(token)
                current_scores.append(score)
            else:
                if current_tokens and current_label:
                    predictions.append(NERPrediction(
                        label=current_label,
                        value=self._tokens_to_text(current_tokens),
                        score=sum(current_scores) / len(current_scores),
                    ))
                current_tokens = []
                current_label = None
                current_scores = []

        if current_tokens and current_label:
            predictions.append(NERPrediction(
                label=current_label,
                value=self._tokens_to_text(current_tokens),
                score=sum(current_scores) / len(current_scores),
            ))

        # For CRF models we trust the decode fully; only threshold for softmax models
        if self._use_crf:
            return predictions
        return [p for p in predictions if p.score >= self.confidence_threshold]

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
