import pandas as pd
import sys
import json
import spacy  # Added import
from spacy.training import offsets_to_biluo_tags  # Added import
import ast  # Use ast.literal_eval instead of eval for safety

# Load a blank English model for tokenization
try:
    nlp = spacy.blank('en')
    print("Loaded blank SpaCy English model for tokenization.")
except OSError:
    print("Error: Could not load blank SpaCy English model.")
    print("Please ensure SpaCy is installed ('pip install spacy') and download the English model if needed ('python -m spacy download en_core_web_sm').")
    nlp = None  # Set nlp to None if loading fails

def inspect_dataset(file_path):
    """
    Inspect a dataset CSV file to identify potential issues, including entity alignment.
    """
    if nlp is None:
        print("Cannot perform alignment checks because SpaCy model failed to load.")
        return  # Exit if SpaCy isn't available

    print(f"Inspecting dataset: {file_path}")

    try:
        # Try detecting encoding issues
        try:
            df = pd.read_csv(file_path)
        except UnicodeDecodeError:
            print("Warning: UTF-8 decoding failed. Trying 'latin1' encoding.")
            df = pd.read_csv(file_path, encoding='latin1')
        except Exception as e:
            raise e  # Re-raise other read errors
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
        # Don't exit, but alignment checks might fail if 'query' or 'entities' are missing

    # Sample data
    print("\nSample data (first 5 rows):")
    print(df.head().to_string())

    # Check entities column format
    if 'entities' in df.columns and 'query' in df.columns:
        print("\nEntities column analysis:")

        # Check for null values
        null_entity_count = df['entities'].isna().sum()
        print(f"- Null entity values: {null_entity_count} ({null_entity_count/len(df)*100:.2f}%)")
        null_query_count = df['query'].isna().sum()
        if null_query_count > 0:
            print(f"- WARNING: Null query values found: {null_query_count}")

        # Check data types
        type_counts = df['entities'].apply(type).value_counts()
        print(f"- Entity data types: {type_counts.to_dict()}")

        # Sample of entity formats
        print("\nSample entity formats:")
        non_null_entities = df['entities'].dropna().reset_index(drop=True)
        if len(non_null_entities) > 0:
            for i in range(min(5, len(non_null_entities))):
                print(f"Row {i} (original index may vary): {repr(non_null_entities[i])}")

        # Try parsing entities and check alignment
        print("\nAttempting to parse entities and check alignment:")
        parse_success = 0
        parse_failures = []
        alignment_issues = []
        valid_entity_struct_count = 0

        for i, row in df.iterrows():
            entity_value = row['entities']
            query_text = row['query']
            parsed_entities = None

            if pd.isna(entity_value) or entity_value == '[]':  # Treat empty string '[]' as valid empty list
                parse_success += 1
                valid_entity_struct_count += 1
                continue  # Skip alignment check for empty entities

            if pd.isna(query_text) or not isinstance(query_text, str):
                # Cannot check alignment without valid query text
                continue

            # --- Parsing Logic ---
            try:
                if isinstance(entity_value, str):
                    # Use ast.literal_eval for safer evaluation than eval
                    parsed = ast.literal_eval(entity_value)
                    if isinstance(parsed, list):
                        parsed_entities = parsed
                        parse_success += 1
                    else:
                        raise TypeError("Parsed entity string is not a list")
                elif isinstance(entity_value, list):  # Handle cases where it might already be a list
                    parsed_entities = entity_value
                    parse_success += 1
                else:
                    raise TypeError(f"Unexpected entity type: {type(entity_value)}")

            except Exception as e:
                parse_failures.append((i, entity_value, str(e)))
                if len(parse_failures) <= 5:
                    print(f"Row {i} parse error: {e}, Value: {repr(entity_value)}")
                continue  # Skip alignment check if parsing failed

            # --- Structure Validation ---
            is_valid_structure = True
            if parsed_entities is not None:
                if not isinstance(parsed_entities, list):
                    is_valid_structure = False
                else:
                    for item in parsed_entities:
                        if not (isinstance(item, (tuple, list)) and len(item) == 3 and
                                isinstance(item[0], int) and isinstance(item[1], int) and
                                isinstance(item[2], str)):
                            is_valid_structure = False
                            break
                if is_valid_structure:
                    valid_entity_struct_count += 1
                else:
                    if len(parse_failures) < 5 and (i, entity_value, "Invalid entity structure") not in parse_failures:
                        print(f"Row {i} structure error: Expected list of (int, int, str) tuples/lists. Value: {repr(parsed_entities)}")
                        parse_failures.append((i, entity_value, "Invalid entity structure"))
                    continue  # Skip alignment if structure is wrong

            # --- Alignment Check ---
            if parsed_entities and is_valid_structure:  # Only check alignment if parsing and structure validation succeeded
                try:
                    doc = nlp.make_doc(query_text)
                    tags = offsets_to_biluo_tags(doc, parsed_entities)
                    if '-' in tags:
                        # Find which specific entity caused the misalignment
                        problem_indices = [idx for idx, tag in enumerate(tags) if tag == '-']
                        # Note: BILUO tags map to tokens, not directly back to original entity list easily.
                        # We report the row, query, and entities. Manual inspection is needed.
                        alignment_issues.append((i, query_text, parsed_entities))
                        if len(alignment_issues) <= 10:  # Show first 10 alignment issues
                            print(f"Row {i} alignment issue: Query='{query_text}', Entities={parsed_entities}, Tags={tags}")

                except ValueError as e:
                    # Handle potential errors during BILUO tag generation (e.g., overlapping spans)
                    print(f"Row {i} alignment check error (ValueError): {e}. Query='{query_text}', Entities={parsed_entities}")
                    alignment_issues.append((i, query_text, parsed_entities))  # Still flag as an issue
                except Exception as e:
                    print(f"Row {i} alignment check error (Unexpected): {e}. Query='{query_text}', Entities={parsed_entities}")
                    alignment_issues.append((i, query_text, parsed_entities))  # Still flag as an issue

        print(f"\nEntity parsing results: {parse_success}/{len(df)} successes, {len(parse_failures)} failures.")
        print(f"Valid entity structure count: {valid_entity_struct_count}/{len(df)}.")  # Count rows with correctly structured entities list

        if parse_failures:
            print("\n--- PARSING FAILURES (Examples) ---")
            for idx, val, err in parse_failures[:5]:
                print(f"Row {idx}: Error='{err}', Value={repr(val)}")
            print("------------------------------------")
            print("Suggestions for parsing failures:")
            print("1. Ensure entity strings are valid Python list representations: e.g., \"[(0, 5, 'BRAND')]\"")
            print("2. Check for unescaped quotes within labels or incorrect syntax.")
            print("3. Use '[]' for rows with no entities.")

        print(f"\nAlignment check results: {len(alignment_issues)} rows with potential alignment issues found.")
        if alignment_issues:
            print("\n--- ALIGNMENT ISSUES DETECTED (Examples) ---")
            print("Alignment issues mean the character offsets might not match SpaCy's token boundaries.")
            print("This can happen with punctuation, extra spaces, or incorrect offsets.")
            print("SpaCy will ignore misaligned entities during training.")
            for idx, q, e in alignment_issues[:10]:
                print(f"Row {idx}: Query='{q}', Entities={e}")
            print("------------------------------------------")
            print("Suggestions for alignment issues:")
            print("1. Manually review the offsets for the reported rows in your CSV.")
            print("2. Ensure start/end offsets exactly match the entity text in the query.")
            print("3. Be mindful of spaces and punctuation around entities.")
            print("4. Use SpaCy's displaCy visualizer or print tokens/chars to debug offsets.")

    else:
        print("\nSkipping entity analysis because 'query' or 'entities' column is missing.")

if __name__ == "__main__":
    # Prepend 'data/' if the path doesn't seem absolute or relative from project root
    default_path = "data/dataset.csv"  # Default path relative to backend folder
    file_arg = default_path
    if len(sys.argv) > 1:
        file_arg = sys.argv[1]
        print(f"Using provided dataset path: {file_arg}")
    else:
        print(f"No dataset path provided. Using default: {default_path}")

    inspect_dataset(file_arg)