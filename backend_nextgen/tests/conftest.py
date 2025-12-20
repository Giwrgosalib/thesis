import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import pytest

from backend_nextgen.config.loader import NextGenConfig
from backend_nextgen.ranking.neural_reranker import RankedItem


os.environ.setdefault("NEXTGEN_SKIP_AUTOINIT", "1")


class DummyNERInference:
    def extract_entities(self, query: str) -> Dict[str, Any]:
        buckets = {}
        lower = query.lower()
        if "nike" in lower:
            buckets["BRAND"] = ["Nike"]
        if any(token in lower for token in ("black", "white", "red")):
            buckets["COLOR"] = [token for token in ("black", "white", "red") if token in lower]
        if any(token in lower for token in ("size", "10")):
            buckets["SIZE"] = ["10"]
        return {"entities": buckets, "raw_entities": []}


class DummyGenerator:
    def generate(self, prompt: str) -> str:  # pragma: no cover - deterministic helper
        lines = {line.split(":", 1)[0].strip(): line.split(":", 1)[1].strip() for line in prompt.splitlines() if ":" in line}
        anchor = lines.get("Anchor", "")
        refinement = lines.get("Refinement", "")
        history_line = lines.get("History", "")

        rewritten = f"{anchor} {refinement}".strip()
        if "nike" in history_line.lower() and "nike" not in rewritten.lower():
            rewritten = f"nike shoes {rewritten}"
        return rewritten


class DummyRetriever:
    def retrieve(self, query: str, top_k: int = 5):  # pragma: no cover - deterministic helper
        return []

    def encode_queries(self, texts: List[str]):  # pragma: no cover - deterministic helper
        return []


class DummyReranker:
    def rerank(self, query: str, items: List[Dict[str, Any]], top_k: int = 20):
        return [
            RankedItem(
                item_id=item.get("item_id", f"item-{idx}"),
                score=float(top_k - idx),
                payload=item,
            )
            for idx, item in enumerate(items[:top_k])
        ]


class DummyRAG:
    def generate(self, *_args: Any, **_kwargs: Any) -> str:  # pragma: no cover - helper
        return "Here are some results based on your request."

    def answer(self, query: str, items: List[Dict[str, Any]]):  # pragma: no cover - helper
        top_title = items[0]["title"] if items else "a relevant option"
        return type("RagAnswer", (), {"answer": f"Top pick for '{query}' is {top_title}."})


class DummyBandit:
    def __init__(self) -> None:
        self.feature_dim = 32
        self.updates: List[Dict[str, Any]] = []

    @dataclass
    class Recommendation:
        item_id: str
        score: float
        metadata: Dict[str, Any]
        explanation: str = "Contextual Thompson Sampling (stub)"

    def recommend(self, user_id: str, candidates: List[Dict[str, Any]]):  # pragma: no cover - helper
        return candidates[0] if candidates else None

    def update(self, user_id: str, item_id: str, reward: float, _context: Dict[str, Any]):  # pragma: no cover
        self.updates.append({"user_id": user_id, "item_id": item_id, "reward": reward})

    def save_state(self, path: str) -> None:  # pragma: no cover - helper
        Path(path).write_bytes(b"")

    def select(self, candidates: List[Any]) -> "DummyBandit.Recommendation":  # pragma: no cover - helper
        if not candidates:
            return self.Recommendation(item_id="none", score=0.0, metadata={})
        item_id, _features, payload = candidates[0]
        return self.Recommendation(item_id=item_id, score=1.0, metadata=payload)


class DummyEbayService:
    def search(self, intent_payload: Dict[str, Any], user_id: str | None = None, limit: int = 10, offset: int = 0):
        items = [
            {
                "item_id": "ebay-1",
                "title": "Nike Pegasus Road Running Shoes",
                "price": {"value": 119.99, "currency": "USD"},
                "seller": {"username": "trusted_seller", "feedbackPercentage": 99.8},
                "condition": "New",
            },
            {
                "item_id": "ebay-2",
                "title": "Adidas Ultraboost 22",
                "price": {"value": 89.5, "currency": "USD"},
                "seller": {"username": "gear_shop", "feedbackPercentage": 98.0},
                "condition": "Used",
            },
        ]
        return items[offset : offset + limit]


@dataclass
class DummyMetricRecord:
    name: str
    value: float
    metadata: Dict[str, Any] | None = None


class DummyMetricSink:
    def __init__(self) -> None:
        self.records: List[DummyMetricRecord] = []

    def log(self, record: DummyMetricRecord) -> None:
        self.records.append(record)

    def query(self, name: str, since: float) -> List[DummyMetricRecord]:
        if not self.records:
            return [DummyMetricRecord(name=name, value=0.0)]
        return [r for r in self.records if r.name == name]


def _build_stub_orchestrator(tmp_path) -> Any:
    from backend_nextgen import orchestrator as orch_module

    orch = orch_module.NextGenAIOrchestrator.__new__(orch_module.NextGenAIOrchestrator)
    orch.config = NextGenConfig(
        raw={
            "ranking": {"rerank_top_k": 5},
            "personalization": {"exploration_rate": 0.1},
            "rag": {"max_context_docs": 3, "response_max_tokens": 64, "temperature": 0.3},
            "observability": {"metrics_path": str(tmp_path / "metrics.db")},
        }
    )
    orch.tag_to_idx = {"O": 0}
    orch.ner_inference = DummyNERInference()
    orch.generator = DummyGenerator()
    orch.retriever = DummyRetriever()
    orch.reranker = DummyReranker()
    orch.rag = DummyRAG()
    orch.metric_sink = DummyMetricSink()
    orch.bandit = DummyBandit()
    orch.bandit_path = str(tmp_path / "bandit_model.npz")
    orch.user_vectors = {}
    orch.user_vectors_path = str(tmp_path / "user_vectors.npz")
    orch.fallback_categories = ["shoes", "phone", "laptop"]
    orch.fallback_brands = ["nike", "apple", "samsung"]
    orch.ebay_service = DummyEbayService()
    orch.vector_index_ready = True
    orch.rewrite_validator = None
    orch.rewrite_tokenizer = None
    return orch


@pytest.fixture(scope="session")
def orchestrator_stub(tmp_path_factory):
    tmp_dir = tmp_path_factory.mktemp("nextgen_stub")
    orch_module = sys.modules.pop("backend_nextgen.orchestrator", None)
    if orch_module:
        sys.modules.pop("backend_nextgen.orchestrator", None)
    import backend_nextgen.orchestrator as orch_module_reloaded

    stub = _build_stub_orchestrator(tmp_dir)
    orch_module_reloaded.orchestrator = stub
    return stub


@pytest.fixture(autouse=True)
def _use_stub(orchestrator_stub):
    # Make sure every test sees the stubbed orchestrator
    yield orchestrator_stub
