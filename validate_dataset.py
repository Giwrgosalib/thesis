import pandas as pd
import sys
import json

def inspect_dataset(file_path):
    """
    Inspect a dataset CSV file to identify potential issues
    """
    print(f"Inspecting dataset: {file_path}")
    
    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        print(f"Error loading CSV file: {e}")
        return
    
    print(f"\nDataset shape: {df.shape}")
    print(f"Columns: {df.columns.tolist()}")
    
    # Check for required columns
    required_columns = ['query', 'intent', 'entities']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        print(f"\nWARNING: Missing required columns: {missing_columns}")
    
    # Sample data
    print("\nSample data (first 5 rows):")
    print(df.head().to_string())
    
    # Check entities column format
    if 'entities' in df.columns:
        print("\nEntities column analysis:")
        
        # Check for null values
        null_count = df['entities'].isna().sum()
        print(f"- Null values: {null_count} ({null_count/len(df)*100:.2f}%)")
        
        # Check data types
        type_counts = df['entities'].apply(type).value_counts()
        print(f"- Data types: {type_counts.to_dict()}")
        
        # Sample of entity formats
        print("\nSample entity formats:")
        non_null_entities = df['entities'].dropna().reset_index(drop=True)
        if len(non_null_entities) > 0:
            for i in range(min(5, len(non_null_entities))):
                print(f"Row {i}: {repr(non_null_entities[i])}")
        
        # Try parsing entities
        print("\nAttempting to parse entities:")
        success = 0
        failures = []
        
        for i, entity_value in enumerate(df['entities']):
            if pd.isna(entity_value):
                continue
                
            try:
                if isinstance(entity_value, str):
                    parsed = eval(entity_value)
                    success += 1
                else:
                    success += 1
            except Exception as e:
                failures.append((i, entity_value, str(e)))
                if len(failures) <= 5:  # Show only first 5 failures
                    print(f"Row {i} parse error: {e}, Value: {repr(entity_value)}")
        
        print(f"\nEntity parsing results: {success} successes, {len(failures)} failures")
        
        if failures:
            print("\nSuggested entity format fixes:")
            print("1. Ensure entities are in the format: [(start, end, 'LABEL')]")
            print("2. For multiple entities: [(0, 5, 'BRAND'), (10, 15, 'CATEGORY')]")
            print("3. Empty entities should be represented as: []")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        inspect_dataset(sys.argv[1])
    else:
        print("Usage: python validate_dataset.py path/to/dataset.csv")