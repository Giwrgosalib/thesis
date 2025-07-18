
import spacy
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
import joblib
from typing import Dict, Any, List, Optional
# from spacy.training import Example # No longer needed for NER
from collections import defaultdict
import os
import random
# from spacy.util import minibatch, compounding # No longer needed for NER
import re
import ast # Use ast.literal_eval for safety

# --- PyTorch Imports for From-Scratch NER Model ---
import torch
import torch.nn as nn
import torch.optim as optim

# --- From-Scratch BiLSTM-CRF Model Definition ---
class BiLSTM_CRF(nn.Module):
    def __init__(self, vocab_size, tag_to_ix, embedding_dim, hidden_dim):
        super(BiLSTM_CRF, self).__init__()
        self.embedding_dim = embedding_dim
        self.hidden_dim = hidden_dim
        self.vocab_size = vocab_size
        self.tag_to_ix = tag_to_ix
        self.tagset_size = len(tag_to_ix)

        self.word_embeds = nn.Embedding(vocab_size, embedding_dim)
        self.lstm = nn.LSTM(embedding_dim, hidden_dim // 2,
                            num_layers=1, bidirectional=True)
        self.hidden2tag = nn.Linear(hidden_dim, self.tagset_size)

        self.transitions = nn.Parameter(
            torch.randn(self.tagset_size, self.tagset_size))
        self.transitions.data[tag_to_ix["START_TAG"], :] = -10000
        self.transitions.data[:, tag_to_ix["STOP_TAG"]] = -10000

    def _get_lstm_features(self, sentence):
        embeds = self.word_embeds(sentence).view(len(sentence), 1, -1)
        lstm_out, _ = self.lstm(embeds)
        lstm_out = lstm_out.view(len(sentence), self.hidden_dim)
        lstm_feats = self.hidden2tag(lstm_out)
        return lstm_feats

    def _forward_alg(self, feats):
        device = feats.device
        init_alphas = torch.full((1, self.tagset_size), -10000., device=device)
        init_alphas[0][self.tag_to_ix["START_TAG"]] = 0.
        forward_var = init_alphas
        for feat in feats:
            alphas_t = []
            for next_tag in range(self.tagset_size):
                emit_score = feat[next_tag].view(1, -1).expand(1, self.tagset_size)
                trans_score = self.transitions[next_tag].view(1, -1)
                next_tag_var = forward_var + trans_score + emit_score
                alphas_t.append(torch.logsumexp(next_tag_var, dim=1).view(1))
            forward_var = torch.cat(alphas_t).view(1, -1)
        terminal_var = forward_var + self.transitions[self.tag_to_ix["STOP_TAG"]]
        alpha = torch.logsumexp(terminal_var, dim=1)
        return alpha

    def _score_sentence(self, feats, tags):
        device = feats.device
        score = torch.zeros(1, device=device)
        tags = torch.cat([torch.tensor([self.tag_to_ix["START_TAG"]], dtype=torch.long, device=device), tags])
        for i, feat in enumerate(feats):
            score = score + \
                self.transitions[tags[i + 1], tags[i]] + feat[tags[i + 1]]
        score = score + self.transitions[self.tag_to_ix["STOP_TAG"], tags[-1]]
        return score

    def neg_log_likelihood(self, sentence, tags):
        feats = self._get_lstm_features(sentence)
        forward_score = self._forward_alg(feats)
        gold_score = self._score_sentence(feats, tags)
        return forward_score - gold_score

    def _viterbi_decode(self, feats):
        device = feats.device
        backpointers = []
        init_vvars = torch.full((1, self.tagset_size), -10000., device=device)
        init_vvars[0][self.tag_to_ix["START_TAG"]] = 0
        forward_var = init_vvars
        for feat in feats:
            bptrs_t = []
            viterbivars_t = []
            for next_tag in range(self.tagset_size):
                next_tag_var = forward_var + self.transitions[next_tag]
                best_tag_id = torch.argmax(next_tag_var)
                bptrs_t.append(best_tag_id)
                viterbivars_t.append(next_tag_var[0][best_tag_id].view(1))
            forward_var = (torch.cat(viterbivars_t) + feat).view(1, -1)
            backpointers.append(bptrs_t)
        terminal_var = forward_var + self.transitions[self.tag_to_ix["STOP_TAG"]]
        best_tag_id = torch.argmax(terminal_var)
        path_score = terminal_var[0][best_tag_id]
        best_path = [best_tag_id]
        for bptrs_t in reversed(backpointers):
            best_tag_id = bptrs_t[best_tag_id]
            best_path.append(best_tag_id)
        start = best_path.pop()
        assert start == self.tag_to_ix["START_TAG"]
        best_path.reverse()
        return path_score, best_path

    def forward(self, sentence):
        lstm_feats = self._get_lstm_features(sentence)
        score, tag_seq = self._viterbi_decode(lstm_feats)
        return score, tag_seq

# Helper function for PyTorch model
def prepare_sequence(seq, to_ix):
    idxs = [to_ix.get(w, 0) for w in seq] # Use .get(w, 0) to handle unknown words
    return torch.tensor(idxs, dtype=torch.long)

class EBayNLP:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"Using device: {self.device}")
        # ML Models
        self.intent_pipeline = None
        # self.entity_recognizer = None # Old spaCy model
        
        # --- New From-Scratch NER Model Components ---
        self.ner_model = None
        self.word_to_ix = {"[UNK]": 0} # Add UNK token for unknown words
        self.tag_to_ix = {}
        self.ix_to_tag = {}
        # -------------------------------------------

        self._prepare_models()

    def _prepare_models(self):
        """Initialize or load trained models"""
        self.intent_model_path = os.path.join('models', 'intent_model.pkl')
        # self.entity_model_path = os.path.join('models', 'entity_model') # Old spaCy path
        
        # --- New PyTorch model path ---
        self.ner_model_path = os.path.join('models', 'ner_model.pth')
        self.ner_vocab_path = os.path.join('models', 'ner_vocab.pkl')
        # --------------------------------

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

        # --- Load From-Scratch NER Model ---
        if os.path.exists(self.ner_model_path) and os.path.exists(self.ner_vocab_path):
            print("Loading from-scratch NER model...")
            try:
                # Load vocab and tag mappings
                vocab_data = joblib.load(self.ner_vocab_path)
                self.word_to_ix = vocab_data['word_to_ix']
                self.tag_to_ix = vocab_data['tag_to_ix']
                self.ix_to_tag = {v: k for k, v in self.tag_to_ix.items()}

                # Initialize model with saved dimensions
                EMBEDDING_DIM = 128 # Should be saved/loaded as well, but hardcoded for now
                HIDDEN_DIM = 256
                self.ner_model = BiLSTM_CRF(len(self.word_to_ix), self.tag_to_ix, EMBEDDING_DIM, HIDDEN_DIM)
                
                # Load the trained weights
                self.ner_model.load_state_dict(torch.load(self.ner_model_path, map_location=self.device))
                self.ner_model.to(self.device)
                print("Loaded trained from-scratch NER model.")
            except Exception as e:
                print(f"Error loading from-scratch NER model: {e}. Model will be retrained.")
                self.ner_model = None # Ensure model is None if loading fails
        else:
            print("No trained from-scratch NER model found. Model will be initialized during training.")
        # -------------------------------------

        """ --- Old spaCy Model Loading ---
        try:
            self.entity_recognizer = spacy.load(self.entity_model_path)
            print("Loaded trained entity model.")
        except Exception as e:
            print(f"Could not load trained entity model: {e}. Initializing blank model.")
            self.entity_recognizer = spacy.blank('en')
            if not self.entity_recognizer.has_pipe('ner'):
                self.entity_recognizer.add_pipe('ner')
        """

    def extract_entities(self, query: str) -> Dict[str, Any]:
        """
        ML-powered entity extraction, where the NER model handles all entities
        including price ranges.
        """
        intent = self._predict_intent(query)
        
        # --- NER Inference to get text-based entities ---
        grouped_entities = defaultdict(list)
        if self.ner_model:
            with torch.no_grad():
                query_tokens = re.findall(r'\w+|[.,!?;]', query)
                sentence_in = prepare_sequence(query_tokens, self.word_to_ix).to(self.device)
                
                score, tag_indices = self.ner_model(sentence_in)
                predicted_tags = [self.ix_to_tag.get(ix.item(), 'O') for ix in tag_indices]

                current_entity_text = []
                current_entity_label = ""
                for token, tag in zip(query_tokens, predicted_tags):
                    if tag.startswith("B-"):
                        if current_entity_text:
                            grouped_entities[current_entity_label].append(" ".join(current_entity_text))
                        current_entity_text = [token]
                        current_entity_label = tag[2:]
                    elif tag.startswith("I-"):
                        if current_entity_label == tag[2:]:
                            current_entity_text.append(token)
                        else:
                            if current_entity_text:
                                grouped_entities[current_entity_label].append(" ".join(current_entity_text))
                            current_entity_text = []
                            current_entity_label = ""
                    else:
                        if current_entity_text:
                            grouped_entities[current_entity_label].append(" ".join(current_entity_text))
                        current_entity_text = []
                        current_entity_label = ""
                
                if current_entity_text:
                    grouped_entities[current_entity_label].append(" ".join(current_entity_text))
        else:
            print("Warning: NER model not available for entity extraction.")
        
        extracted_data = dict(grouped_entities)
        extracted_data["intent"] = intent
        extracted_data["raw_query"] = query

        # --- Post-processing for specific entities ---
        
        # 1. Handle Price Range by parsing the text extracted by the NER model
        price_range_text = extracted_data.get("PRICE_RANGE", [])
        extracted_data["PRICE_RANGE"] = self._parse_price_range_text(price_range_text)

        # 2. Consolidate CATEGORY and PRODUCT_TYPE
        if "PRODUCT_TYPE" in extracted_data and "CATEGORY" not in extracted_data:
            extracted_data["CATEGORY"] = extracted_data.pop("PRODUCT_TYPE")
        elif "CATEGORY" in extracted_data and "PRODUCT_TYPE" in extracted_data:
            extracted_data["CATEGORY"].extend(extracted_data.pop("PRODUCT_TYPE"))
            del extracted_data["PRODUCT_TYPE"]

        # 3. Ensure all expected keys exist
        expected_keys = ["BRAND", "CATEGORY", "PRODUCT_TYPE", "PRICE_RANGE"]
        for key in expected_keys:
            if key not in extracted_data:
                extracted_data[key] = []

        return extracted_data

    def _parse_price_range_text(self, price_texts: List[str]) -> List[Optional[int]]:
        """
        Parses extracted price range text (e.g., 'under 500') into a structured list.
        Returns a list like [min_price, max_price].
        """
        if not price_texts:
            return []

        # For simplicity, process the first detected price text
        text = price_texts[0].lower()
        
        # Match patterns like "under 500", "below $300", etc.
        match = re.search(r'(under|below|less than)\s*\$?(\d+)', text)
        if match:
            price = int(match.group(2))
            return [0, price]
            
        # Match patterns like "over 500", "above $300", etc.
        match = re.search(r'(over|above|more than)\s*\$?(\d+)', text)
        if match:
            price = int(match.group(2))
            return [price, None]
            
        # Match patterns like "between 300 and 500"
        match = re.search(r'between\s*\$?(\d+)\s*and\s*\$?(\d+)', text)
        if match:
            return [int(match.group(1)), int(match.group(2))]
        
        # Handle simple numbers like "$500" as an exact price or a max price
        match = re.search(r'^\$?(\d+)', text)
        if match:
            price = int(match.group(1))
            return [price, price]

        return [] # Return empty if no pattern matched

    def _predict_intent(self, query: str) -> str:
        # This method remains unchanged
        if not hasattr(self.intent_pipeline, 'classes_') or self.intent_pipeline.classes_ is None:
            return "unknown_intent"
        try:
            return self.intent_pipeline.predict([query])[0]
        except Exception as e:
            print(f"Error during intent prediction: {e}")
            return "unknown_intent"

    def train(self, dataset_path: str, new_data_path: Optional[str] = None, iterations: int = 10):
        """
        Train or update both the intent and NER models using a base dataset and optional new data.
        This function now includes robust data loading, cleaning, and preparation for both models.
        """
        print(f"Starting training process...")
        
        # --- 1. Data Loading and Preparation ---
        print(f"Loading base dataset from {dataset_path}")
        try:
            df_base = pd.read_csv(dataset_path)
        except FileNotFoundError:
            print(f"Error: Base dataset file not found at {dataset_path}")
            return

        if new_data_path:
            print(f"Loading new data from {new_data_path}")
            try:
                df_new = pd.read_csv(new_data_path)
                df = pd.concat([df_base, df_new], ignore_index=True)
            except FileNotFoundError:
                print(f"Warning: New data file not found. Proceeding with base dataset only.")
                df = df_base
        else:
            df = df_base

        required_columns = ['query', 'intent', 'entities']
        if not all(col in df.columns for col in required_columns):
            print(f"Error: Dataset missing one or more required columns: {required_columns}")
            return

        # Clean and shuffle the data
        df.drop_duplicates(subset=['query'], keep='last', inplace=True)
        df = df.sample(frac=1, random_state=42).reset_index(drop=True)
        print(f"Total unique queries for training: {len(df)}")

        # --- 2. Intent Classifier Training ---
        print("\n--- Training Intent Classifier ---")
        self.intent_pipeline.fit(df['query'], df['intent'])
        print("Intent classifier trained/retrained.")
        joblib.dump(self.intent_pipeline, self.intent_model_path)
        print(f"Intent model saved to {self.intent_model_path}")

        # --- 3. From-Scratch NER Model Training ---
        print("\n--- Training From-Scratch NER Model ---")
        print("Preparing aligned data for NER model...")
        
        # a. Build vocabulary and tag mappings from the entire dataset
        self.tag_to_ix = {"O": 0, "START_TAG": 1, "STOP_TAG": 2} # Reset mappings
        self.word_to_ix = {"[UNK]": 0}
        all_training_data = []

        for _, row in df.iterrows():
            query = row['query']
            try:
                entities = self._parse_entities(row['entities'])
                if entities:
                    tokens, tags = self._create_aligned_tags(query, entities)
                    all_training_data.append((tokens, tags))

                    for word in tokens:
                        if word not in self.word_to_ix:
                            self.word_to_ix[word] = len(self.word_to_ix)
                    for tag in tags:
                        if tag not in self.tag_to_ix:
                            self.tag_to_ix[tag] = len(self.tag_to_ix)
            except Exception as e:
                print(f"Skipping row due to parsing/alignment error: {e}")
                continue
        
        self.ix_to_tag = {v: k for k, v in self.tag_to_ix.items()}
        
        # --- Verification Step ---
        total_entities = sum(1 for _, tags in all_training_data for tag in tags if tag != 'O')
        print(f"Total entities found in training data after parsing: {total_entities}")
        if total_entities == 0:
            print("CRITICAL WARNING: No entities were found in the training data. The model will not learn to extract any entities. Check the 'entities' column format in your CSV.")
        # -------------------------

        print(f"Vocabulary size: {len(self.word_to_ix)}, Tag set size: {len(self.tag_to_ix)}")

        # b. Initialize the model and optimizer
        EMBEDDING_DIM = 128
        HIDDEN_DIM = 256
        self.ner_model = BiLSTM_CRF(len(self.word_to_ix), self.tag_to_ix, EMBEDDING_DIM, HIDDEN_DIM).to(self.device)
        optimizer = optim.SGD(self.ner_model.parameters(), lr=0.01, weight_decay=1e-4)

        # c. The Training Loop
        print(f"Starting NER model training with {len(all_training_data)} samples...")
        for epoch in range(1, iterations + 1):
            total_loss = 0
            # Add tqdm for a progress bar
            from tqdm import tqdm
            for tokens, tags in tqdm(all_training_data, desc=f"NER Epoch {epoch}/{iterations}"):
                self.ner_model.zero_grad()
                
                sentence_in = prepare_sequence(tokens, self.word_to_ix).to(self.device)
                targets = torch.tensor([self.tag_to_ix[t] for t in tags], dtype=torch.long).to(self.device)

                loss = self.ner_model.neg_log_likelihood(sentence_in, targets)
                total_loss += loss.item()
                loss.backward()
                optimizer.step()
            print(f"NER Epoch {epoch}/{iterations}, Loss: {total_loss}")

        # d. Save the trained model and vocab
        print("Saving from-scratch NER model...")
        torch.save(self.ner_model.state_dict(), self.ner_model_path)
        joblib.dump({
            'word_to_ix': self.word_to_ix,
            'tag_to_ix': self.tag_to_ix
        }, self.ner_vocab_path)
        print(f"From-scratch NER model saved successfully to {self.ner_model_path}")
        print("\nTraining process completed.")

    def _parse_entities(self, entity_value):
        """Helper function to parse the entity string safely."""
        if pd.isna(entity_value):
            return []
        if isinstance(entity_value, list):
            # Already parsed, just validate structure
            return [tuple(item) for item in entity_value if isinstance(item, (tuple, list)) and len(item) == 3]
        if isinstance(entity_value, str):
            try:
                # Use ast.literal_eval for safer evaluation than eval
                parsed = ast.literal_eval(entity_value)
                if isinstance(parsed, list):
                    # Validate the structure of each item in the list
                    validated_entities = []
                    for item in parsed:
                        if isinstance(item, (tuple, list)) and len(item) == 3:
                            validated_entities.append(tuple(item))
                        else:
                            # Log or handle malformed items within the list
                            print(f"Warning: Skipping malformed entity item: {item}")
                    return validated_entities
                else:
                    print(f"Warning: Parsed entity string is not a list: {entity_value}")
                    return []
            except (ValueError, SyntaxError, TypeError) as e:
                # Catch specific errors from literal_eval
                print(f"Warning: Could not parse entity string: {entity_value}. Error: {e}")
                return []
        return []

    def _create_aligned_tags(self, query: str, entities: List[tuple]) -> (List[str], List[str]):
        """
        Aligns character-offset entities to token-level IOB tags.
        Returns a list of tokens and a corresponding list of IOB tags.
        """
        tokens = re.findall(r'\w+|[.,!?;]', query)
        tags = ['O'] * len(tokens)
        
        token_spans = []
        current_pos = 0
        for token in tokens:
            start = query.find(token, current_pos)
            if start == -1:
                continue
            end = start + len(token)
            token_spans.append((start, end))
            current_pos = end

        for ent_start, ent_end, ent_label in entities:
            is_first_token = True
            for i, (tok_start, tok_end) in enumerate(token_spans):
                # Check for any overlap between token and entity
                if max(tok_start, ent_start) < min(tok_end, ent_end):
                    if is_first_token:
                        tags[i] = f"B-{ent_label}"
                        is_first_token = False
                    else:
                        tags[i] = f"I-{ent_label}"
        
        return tokens, tags
