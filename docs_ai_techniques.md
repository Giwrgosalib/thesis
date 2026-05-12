# AI Techniques Used in the eBay Product Search Assistant

This document explains every AI/ML technique used in the project in plain language, suitable for a thesis discussion with a professor.

---

## Overview

The system compares two generations of AI pipeline for understanding natural-language product search queries (e.g. *"red Nike running shoes under €100 size 10"*):

| | Legacy Engine | NextGen Engine |
|---|---|---|
| Core model | BiLSTM-CRF | DeBERTa-v3-base + CRF |
| Task | Named Entity Recognition (NER) | NER + Retrieval + Reranking + Personalisation |
| Training data | ~2 383 labelled queries | Same dataset, fine-tuned on pre-trained transformer |
| NER F1 (test) | 0.442 | 0.663 |
| Inference latency | ~669 ms | ~52 ms |

---

## 1. Named Entity Recognition (NER) — shared concept

**What it is:**  
NER is the task of identifying and classifying spans of text into predefined categories. In this project the categories are product attributes: `BRAND`, `COLOR`, `SIZE`, `PRICE_RANGE`, `PRODUCT_TYPE`, `MODEL`, `CONDITION`, etc. (17 canonical types in total).

**BIO tagging scheme:**  
Both engines label every token using the BIO convention:
- `B-BRAND` = Beginning of a brand span
- `I-BRAND` = Inside (continuation of) a brand span
- `O` = Outside any entity

Example:
```
Query:  red   Nike  running shoes  under  $100
Tags:   B-COL  B-BRD  O     B-PRD   O    B-PRC
```

This lets the model handle multi-word entities cleanly.

---

## 2. Legacy Engine — Enhanced BiLSTM-CRF

### 2.1 Word Embeddings
Each word in the query is mapped to a dense vector (128 dimensions) via a learned embedding lookup table. Similar words cluster together in this space. The vocabulary was built from the training corpus (~3 026 unique tokens).

### 2.2 Bidirectional LSTM (BiLSTM)
A Long Short-Term Memory (LSTM) network reads the token sequence left-to-right and right-to-left simultaneously, producing context-aware representations for each token. The bidirectional reading is crucial: to label "Air" as part of `B-BRAND` in "Nike Air Max", the model needs to see what comes *after* "Air" as well.

Architecture:
- 2 stacked BiLSTM layers (256 hidden units each direction)
- Dropout (0.3) between layers to prevent overfitting

### 2.3 Multi-Head Attention
After the BiLSTM, a self-attention layer lets each token weight the importance of every other token in the sequence. For product search this is valuable — the word "shoes" should attend strongly to "Nike" even if they are far apart in the query.

### 2.4 Conditional Random Field (CRF) Decoding
A plain classifier on top of the LSTM would label each token independently. A CRF instead models the *joint probability* of the entire tag sequence, enforcing structural constraints (e.g. `I-BRAND` cannot follow `B-COLOR`). This produces globally consistent BIO sequences rather than locally greedy ones.

The CRF uses the Viterbi algorithm at inference to find the highest-scoring valid tag path.

### 2.5 Training Setup
| Hyperparameter | Value |
|---|---|
| Optimizer | AdamW |
| Learning rate | 1 × 10⁻³ |
| LR schedule | Cosine decay with warmup |
| Batch size | 32 |
| Max epochs | 25 |
| Early stopping patience | 3 epochs (on validation F1) |
| Train/val/test split | 80 / 10 / 10 |

### 2.6 Evaluation
Entity-level F1 is computed using `seqeval` — a span must have the correct boundary *and* label to count as a true positive. This is more rigorous than token-level accuracy.

---

## 3. NextGen Engine — DeBERTa-v3-base

### 3.1 Transfer Learning & Fine-tuning
DeBERTa-v3-base (*Decoding-Enhanced BERT with Disentangled Attention*, Microsoft 2021) is a transformer model pre-trained on billions of tokens of text. Instead of training from random weights, we *fine-tune* the pre-trained model on our 2 383 product-search queries. This means:
- The model arrives already knowing grammar, word meanings, and entity patterns from general text
- We only need to adapt it to our domain-specific labels in 5 epochs

This is why it outperforms the BiLSTM-CRF trained from scratch despite using the same data.

### 3.2 Disentangled Attention (DeBERTa's key innovation)
Standard BERT uses a single attention matrix that mixes token *content* and *position* together. DeBERTa separates them into two independent matrices:
- Content-to-content attention
- Position-to-content attention (relative, not absolute)

This gives better handling of word order, which matters for product queries where "shoes Nike" and "Nike shoes" mean the same thing but "not Nike" is very different from "Nike not".

### 3.3 CRF Head (same role as in the legacy engine)
The transformer encoder's output is passed through a linear projection and a CRF decoder, for the same reasons as in the legacy engine — globally coherent BIO sequences.

### 3.4 Training Setup
| Hyperparameter | Value |
|---|---|
| Base model | microsoft/deberta-v3-base |
| Optimizer | AdamW |
| Learning rate | 2 × 10⁻⁵ |
| Batch size | 16 (gradient accumulation ×2) |
| Epochs | 5 |
| Best validation F1 | 0.757 (epoch 5) |

---

## 4. Semantic Retrieval — E5-base-v2 + FAISS

Once entities are extracted, the system must find relevant products.

### 4.1 Dense Retrieval (Bi-Encoder)
The query is encoded into a dense vector (768 dimensions) using **E5-base-v2** (Microsoft, 2023), a transformer model fine-tuned specifically for embedding-based retrieval. The product catalogue is pre-encoded into the same vector space.

**Why mean pooling?**  
E5 is trained with mean pooling — the final representation is the average of all token embeddings, weighted by the attention mask (to ignore padding). Using only the `[CLS]` token (as earlier models do) degrades retrieval quality for this family of models.

```
embedding = (Σ token_hidden * mask) / Σ mask
```

### 4.2 FAISS Index (Facebook AI Similarity Search)
Naively comparing a query vector against every product vector is O(N). FAISS provides an `IndexFlatIP` (exact inner product search on L2-normalised vectors = cosine similarity) that runs in milliseconds for thousands of products.

All vectors are L2-normalised before indexing, so cosine similarity reduces to inner product:
```
cosine(q, p) = q · p   (when ||q|| = ||p|| = 1)
```

---

## 5. Cross-Encoder Reranking

The bi-encoder retrieves the top-100 candidates quickly but somewhat coarsely (each vector is a compressed summary of the whole sentence). A **cross-encoder** (`cross-encoder/ms-marco-MiniLM-L-6-v2`) then *reranks* the top 100 by reading the query and each candidate *together* — allowing full attention between them — and scoring relevance more precisely.

This two-stage approach (retrieve cheap → rerank expensive) is standard in modern search systems. It keeps latency low while maximising ranking quality.

---

## 6. Retrieval-Augmented Generation (RAG)

Before presenting results to the user, a small language model rewrites the query using the retrieved products as context. This step:
- Resolves ambiguity (e.g. "Apple" → "Apple iPhone" given electronics context)
- Expands abbreviations ("sz 10" → "size 10")
- Normalises phrasing for downstream retrieval

The rewritten query is validated for semantic similarity to the original (cosine > 0.7) to prevent hallucination.

---

## 7. Contextual Bandit Personalisation

The ranking order is adjusted per user using a **Contextual Thompson Sampling** bandit.

**What is a bandit?**  
A multi-armed bandit balances *exploration* (trying items we haven't shown the user before) vs *exploitation* (showing items we know they like). The contextual variant conditions decisions on feature vectors describing the user and query.

**Thompson Sampling:**  
Instead of storing a single estimate of each item's value, the model maintains a Bayesian posterior (mean + uncertainty). At each request it samples from this posterior — items with high uncertainty are more likely to be explored. As the user interacts, the posterior narrows.

The model uses a linear Bayesian update:
```
A ← A + φφᵀ   (add outer product of feature vector on reward)
b ← b + r·φ   (accumulate reward-weighted features)
θ = A⁻¹b      (posterior mean weight vector)
```

---

## 8. Active Learning

When the NER model produces a prediction with low confidence (entropy above a threshold), the query is flagged as a candidate for human review and re-labelling. This creates a feedback loop:

```
Low-confidence prediction → human labels it → added to training set → model retrained
```

Uncertainty is measured by **entropy** over the predicted tag probability distribution. High entropy = the model is unsure between competing labels.

---

## 9. Knowledge Graph Query Expansion

A lightweight knowledge graph stores typed relationships between entities (e.g. `Nike —[is_brand_of]→ Footwear`). When the NER extracts a brand, the graph is traversed to expand the query intent with related categories. This helps retrieval even for queries that omit the product category.

---

## 10. Evaluation Metrics

| Metric | What it measures | Used for |
|---|---|---|
| Entity-level F1 (seqeval) | Precision × Recall balance for NER spans | NER quality |
| Recall@k | % of relevant items in top-k results | Retrieval coverage |
| MRR (Mean Reciprocal Rank) | How high the first relevant item ranks | Retrieval ranking |
| NDCG@k | Discounted Cumulative Gain — rewards relevant items ranked higher | Reranker quality |
| Inference latency (ms) | Wall-clock time per query | Production readiness |

---

## Summary for the Thesis

The project demonstrates a progression from a **classical sequence labelling approach** (hand-crafted embeddings + BiLSTM + CRF, trained from scratch) to a **modern transformer pipeline** (pre-trained DeBERTa fine-tuned on domain data). The 50% F1 improvement and 12.8× speed-up are directly attributable to transfer learning — the transformer arrives with rich linguistic priors that the BiLSTM must laboriously learn from limited data.

The retrieval, reranking, and personalisation components extend the system from NER-only to a full end-to-end search assistant, demonstrating how NER is a foundational component in larger ML pipelines rather than an end in itself.
