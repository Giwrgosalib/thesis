
import sys
import os
import logging

# Add project root to path
sys.path.append(os.getcwd())

from backend_nextgen.nlp.inference import TransformerNERInference
from backend_nextgen.nlp.inference import TransformerNERInference
# from backend_nextgen.orchestrator import Orchestrator # Caused circular import

# Mock config and dependencies to avoid full startup
class MockConfig:
    def section(self, name):
        return {
            "model_path": "backend_nextgen/models/ner_model",
            "bert_model_name": "bert-base-uncased",
            "device": "cpu",
            "label_map_path": "backend_nextgen/models/ner_model/label_map.json",
            "generator_name": "gpt2",
            "response_max_tokens": 50,
            "temperature": 0.7,
            "max_context_docs": 3,
            "metrics_path": "metrics.db",
            "disagreement_threshold": 0.5,
            "batch_size": 10
        }

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def debug_flow():
    print("--- Initializing NER ---")
    try:
        # We only need NER for this test
        ner = TransformerNERInference(
            model_path="backend_nextgen/models/ner",
            device="cpu"
        )
    except Exception as e:
        print(f"Failed to load NER: {e}")
        return

    # Mock Orchestrator's _enrich_with_context method (or instantiate if possible, but mocking is safer for isolation)
    # Actually, let's just use the logic directly since we want to test the *logic*, not the whole class overhead.
    
    # Test lowercase input as per user's claim
    history = ["laptop with rtx 4060"]
    current_query = "best give ones with rtx 5050"
    
    print(f"\n--- History Query: '{history[0]}' ---")
    hist_entities = ner.extract_entities(history[0])
    print(f"Extracted: {hist_entities.get('entities')}")
    
    print(f"\n--- Current Query: '{current_query}' ---")
    curr_entities = ner.extract_entities(current_query)
    print(f"Extracted: {curr_entities.get('entities')}")
    
    # Simulate _build_intent_payload
    def build_payload(query, entity_payload):
        entities = entity_payload.get("entities", {})
        return {
            "raw_query": query,
            "entities": entities,
            "brands": entities.get("BRAND", []),
            "categories": entities.get("CATEGORY", []) or entities.get("PRODUCT_TYPE", []),
        }

    intent_payload = build_payload(current_query, curr_entities)
    print(f"\nInitial Intent Payload: {intent_payload}")

    # Simulate _enrich_with_context logic
    print("\n--- Running Context Logic ---")
    
    # Logic from orchestrator.py
    if intent_payload.get("categories") or intent_payload.get("brands"):
        print("Context logic SKIPPED because current query has categories/brands.")
    else:
        print("Context logic ACTIVE. Looking back...")
        for past_query in reversed(history):
            print(f"Processing history item: {past_query}")
            past_ent = ner.extract_entities(past_query)
            past_buckets = past_ent.get("entities", {})
            
            cats = past_buckets.get("CATEGORY", []) or past_buckets.get("PRODUCT_TYPE", [])
            if cats:
                print(f"Found Categories in history: {cats}")
                intent_payload["categories"] = cats
            
            brands = past_buckets.get("BRAND", [])
            if brands:
                print(f"Found Brands in history: {brands}")
                intent_payload["brands"] = brands
            
            if intent_payload.get("categories") or intent_payload.get("brands"):
                break
    
    print(f"\nFinal Intent Payload: {intent_payload}")

if __name__ == "__main__":
    debug_flow()
