"""
Wrapper around a causal language model for response generation.
"""

from __future__ import annotations

import torch

try:
    from transformers import AutoModelForCausalLM, AutoTokenizer
except ImportError as exc:
    raise ImportError("Install transformers to use the generative model wrapper") from exc


class GenerativeResponder:
    """
    Simple interface to run inference with a decoder-only model.
    """

    def __init__(
        self,
        model_name: str,
        max_tokens: int = 384,
        temperature: float = 0.4,
        device: str | torch.device = "cpu",
    ) -> None:
        self.device = torch.device(device)
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(model_name)
        self.model.to(self.device)
        self.max_tokens = max_tokens
        self.temperature = temperature

    def generate(self, prompt: str) -> str:
        encoded = self.tokenizer(prompt, return_tensors="pt").to(self.device)
        with torch.no_grad():
            output_ids = self.model.generate(
                **encoded,
                max_new_tokens=self.max_tokens,
                temperature=self.temperature,
                do_sample=self.temperature > 0,
            )
        response = self.tokenizer.decode(output_ids[0], skip_special_tokens=True)
        generated = response[len(prompt) :].strip()
        return generated or "I'm still gathering more detailed recommendations for you."
