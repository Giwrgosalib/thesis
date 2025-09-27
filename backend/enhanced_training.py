"""
Enhanced training pipeline for the eBay AI Chatbot.
Includes advanced training techniques, evaluation, and model optimization.
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
import os
import json
import time
from tqdm import tqdm
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import classification_report, confusion_matrix
from collections import Counter

from enhanced_models import EnhancedBiLSTM_CRF, EnhancedIntentClassifier, LearningRateScheduler
from dataset_improvements import EntityConsolidator, DatasetValidator

class EBayDataset(Dataset):
    """Custom dataset class for eBay queries."""
    
    def __init__(self, df: pd.DataFrame, word_to_ix: Dict[str, int], tag_to_ix: Dict[str, int], 
                 intent_to_ix: Dict[str, int], max_length: int = 100):
        self.df = df
        self.word_to_ix = word_to_ix
        self.tag_to_ix = tag_to_ix
        self.intent_to_ix = intent_to_ix
        self.max_length = max_length
        
        # Preprocess data
        self.samples = self._preprocess_data()
    
    def _preprocess_data(self) -> List[Dict]:
        """Preprocess the dataset."""
        samples = []
        
        for _, row in self.df.iterrows():
            try:
                query = str(row['query']).strip()
                intent = str(row['intent']).strip()
                entities = ast.literal_eval(row['entities']) if isinstance(row['entities'], str) else row['entities']
                
                # Tokenize query
                words = query.split()
                if len(words) > self.max_length:
                    words = words[:self.max_length]
                
                # Convert to indices
                word_indices = [self.word_to_ix.get(w, self.word_to_ix.get("[UNK]", 0)) for w in words]
                intent_index = self.intent_to_ix.get(intent, 0)
                
                # Create BIO tags
                tags = ['O'] * len(words)
                for start, end, label in entities:
                    # Find word boundaries
                    word_start = 0
                    for i, word in enumerate(words):
                        word_end = word_start + len(word)
                        if start >= word_start and end <= word_end:
                            tags[i] = f"B-{label}"
                            break
                        elif start < word_end and end > word_start:
                            tags[i] = f"I-{label}"
                        word_start = word_end + 1
                
                # Convert tags to indices
                tag_indices = [self.tag_to_ix.get(tag, 0) for tag in tags]
                
                samples.append({
                    'words': words,
                    'word_indices': torch.tensor(word_indices, dtype=torch.long),
                    'tags': tags,
                    'tag_indices': torch.tensor(tag_indices, dtype=torch.long),
                    'intent': intent,
                    'intent_index': intent_index,
                    'query': query
                })
                
            except Exception as e:
                print(f"Error processing row: {e}")
                continue
        
        return samples
    
    def __len__(self):
        return len(self.samples)
    
    def __getitem__(self, idx):
        return self.samples[idx]

def collate_fn(batch):
    """Custom collate function for DataLoader."""
    words = [item['words'] for item in batch]
    word_indices = [item['word_indices'] for item in batch]
    tag_indices = [item['tag_indices'] for item in batch]
    intent_indices = [item['intent_index'] for item in batch]
    queries = [item['query'] for item in batch]
    
    # Pad sequences
    word_indices = torch.nn.utils.rnn.pad_sequence(word_indices, batch_first=True, padding_value=0)
    tag_indices = torch.nn.utils.rnn.pad_sequence(tag_indices, batch_first=True, padding_value=0)
    intent_indices = torch.tensor(intent_indices, dtype=torch.long)
    
    return {
        'words': words,
        'word_indices': word_indices,
        'tag_indices': tag_indices,
        'intent_indices': intent_indices,
        'queries': queries
    }

class EnhancedTrainer:
    """Enhanced trainer with advanced techniques."""
    
    def __init__(self, config: Dict):
        self.config = config
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"Using device: {self.device}")
        
        # Initialize models
        self.ner_model = None
        self.intent_model = None
        
        # Training history
        self.history = {
            'ner_loss': [],
            'intent_loss': [],
            'ner_f1': [],
            'intent_accuracy': []
        }
    
    def build_vocabularies(self, df: pd.DataFrame) -> Tuple[Dict, Dict, Dict]:
        """Build vocabularies from dataset."""
        print("Building vocabularies...")
        
        # Word vocabulary
        word_to_ix = {"[UNK]": 0, "[PAD]": 1}
        tag_to_ix = {"O": 0, "START_TAG": 1, "STOP_TAG": 2}
        intent_to_ix = {}
        
        # Collect all words and tags
        all_words = set()
        all_tags = set()
        all_intents = set()
        
        for _, row in df.iterrows():
            try:
                query = str(row['query']).strip()
                intent = str(row['intent']).strip()
                entities = ast.literal_eval(row['entities']) if isinstance(row['entities'], str) else row['entities']
                
                # Add words
                words = query.split()
                all_words.update(words)
                all_intents.add(intent)
                
                # Add tags
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
        
        for intent in sorted(all_intents):
            if intent not in intent_to_ix:
                intent_to_ix[intent] = len(intent_to_ix)
        
        print(f"Vocabulary sizes: words={len(word_to_ix)}, tags={len(tag_to_ix)}, intents={len(intent_to_ix)}")
        
        return word_to_ix, tag_to_ix, intent_to_ix
    
    def train_ner_model(self, train_loader: DataLoader, val_loader: DataLoader, 
                       word_to_ix: Dict, tag_to_ix: Dict) -> None:
        """Train the NER model."""
        print("\n🏋️ Training NER model...")
        
        # Initialize model
        self.ner_model = EnhancedBiLSTM_CRF(
            vocab_size=len(word_to_ix),
            tag_to_ix=tag_to_ix,
            embedding_dim=self.config['embedding_dim'],
            hidden_dim=self.config['hidden_dim'],
            num_layers=self.config['num_layers'],
            dropout=self.config['dropout'],
            use_attention=self.config['use_attention'],
            use_char_embeddings=self.config['use_char_embeddings']
        ).to(self.device)
        
        # Optimizer and scheduler
        optimizer = optim.AdamW(self.ner_model.parameters(), lr=self.config['learning_rate'], weight_decay=1e-4)
        scheduler = LearningRateScheduler(optimizer, warmup_steps=1000, d_model=self.config['hidden_dim'])
        
        # Training loop
        best_f1 = 0
        patience = 0
        
        for epoch in range(self.config['epochs']):
            # Training
            self.ner_model.train()
            total_loss = 0
            
            for batch in tqdm(train_loader, desc=f"NER Epoch {epoch+1}/{self.config['epochs']}"):
                optimizer.zero_grad()
                
                word_indices = batch['word_indices'].to(self.device)
                tag_indices = batch['tag_indices'].to(self.device)
                words = batch['words']
                
                # Calculate loss for each sequence in batch
                batch_loss = 0
                for i in range(word_indices.size(0)):
                    # Remove padding
                    seq_len = (word_indices[i] != 0).sum().item()
                    if seq_len == 0:
                        continue
                    
                    sentence = word_indices[i][:seq_len]
                    tags = tag_indices[i][:seq_len]
                    word_list = words[i][:seq_len]
                    
                    loss = self.ner_model.neg_log_likelihood(sentence, tags, word_list)
                    batch_loss += loss
                
                batch_loss = batch_loss / word_indices.size(0)
                batch_loss.backward()
                
                # Gradient clipping
                torch.nn.utils.clip_grad_norm_(self.ner_model.parameters(), max_norm=1.0)
                
                optimizer.step()
                scheduler.step()
                
                total_loss += batch_loss.item()
            
            avg_loss = total_loss / len(train_loader)
            self.history['ner_loss'].append(avg_loss)
            
            # Validation
            if val_loader:
                f1_score = self.evaluate_ner_model(val_loader, word_to_ix, tag_to_ix)
                self.history['ner_f1'].append(f1_score)
                
                print(f"NER Epoch {epoch+1}: Loss={avg_loss:.4f}, F1={f1_score:.4f}")
                
                # Early stopping
                if f1_score > best_f1:
                    best_f1 = f1_score
                    patience = 0
                    self.save_model('ner_model', self.ner_model, word_to_ix, tag_to_ix)
                else:
                    patience += 1
                    if patience >= self.config['patience']:
                        print(f"Early stopping at epoch {epoch+1}")
                        break
            else:
                print(f"NER Epoch {epoch+1}: Loss={avg_loss:.4f}")
    
    def train_intent_model(self, train_loader: DataLoader, val_loader: DataLoader,
                          word_to_ix: Dict, intent_to_ix: Dict) -> None:
        """Train the intent classification model."""
        print("\n🏋️ Training Intent model...")
        
        # Initialize model
        self.intent_model = EnhancedIntentClassifier(
            vocab_size=len(word_to_ix),
            num_intents=len(intent_to_ix),
            embedding_dim=self.config['embedding_dim'],
            hidden_dim=self.config['hidden_dim'],
            num_layers=self.config['num_layers'],
            dropout=self.config['dropout']
        ).to(self.device)
        
        # Optimizer and scheduler
        optimizer = optim.AdamW(self.intent_model.parameters(), lr=self.config['learning_rate'], weight_decay=1e-4)
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='max', patience=3, factor=0.5)
        
        # Loss function
        criterion = nn.CrossEntropyLoss()
        
        # Training loop
        best_accuracy = 0
        patience = 0
        
        for epoch in range(self.config['epochs']):
            # Training
            self.intent_model.train()
            total_loss = 0
            
            for batch in tqdm(train_loader, desc=f"Intent Epoch {epoch+1}/{self.config['epochs']}"):
                optimizer.zero_grad()
                
                word_indices = batch['word_indices'].to(self.device)
                intent_indices = batch['intent_indices'].to(self.device)
                
                # Forward pass
                logits = self.intent_model(word_indices)
                loss = criterion(logits, intent_indices)
                
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.intent_model.parameters(), max_norm=1.0)
                optimizer.step()
                
                total_loss += loss.item()
            
            avg_loss = total_loss / len(train_loader)
            self.history['intent_loss'].append(avg_loss)
            
            # Validation
            if val_loader:
                accuracy = self.evaluate_intent_model(val_loader, word_to_ix, intent_to_ix)
                self.history['intent_accuracy'].append(accuracy)
                scheduler.step(accuracy)
                
                print(f"Intent Epoch {epoch+1}: Loss={avg_loss:.4f}, Accuracy={accuracy:.4f}")
                
                # Early stopping
                if accuracy > best_accuracy:
                    best_accuracy = accuracy
                    patience = 0
                    self.save_model('intent_model', self.intent_model, word_to_ix, intent_to_ix)
                else:
                    patience += 1
                    if patience >= self.config['patience']:
                        print(f"Early stopping at epoch {epoch+1}")
                        break
            else:
                print(f"Intent Epoch {epoch+1}: Loss={avg_loss:.4f}")
    
    def evaluate_ner_model(self, val_loader: DataLoader, word_to_ix: Dict, tag_to_ix: Dict) -> float:
        """Evaluate NER model."""
        self.ner_model.eval()
        
        all_predictions = []
        all_targets = []
        
        with torch.no_grad():
            for batch in val_loader:
                word_indices = batch['word_indices'].to(self.device)
                tag_indices = batch['tag_indices'].to(self.device)
                words = batch['words']
                
                for i in range(word_indices.size(0)):
                    seq_len = (word_indices[i] != 0).sum().item()
                    if seq_len == 0:
                        continue
                    
                    sentence = word_indices[i][:seq_len]
                    targets = tag_indices[i][:seq_len]
                    word_list = words[i][:seq_len]
                    
                    # Get predictions
                    _, predicted_tags = self.ner_model(sentence, word_list)
                    
                    # Convert to lists
                    predicted_tags = [tag.item() for tag in predicted_tags]
                    targets = targets.cpu().numpy().tolist()
                    
                    all_predictions.extend(predicted_tags)
                    all_targets.extend(targets)
        
        # Calculate F1 score
        from sklearn.metrics import f1_score
        f1 = f1_score(all_targets, all_predictions, average='weighted', zero_division=0)
        
        return f1
    
    def evaluate_intent_model(self, val_loader: DataLoader, word_to_ix: Dict, intent_to_ix: Dict) -> float:
        """Evaluate intent model."""
        self.intent_model.eval()
        
        correct = 0
        total = 0
        
        with torch.no_grad():
            for batch in val_loader:
                word_indices = batch['word_indices'].to(self.device)
                intent_indices = batch['intent_indices'].to(self.device)
                
                logits = self.intent_model(word_indices)
                predictions = torch.argmax(logits, dim=1)
                
                correct += (predictions == intent_indices).sum().item()
                total += intent_indices.size(0)
        
        return correct / total
    
    def save_model(self, model_name: str, model: nn.Module, word_to_ix: Dict, label_to_ix: Dict):
        """Save model and vocabularies."""
        os.makedirs('models/enhanced', exist_ok=True)
        
        # Save model
        torch.save(model.state_dict(), f'models/enhanced/{model_name}.pth')
        
        # Save vocabularies
        vocab_data = {
            'word_to_ix': word_to_ix,
            'label_to_ix': label_to_ix
        }
        
        import joblib
        joblib.dump(vocab_data, f'models/enhanced/{model_name}_vocab.pkl')
        
        print(f"Saved {model_name} to models/enhanced/")
    
    def plot_training_history(self):
        """Plot training history."""
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        
        # NER Loss
        axes[0, 0].plot(self.history['ner_loss'])
        axes[0, 0].set_title('NER Training Loss')
        axes[0, 0].set_xlabel('Epoch')
        axes[0, 0].set_ylabel('Loss')
        
        # NER F1
        axes[0, 1].plot(self.history['ner_f1'])
        axes[0, 1].set_title('NER Validation F1')
        axes[0, 1].set_xlabel('Epoch')
        axes[0, 1].set_ylabel('F1 Score')
        
        # Intent Loss
        axes[1, 0].plot(self.history['intent_loss'])
        axes[1, 0].set_title('Intent Training Loss')
        axes[1, 0].set_xlabel('Epoch')
        axes[1, 0].set_ylabel('Loss')
        
        # Intent Accuracy
        axes[1, 1].plot(self.history['intent_accuracy'])
        axes[1, 1].set_title('Intent Validation Accuracy')
        axes[1, 1].set_xlabel('Epoch')
        axes[1, 1].set_ylabel('Accuracy')
        
        plt.tight_layout()
        plt.savefig('models/enhanced/training_history.png')
        plt.close()

def main():
    """Main training function."""
    print("🚀 Enhanced Training Pipeline for eBay AI Chatbot")
    print("=" * 60)
    
    # Configuration
    config = {
        'embedding_dim': 128,
        'hidden_dim': 256,
        'num_layers': 2,
        'dropout': 0.3,
        'learning_rate': 0.001,
        'epochs': 50,
        'batch_size': 32,
        'patience': 10,
        'use_attention': True,
        'use_char_embeddings': False
    }
    
    # Load improved datasets
    train_df = pd.read_csv('data/improved_dataset.csv')
    val_df = pd.read_csv('data/improved_validation.csv')
    
    print(f"Training samples: {len(train_df)}")
    print(f"Validation samples: {len(val_df)}")
    
    # Initialize trainer
    trainer = EnhancedTrainer(config)
    
    # Build vocabularies
    word_to_ix, tag_to_ix, intent_to_ix = trainer.build_vocabularies(train_df)
    
    # Create datasets
    train_dataset = EBayDataset(train_df, word_to_ix, tag_to_ix, intent_to_ix)
    val_dataset = EBayDataset(val_df, word_to_ix, tag_to_ix, intent_to_ix)
    
    # Create data loaders
    train_loader = DataLoader(train_dataset, batch_size=config['batch_size'], 
                             shuffle=True, collate_fn=collate_fn)
    val_loader = DataLoader(val_dataset, batch_size=config['batch_size'], 
                           shuffle=False, collate_fn=collate_fn)
    
    # Train models
    trainer.train_ner_model(train_loader, val_loader, word_to_ix, tag_to_ix)
    trainer.train_intent_model(train_loader, val_loader, word_to_ix, intent_to_ix)
    
    # Plot training history
    trainer.plot_training_history()
    
    print("\n🎉 Training complete!")
    print("📊 Models saved to models/enhanced/")
    print("📈 Training history saved to models/enhanced/training_history.png")

if __name__ == "__main__":
    main()
