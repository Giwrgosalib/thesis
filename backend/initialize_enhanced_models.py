#!/usr/bin/env python3
"""
Initialize enhanced models for single intent architecture.
Creates new model structure optimized for the refined datasets.
"""

import torch
import torch.nn as nn
import pandas as pd
import ast
import json
import os
from collections import Counter, defaultdict
from typing import Dict, List, Tuple
from pathlib import Path
import joblib

# Path constants
BACKEND_ROOT = Path(__file__).resolve().parent
DATA_DIR = BACKEND_ROOT / 'data'
MODELS_DIR = BACKEND_ROOT / 'models'
ENHANCED_MODELS_DIR = MODELS_DIR / 'enhanced'

from enhanced_models import EnhancedBiLSTM_CRF, EnhancedIntentClassifier

DEFAULT_DATASET_FILE = DATA_DIR / 'refined_balanced_dataset_train.csv'

class ModelInitializer:
    """Initialize enhanced models for single intent architecture."""
    
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"Using device: {self.device}")
        
        # Model configuration
        self.config = {
            'embedding_dim': 128,
            'hidden_dim': 256,
            'num_layers': 2,
            'dropout': 0.3,
            'learning_rate': 0.001,
            'use_attention': True,
            'use_char_embeddings': False
        }
        
        # Single intent (no intent classifier needed!)
        self.intent = "search_product"
        
    def build_vocabularies(self, dataset_path: Path) -> Tuple[Dict, Dict]:
        """Build vocabularies from the refined dataset."""
        print(f"Building vocabularies from {dataset_path}...")
        
        try:
            df = pd.read_csv(dataset_path)
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"Dataset not found at {dataset_path}.") from exc
        
        # Word vocabulary
        word_to_ix = {"[UNK]": 0, "[PAD]": 1}
        tag_to_ix = {"O": 0, "START_TAG": 1, "STOP_TAG": 2}
        
        # Collect all words and tags
        all_words = set()
        all_tags = set()
        
        for _, row in df.iterrows():
            try:
                query = str(row['query']).strip()
                entities = ast.literal_eval(row['entities']) if isinstance(row['entities'], str) else row['entities']
                
                # Add words
                words = query.split()
                all_words.update(words)
                
                # Add tags (BIO format)
                for _, _, label in entities:
                    all_tags.add(f"B-{label}")
                    all_tags.add(f"I-{label}")
                
            except Exception as e:
                continue
        
        # Build vocabularies
        for word in sorted(all_words):
            if word not in word_to_ix:
                word_to_ix[word] = len(word_to_ix)
        
        for tag in sorted(all_tags):
            if tag not in tag_to_ix:
                tag_to_ix[tag] = len(tag_to_ix)
        
        print(f"Vocabulary sizes: words={len(word_to_ix)}, tags={len(tag_to_ix)}")
        
        return word_to_ix, tag_to_ix
    
    def initialize_ner_model(self, word_to_ix: Dict, tag_to_ix: Dict) -> EnhancedBiLSTM_CRF:
        """Initialize the enhanced NER model."""
        print("Initializing enhanced NER model...")
        
        model = EnhancedBiLSTM_CRF(
            vocab_size=len(word_to_ix),
            tag_to_ix=tag_to_ix,
            embedding_dim=self.config['embedding_dim'],
            hidden_dim=self.config['hidden_dim'],
            num_layers=self.config['num_layers'],
            dropout=self.config['dropout'],
            use_attention=self.config['use_attention'],
            use_char_embeddings=self.config['use_char_embeddings']
        ).to(self.device)
        
        print(f"NER model initialized with {sum(p.numel() for p in model.parameters())} parameters")
        return model
    
    def save_model_artifacts(self, model: nn.Module, word_to_ix: Dict, tag_to_ix: Dict, model_name: str):
        """Save model and vocabularies."""
        ENHANCED_MODELS_DIR.mkdir(parents=True, exist_ok=True)

        # Save model state
        model_path = ENHANCED_MODELS_DIR / f"{model_name}.pth"
        torch.save(model.state_dict(), model_path)

        # Save vocabularies
        vocab_data = {
            'word_to_ix': word_to_ix,
            'tag_to_ix': tag_to_ix,
            'config': self.config,
            'intent': self.intent
        }

        vocab_path = ENHANCED_MODELS_DIR / f"{model_name}_vocab.pkl"
        joblib.dump(vocab_data, vocab_path)

        print(f"Saved {model_name} to {ENHANCED_MODELS_DIR}")
    
    def create_model_info(self, word_to_ix: Dict, tag_to_ix: Dict):
        """Create model information file."""
        model_info = {
            'architecture': 'Enhanced BiLSTM-CRF with Attention',
            'intent': self.intent,
            'vocab_sizes': {
                'words': len(word_to_ix),
                'tags': len(tag_to_ix)
            },
            'config': self.config,
            'entity_types': list(set([tag.replace('B-', '').replace('I-', '') for tag in tag_to_ix.keys() if tag not in ['O', 'START_TAG', 'STOP_TAG']])),
            'device': str(self.device),
            'description': 'Single intent architecture with enhanced NER model for eBay product search'
        }
        
        ENHANCED_MODELS_DIR.mkdir(parents=True, exist_ok=True)
        model_info_path = ENHANCED_MODELS_DIR / "model_info.json"
        with model_info_path.open('w', encoding='utf-8') as f:
            json.dump(model_info, f, indent=2)

        print(f"Model information saved to {model_info_path}")
    
    def _resolve_dataset_path(self, dataset_path: str) -> Path:
        """Resolve dataset path with sensible fallbacks."""
        candidate_strings = [dataset_path] if dataset_path else []
        candidate_strings.extend([
            'backend/data/refined_balanced_dataset_train.csv',
            'backend/data/refined_balanced_dataset.csv',
            'backend/data/train.csv',
            'backend/data/training.csv'
        ])

        seen = set()
        candidates = []
        for candidate in candidate_strings:
            if candidate and candidate not in seen:
                seen.add(candidate)
                candidates.append(Path(candidate))

        for candidate in candidates:
            if candidate.exists():
                print(f"Using dataset file: {candidate}")
                return candidate

        checked = ', '.join(str(p) for p in candidates)
        raise FileNotFoundError(f"No dataset file found. Checked: {checked}")

    def initialize_models(self, dataset_path: str = 'backend/data/refined_balanced_dataset_train.csv'):
        """Initialize all models for the single intent architecture."""
        print("Initializing Enhanced Models for Single Intent Architecture")
        print("=" * 60)

        resolved_dataset = self._resolve_dataset_path(dataset_path)

        # Build vocabularies
        word_to_ix, tag_to_ix = self.build_vocabularies(resolved_dataset)

        # Initialize NER model (no intent model needed!)
        ner_model = self.initialize_ner_model(word_to_ix, tag_to_ix)

        # Save model artifacts
        self.save_model_artifacts(ner_model, word_to_ix, tag_to_ix, 'enhanced_ner_model')

        # Create model information
        self.create_model_info(word_to_ix, tag_to_ix)

        print("\nMODEL INITIALIZATION COMPLETE!")
        print("Models saved to: models/enhanced/")
        print("Architecture: Single intent + Enhanced NER")
        print(f"Vocabulary sizes: {len(word_to_ix)} words, {len(tag_to_ix)} tags")
        print("Ready for training with enhanced datasets!")

        return ner_model, word_to_ix, tag_to_ix

def main():
    """Main initialization function."""
    initializer = ModelInitializer()
    
    # Initialize models
    ner_model, word_to_ix, tag_to_ix = initializer.initialize_models()
    
    print("\nMODEL SUMMARY:")
    print(f"   Intent: {initializer.intent} (always correct!)")
    print("   NER Model: Enhanced BiLSTM-CRF with attention")
    print(f"   Parameters: {sum(p.numel() for p in ner_model.parameters()):,}")
    print(f"   Entity Types: {len([tag for tag in tag_to_ix.keys() if tag not in ['O', 'START_TAG', 'STOP_TAG']])}")

    print("\nHighlights:")
    print("   - Single intent architecture")
    print("   - Enhanced NER model")
    print("   - Production-ready structure")
    print("   - Clean, optimized codebase")

if __name__ == "__main__":
    main()
