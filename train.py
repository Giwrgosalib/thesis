from custom_nlp import EBayNLP
import os # Import os

# Define paths
base_dataset_path = "data/dataset.csv"
feedback_log_path = "data/feedback_log.csv" # Path to the log file created by app.py

# Initialize NLP processor
nlp = EBayNLP()

# Train the model using the base dataset and the feedback log for continuous learning
# Check if feedback log exists, otherwise only train on base data
if os.path.exists(feedback_log_path):
    print(f"--- Training with base dataset and feedback log ({feedback_log_path}) ---")
    nlp.train(base_dataset_path, new_data_path=feedback_log_path)
else:
    print(f"--- Training with base dataset only (Feedback log not found at {feedback_log_path}) ---")
    nlp.train(base_dataset_path)

print("\n--- Training script finished ---")