import argparse
from custom_nlp import EBayNLP
import os

# --- Argument Parser ---
parser = argparse.ArgumentParser(description="Train the NLP model.")
parser.add_argument('--epochs', type=int, default=10, help='Number of training epochs for the NER model.')
parser.add_argument('--dataset_path', type=str, default="backend/data/dataset.csv", help='Path to the base dataset.')
args = parser.parse_args()


# Define paths
feedback_log_path = "data/dataset.csv" # Path to the log file created by app.py

# Initialize NLP processor
nlp = EBayNLP()

# Train the model using the base dataset and the feedback log for continuous learning
# Check if feedback log exists, otherwise only train on base data
if os.path.exists(feedback_log_path):
    print(f"--- Training with base dataset and feedback log ({feedback_log_path}) ---")
    nlp.train(args.dataset_path, new_data_path=feedback_log_path, iterations=args.epochs)
else:
    print(f"--- Training with base dataset only (Feedback log not found at {feedback_log_path}) ---")
    nlp.train(args.dataset_path, iterations=args.epochs)

print("\n--- Training script finished ---")
