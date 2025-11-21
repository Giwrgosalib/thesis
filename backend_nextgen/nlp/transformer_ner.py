"""
Transformer-based NER model with optional CRF decoding.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Dict, List

import torch
from torch import nn

try:
    from transformers import AutoConfig, AutoModel
except ImportError as exc:
    raise ImportError("Install transformers to use the next-gen NER module") from exc

try:
    from torchcrf import CRF  # type: ignore
except ImportError:
    CRF = None  # type: ignore


@dataclass
class NEROutput:
    tokens: List[str]
    tags: List[str]
    scores: List[float]


class TransformerCRFNER(nn.Module):
    """
    Transformer encoder with a projection head and optional CRF decoding.
    """

    def __init__(
        self,
        model_name: str,
        tag_to_idx: Dict[str, int],
        use_crf: bool = True,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        self.tag_to_idx = tag_to_idx
        self.idx_to_tag = {v: k for k, v in tag_to_idx.items()}
        self.use_crf = use_crf and CRF is not None

        if use_crf and CRF is None:
            warnings.warn(
                "torchcrf is not installed; falling back to softmax tagging.",
                RuntimeWarning,
            )

        self.config = AutoConfig.from_pretrained(model_name)
        self.encoder = AutoModel.from_pretrained(model_name, config=self.config)
        hidden_size = self.encoder.config.hidden_size

        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Linear(hidden_size, len(tag_to_idx))

        self.crf = CRF(len(tag_to_idx), batch_first=True) if self.use_crf else None

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor,
        labels: torch.Tensor | None = None,
    ):
        outputs = self.encoder(input_ids=input_ids, attention_mask=attention_mask)
        sequence_output = self.dropout(outputs.last_hidden_state)
        emissions = self.classifier(sequence_output)

        if self.use_crf and self.crf is not None:
            loss = None
            if labels is not None:
                loss = -self.crf(
                    emissions, labels, mask=attention_mask.bool(), reduction="mean"
                )
            tag_seqs = self.crf.decode(emissions, mask=attention_mask.bool())
            return loss, tag_seqs

        logits = emissions
        loss = None
        if labels is not None:
            loss_fn = nn.CrossEntropyLoss()
            loss = loss_fn(logits.view(-1, logits.size(-1)), labels.view(-1))
        predictions = logits.argmax(dim=-1)
        return loss, predictions

    def decode(self, token_ids: torch.Tensor, attention_mask: torch.Tensor) -> List[List[str]]:
        self.eval()
        with torch.no_grad():
            _, predictions = self.forward(token_ids, attention_mask)

        decoded_tags: List[List[str]] = []
        for pred, mask in zip(predictions, attention_mask):
            decoded_tags.append(
                [self.idx_to_tag[idx.item()] for idx, m in zip(pred, mask) if m.item() == 1]
            )
        return decoded_tags
