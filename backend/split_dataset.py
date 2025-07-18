import pandas as pd
from sklearn.model_selection import train_test_split
import argparse
import os

def split_dataset(dataset_path: str, test_size: float = 0.2, random_state: int = 42):
    """
    Splits a dataset into training and validation sets.
    """
    print(f"Loading dataset from {dataset_path}...")
    try:
        df = pd.read_csv(dataset_path)
    except FileNotFoundError:
        print(f"Error: Dataset not found at {dataset_path}")
        return

    # Shuffle and split the dataset
    train_df, val_df = train_test_split(df, test_size=test_size, random_state=random_state)

    # Get the directory of the original dataset
    data_dir = os.path.dirname(dataset_path)

    # Define the output paths
    train_path = os.path.join(data_dir, "train.csv")
    validation_path = os.path.join(data_dir, "validation.csv")

    # Save the new datasets
    train_df.to_csv(train_path, index=False)
    val_df.to_csv(validation_path, index=False)

    print(f"Dataset split successfully!")
    print(f"Training set saved to: {train_path} ({len(train_df)} rows)")
    print(f"Validation set saved to: {validation_path} ({len(val_df)} rows)")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Split a dataset into training and validation sets.")
    parser.add_argument('--dataset_path', type=str, default="backend/data/dataset.csv", help='Path to the dataset to split.')
    parser.add_argument('--test_size', type=float, default=0.2, help='Proportion of the dataset to allocate to the validation set.')
    args = parser.parse_args()

    split_dataset(args.dataset_path, args.test_size)
