import spacy
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
import joblib
from typing import Dict, Any, List
from spacy.training import Example
from collections import defaultdict
import os
import random

class EBayNLP:
    def __init__(self):
        # ML Models
        self.intent_pipeline = None
        self.entity_recognizer = None
        self._prepare_models()

    def _prepare_models(self):
        """Initialize or load trained models"""
        try:
            self.intent_pipeline = joblib.load('models/intent_model.pkl')
            self.entity_recognizer = spacy.load('models/entity_model')
            print("Loaded trained models.")
        except Exception as e:
            print(f"Could not load trained models: {e}. Falling back to untrained models.")
            # Fallback to untrained models
            self.intent_pipeline = Pipeline([
                ('tfidf', TfidfVectorizer()),
                ('clf', RandomForestClassifier())
            ])
            self.entity_recognizer = spacy.blank('en')
            # Add a basic NER pipe if falling back
            if not self.entity_recognizer.has_pipe('ner'):
                self.entity_recognizer.add_pipe('ner')

    def extract_entities(self, query: str) -> Dict[str, Any]:
        """ML-powered entity extraction, grouping entities by label."""
        # Predict intent first
        intent = self._predict_intent(query)

        # Process query with entity recognizer
        doc = self.entity_recognizer(query)

        # Group entities by label
        entities = defaultdict(list)
        for ent in doc.ents:
            entities[ent.label_].append(ent.text)

        # Convert defaultdict to regular dict for the final output
        extracted_data = dict(entities)

        # Add intent and raw query to the result
        extracted_data["intent"] = intent
        extracted_data["raw_query"] = query

        # Explicitly handle expected keys even if not found, returning empty lists
        expected_keys = ["BRAND", "CATEGORY", "PRODUCT_TYPE", "PRICE_RANGE"]
        for key in expected_keys:
            if key not in extracted_data:
                extracted_data[key] = []

        # Example: Consolidate CATEGORY and PRODUCT_TYPE if needed
        if "PRODUCT_TYPE" in extracted_data and "CATEGORY" not in extracted_data:
            extracted_data["CATEGORY"] = extracted_data.pop("PRODUCT_TYPE")
        elif "CATEGORY" in extracted_data and "PRODUCT_TYPE" in extracted_data:
            # Merge them or decide which one to keep
            extracted_data["CATEGORY"].extend(extracted_data.pop("PRODUCT_TYPE"))

        return extracted_data

    def _predict_intent(self, query: str) -> str:
        """Classify search intent with confidence scores"""
        if not hasattr(self.intent_pipeline, 'predict_proba'):
            print("Warning: Intent pipeline not loaded or trained correctly. Returning default intent.")
            return "unknown_intent"  # Or some default

        # Get probabilities instead of just prediction
        probabilities = self.intent_pipeline.predict_proba([query])[0]
        classes = self.intent_pipeline.classes_

        # Get top 3 predictions with their scores
        top_indices = probabilities.argsort()[-3:][::-1]
        predictions = [(classes[i], probabilities[i]) for i in top_indices]

        # Log predictions for debugging
        print(f"Query: '{query}' → Top predictions: {predictions}")

        # Return the class with the highest probability
        return classes[probabilities.argmax()]

    def train(self, dataset_path: str):
        """Train the NLP models with better error handling and data validation"""
        print(f"Loading dataset from {dataset_path}")
        try:
            df = pd.read_csv(dataset_path)
        except FileNotFoundError:
            print(f"Error: Dataset file not found at {dataset_path}")
            return
        except Exception as e:
            print(f"Error loading dataset: {e}")
            return

        # Check if required columns exist
        required_columns = ['query', 'intent', 'entities']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            print(f"Error: Dataset missing required columns: {missing_columns}")
            return

        print(f"Dataset loaded with {len(df)} rows")

        # Process entities column with better error handling
        def parse_entities(entity_value):
            if pd.isna(entity_value):
                return []

            if isinstance(entity_value, list):
                # Further validation for list elements
                validated_list = []
                for item in entity_value:
                    if isinstance(item, (tuple, list)) and len(item) == 3:
                        validated_list.append(tuple(item))  # Ensure tuple format
                return validated_list

            if isinstance(entity_value, str):
                try:
                    # Safely evaluate the string representation of a list of tuples
                    parsed = eval(entity_value)
                    if isinstance(parsed, list):
                        # Validate structure within the list
                        validated_list = []
                        for item in parsed:
                            if isinstance(item, (tuple, list)) and len(item) == 3:
                                validated_list.append(tuple(item))
                        return validated_list
                    else:
                        print(f"Warning: Parsed entity string is not a list: {entity_value}")
                        return []
                except (SyntaxError, NameError, TypeError, ValueError) as e:
                    print(f"Warning: Could not parse entity string: {entity_value}, Error: {e}. Returning empty list.")
                    return []  # Return empty list on parsing error

            # If not a recognized format, return empty list
            print(f"Warning: Unrecognized entity format: {type(entity_value)}, Value: {entity_value}")
            return []

        # Apply the robust parser
        print("Processing entities column...")
        df['entities'] = df['entities'].apply(parse_entities)

        # Train intent classifier
        print("Training intent classifier...")

        # Remove duplicates based on query
        df.drop_duplicates(subset=['query'], inplace=True)
        print(f"After removing duplicate queries: {len(df)} rows")

        # Shuffle data to avoid training bias
        df = df.sample(frac=1, random_state=42).reset_index(drop=True)

        # Show class distribution
        intent_counts = df['intent'].value_counts()
        print("Intent distribution:")
        print(intent_counts)

        # Train intent pipeline
        self.intent_pipeline = Pipeline([
            ('tfidf', TfidfVectorizer(ngram_range=(1, 2))),  # Use bi-grams
            ('clf', RandomForestClassifier(n_estimators=150, class_weight='balanced', random_state=42))  # More estimators
        ])
        self.intent_pipeline.fit(df['query'], df['intent'])
        print("Intent classifier trained.")

        # Prepare SpaCy training data for NER
        print("Preparing entity training data...")
        valid_examples = 0
        skipped_examples = 0

        # Create a blank English model for NER
        nlp = spacy.blank('en')
        if not nlp.has_pipe('ner'):
            ner = nlp.add_pipe('ner', last=True)
        else:
            ner = nlp.get_pipe('ner')

        # Add entity labels dynamically from the dataset
        all_labels = set()
        for entities_list in df['entities']:
            if isinstance(entities_list, list):
                for entity in entities_list:
                    if isinstance(entity, tuple) and len(entity) == 3:
                        _, _, label = entity
                        if isinstance(label, str) and label.strip():  # Ensure label is a non-empty string
                            all_labels.add(label.strip())

        for label in all_labels:
            ner.add_label(label)
        print(f"Added NER labels: {all_labels}")

        # Create training examples in SpaCy's Example format
        training_examples = []
        for _, row in df.iterrows():
            query = row['query']
            entities_list = row['entities']

            # Basic validation
            if not isinstance(query, str) or not query.strip():
                skipped_examples += 1
                continue
            if not isinstance(entities_list, list):
                skipped_examples += 1
                continue

            valid_entities_for_row = []
            for entity in entities_list:
                # Validate entity format and spans
                if not (isinstance(entity, tuple) and len(entity) == 3):
                    continue

                start, end, label = entity
                if not (isinstance(start, int) and isinstance(end, int) and isinstance(label, str) and label.strip()):
                    continue

                # Crucial check: Ensure span indices are valid for the query length
                if 0 <= start < end <= len(query):
                    valid_entities_for_row.append((start, end, label.strip()))

            # Only add examples that have at least one valid entity annotation
            if valid_entities_for_row:
                doc = nlp.make_doc(query)
                try:
                    example = Example.from_dict(doc, {"entities": valid_entities_for_row})
                    training_examples.append(example)
                    valid_examples += 1
                except Exception as e:
                    print(f"Skipping problematic example: '{query}', Error: {e}")
                    skipped_examples += 1
                    continue

        print(f"Prepared {valid_examples} valid training examples for NER (skipped {skipped_examples})")

        if not training_examples:
            print("Error: No valid training examples found for NER. Cannot train entity model.")
            return

        # Train the NER model
        print("Training NER model...")
        other_pipes = [pipe for pipe in nlp.pipe_names if pipe != 'ner']
        with nlp.disable_pipes(*other_pipes):
            optimizer = nlp.begin_training()
            for i in range(20):  # Number of training iterations
                losses = {}
                random.shuffle(training_examples)  # Changed from spacy.util.shuffle
                batches = spacy.util.minibatch(training_examples, size=spacy.util.compounding(4.0, 32.0, 1.001))
                for batch in batches:
                    try:
                        nlp.update(batch, drop=0.35, losses=losses, sgd=optimizer)
                    except Exception as e:
                        print(f"Error during NER update: {e}")
                        continue
                print(f"NER Iteration {i+1}/20, Loss: {losses.get('ner', 0.0)}")

        # Update the class's entity recognizer with the trained one
        self.entity_recognizer = nlp
        print("NER model trained.")

        # Save models
        print("Saving trained models...")
        model_dir = 'models'
        os.makedirs(model_dir, exist_ok=True)
        try:
            joblib.dump(self.intent_pipeline, os.path.join(model_dir, 'intent_model.pkl'))
            nlp.to_disk(os.path.join(model_dir, 'entity_model'))
            print("Models saved successfully.")
        except Exception as e:
            print(f"Error saving models: {e}")

        print("Training completed.")

        # Test prediction on a few samples after training
        print("\nTesting predictions on sample queries:")
        test_queries = [
            "iPhone 15 Pro under $1000",
            "used Nike running shoes size 10",
            "Samsung TV 4K 65 inch",
            "cheap wireless headphones",
            "Gaming laptop like new"
        ]
        for query in test_queries:
            print(f"\n--- Testing Query: '{query}' ---")
            try:
                extracted = self.extract_entities(query)
                print("Extracted Entities:")
                for key, value in extracted.items():
                    if value:
                        print(f"  {key}: {value}")
            except Exception as e:
                print(f"Error during test prediction for '{query}': {e}")
