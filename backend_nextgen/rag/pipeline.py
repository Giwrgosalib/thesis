"""
Retrieval-Augmented Generation pipeline for conversational responses.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any, Optional


@dataclass
class RAGResponse:
    answer: str
    citations: List[Dict[str, str]]


class RAGPipeline:
    """
    Orchestrates retrieval + generation for grounded answers.
    """

    def __init__(self, retriever, generator, max_context_docs: int = 5) -> None:
        self.retriever = retriever
        self.generator = generator
        self.max_context_docs = max_context_docs

    def answer(self, query: str, documents: Optional[List[Dict[str, Any]]] = None) -> RAGResponse:
        if documents is None:
            retrieved = self.retriever.retrieve(query, top_k=self.max_context_docs)
            documents = [doc.metadata for doc in retrieved]
        context_docs = documents[: self.max_context_docs]

        context_lines = []
        for idx, doc in enumerate(context_docs, 1):
            title = doc.get("title", "Listing")
            price = self._format_price(doc.get("price"))
            snippet = doc.get("description") or doc.get("subtitle") or ""
            snippet = snippet.strip()
            if len(snippet) > 160:
                snippet = snippet[:157].rstrip() + "..."
            line = f"{idx}. {title}"
            if price:
                line += f" — {price}"
            if snippet:
                line += f"\n   {snippet}"
            context_lines.append(line)

        context = "\n".join(context_lines) or "No matching listings are available."
        prompt = (
            "You are an AI shopping assistant helping a buyer choose on eBay.\n"
            f"User request: {query}\n\n"
            "Candidate listings:\n"
            f"{context}\n\n"
            "Respond with a short recommendation (1-2 sentences) highlighting the best option(s)."
        )
        answer = self.generator.generate(prompt)
        citations = [
            {"item_id": doc.get("item_id"), "title": doc.get("title", ""), "score": 0.0}
            for doc in context_docs
        ]
        return RAGResponse(answer=answer, citations=citations)

    @staticmethod
    def _format_price(price_payload: Any) -> str:
        if isinstance(price_payload, dict):
            value = price_payload.get("value")
            currency = price_payload.get("currency") or price_payload.get("currencyCode") or "USD"
            if value is not None:
                try:
                    numeric = float(value)
                    return f"{currency} {numeric:.2f}"
                except (TypeError, ValueError):
                    return f"{currency} {value}"
        return ""
