import spacy
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
import joblib
from typing import Dict, Any, List, Optional
from spacy.training import Example
from collections import defaultdict
import os
import random
from spacy.util import minibatch, compounding
import re

class EBayNLP:
    def __init__(self):
        # ML Models
        self.intent_pipeline = None
        self.entity_recognizer = None
        self._prepare_models()

    def _prepare_models(self):
        """Initialize or load trained models"""
        self.intent_model_path = os.path.join('models', 'intent_model.pkl')
        self.entity_model_path = os.path.join('models', 'entity_model')
        os.makedirs('models', exist_ok=True)

        try:
            self.intent_pipeline = joblib.load(self.intent_model_path)
            print("Loaded trained intent model.")
        except Exception as e:
            print(f"Could not load trained intent model: {e}. Initializing new pipeline.")
            self.intent_pipeline = Pipeline([
                ('tfidf', TfidfVectorizer(ngram_range=(1, 2))),
                ('clf', RandomForestClassifier(n_estimators=150, class_weight='balanced', random_state=42))
            ])

        try:
            self.entity_recognizer = spacy.load(self.entity_model_path)
            print("Loaded trained entity model.")
        except Exception as e:
            print(f"Could not load trained entity model: {e}. Initializing blank model.")
            self.entity_recognizer = spacy.blank('en')
            if not self.entity_recognizer.has_pipe('ner'):
                self.entity_recognizer.add_pipe('ner')

    def extract_entities(self, query: str) -> Dict[str, Any]:
        """
        ML-powered entity extraction, grouping entities by label and including offsets.
        Returns a dictionary including intent, raw_query, grouped entities (text only),
        and raw_entities (list of tuples with start, end, label).
        """
        intent = self._predict_intent(query)
        doc = self.entity_recognizer(query)

        # Group entities by label (text only)
        grouped_entities = defaultdict(list)
        # Store raw entities with offsets
        raw_entities_with_offsets = []

        for ent in doc.ents:
            grouped_entities[ent.label_].append(ent.text)
            raw_entities_with_offsets.append((ent.start_char, ent.end_char, ent.label_))

        # Convert defaultdict to regular dict for the final output
        extracted_data = dict(grouped_entities)

        # Add intent, raw query, and raw entities with offsets
        extracted_data["intent"] = intent
        extracted_data["raw_query"] = query
        extracted_data["raw_entities"] = raw_entities_with_offsets

        # Explicitly handle expected keys even if not found, returning empty lists
        expected_keys = ["BRAND", "CATEGORY", "PRODUCT_TYPE", "PRICE_RANGE"]
        for key in expected_keys:
            if key not in extracted_data:
                extracted_data[key] = []

        # Example: Consolidate CATEGORY and PRODUCT_TYPE if needed (adjust if necessary)
        if "PRODUCT_TYPE" in extracted_data and "CATEGORY" not in extracted_data:
            extracted_data["CATEGORY"] = extracted_data.pop("PRODUCT_TYPE")
        elif "CATEGORY" in extracted_data and "PRODUCT_TYPE" in extracted_data:
            extracted_data["CATEGORY"].extend(extracted_data.pop("PRODUCT_TYPE"))

        # --- Price Range Extraction ---
        price_range = []
        # Match patterns like "under 500", "below $300", "less than 1000", "under $500", etc.
        match = re.search(r'(under|below|less than)\s*\$?(\d+)', query, re.IGNORECASE)
        if match:
            price = int(match.group(2))
            price_range = [0, price]
        # Match patterns like "over 500", "above $300", "more than 1000", etc.
        match = re.search(r'(over|above|more than)\s*\$?(\d+)', query, re.IGNORECASE)
        if match:
            price = int(match.group(2))
            price_range = [price, None]
        # Match patterns like "between 300 and 500"
        match = re.search(r'between\s*\$?(\d+)\s*and\s*\$?(\d+)', query, re.IGNORECASE)
        if match:
            price_range = [int(match.group(1)), int(match.group(2))]

        extracted_data["PRICE_RANGE"] = price_range if price_range else []

        return extracted_data

    def _predict_intent(self, query: str) -> str:
        """Classify search intent with confidence scores"""
        if not hasattr(self.intent_pipeline, 'classes_') or self.intent_pipeline.classes_ is None:
            print("Warning: Intent pipeline not fitted. Returning default intent.")
            return "unknown_intent"
        if not hasattr(self.intent_pipeline, 'predict_proba'):
            print("Warning: Intent pipeline does not support predict_proba. Returning simple prediction.")
            try:
                return self.intent_pipeline.predict([query])[0]
            except Exception as e:
                print(f"Error during intent prediction: {e}. Returning default intent.")
                return "unknown_intent"
        try:
            probabilities = self.intent_pipeline.predict_proba([query])[0]
            classes = self.intent_pipeline.classes_
            top_indices = probabilities.argsort()[-3:][::-1]
            predictions = [(classes[i], probabilities[i]) for i in top_indices]
            print(f"Query: '{query}' -> Top predictions: {predictions}")
            return classes[probabilities.argmax()]
        except Exception as e:
            print(f"Error during intent probability prediction: {e}. Returning default intent.")
            return "unknown_intent"

    def train(self, dataset_path: str, new_data_path: Optional[str] = None, iterations: int = 20):
        """
        Train or update the NLP models using a base dataset and optional new data.

        Args:
            dataset_path: Path to the main CSV dataset file.
            new_data_path: Optional path to a CSV file containing new data for continuous learning.
                           Must have the same columns ('query', 'intent', 'entities').
            iterations: Number of training iterations for the NER model.
        """
        print(f"Starting training process...")
        print(f"Loading base dataset from {dataset_path}")
        try:
            df_base = pd.read_csv(dataset_path)
        except FileNotFoundError:
            print(f"Error: Base dataset file not found at {dataset_path}")
            return
        except Exception as e:
            print(f"Error loading base dataset: {e}")
            return

        df_new = None
        if new_data_path:
            print(f"Loading new data from {new_data_path}")
            try:
                df_new = pd.read_csv(new_data_path)
            except FileNotFoundError:
                print(f"Warning: New data file not found at {new_data_path}. Proceeding without it.")
            except Exception as e:
                print(f"Warning: Error loading new data: {e}. Proceeding without it.")

        if df_new is not None and not df_new.empty:
            print(f"Combining base dataset ({len(df_base)} rows) with new data ({len(df_new)} rows)")
            df = pd.concat([df_base, df_new], ignore_index=True)
        else:
            df = df_base

        required_columns = ['query', 'intent', 'entities']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            print(f"Error: Combined dataset missing required columns: {missing_columns}")
            return

        print(f"Total data for training: {len(df)} rows")
        print("Processing entities column...")
        df['entities'] = df['entities'].apply(self._parse_entities)
        df.drop_duplicates(subset=['query'], keep='last', inplace=True)
        print(f"After removing duplicate queries: {len(df)} rows")
        df = df.sample(frac=1, random_state=42).reset_index(drop=True)

        print("Training/Retraining intent classifier...")
        intent_counts = df['intent'].value_counts()
        print("Intent distribution in combined data:")
        print(intent_counts)
        self.intent_pipeline = Pipeline([
            ('tfidf', TfidfVectorizer(ngram_range=(1, 2))),
            ('clf', RandomForestClassifier(n_estimators=150, class_weight='balanced', random_state=42))
        ])
        try:
            self.intent_pipeline.fit(df['query'], df['intent'])
            print("Intent classifier trained/retrained.")
        except Exception as e:
            print(f"Error training intent classifier: {e}")
            return

        print("Preparing entity training data...")
        nlp = self.entity_recognizer
        is_update = nlp.has_pipe('ner') and any(nlp.get_pipe('ner').labels)
        if not nlp.has_pipe('ner'):
            ner = nlp.add_pipe('ner', last=True)
            print("Added new NER pipe.")
        else:
            ner = nlp.get_pipe('ner')
            print("Using existing NER pipe.")

        existing_labels = set(ner.labels)
        current_labels = set()
        for entities_list in df['entities']:
            if isinstance(entities_list, list):
                for entity in entities_list:
                    if isinstance(entity, tuple) and len(entity) == 3:
                        _, _, label = entity
                        if isinstance(label, str) and label.strip():
                            current_labels.add(label.strip())

        new_labels = current_labels - existing_labels
        if new_labels:
            for label in new_labels:
                ner.add_label(label)
            print(f"Added new NER labels: {new_labels}")
        print(f"Total NER labels: {ner.labels}")

        training_examples = []
        valid_examples = 0
        skipped_examples = 0
        for _, row in df.iterrows():
            query = row['query']
            entities_list = row['entities']
            if not isinstance(query, str) or not query.strip(): skipped_examples += 1; continue
            if not isinstance(entities_list, list): skipped_examples += 1; continue
            valid_entities_for_row = []
            for entity in entities_list:
                if not (isinstance(entity, tuple) and len(entity) == 3): continue
                start, end, label = entity
                if not (isinstance(start, int) and isinstance(end, int) and isinstance(label, str) and label.strip()): continue
                if 0 <= start < end <= len(query):
                    clean_label = label.strip()
                    if clean_label in ner.labels:
                        valid_entities_for_row.append((start, end, clean_label))
                    else:
                        print(f"Warning: Label '{clean_label}' not in NER pipe labels. Skipping entity in query: '{query}'")
            doc = nlp.make_doc(query)
            try:
                example = Example.from_dict(doc, {"entities": valid_entities_for_row})
                training_examples.append(example)
                valid_examples += 1
            except Exception as e:
                print(f"Skipping problematic example creation: '{query}', Entities: {valid_entities_for_row}, Error: {e}")
                skipped_examples += 1
                continue

        print(f"Prepared {valid_examples} valid training examples for NER (skipped {skipped_examples})")

        if not training_examples:
            print("Warning: No valid training examples found for NER. Skipping NER training.")
        else:
            print("Training/Updating NER model...")
            other_pipes = [pipe for pipe in nlp.pipe_names if pipe != 'ner']
            with nlp.disable_pipes(*other_pipes):
                if is_update:
                    print("Resuming NER training...")
                    optimizer = nlp.resume_training()
                else:
                    print("Beginning NER training from scratch...")
                    optimizer = nlp.begin_training()
                for i in range(iterations):
                    losses = {}
                    random.shuffle(training_examples)
                    batches = minibatch(training_examples, size=compounding(4.0, 32.0, 1.001))
                    for batch in batches:
                        try:
                            nlp.update(batch, drop=0.35, losses=losses, sgd=optimizer)
                        except Exception as e:
                            print(f"Error during NER update batch: {e}")
                            continue
                    print(f"NER Iteration {i+1}/{iterations}, Loss: {losses.get('ner', 0.0)}")

            self.entity_recognizer = nlp
            print("NER model trained/updated.")

        print("Saving trained models...")
        try:
            joblib.dump(self.intent_pipeline, self.intent_model_path)
            self.entity_recognizer.to_disk(self.entity_model_path)
            print("Models saved successfully.")
        except Exception as e:
            print(f"Error saving models: {e}")

        print("Training process completed.")

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

    def _parse_entities(self, entity_value):
        """Helper function to parse the entity string safely."""
        if pd.isna(entity_value): return []
        if isinstance(entity_value, list):
            return [tuple(item) for item in entity_value if isinstance(item, (tuple, list)) and len(item) == 3]
        if isinstance(entity_value, str):
            try:
                parsed = eval(entity_value)
                if isinstance(parsed, list):
                    return [tuple(item) for item in parsed if isinstance(item, (tuple, list)) and len(item) == 3]
                else:
                    print(f"Warning: Parsed entity string is not a list: {entity_value}")
                    return []
            except Exception as e:
                return []
        return []
