import pandas as pd
import joblib
from typing import Dict, Any, List, Optional, Set
from collections import defaultdict
import os
import re
import ast
import json
from pathlib import Path

# --- PyTorch Imports for Enhanced NER Model ---
import torch
import torch.nn as nn
import torch.optim as optim

# --- Import Enhanced Models ---
from enhanced_models import EnhancedBiLSTM_CRF
from utils.resource_loader import load_json_resource

# Path helpers
BACKEND_ROOT = Path(__file__).resolve().parent
MODELS_DIR = BACKEND_ROOT / 'models'
ENHANCED_MODELS_DIR = MODELS_DIR / 'enhanced'
DATA_DIR = BACKEND_ROOT / 'data'
NLP_RESOURCES_DIR = DATA_DIR / 'nlp'

# NLP resource file names (loaded at runtime to avoid hardcoded heuristics)
ENTITY_NORMALIZATION_FILE = NLP_RESOURCES_DIR / 'entity_normalization_map.json'
BRAND_ALIASES_FILE = NLP_RESOURCES_DIR / 'brand_aliases.json'
PRODUCT_KEYWORD_FILE = NLP_RESOURCES_DIR / 'product_keyword_map.json'
KNOWN_BRANDS_FILE = NLP_RESOURCES_DIR / 'known_brands.json'

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
        self.lstm = nn.LSTM(embedding_dim, hidden_dim // 2, num_layers=1, bidirectional=True)
        self.hidden2tag = nn.Linear(hidden_dim, self.tagset_size)

        # Transition matrix for CRF
        self.transitions = nn.Parameter(torch.randn(self.tagset_size, self.tagset_size))
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
        # Initialize the forward variables in log-space
        forward_var = torch.full((1, self.tagset_size), -10000., device=device)
        forward_var[0][self.tag_to_ix["START_TAG"]] = 0.
        for feat in feats:
            alphas_t = []
            for next_tag in range(self.tagset_size):
                # Emission and transition scores
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
        # Include START tag in the score
        tags = torch.cat([torch.tensor([self.tag_to_ix["START_TAG"]], dtype=torch.long, device=device), tags])
        for i, feat in enumerate(feats):
            score = score + self.transitions[tags[i+1], tags[i]] + feat[tags[i+1]]
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

        # Initialize Viterbi variables
        viterbi_vars = torch.full((1, self.tagset_size), -10000., device=device)
        viterbi_vars[0][self.tag_to_ix["START_TAG"]] = 0

        for feat in feats:
            bptrs_t = []
            vvars_t = []
            for next_tag in range(self.tagset_size):
                next_tag_var = viterbi_vars + self.transitions[next_tag]
                best_tag_id = torch.argmax(next_tag_var)
                bptrs_t.append(best_tag_id)
                vvars_t.append(next_tag_var[0][best_tag_id].view(1))
            viterbi_vars = (torch.cat(vvars_t) + feat).view(1, -1)
            backpointers.append(bptrs_t)

        # Transition to STOP_TAG
        terminal_var = viterbi_vars + self.transitions[self.tag_to_ix["STOP_TAG"]]
        best_tag_id = torch.argmax(terminal_var)
        path_score = terminal_var[0][best_tag_id]

        # Backtrack through pointers to decode best path
        best_path = [best_tag_id]
        for bptrs_t in reversed(backpointers):
            best_tag_id = bptrs_t[best_tag_id]
            best_path.append(best_tag_id)
        # Drop the START tag
        best_path.pop()
        best_path.reverse()
        return path_score, best_path

    def forward(self, sentence):
        # Run forward algorithm (BiLSTM + CRF decoding)
        lstm_feats = self._get_lstm_features(sentence)
        score, tag_seq = self._viterbi_decode(lstm_feats)
        return score, tag_seq

# Helper function to convert word sequence to tensor of indices
def prepare_sequence(seq, to_ix):
    idxs = [to_ix.get(w, 0) for w in seq]
    return torch.tensor(idxs, dtype=torch.long)

class EBayNLP:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"Using device: {self.device}")
        
        # Single intent architecture - no intent classifier needed!
        self.intent = "search_product"
        
        # Enhanced NER Model Components
        self.ner_model = None
        self.word_to_ix = {"[UNK]": 0, "[PAD]": 1}
        self.tag_to_ix = {}
        self.ix_to_tag = {}
        self.model_config = {}

        # Data-driven NLP resources
        self.entity_normalization_map: Dict[str, str] = {}
        self.brand_aliases: Dict[str, str] = {}
        self.product_keyword_map: List[Dict[str, Any]] = []
        self.known_brands: Set[str] = set()
        self._load_static_resources()
        
        # Initialize spaCy English tokenizer for robust tokenization
        try:
            import spacy
            self.spacy_nlp = spacy.blank("en")
        except ImportError:
            print("spaCy not available, using basic tokenization")
            self.spacy_nlp = None
        
        self._prepare_models()

    def _load_static_resources(self) -> None:
        """Load NLP resource files so heuristics remain data-driven."""
        normalization_map = load_json_resource(ENTITY_NORMALIZATION_FILE, {})
        if not isinstance(normalization_map, dict):
            print(f"Normalization map invalid; expected dict, got {type(normalization_map).__name__}.")
            normalization_map = {}
        self.entity_normalization_map = {
            str(label).upper(): str(target)
            for label, target in normalization_map.items()
        }

        brand_aliases = load_json_resource(BRAND_ALIASES_FILE, {})
        if not isinstance(brand_aliases, dict):
            print(f"Brand alias data invalid; expected dict, got {type(brand_aliases).__name__}.")
            brand_aliases = {}
        # Normalize alias keys to lowercase for matching
        self.brand_aliases = {str(k).lower(): str(v) for k, v in brand_aliases.items()}

        keyword_map = load_json_resource(PRODUCT_KEYWORD_FILE, [])
        if not isinstance(keyword_map, list):
            print(f"Keyword map invalid; expected list, got {type(keyword_map).__name__}.")
            keyword_map = []
        # Sort by pattern length descending to preserve original precedence
        self.product_keyword_map = sorted(
            [
                {
                    "pattern": str(entry.get("pattern", "")).lower(),
                    "product": entry.get("product"),
                    "category": entry.get("category"),
                    "brand": entry.get("brand")
                }
                for entry in keyword_map
                if entry.get("pattern")
            ],
            key=lambda item: len(item["pattern"]),
            reverse=True
        )

        known_brands = load_json_resource(KNOWN_BRANDS_FILE, [])
        if isinstance(known_brands, dict):
            # Support both list and dict-of-flags
            known_brands = list(known_brands.keys())
        if not isinstance(known_brands, list):
            print(f"Known brands invalid; expected list, got {type(known_brands).__name__}.")
            known_brands = []
        self.known_brands = {str(brand).lower() for brand in known_brands if isinstance(brand, str)}

    def _prepare_models(self):
        """Initialize or load enhanced models"""
        # Enhanced model paths
        self.ner_model_path = ENHANCED_MODELS_DIR / 'enhanced_ner_model.pth'
        self.ner_vocab_path = ENHANCED_MODELS_DIR / 'enhanced_ner_model_vocab.pkl'
        self.model_info_path = ENHANCED_MODELS_DIR / 'model_info.json'
        
        # Load enhanced NER model if available
        if self.ner_model_path.exists() and self.ner_vocab_path.exists():
            print("Loading enhanced NER model...")
            try:
                # Load vocabularies and config
                vocab_data = joblib.load(self.ner_vocab_path)
                self.word_to_ix = vocab_data['word_to_ix']
                self.tag_to_ix = vocab_data['tag_to_ix']
                self.ix_to_tag = {v: k for k, v in self.tag_to_ix.items()}
                self.model_config = vocab_data.get('config', {})
                
                # Load model info if available
                if self.model_info_path.exists():
                    with self.model_info_path.open('r', encoding='utf-8') as f:
                        model_info = json.load(f)
                        print(f"Model info: {model_info.get('description', 'Enhanced NER model')}")
                
                # Initialize enhanced model
                self.ner_model = EnhancedBiLSTM_CRF(
                    vocab_size=len(self.word_to_ix),
                    tag_to_ix=self.tag_to_ix,
                    embedding_dim=self.model_config.get('embedding_dim', 128),
                    hidden_dim=self.model_config.get('hidden_dim', 256),
                    num_layers=self.model_config.get('num_layers', 2),
                    dropout=self.model_config.get('dropout', 0.3),
                    use_attention=self.model_config.get('use_attention', True),
                    use_char_embeddings=self.model_config.get('use_char_embeddings', False)
                )
                self.ner_model.load_state_dict(torch.load(self.ner_model_path, map_location=self.device))
                self.ner_model.to(self.device)
                print("Loaded trained from-scratch NER model.")
            except Exception as e:
                print(f"Error loading from-scratch NER model: {e}. Model will be retrained.")
                self.ner_model = None
        else:
            print(f"No trained from-scratch NER model found at {self.ner_model_path}. A new model will be initialized during training.")

    def extract_entities(self, query: str) -> Dict[str, Any]:
        """
        Entity extraction using the enhanced NER model with single intent architecture.
        """
        # Single intent - always correct!
        intent = self.intent
        
        grouped_entities = defaultdict(list)
        raw_entities = []
        if self.ner_model:
            with torch.no_grad():
                # Tokenize query
                if self.spacy_nlp:
                    doc = self.spacy_nlp(query)
                    query_tokens = [token.text for token in doc]
                else:
                    # Fallback to basic tokenization
                    query_tokens = query.split()
                
                # Prepare sequence for enhanced model
                sentence_in = prepare_sequence(query_tokens, self.word_to_ix).to(self.device)
                
                # Use enhanced model with attention
                score, tag_indices = self.ner_model(sentence_in, query_tokens)
                predicted_tags = [self.ix_to_tag.get(ix.item(), 'O') for ix in tag_indices]
                # Group contiguous tokens for each predicted entity
                current_entity_text = []
                current_entity_label = ""

                def finalize_entity():
                    nonlocal current_entity_text, current_entity_label
                    if current_entity_text and current_entity_label:
                        entity_text = " ".join(current_entity_text)
                        grouped_entities[current_entity_label].append(entity_text)
                        raw_entities.append({
                            'label': current_entity_label,
                            'value': entity_text
                        })
                    current_entity_text = []
                    current_entity_label = ""

                for token, tag in zip(query_tokens, predicted_tags):
                    if tag.startswith("B-"):
                        finalize_entity()
                        current_entity_text = [token]
                        current_entity_label = tag[2:]
                    elif tag.startswith("I-"):
                        label = tag[2:]
                        if current_entity_label == label:
                            current_entity_text.append(token)
                        else:
                            if not current_entity_text:
                                # Treat standalone I- as beginning of a new entity
                                current_entity_text = [token]
                                current_entity_label = label
                            else:
                                # Malformed sequence, close previous entity and start a new one
                                finalize_entity()
                                current_entity_text = [token]
                                current_entity_label = label
                    else:
                        # tag == 'O', close any open entity
                        finalize_entity()
                finalize_entity()
        else:
            print("Warning: NER model not available for entity extraction.")
        normalized_grouped = defaultdict(list)
        normalized_raw_entities = []
        for label, values in grouped_entities.items():
            target_label = self.entity_normalization_map.get(label, label)
            normalized_grouped[target_label].extend(values)
        for entity in raw_entities:
            target_label = self.entity_normalization_map.get(entity['label'], entity['label'])
            normalized_raw_entities.append({
                'label': target_label,
                'value': entity['value']
            })

        extracted_data = dict(normalized_grouped)
        extracted_data["intent"] = intent
        extracted_data["raw_query"] = query
        extracted_data["raw_entities"] = normalized_raw_entities

        return self._post_process_entities(extracted_data)

    def _post_process_entities(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:

        """Normalize, deduplicate, and enrich extracted entity data."""

        query = extracted_data.get('raw_query', '') or ''

        query_lower = query.lower()



        raw_entities_list = extracted_data.get('raw_entities', [])



        def add_raw(label: str, value: Any) -> None:

            if value is None:

                return

            if not isinstance(value, str):

                value = str(value)

            normalized = value.strip()

            if not normalized:

                return

            entry = {'label': label, 'value': normalized}

            if entry not in raw_entities_list:

                raw_entities_list.append(entry)



        def add_value(key: str, value: Any, label: Optional[str] = None) -> None:

            if value is None:

                return

            if isinstance(value, str):

                value_to_use = value.strip()

                if not value_to_use:

                    return

            else:

                value_to_use = value

            container = extracted_data.setdefault(key, [])

            if value_to_use not in container:

                container.append(value_to_use)

            if label:

                add_raw(label, value_to_use)



        # Collect price clues

        price_tokens = []

        price_tokens.extend(extracted_data.get('PRICE_RANGE', []))

        price_tokens.extend(extracted_data.pop('PRICE_TOKEN', []))

        price_tokens.extend(extracted_data.pop('PRICE_QUALIFIER', []))



        combined_price_text = ' '.join(token for token in price_tokens if isinstance(token, str))

        price_range = []

        if combined_price_text:

            price_range = self._parse_price_range_text([combined_price_text])

        if not price_range:

            price_range = self._parse_price_range_text([query])

        if not price_range:

            price_range = self._regex_price_parse(query)

        extracted_data['PRICE_RANGE'] = price_range or []



        # Merge model tokens and variants

        model_tokens = extracted_data.get('MODEL', []) + extracted_data.pop('MODEL_VARIANT', [])

        if model_tokens:

            combined_model = ' '.join(model_tokens).strip()

            extracted_data['MODEL'] = [combined_model] if combined_model else []

        else:

            extracted_data['MODEL'] = []



        # Ensure expected keys exist

        for key in ['BRAND', 'CATEGORY', 'PRODUCT_TYPE', 'MODEL', 'PRICE_RANGE', 'SIZE']:

            extracted_data.setdefault(key, [])



        # Convert usage tokens to size when context implies it

        if 'size' in query_lower and extracted_data.get('USAGE'):

            remaining_usage = []

            for value in extracted_data['USAGE']:

                if isinstance(value, str) and re.fullmatch(r'\d+(?:\.\d{1,2})?', value.strip()):

                    add_value('SIZE', value.strip(), 'SIZE')

                else:

                    remaining_usage.append(value)

            extracted_data['USAGE'] = remaining_usage



        # Keyword-based enrichment for product types, categories, and brands

        for entry in self.product_keyword_map:

            pattern = entry['pattern']

            if pattern and pattern in query_lower:

                if entry.get('product'):
                    add_value('PRODUCT_TYPE', entry['product'], 'PRODUCT_TYPE')

                if entry.get('category'):

                    add_value('CATEGORY', entry['category'], 'CATEGORY')

                if entry.get('brand'):

                    add_value('BRAND', entry['brand'], 'BRAND')



        # Additional category inference from model contents

        for model_value in list(extracted_data['MODEL']):

            lowered = model_value.lower()

            if any(token in lowered for token in ['shoe', 'sneaker', 'boot']):

                add_value('CATEGORY', 'Footwear', 'CATEGORY')

            if 'headphone' in lowered or 'earbud' in lowered:

                add_value('CATEGORY', 'Audio', 'CATEGORY')



        # Size parsing from query text

        size_patterns = [

            r'size\s*(\d+(?:\.\d{1,2})?)',

            r'(?:us|uk|eu)\s*(\d+(?:\.\d{1,2})?)',

            r'(\d+(?:\.\d{1,2})?)\s*(?:cm|mm|in|inch|inches)'

        ]

        for pattern in size_patterns:

            for match in re.finditer(pattern, query, re.IGNORECASE):

                size_value = match.group(1) if match.groups() else match.group(0)

                add_value('SIZE', size_value, 'SIZE')



        # Harmonize brand names using alias map

        harmonized_brands = []

        for brand in extracted_data['BRAND']:

            if isinstance(brand, str):

                alias = self.brand_aliases.get(brand.lower())

                harmonized_brands.append(alias or brand)

        extracted_data['BRAND'] = harmonized_brands



        # Brand fallback using known brand lexicon

        if not extracted_data['BRAND']:

            brand_candidates = []

            for source in extracted_data.get('PRODUCT_TYPE', []) + extracted_data.get('MODEL', []):

                if isinstance(source, str) and source.lower() in self.known_brands:

                    brand_candidates.append(source)

            for token in re.split(r'[^A-Za-z0-9\-]+', query):

                if token and token.lower() in self.known_brands:

                    brand_candidates.append(token)

            if brand_candidates:

                alias = self.brand_aliases.get(brand_candidates[0].lower())

                add_value('BRAND', alias or brand_candidates[0], 'BRAND')



        # Deduplicate values while preserving order

        for key, values in list(extracted_data.items()):

            if key == 'raw_entities' or not isinstance(values, list):

                continue

            seen = set()

            deduped = []

            for value in values:

                if isinstance(value, (int, float)):

                    if value not in deduped:

                        deduped.append(value)

                    continue

                if not isinstance(value, str):

                    continue

                normalized = value.strip()

                if not normalized:

                    continue

                lowered = normalized.lower()

                if lowered not in seen:

                    deduped.append(normalized)

                    seen.add(lowered)

            extracted_data[key] = deduped



        extracted_data['raw_entities'] = raw_entities_list

        return extracted_data





    def _regex_price_parse(self, text: str) -> List[int]:

        lowered = text.lower()

        triggers = ['$', 'under', 'below', 'less than', 'over', 'more than', 'between']

        if not any(trigger in lowered for trigger in triggers):

            return []



        matches = list(re.finditer(r'(?:under|below|less than|upto|up to)\s*\$?(\d+)', text, re.IGNORECASE))

        if matches:

            value = int(matches[-1].group(1))

            return [0, value]



        between = re.search(r'between\s*\$?(\d+)\s*and\s*\$?(\d+)', text, re.IGNORECASE)

        if between:

            return [int(between.group(1)), int(between.group(2))]



        currency = re.search(r'\$\s*(\d+(?:,\d{3})*)', text)

        if currency:

            value = int(currency.group(1).replace(',', ''))

            return [value, value]



        single = re.search(r'(\d+)', text)

        if single:

            value = int(single.group(1))

            return [value, value]



        return []





    def _parse_price_range_text(self, price_texts: List[str]) -> List[Optional[int]]:
        """
        Parses a price range string (e.g., "under 500") into [min_price, max_price] format.
        """
        if not price_texts:
            return []
        text = price_texts[0].lower()
        match = re.search(r'(under|below|less than)\s*\$?(\d+)', text)
        if match:
            price = int(match.group(2))
            return [0, price]
        match = re.search(r'(over|above|more than)\s*\$?(\d+)', text)
        if match:
            price = int(match.group(2))
            return [price, None]
        match = re.search(r'between\s*\$?(\d+)\s*and\s*\$?(\d+)', text)
        if match:
            return [int(match.group(1)), int(match.group(2))]
        match = re.search(r'^\$?(\d+)', text)
        if match:
            price = int(match.group(1))
            return [price, price]
        return []  # No pattern matched

    def _predict_intent(self, query: str) -> str:
        # Single intent architecture - always return search_product
        return self.intent

    def train(self, dataset_path: str, new_data_path: Optional[str] = None, iterations: int = 10):
        """
        Train or update both the intent classifier and NER model using a base dataset (and optional new data).
        This training routine includes robust data loading, validation, and preparation steps.
        """
        print("Starting training process...")
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
                print("Warning: New data file not found. Proceeding with base dataset only.")
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
        # a. Build vocabulary and tag mappings from the dataset
        self.tag_to_ix = {"O": 0, "START_TAG": 1, "STOP_TAG": 2}
        self.word_to_ix = {"[UNK]": 0}
        all_training_data = []
        skipped_rows = 0
        for _, row in df.iterrows():
            query = row['query']
            if not isinstance(query, str) or not query.strip():
                print(f"Skipping row with invalid query text: {query}")
                skipped_rows += 1
                continue
            try:
                entities = self._parse_entities(row['entities'])
            except Exception as e:
                print(f"Skipping row due to parse error: {e}")
                skipped_rows += 1
                continue
            if not entities:
                print(f"Skipping query '{query}' due to no valid entities.")
                skipped_rows += 1
                continue
            try:
                tokens, tags = self._create_aligned_tags(query, entities)
            except Exception as e:
                print(f"Skipping row due to alignment error: {e}")
                skipped_rows += 1
                continue
            all_training_data.append((tokens, tags))
            for word in tokens:
                if word not in self.word_to_ix:
                    self.word_to_ix[word] = len(self.word_to_ix)
            for tag in tags:
                if tag not in self.tag_to_ix:
                    self.tag_to_ix[tag] = len(self.tag_to_ix)
        print(f"Prepared {len(all_training_data)} training examples for NER (skipped {skipped_rows} rows due to errors).")
        self.ix_to_tag = {v: k for k, v in self.tag_to_ix.items()}
        # --- Verification Step ---
        total_entities = sum(1 for _, tags in all_training_data for tag in tags if tag != 'O')
        print(f"Total entities found in training data after parsing: {total_entities}")
        if total_entities == 0:
            print("CRITICAL WARNING: No entities were found in the training data. The model will not learn to extract any entities.")
        # Summarize token count as well
        total_tokens = sum(len(tokens) for tokens, tags in all_training_data)
        print(f"Total tokens in training data after cleaning: {total_tokens}")
        print(f"Vocabulary size: {len(self.word_to_ix)}, Tag set size: {len(self.tag_to_ix)}")
        # b. Initialize model and optimizer
        EMBEDDING_DIM = 128
        HIDDEN_DIM = 256
        embedding_matrix = None
        glove_path = DATA_DIR / 'glove.6B.100d.txt'
        if glove_path.exists():
            print(f"Loading pretrained embeddings from {glove_path}...")
            glove_vectors = {}
            with glove_path.open('r', encoding='utf-8') as f:
                for line in f:
                    parts = line.strip().split()
                    if not parts:
                        continue
                    word = parts[0]
                    if word in self.word_to_ix:
                        vector = [float(x) for x in parts[1:]]
                        glove_vectors[word] = vector
            if glove_vectors:
                glove_dim = len(next(iter(glove_vectors.values())))
                if glove_dim != EMBEDDING_DIM:
                    print(f"Note: GloVe vector length {glove_dim} does not match EMBEDDING_DIM {EMBEDDING_DIM}. Adjusting embedding dimension to {glove_dim}.")
                    EMBEDDING_DIM = glove_dim
                vocab_size = len(self.word_to_ix)
                embedding_matrix = torch.randn(vocab_size, EMBEDDING_DIM)
                # Initialize [UNK] embedding as zero vector for consistency
                embedding_matrix[self.word_to_ix["[UNK]"]] = torch.zeros(EMBEDDING_DIM)
                for word, idx in self.word_to_ix.items():
                    if word in glove_vectors:
                        embedding_matrix[idx] = torch.tensor(glove_vectors[word])
                print(f"Loaded GloVe vectors for {len(glove_vectors)} words out of {len(self.word_to_ix)} in vocabulary.")
            else:
                print("Warning: No vocabulary words found in GloVe file; using random init for embeddings.")
        else:
            print("GloVe embeddings file not found; using random initialization for embeddings.")
        self.ner_model = BiLSTM_CRF(len(self.word_to_ix), self.tag_to_ix, EMBEDDING_DIM, HIDDEN_DIM)
        if embedding_matrix is not None:
            with torch.no_grad():
                self.ner_model.word_embeds.weight.copy_(embedding_matrix)
        self.ner_model = self.ner_model.to(self.device)
        optimizer = optim.SGD(self.ner_model.parameters(), lr=0.01, weight_decay=1e-4)
        # c. Training Loop
        print(f"Starting NER model training with {len(all_training_data)} samples...")
        from tqdm import tqdm
        for epoch in range(1, iterations + 1):
            total_loss = 0
            for tokens, tags in tqdm(all_training_data, desc=f"NER Epoch {epoch}/{iterations}"):
                self.ner_model.zero_grad()
                sentence_in = prepare_sequence(tokens, self.word_to_ix).to(self.device)
                targets = torch.tensor([self.tag_to_ix[t] for t in tags], dtype=torch.long).to(self.device)
                loss = self.ner_model.neg_log_likelihood(sentence_in, targets)
                total_loss += loss.item()
                loss.backward()
                optimizer.step()
            print(f"NER Epoch {epoch}/{iterations}, Loss: {total_loss}")
        # d. Save the trained model and mappings
        print("Saving from-scratch NER model...")
        torch.save(self.ner_model.state_dict(), self.ner_model_path)
        joblib.dump({'word_to_ix': self.word_to_ix, 'tag_to_ix': self.tag_to_ix, 'embedding_dim': EMBEDDING_DIM}, self.ner_vocab_path)
        print(f"From-scratch NER model saved to {self.ner_model_path}")
        print("Training process completed.")

    def _parse_entities(self, entity_value):
        """Helper function to safely parse the 'entities' field."""
        if pd.isna(entity_value):
            return []
        if isinstance(entity_value, list):
            return [tuple(item) for item in entity_value if isinstance(item, (tuple, list)) and len(item) == 3]
        if isinstance(entity_value, str):
            try:
                parsed = ast.literal_eval(entity_value)
                if isinstance(parsed, list):
                    validated_entities = []
                    for item in parsed:
                        if isinstance(item, (tuple, list)) and len(item) == 3:
                            validated_entities.append(tuple(item))
                        else:
                            print(f"Warning: Skipping malformed entity item: {item}")
                    return validated_entities
                else:
                    print(f"Warning: Parsed entity string is not a list: {entity_value}")
                    return []
            except (ValueError, SyntaxError, TypeError) as e:
                print(f"Warning: Could not parse entity string: {entity_value}. Error: {e}")
                return []
        return []

    def _create_aligned_tags(self, query: str, entities: List[tuple]) -> (List[str], List[str]):
        """
        Align character-indexed entities to token-level BIO tags using spaCy tokenization.
        Returns a list of tokens and a parallel list of IOB tags.
        """
        # Tokenize the query with spaCy for robust splitting
        doc = self.spacy_nlp(query)
        tokens = [token.text for token in doc]
        tags = ['O'] * len(tokens)
        token_spans = [(token.idx, token.idx + len(token)) for token in doc]
        for ent_start, ent_end, ent_label in entities:
            is_first_token = True
            for i, (tok_start, tok_end) in enumerate(token_spans):
                if max(tok_start, ent_start) < min(tok_end, ent_end):  # overlap with entity span
                    if is_first_token:
                        tags[i] = f"B-{ent_label}"
                        is_first_token = False
                    else:
                        tags[i] = f"I-{ent_label}"
        return tokens, tags
