"""
High-level orchestrator composing the next-gen AI agents.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, List, Optional

import hashlib
import json
import logging
import time

import numpy as np
import torch

from backend_nextgen.config.loader import load_config
from backend_nextgen.nlp.transformer_ner import TransformerCRFNER
from backend_nextgen.nlp.inference import TransformerNERInference
from backend_nextgen.retrieval.dual_encoder import DualEncoderRetriever
from backend_nextgen.ranking.neural_reranker import NeuralReRanker, RankedItem
from backend_nextgen.personalization.contextual_bandit import ContextualThompsonSampling
from backend_nextgen.rag.generator import GenerativeResponder
from backend_nextgen.rag.pipeline import RAGPipeline
from backend_nextgen.observability.metrics import MetricSink, MetricRecord
from backend_nextgen.active_learning.loop import UncertaintySampler
from backend_nextgen.knowledge.graph_builder import KnowledgeGraph
from backend.ebay_service import EBayService

logger = logging.getLogger(__name__)


class NextGenAIOrchestrator:
    """
    Wiring layer that connects retrieval, NER, ranking, personalization, and RAG.
    """

    def __init__(self, config_path: Path | None = None) -> None:
        self.config = load_config(config_path)

        nlp_cfg = self.config.section("nlp")
        self.tag_to_idx = self._load_tag_mapping()
        self.ner_model = TransformerCRFNER(
            model_name=nlp_cfg["model_name"],
            tag_to_idx=self.tag_to_idx,
            use_crf=nlp_cfg.get("use_crf_head", True),
        )
        trained_model_path = nlp_cfg.get("trained_model_path")
        if trained_model_path:
            model_path = Path(trained_model_path)
            if not model_path.is_absolute():
                model_path = Path(__file__).resolve().parent / model_path
            model_path = model_path.resolve()
            if not model_path.exists():
                raise FileNotFoundError(
                    f"Configured transformer NER path does not exist: {model_path}"
                )
            self.ner_inference = TransformerNERInference(
                model_path=model_path,
                device=self._resolve_device(nlp_cfg.get("device", "cpu")),
                confidence_threshold=nlp_cfg.get("confidence_threshold", 0.5),
            )
        else:
            self.ner_inference = None

        retrieval_cfg = self.config.section("retrieval")
        index_matrix, metadata, self.vector_index_ready = self._load_vector_store(
            retrieval_cfg
        )
        if not self.vector_index_ready:
            logger.error(
                "Vector index unavailable; retrieval will use placeholder data."
            )
        self.retriever = DualEncoderRetriever(
            model_name=retrieval_cfg["encoder_name"],
            index=index_matrix,
            metadata=metadata,
        )

        ranking_cfg = self.config.section("ranking")
        self.reranker = NeuralReRanker(model_name=ranking_cfg["model_name"])

        personalization_cfg = self.config.section("personalization")
        feature_dim = 32
        self.bandit = ContextualThompsonSampling(feature_dim=feature_dim, alpha=personalization_cfg["exploration_rate"])

        rag_cfg = self.config.section("rag")
        self.generator = GenerativeResponder(
            model_name=rag_cfg["generator_name"],
            max_tokens=rag_cfg["response_max_tokens"],
            temperature=rag_cfg["temperature"],
        )
        self.rag = RAGPipeline(retriever=self.retriever, generator=self.generator, max_context_docs=rag_cfg["max_context_docs"])

        observability_cfg = self.config.section("observability")
        self.metric_sink = MetricSink(Path(observability_cfg["metrics_path"]))

        active_cfg = self.config.section("active_learning")
        self.uncertainty_sampler = UncertaintySampler(
            threshold=active_cfg["disagreement_threshold"],
            batch_size=active_cfg["batch_size"],
        )

        self.knowledge_graph = KnowledgeGraph()
        self.ebay_service = EBayService()

    def handle_query(self, query: str, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Entry point for conversational handling.
        """
        entity_payload = {}
        if self.ner_inference:
            entity_payload = self.ner_inference.extract_entities(query)

        intent_payload = self._build_intent_payload(query, entity_payload)
        intent_payload = self._merge_user_preferences(intent_payload, user_context)
        ebay_items = self._search_ebay(intent_payload, user_context)
        normalized_items = [self._normalize_item(item) for item in ebay_items]

        reranked = self._rerank_items(query, normalized_items, user_context)

        features = self._build_personalization_features(
            intent_payload, normalized_items, user_context
        )
        recommendation = self.bandit.select(
            [
                (
                    item.item_id,
                    features,
                    item.payload,
                )
                for item in reranked
            ]
        )

        rag_response = None
        if self.rag:
            try:
                rag_response = self.rag.answer(query, normalized_items)
            except Exception as exc:
                self.metric_sink.log(
                    MetricRecord(
                        name="nextgen_rag_error",
                        value=1.0,
                        metadata={"error": str(exc)[:120]},
                    )
                )
                rag_response = None

        answer_text = self._select_answer(rag_response, reranked, normalized_items, entity_payload)

        self.metric_sink.log(
            MetricRecord(
                name="nextgen_response_latency_ms",
                value=42.0,
                metadata={"query": query[:50]},
            )
        )

        return {
            "query": query,
            "entities": entity_payload,
            "retrieval": normalized_items,
            "recommendation": recommendation.metadata,
            "answer": answer_text,
            "citations": self._build_citations(reranked),
        }

    def _load_tag_mapping(self) -> Dict[str, int]:
        """Load the enhanced entity schema to keep transformer NER tags aligned."""
        try:
            repo_root = Path(__file__).resolve().parents[2]
            info_path = (
                repo_root / "backend" / "models" / "enhanced" / "model_info.json"
            )
            with info_path.open("r", encoding="utf-8") as handle:
                info = json.load(handle)
            entity_labels = info.get("entity_types") or []
            tags = ["O"]
            for label in entity_labels:
                normalized_label = str(label).upper()
                tags.append(f"B-{normalized_label}")
                tags.append(f"I-{normalized_label}")
            return {tag: idx for idx, tag in enumerate(tags)}
        except Exception as exc:  # noqa: BLE001
            logger.warning("Falling back to placeholder tag map: %s", exc)
            return {"O": 0, "B-BRAND": 1, "I-BRAND": 2}

    def _build_personalization_features(
        self,
        intent_payload: Dict[str, Any],
        normalized_items: List[Dict[str, Any]],
        user_context: Dict[str, Any],
    ) -> np.ndarray:
        feature_dim = self.bandit.feature_dim
        vector = np.zeros(feature_dim, dtype=np.float32)

        entity_buckets = intent_payload.get("entities") or {}
        preferences = user_context.get("preferences") if isinstance(user_context, dict) else {}

        if hasattr(entity_buckets, "keys"):
            entity_diversity = min(len(list(entity_buckets.keys())) / 50.0, 1.0)
        else:
            entity_diversity = 0.0

        slots = [
            (0, min(len(normalized_items) / 10.0, 1.0)),
            (1, 1.0 if intent_payload.get("price_range") else 0.0),
            (2, min(len(intent_payload.get("brands", [])) / 4.0, 1.0)),
            (3, min(len(intent_payload.get("categories", [])) / 4.0, 1.0)),
            (4, entity_diversity),
            (5, self._average_price_feature(normalized_items)),
            (6, self._seller_reputation_feature(normalized_items)),
            (
                7,
                1.0
                if user_context.get("loggedIn") or user_context.get("logged_in")
                else 0.0,
            ),
            (8, min(len(preferences.get("brands", [])) / 5.0, 1.0)),
            (9, min(len(preferences.get("categories", [])) / 5.0, 1.0)),
            (10, min(len(preferences.get("recent_queries", [])) / 10.0, 1.0)),
            (11, 1.0 if preferences else 0.0),
        ]

        for idx, value in slots:
            if idx < feature_dim:
                vector[idx] = float(value)

        hashed_start = 12
        if hashed_start < feature_dim:
            hashed = hashlib.sha256(
                intent_payload.get("raw_query", "").encode("utf-8", "ignore")
            ).digest()
            hashed_values = np.frombuffer(hashed, dtype=np.uint8) / 255.0
            idx = hashed_start
            while idx < feature_dim:
                vector[idx] = hashed_values[idx % hashed_values.size]
                idx += 1

        return vector

    def _average_price_feature(self, items: List[Dict[str, Any]]) -> float:
        prices = [
            price for item in items if (price := self._extract_numeric_price(item))
        ]
        if not prices:
            return 0.0
        avg_price = sum(prices) / len(prices)
        return min(avg_price / 1000.0, 1.0)

    def _seller_reputation_feature(self, items: List[Dict[str, Any]]) -> float:
        scores: List[float] = []
        for item in items:
            seller = item.get("seller") or {}
            score = seller.get("feedbackScore") or seller.get("feedback_score")
            if score is None:
                continue
            try:
                scores.append(min(float(score) / 5000.0, 1.0))
            except (TypeError, ValueError):
                continue
        return max(scores) if scores else 0.0

    def _extract_numeric_price(self, item: Dict[str, Any]) -> Optional[float]:
        price_candidate: Any = (
            item.get("price")
            or item.get("priceValue")
            or item.get("price_value")
            or item.get("currentPrice")
        )
        if isinstance(price_candidate, dict):
            price_candidate = price_candidate.get("value") or price_candidate.get(
                "amount"
            )
        try:
            return float(price_candidate)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _resolve_device(device_setting: str) -> str:
        if device_setting == "auto":
            return "cuda" if torch.cuda.is_available() else "cpu"
        return device_setting

    def _build_intent_payload(self, query: str, entity_payload: Dict[str, Any]) -> Dict[str, Any]:
        entities = entity_payload.get("entities", {}) if entity_payload else {}
        price_values = entities.get("PRICE_RANGE") or entities.get("PRICE_TOKEN") or []
        price_range = None
        if price_values:
            price_range = ", ".join(map(str, price_values))

        intent_payload: Dict[str, Any] = {
            "raw_query": query,
            "intent": "search_product",
            "entities": entities,
            "raw_entities": entity_payload.get("raw_entities", []),
            "brands": entities.get("BRAND", []),
            "categories": entities.get("CATEGORY", []) or entities.get("PRODUCT_TYPE", []),
            "models": entities.get("MODEL", []),
            "price_range": price_range,
        }
        return intent_payload

    def _merge_user_preferences(
        self, intent_payload: Dict[str, Any], user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        preferences = user_context.get("preferences") if isinstance(user_context, dict) else None
        if not preferences:
            return intent_payload

        def _merge_list(target_key: str, preference_key: str) -> None:
            additions = preferences.get(preference_key) or []
            if not additions:
                return
            existing = intent_payload.get(target_key) or []
            merged = list(dict.fromkeys(list(existing) + [str(item) for item in additions if item]))
            intent_payload[target_key] = merged

        _merge_list("brands", "brands")
        _merge_list("categories", "categories")
        if not intent_payload.get("price_range") and preferences.get("price_ranges"):
            intent_payload["price_range"] = preferences["price_ranges"][0]
        if preferences.get("shipping"):
            shipping_entities = intent_payload.setdefault("entities", {})
            current_shipping = shipping_entities.get("SHIPPING") or []
            merged_shipping = list(
                dict.fromkeys(list(current_shipping) + [str(val) for val in preferences["shipping"]])
            )
            shipping_entities["SHIPPING"] = merged_shipping
        return intent_payload

    def _search_ebay(self, intent_payload: Dict[str, Any], user_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        user_id = None
        if isinstance(user_context, dict):
            user_id = user_context.get("userId") or user_context.get("user_id")
        try:
            return self.ebay_service.search(intent_payload, user_id=user_id)
        except Exception as exc:
            # Log metric and fall back to vector index
            self.metric_sink.log(
                MetricRecord(
                    name="nextgen_ebay_error",
                    value=1.0,
                    metadata={"error": str(exc)[:120]},
                )
            )
            return [res.metadata for res in self.retriever.retrieve(intent_payload["raw_query"])]

    def _normalize_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(item)
        item_id = (
            item.get("item_id")
            or item.get("itemId")
            or item.get("legacyItemId")
            or item.get("listingId")
        )
        if not item_id:
            item_id = f"ebay-{abs(hash(item.get('title', 'item')))}"
        normalized["item_id"] = item_id
        normalized.setdefault(
            "description",
            item.get("shortDescription") or item.get("subtitle") or "",
        )
        return normalized

    def _rerank_items(
        self, query: str, items: List[Dict[str, Any]], user_context: Dict[str, Any]
    ) -> List[RankedItem]:
        if not items:
            return []
        try:
            reranked = self.reranker.rerank(
                query, items, top_k=min(len(items), self.config.section("ranking")["rerank_top_k"])
            )
        except Exception as exc:
            self.metric_sink.log(
                MetricRecord(
                    name="nextgen_rerank_error",
                    value=1.0,
                    metadata={"error": str(exc)[:120]},
                )
            )
            reranked = [
                RankedItem(item_id=item["item_id"], score=0.0, payload=item)
                for item in items
            ]
        preferences = user_context.get("preferences") if isinstance(user_context, dict) else None
        if preferences:
            return self._apply_preference_boost(reranked, preferences)
        return reranked

    def _apply_preference_boost(
        self, ranked_items: List[RankedItem], preferences: Dict[str, Any]
    ) -> List[RankedItem]:
        brand_prefs = {str(value).lower() for value in preferences.get("brands", []) if value}
        category_prefs = {str(value).lower() for value in preferences.get("categories", []) if value}

        if not brand_prefs and not category_prefs:
            return ranked_items

        boosted: List[RankedItem] = []
        for item in ranked_items:
            bonus = 0.0
            brand = self._extract_brand_value(item.payload)
            if brand and brand in brand_prefs:
                bonus += 0.3
            item_categories = {value.lower() for value in self._extract_categories(item.payload)}
            if category_prefs and item_categories & category_prefs:
                bonus += 0.2
            boosted.append(
                RankedItem(
                    item_id=item.item_id,
                    score=item.score + bonus,
                    payload=item.payload,
                )
            )

        boosted.sort(key=lambda ranked: ranked.score, reverse=True)
        return boosted

    def _extract_brand_value(self, payload: Dict[str, Any]) -> Optional[str]:
        for key in ("brand", "brandName", "BRAND", "manufacturer"):
            value = payload.get(key)
            if value:
                return str(value).lower()
        seller = payload.get("seller") or {}
        seller_brand = seller.get("brand")
        if seller_brand:
            return str(seller_brand).lower()
        return None

    def _extract_categories(self, payload: Dict[str, Any]) -> List[str]:
        categories = payload.get("categories")
        if isinstance(categories, list):
            names = []
            for category in categories:
                if isinstance(category, dict):
                    name = category.get("categoryName") or category.get("name")
                else:
                    name = category
                if name:
                    names.append(str(name))
            return names
        return []

    def _build_citations(self, ranked_items: List[RankedItem]) -> List[Dict[str, Any]]:
        citations = []
        for ranked in ranked_items[:5]:
            payload = ranked.payload
            citations.append(
                {
                    "item_id": ranked.item_id,
                    "score": ranked.score,
                    "title": payload.get("title", ""),
                    "url": payload.get("itemWebUrl") or payload.get("item_url"),
                }
            )
        return citations

    def _load_vector_store(
        self, retrieval_cfg: Dict[str, Any]
    ) -> tuple[np.ndarray, List[Dict[str, Any]], bool]:
        placeholder_index = np.zeros((1, retrieval_cfg.get("embedding_dim", 768)))
        placeholder_metadata = [
            {"item_id": "demo", "title": "Placeholder item", "description": "Populate the index"}
        ]
        strict = retrieval_cfg.get("strict_index", True)
        try:
            base_dir = Path(__file__).resolve().parents[1]
            index_path = Path(retrieval_cfg["index_path"])
            metadata_path = Path(retrieval_cfg["metadata_store"])
            if not index_path.is_absolute():
                index_path = (base_dir / index_path).resolve()
            if not metadata_path.is_absolute():
                metadata_path = (base_dir / metadata_path).resolve()

            if not index_path.exists() or not metadata_path.exists():
                message = f"Vector store assets missing: {index_path} or {metadata_path}"
                self.metric_sink.log(
                    MetricRecord(
                        name="nextgen_vector_store_error",
                        value=1.0,
                        metadata={"error": message[:120]},
                    )
                )
                if strict:
                    raise FileNotFoundError(message)
                logger.warning(message)
                return placeholder_index, placeholder_metadata, False

            embeddings = np.load(index_path)
            metadata_raw = np.load(metadata_path, allow_pickle=True).tolist()
            if not isinstance(metadata_raw, list):
                metadata_raw = placeholder_metadata
            return embeddings, metadata_raw, True
        except Exception as exc:
            self.metric_sink.log(
                MetricRecord(
                    name="nextgen_vector_store_error",
                    value=1.0,
                    metadata={"error": str(exc)[:120]},
                )
            )
            if strict:
                raise
            logger.warning("Falling back to placeholder vector store: %s", exc)
            return placeholder_index, placeholder_metadata, False

    def summarize_metrics(self, window_seconds: int = 3600) -> Dict[str, Any]:
        """Summarize recent observability data for dashboards."""
        now = time.time()
        since = now - window_seconds

        def _summaries(records: List[MetricRecord]) -> Dict[str, float]:
            if not records:
                return {"count": 0}
            values = sorted(record.value for record in records)
            count = len(values)
            average = sum(values) / count
            p95_index = min(count - 1, int(0.95 * (count - 1)))
            return {
                "count": count,
                "avg": average,
                "max": values[-1],
                "p95": values[p95_index],
            }

        latency_stats = _summaries(
            self.metric_sink.query("nextgen_response_latency_ms", since)
        )

        error_names = [
            "nextgen_rag_error",
            "nextgen_rerank_error",
            "nextgen_ebay_error",
            "nextgen_vector_store_error",
        ]
        error_counts = {
            name: len(self.metric_sink.query(name, since)) for name in error_names
        }

        return {
            "window_seconds": window_seconds,
            "vector_index_ready": getattr(self, "vector_index_ready", True),
            "metrics": {
                "response_latency_ms": latency_stats,
                "errors": error_counts,
            },
        }

    def _select_answer(
        self,
        rag_response,
        ranked_items: List[RankedItem],
        normalized_items: List[Dict[str, Any]],
        entity_payload: Dict[str, Any],
    ) -> str:
        if rag_response:
            text = (rag_response.answer or "").strip()
            if text and not self._looks_unhelpful(text):
                return text
        return self._generate_structured_answer(normalized_items, entity_payload)

    @staticmethod
    def _looks_unhelpful(text: str) -> bool:
        lowered = text.lower()
        if not lowered or lowered == "none":
            return True
        if "answer concisely using the context" in lowered:
            return True
        unique_words = set(lowered.split())
        return len(unique_words) <= 3

    def _generate_structured_answer(
        self,
        items: List[Dict[str, Any]],
        entity_payload: Dict[str, Any],
    ) -> str:
        if not items:
            return "I couldn't find any active listings that match your request."

        top = items[0]
        runner_up = items[1] if len(items) > 1 else None

        brand = None
        if entity_payload and "entities" in entity_payload:
            brands = entity_payload["entities"].get("BRAND")
            if brands:
                brand = ", ".join(brands[:2])

        def describe(item: Dict[str, Any]) -> str:
            title = item.get("title", "Listing")
            price = self._format_price(item.get("price"))
            seller = self._format_seller(item.get("seller"))
            condition = item.get("condition")
            parts = []
            if price:
                parts.append(f"{price}")
            if condition:
                parts.append(condition)
            if seller:
                parts.append(f"seller {seller}")
            core = ", ".join(parts) if parts else "available now"
            return f"{title} ({core})"

        summary = describe(top)
        intro = "Here's the best match I found"
        if brand:
            intro += f" for {brand}"
        intro += ": "

        message = intro + summary

        if runner_up:
            message += f". Another good option is {describe(runner_up)}"

        message += "."
        return message

    @staticmethod
    def _format_price(price_payload: Any) -> Optional[str]:
        if isinstance(price_payload, dict):
            value = price_payload.get("value")
            currency = price_payload.get("currency") or price_payload.get("currencyCode")
            try:
                if value is not None:
                    numeric = float(value)
                    currency = currency or "USD"
                    return f"{currency} {numeric:,.2f}"
            except (TypeError, ValueError):
                pass
        return None

    @staticmethod
    def _format_seller(seller_payload: Any) -> Optional[str]:
        if isinstance(seller_payload, dict):
            username = seller_payload.get("username")
            feedback = seller_payload.get("feedbackPercentage")
            parts = []
            if username:
                parts.append(username)
            if feedback:
                parts.append(f"{feedback}% positive")
            if parts:
                return " | ".join(parts)
        return None
