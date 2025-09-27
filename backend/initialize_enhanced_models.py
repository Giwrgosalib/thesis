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
import joblib

from enhanced_models import EnhancedBiLSTM_CRF, EnhancedIntentClassifier

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
        
    def build_vocabularies(self, dataset_path: str) -> Tuple[Dict, Dict]:
        """Build vocabularies from the refined dataset."""
        print(f"Building vocabularies from {dataset_path}...")
        
        df = pd.read_csv(dataset_path)
        
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
        os.makedirs('models/enhanced', exist_ok=True)
        
        # Save model state
        torch.save(model.state_dict(), f'models/enhanced/{model_name}.pth')
        
        # Save vocabularies
        vocab_data = {
            'word_to_ix': word_to_ix,
            'tag_to_ix': tag_to_ix,
            'config': self.config,
            'intent': self.intent
        }
        
        joblib.dump(vocab_data, f'models/enhanced/{model_name}_vocab.pkl')
        
        print(f"Saved {model_name} to models/enhanced/")
    
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
        
        with open('models/enhanced/model_info.json', 'w') as f:
            json.dump(model_info, f, indent=2)
        
        print("Model information saved to models/enhanced/model_info.json")
    
    def initialize_models(self, dataset_path: str = 'data/refined_balanced_dataset_train.csv'):
        """Initialize all models for the single intent architecture."""
        print("🚀 Initializing Enhanced Models for Single Intent Architecture")
        print("=" * 60)
        
        # Build vocabularies
        word_to_ix, tag_to_ix = self.build_vocabularies(dataset_path)
        
        # Initialize NER model (no intent model needed!)
        ner_model = self.initialize_ner_model(word_to_ix, tag_to_ix)
        
        # Save model artifacts
        self.save_model_artifacts(ner_model, word_to_ix, tag_to_ix, 'enhanced_ner_model')
        
        # Create model information
        self.create_model_info(word_to_ix, tag_to_ix)
        
        print(f"\n🎉 MODEL INITIALIZATION COMPLETE!")
        print(f"📁 Models saved to: models/enhanced/")
        print(f"🎯 Architecture: Single intent + Enhanced NER")
        print(f"📊 Vocabulary sizes: {len(word_to_ix)} words, {len(tag_to_ix)} tags")
        print(f"🚀 Ready for training with enhanced datasets!")
        
        return ner_model, word_to_ix, tag_to_ix

def main():
    """Main initialization function."""
    initializer = ModelInitializer()
    
    # Initialize models
    ner_model, word_to_ix, tag_to_ix = initializer.initialize_models()
    
    print(f"\n📋 MODEL SUMMARY:")
    print(f"   Intent: {initializer.intent} (always correct!)")
    print(f"   NER Model: Enhanced BiLSTM-CRF with attention")
    print(f"   Parameters: {sum(p.numel() for p in ner_model.parameters()):,}")
    print(f"   Entity Types: {len([tag for tag in tag_to_ix.keys() if tag not in ['O', 'START_TAG', 'STOP_TAG']])}")
    
    print(f"\n🎓 Perfect for your thesis!")
    print(f"   ✅ Single intent architecture")
    print(f"   ✅ Enhanced NER model")
    print(f"   ✅ Production-ready structure")
    print(f"   ✅ Clean, optimized codebase")

if __name__ == "__main__":
    main()
