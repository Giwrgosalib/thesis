import argparse
import pandas as pd
from sklearn.metrics import f1_score, precision_score, recall_score, accuracy_score
from custom_nlp import EBayNLP

def evaluate_model(model_path: str, dataset_path: str):
    """
    Evaluate the trained NLP model on a validation dataset.
    """
    print(f"Loading model from {model_path}...")
    nlp = EBayNLP()
    nlp._prepare_models() # Ensure models are loaded

    print(f"Loading validation dataset from {dataset_path}...")
    try:
        df_val = pd.read_csv(dataset_path)
    except FileNotFoundError:
        print(f"Error: Validation dataset not found at {dataset_path}")
        return

    # --- Intent Evaluation ---
    print("\n--- Evaluating Intent Classification ---")
    y_true_intent = df_val['intent']
    y_pred_intent = [nlp._predict_intent(query) for query in df_val['query']]
    
    intent_accuracy = accuracy_score(y_true_intent, y_pred_intent)
    print(f"Intent Accuracy: {intent_accuracy:.4f}")

    # --- Entity Evaluation ---
    print("\n--- Evaluating Entity Extraction ---")
    total_tp = 0
    total_fp = 0
    total_fn = 0

    for _, row in df_val.iterrows():
        query_text = row['query']
        if not isinstance(query_text, str):
            continue # Skip rows with no query

        # --- Get True Entities ---
        true_entities_structured = nlp._parse_entities(row['entities'])
        true_entities_set = set()
        for start, end, label in true_entities_structured:
            # Ensure offsets are valid
            if start < len(query_text) and end <= len(query_text):
                value = query_text[start:end]
                true_entities_set.add(f"{label}:{value}")

        # --- Get Predicted Entities ---
        extracted_data = nlp.extract_entities(query_text)
        pred_entities_set = set()
        for label, values in extracted_data.items():
            if label not in ["intent", "raw_query", "PRICE_RANGE"]:
                for value in values:
                    pred_entities_set.add(f"{label}:{value}")

        # --- Calculate TP, FP, FN for the current sample ---
        tp = len(true_entities_set.intersection(pred_entities_set))
        fp = len(pred_entities_set.difference(true_entities_set))
        fn = len(true_entities_set.difference(pred_entities_set))

        total_tp += tp
        total_fp += fp
        total_fn += fn

    # --- Calculate Overall Metrics ---
    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0
    recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

    print(f"Entity F1-Score (micro): {f1:.4f}")
    print(f"Entity Precision (micro): {precision:.4f}")
    print(f"Entity Recall (micro): {recall:.4f}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate the NLP model.")
    parser.add_argument('--model_path', type=str, default="models", help='Path to the directory containing the trained models.')
    parser.add_argument('--dataset_path', type=str, default="backend/data/validation.csv", help='Path to the validation dataset.')
    args = parser.parse_args()

    evaluate_model(args.model_path, args.dataset_path)
