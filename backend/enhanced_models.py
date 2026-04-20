"""
Enhanced ML models for the eBay AI Chatbot.
Includes improved BiLSTM-CRF with attention, better intent classification, and advanced training techniques.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.nn.utils.rnn import pad_sequence
import numpy as np
from typing import Dict, List, Tuple, Optional
import math

class AttentionLayer(nn.Module):
    """Self-attention layer for better sequence modeling."""
    
    def __init__(self, hidden_dim: int, attention_dim: int = 128):
        super(AttentionLayer, self).__init__()
        self.hidden_dim = hidden_dim
        self.attention_dim = attention_dim
        
        self.attention_linear = nn.Linear(hidden_dim, attention_dim)
        self.context_vector = nn.Linear(attention_dim, 1, bias=False)
        
    def forward(self, lstm_outputs):
        """
        Args:
            lstm_outputs: (seq_len, batch_size, hidden_dim)
        Returns:
            attended_output: (batch_size, hidden_dim)
            attention_weights: (batch_size, seq_len)
        """
        # Calculate attention scores
        attention_scores = self.attention_linear(lstm_outputs)  # (seq_len, batch_size, attention_dim)
        attention_scores = torch.tanh(attention_scores)
        attention_weights = self.context_vector(attention_scores).squeeze(-1)  # (seq_len, batch_size)
        attention_weights = F.softmax(attention_weights, dim=0)  # (seq_len, batch_size)
        
        # Apply attention weights
        attended_output = torch.sum(attention_weights.unsqueeze(-1) * lstm_outputs, dim=0)  # (batch_size, hidden_dim)
        
        return attended_output, attention_weights

class EnhancedBiLSTM_CRF(nn.Module):
    """Enhanced BiLSTM-CRF model with attention mechanism and improved architecture."""
    
    def __init__(self, vocab_size: int, tag_to_ix: Dict[str, int], embedding_dim: int = 128, 
                 hidden_dim: int = 256, num_layers: int = 2, dropout: float = 0.3,
                 use_attention: bool = True, use_char_embeddings: bool = False):
        super(EnhancedBiLSTM_CRF, self).__init__()
        
        self.embedding_dim = embedding_dim
        self.hidden_dim = hidden_dim
        self.vocab_size = vocab_size
        self.tag_to_ix = tag_to_ix
        self.tagset_size = len(tag_to_ix)
        self.num_layers = num_layers
        self.dropout = dropout
        self.use_attention = use_attention
        self.use_char_embeddings = use_char_embeddings
        
        # Word embeddings
        self.word_embeds = nn.Embedding(vocab_size, embedding_dim)
        
        # Character-level embeddings (optional)
        if use_char_embeddings:
            self.char_embedding_dim = 25
            self.char_embeds = nn.Embedding(256, self.char_embedding_dim)  # ASCII characters
            self.char_lstm = nn.LSTM(self.char_embedding_dim, 25, batch_first=True, bidirectional=True)
            self.embedding_dim += 50  # 25 * 2 for bidirectional
        
        # Dropout for embeddings
        self.embed_dropout = nn.Dropout(dropout)
        
        # Enhanced BiLSTM with multiple layers
        self.lstm = nn.LSTM(
            self.embedding_dim, 
            hidden_dim // 2, 
            num_layers=num_layers, 
            bidirectional=True,
            dropout=dropout if num_layers > 1 else 0,
            batch_first=False
        )
        
        # Attention mechanism
        if use_attention:
            self.attention = AttentionLayer(hidden_dim)
        
        # Output projection with dropout
        self.hidden2tag = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, self.tagset_size)
        )
        
        # CRF transition matrix
        self.transitions = nn.Parameter(torch.randn(self.tagset_size, self.tagset_size))
        
        # Initialize transitions
        self.transitions.data[tag_to_ix["START_TAG"], :] = -10000
        self.transitions.data[:, tag_to_ix["STOP_TAG"]] = -10000
        
        # Initialize weights
        self._init_weights()
    
    def _init_weights(self):
        """Initialize model weights."""
        # Initialize LSTM weights
        for name, param in self.lstm.named_parameters():
            if 'weight' in name:
                nn.init.xavier_uniform_(param)
            elif 'bias' in name:
                nn.init.zeros_(param)
        
        # Initialize linear layer weights
        for module in self.hidden2tag:
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                nn.init.zeros_(module.bias)
    
    def _get_char_embeddings(self, words: List[str]) -> torch.Tensor:
        """Get character-level embeddings for words."""
        char_embeddings = []
        for word in words:
            char_ids = [ord(c) for c in word[:20]]  # Limit to 20 chars
            if len(char_ids) < 20:
                char_ids.extend([0] * (20 - len(char_ids)))  # Pad with 0
            
            char_tensor = torch.tensor(char_ids, dtype=torch.long)
            char_emb = self.char_embeds(char_tensor.unsqueeze(0))  # (1, seq_len, char_emb_dim)
            char_lstm_out, _ = self.char_lstm(char_emb)
            char_emb = char_lstm_out[:, -1, :]  # Take last output (1, char_emb_dim)
            char_embeddings.append(char_emb.squeeze(0))
        
        return torch.stack(char_embeddings)  # (seq_len, char_emb_dim)
    
    def _get_lstm_features(self, sentence: torch.Tensor, words: Optional[List[str]] = None):
        """Get LSTM features with optional character embeddings."""
        # Word embeddings
        word_embeds = self.word_embeds(sentence)  # (seq_len, embedding_dim)
        word_embeds = self.embed_dropout(word_embeds)
        
        # Add character embeddings if enabled
        if self.use_char_embeddings and words is not None:
            char_embeds = self._get_char_embeddings(words)  # (seq_len, char_emb_dim)
            word_embeds = torch.cat([word_embeds, char_embeds], dim=-1)
        
        # Reshape for LSTM (seq_len, 1, embedding_dim)
        word_embeds = word_embeds.unsqueeze(1)
        
        # LSTM forward pass
        lstm_out, _ = self.lstm(word_embeds)  # (seq_len, 1, hidden_dim)

        # Apply attention if enabled
        if self.use_attention:
            attention_input = lstm_out  # preserve sequence length
            attended_out, attention_weights = self.attention(attention_input)
            # attention_weights shape: (seq_len, batch)
            attention_weights = attention_weights.unsqueeze(-1)  # (seq_len, batch, 1)
            lstm_out = attention_input * attention_weights
        
        # Remove batch dimension
        lstm_out = lstm_out.squeeze(1)  # (seq_len, hidden_dim)

        # Project to tag space
        tag_space = self.hidden2tag(lstm_out)  # (seq_len, tagset_size)
        
        return tag_space
    
    def _forward_alg(self, feats: torch.Tensor):
        """Vectorised forward algorithm for CRF (no Python loop over tags).

        Replaces the original per-tag Python loop with a single batched
        logsumexp, giving ~K× speedup (K = tagset_size).

        Args:
            feats: (seq_len, tagset_size) emission scores
        Returns:
            alpha: scalar log-partition score
        """
        device = feats.device
        # forward_var: (tagset_size,) log-alpha for each tag
        forward_var = torch.full((self.tagset_size,), -10000., device=device)
        forward_var[self.tag_to_ix["START_TAG"]] = 0.

        for feat in feats:
            # broadcast: next_tag_var[next_tag, prev_tag] =
            #   forward_var[prev_tag] + transitions[next_tag, prev_tag]
            # shape: (tagset_size, tagset_size)
            next_tag_var = forward_var.unsqueeze(0) + self.transitions
            # logsumexp over prev_tags, then add emission: (tagset_size,)
            forward_var = torch.logsumexp(next_tag_var, dim=1) + feat

        terminal_var = forward_var + self.transitions[self.tag_to_ix["STOP_TAG"]]
        alpha = torch.logsumexp(terminal_var, dim=0)
        return alpha.unsqueeze(0)   # keep (1,) shape for compatibility

    def _score_sentence(self, feats: torch.Tensor, tags: torch.Tensor):
        """Vectorised sequence scorer (no Python loop over positions).

        Args:
            feats: (seq_len, tagset_size) emission scores
            tags:  (seq_len,) gold tag indices
        Returns:
            score: (1,) scalar
        """
        device = feats.device
        start = torch.tensor([self.tag_to_ix["START_TAG"]], dtype=torch.long, device=device)
        tags_with_start = torch.cat([start, tags])          # (seq_len+1,)

        # Transition scores for each step: transitions[tags[t], tags[t-1]]
        trans_scores = self.transitions[tags_with_start[1:], tags_with_start[:-1]]  # (seq_len,)
        # Emission scores: feats[t, tags[t]]
        emit_scores  = feats[torch.arange(feats.size(0), device=device), tags]     # (seq_len,)

        score = (trans_scores + emit_scores).sum()
        score = score + self.transitions[self.tag_to_ix["STOP_TAG"], tags[-1]]
        return score.unsqueeze(0)
    
    def neg_log_likelihood(self, sentence: torch.Tensor, tags: torch.Tensor, words: Optional[List[str]] = None):
        """Negative log likelihood loss for single sample."""
        feats = self._get_lstm_features(sentence, words)
        forward_score = self._forward_alg(feats)
        gold_score = self._score_sentence(feats, tags)
        return forward_score - gold_score
    
    # =========================================================================
    # BATCH TRAINING METHODS (for efficient GPU utilization)
    # =========================================================================
    
    def _get_lstm_features_batch(self, sentences: torch.Tensor, lengths: List[int]):
        """
        Get LSTM features for a batch of sentences.
        
        Args:
            sentences: (batch_size, max_seq_len) - padded word indices
            lengths: List of actual sequence lengths
            
        Returns:
            tag_space: (batch_size, max_seq_len, tagset_size)
        """
        from torch.nn.utils.rnn import pack_padded_sequence, pad_packed_sequence
        
        batch_size = sentences.size(0)
        max_len = sentences.size(1)
        
        # Word embeddings: (batch_size, max_seq_len, embedding_dim)
        word_embeds = self.word_embeds(sentences)
        word_embeds = self.embed_dropout(word_embeds)
        
        # Transpose for LSTM: (max_seq_len, batch_size, embedding_dim)
        word_embeds = word_embeds.transpose(0, 1)
        
        # Pack sequences for efficient LSTM processing
        packed = pack_padded_sequence(word_embeds, lengths, enforce_sorted=True)
        
        # LSTM forward pass
        packed_out, _ = self.lstm(packed)
        
        # Unpack: (max_seq_len, batch_size, hidden_dim)
        lstm_out, _ = pad_packed_sequence(packed_out)
        
        # Apply attention if enabled (simplified for batch)
        if self.use_attention:
            # For batch training, use simpler attention weighting
            attention_input = lstm_out
            attended_out, attention_weights = self.attention(attention_input)
            attention_weights = attention_weights.unsqueeze(-1)
            lstm_out = attention_input * attention_weights
        
        # Transpose back: (batch_size, max_seq_len, hidden_dim)
        lstm_out = lstm_out.transpose(0, 1)
        
        # Project to tag space: (batch_size, max_seq_len, tagset_size)
        tag_space = self.hidden2tag(lstm_out)
        
        return tag_space
    
    def neg_log_likelihood_batch(self, sentences: torch.Tensor, tags: torch.Tensor, lengths: List[int]):
        """
        Compute batch negative log likelihood loss.
        
        Args:
            sentences: (batch_size, max_seq_len) - padded word indices
            tags: (batch_size, max_seq_len) - padded tag indices
            lengths: List of actual sequence lengths
            
        Returns:
            loss: Scalar tensor (mean loss over batch)
        """
        device = sentences.device
        batch_size = sentences.size(0)
        
        # Get features for entire batch at once
        feats_batch = self._get_lstm_features_batch(sentences, lengths)
        
        # Compute loss for each sample (CRF doesn't easily parallelize)
        total_loss = torch.zeros(1, device=device)
        for i in range(batch_size):
            seq_len = lengths[i]
            feats = feats_batch[i, :seq_len]  # (seq_len, tagset_size)
            sample_tags = tags[i, :seq_len]   # (seq_len,)
            
            forward_score = self._forward_alg(feats)
            gold_score = self._score_sentence(feats, sample_tags)
            total_loss = total_loss + (forward_score - gold_score)
        
        return total_loss / batch_size
    
    def _viterbi_decode(self, feats: torch.Tensor):
        """Viterbi decoding for inference."""
        device = feats.device
        seq_len = feats.size(0)
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
        
        # Backtrack
        best_path = [best_tag_id]
        for bptrs_t in reversed(backpointers):
            best_tag_id = bptrs_t[best_tag_id]
            best_path.append(best_tag_id)
        
        best_path.pop()  # Remove START tag
        best_path.reverse()
        return path_score, best_path
    
    def forward(self, sentence: torch.Tensor, words: Optional[List[str]] = None):
        """Forward pass for inference."""
        feats = self._get_lstm_features(sentence, words)
        score, tag_seq = self._viterbi_decode(feats)
        return score, tag_seq

class EnhancedIntentClassifier(nn.Module):
    """Enhanced intent classifier with attention and better architecture."""
    
    def __init__(self, vocab_size: int, num_intents: int, embedding_dim: int = 128,
                 hidden_dim: int = 256, num_layers: int = 2, dropout: float = 0.3):
        super(EnhancedIntentClassifier, self).__init__()
        
        self.embedding_dim = embedding_dim
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.dropout = dropout
        
        # Embeddings
        self.word_embeds = nn.Embedding(vocab_size, embedding_dim)
        self.embed_dropout = nn.Dropout(dropout)
        
        # BiLSTM
        self.lstm = nn.LSTM(
            embedding_dim,
            hidden_dim // 2,
            num_layers=num_layers,
            bidirectional=True,
            dropout=dropout if num_layers > 1 else 0,
            batch_first=False
        )
        
        # Attention
        self.attention = AttentionLayer(hidden_dim)
        
        # Classifier
        self.classifier = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, num_intents)
        )
        
        self._init_weights()
    
    def _init_weights(self):
        """Initialize model weights."""
        for name, param in self.lstm.named_parameters():
            if 'weight' in name:
                nn.init.xavier_uniform_(param)
            elif 'bias' in name:
                nn.init.zeros_(param)
        
        for module in self.classifier:
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                nn.init.zeros_(module.bias)
    
    def forward(self, sentence: torch.Tensor):
        """Forward pass."""
        # Embeddings
        embeds = self.word_embeds(sentence)
        embeds = self.embed_dropout(embeds)
        embeds = embeds.unsqueeze(1)  # (seq_len, 1, embedding_dim)
        
        # LSTM
        lstm_out, _ = self.lstm(embeds)  # (seq_len, 1, hidden_dim)
        lstm_out = lstm_out.squeeze(1)  # (seq_len, hidden_dim)
        
        # Attention
        lstm_out = lstm_out.unsqueeze(1)  # (seq_len, 1, hidden_dim)
        attended_out, _ = self.attention(lstm_out)
        
        # Classification
        logits = self.classifier(attended_out)
        return logits

class LearningRateScheduler:
    """Learning rate scheduler with warmup and decay."""
    
    def __init__(self, optimizer, warmup_steps: int = 1000, d_model: int = 256):
        self.optimizer = optimizer
        self.warmup_steps = warmup_steps
        self.d_model = d_model
        self.step_count = 0
    
    def step(self):
        """Update learning rate."""
        self.step_count += 1
        lr = self._get_lr()
        for param_group in self.optimizer.param_groups:
            param_group['lr'] = lr
    
    def _get_lr(self):
        """Calculate learning rate."""
        return (self.d_model ** -0.5) * min(
            self.step_count ** -0.5,
            self.step_count * (self.warmup_steps ** -1.5)
        )

def prepare_sequence(seq: List[str], to_ix: Dict[str, int]) -> torch.Tensor:
    """Convert sequence to tensor with proper handling of unknown words."""
    idxs = [to_ix.get(w, to_ix.get("[UNK]", 0)) for w in seq]
    return torch.tensor(idxs, dtype=torch.long)

def pad_sequences(sequences: List[torch.Tensor], pad_value: int = 0) -> torch.Tensor:
    """Pad sequences to the same length."""
    return pad_sequence(sequences, batch_first=True, padding_value=pad_value)
