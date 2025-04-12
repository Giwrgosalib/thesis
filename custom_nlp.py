import spacy
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
import joblib
from typing import Dict, Any
from spacy.training import Example

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
        except:
            # Fallback to untrained models
            self.intent_pipeline = Pipeline([
                ('tfidf', TfidfVectorizer()),
                ('clf', RandomForestClassifier())
            ])
            self.entity_recognizer = spacy.blank('en')

    def extract_entities(self, query: str) -> Dict[str, Any]:
        """ML-powered entity extraction"""
        doc = self.entity_recognizer(query)
        return {
            "intent": self._predict_intent(query),
            "brands": [ent.text for ent in doc.ents if ent.label_ == "BRAND"],
            "categories": [ent.text for ent in doc.ents if ent.label_ == "CATEGORY"],
            "price_range": self._extract_price(query),
            "raw_query": query
        }

    def _predict_intent(self, query: str) -> str:
        """Classify search intent"""
        return self.intent_pipeline.predict([query])[0]

    def _extract_price(self, query: str) -> str:
        """Price range extraction with ML"""
        # This would use a dedicated price parser model in production
        price_ents = [ent for ent in self.entity_recognizer(query).ents 
                     if ent.label_ == "MONEY"]
        return self._price_to_range(price_ents[0].text) if price_ents else None

    def train(self, dataset_path: str):
        """Train the NLP models with better error handling and data validation"""
        print(f"Loading dataset from {dataset_path}")
        df = pd.read_csv(dataset_path)
        
        # Check if required columns exist
        required_columns = ['query', 'intent', 'entities']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Dataset missing required columns: {missing_columns}")
        
        print(f"Dataset loaded with {len(df)} rows")
        
        # Process entities column with better error handling
        def parse_entities(entity_value):
            if pd.isna(entity_value):
                return []
            
            if isinstance(entity_value, list):
                return entity_value
                
            if isinstance(entity_value, str):
                try:
                    # Try to safely evaluate the string as a Python expression
                    # This handles formats like "[(0, 5, 'BRAND')]"
                    return eval(entity_value)
                except (SyntaxError, ValueError) as e:
                    print(f"Error parsing entity: {entity_value}, Error: {e}")
                    
                    # Try alternative formats
                    # For comma-separated format like "0,5,BRAND|6,10,CATEGORY"
                    try:
                        entities = []
                        for entity_str in entity_value.split('|'):
                            parts = entity_str.strip().split(',')
                            if len(parts) == 3:
                                start, end, label = int(parts[0]), int(parts[1]), parts[2]
                                entities.append((start, end, label))
                        return entities
                    except Exception:
                        # If all parsing attempts fail, return empty list
                        return []
            
            return []
        
        # Apply the robust parser
        print("Processing entities column...")
        df['entities'] = df['entities'].apply(parse_entities)
        
        # Train intent classifier
        print("Training intent classifier...")
        self.intent_pipeline.fit(df['query'], df['intent'])
        
        # Prepare SpaCy training data
        print("Preparing entity training data...")
        valid_examples = 0
        skipped_examples = 0
        
        # Create a blank model
        nlp = spacy.blank('en')
        ner = nlp.add_pipe('ner')
        
        # Add entity labels from the dataset
        for _, row in df.iterrows():
            if not isinstance(row['query'], str):
                continue
                
            for entity in row['entities']:
                if isinstance(entity, tuple) and len(entity) == 3:
                    _, _, label = entity
                    if isinstance(label, str):
                        ner.add_label(label)
        
        # Create training examples in the new format
        training_examples = []
        for _, row in df.iterrows():
            query = row['query']
            if not isinstance(query, str):
                skipped_examples += 1
                continue
                
            entities = []
            for entity in row['entities']:
                # Validate entity format and spans
                if not isinstance(entity, tuple) or len(entity) != 3:
                    continue
                    
                start, end, label = entity
                if not (isinstance(start, int) and isinstance(end, int) and isinstance(label, str)):
                    continue
                    
                if 0 <= start < end <= len(query):
                    entities.append((start, end, label))
            
            if entities:  # Only add examples with valid entities
                doc = nlp.make_doc(query)
                try:
                    # Create entity spans
                    spans = []
                    for start, end, label in entities:
                        span = doc.char_span(start, end, label=label)
                        if span is not None:  # Only add valid spans
                            spans.append(span)
                    
                    # Create the reference doc with entities
                    reference = {"entities": spans}
                    
                    # Create an Example object
                    example = Example.from_dict(doc, reference)
                    training_examples.append(example)
                    valid_examples += 1
                except Exception as e:
                    print(f"Skipping problematic example: {query}, Error: {e}")
                    continue
        
        print(f"Prepared {valid_examples} valid training examples (skipped {skipped_examples})")
        
        if not training_examples:
            raise ValueError("No valid training examples found in the dataset")
        
        # Configure training
        optimizer = nlp.begin_training()
        for _ in range(10):  # 10 iterations
            losses = {}
            # Use minibatch with Example objects
            batches = spacy.util.minibatch(training_examples, size=8)
            for batch in batches:
                nlp.update(batch, drop=0.5, losses=losses, sgd=optimizer)
            print(f"Loss: {losses}")
        
        # Update the models
        self.intent_pipeline = self.intent_pipeline
        self.entity_recognizer = nlp
        
        # Save models
        print("Saving trained models...")
        import os
        os.makedirs('models', exist_ok=True)
        joblib.dump(self.intent_pipeline, 'models/intent_model.pkl')
        nlp.to_disk('models/entity_model')
        
        print("Training completed successfully")
        
    def _price_to_range(self, price_text):
        """Convert price text to a standardized range format"""
        # This is a placeholder - in a real implementation, 
        # this would parse various price formats
        return price_text
