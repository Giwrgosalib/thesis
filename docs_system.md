# System Documentation — eBay AI Product Search Assistant

A full-stack AI-powered search assistant that takes natural-language product queries (e.g. *"red Nike running shoes under €100 size 10"*), understands them with NLP, retrieves relevant eBay listings, and personalises results per user. The project compares two generations of AI engine as part of a diploma thesis.

---

## Table of Contents

1. [High-Level Architecture](#1-high-level-architecture)
2. [Repository Layout](#2-repository-layout)
3. [Legacy Backend (`backend/`)](#3-legacy-backend)
4. [NextGen Backend (`backend_nextgen/`)](#4-nextgen-backend)
5. [Frontend (`frontend/`)](#5-frontend)
6. [API Reference](#6-api-reference)
7. [Data & Models](#7-data--models)
8. [Configuration & Environment](#8-configuration--environment)
9. [Running the Project](#9-running-the-project)
10. [Evaluation & Results](#10-evaluation--results)

---

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Browser / ngrok                       │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP
┌──────────────────────────▼──────────────────────────────────┐
│              Vue 3 SPA  (port 8080)                          │
│  LoginView → FullApp (chat + product panel + engine toggle)  │
└──────────┬───────────────────────────┬───────────────────────┘
           │ /auth /api/classic        │ /api/nextgen
           ▼                           ▼
┌─────────────────────┐   ┌─────────────────────────────────────┐
│  Legacy Flask API   │   │       NextGen Flask API              │
│   (port 5000)       │   │         (port 5001)                  │
│                     │   │                                       │
│  eBay OAuth         │   │  NextGenAIOrchestrator               │
│  Session mgmt       │   │  ┌─────────────────────────────┐    │
│  User preferences   │   │  │ 1. DeBERTa NER              │    │
│  EBayNLP (legacy)   │   │  │ 2. Knowledge Graph expansion │    │
│  EBay Browse API    │   │  │ 3. E5 + FAISS retrieval      │    │
│                     │   │  │ 4. Cross-encoder reranking   │    │
└────────┬────────────┘   │  │ 5. Thompson Sampling bandit  │    │
         │                │  │ 6. RAG query rewriting        │    │
         ▼                │  └─────────────────────────────┘    │
┌─────────────────┐       └──────────────┬──────────────────────┘
│    MongoDB      │                      │
│  • auth_sessions│◄─────────────────────┘
│  • preferences  │  (preference read/write)
│  • search_hist  │
└─────────────────┘
```

---

## 2. Repository Layout

```
.
├── backend/                    # Legacy BiLSTM-CRF engine
│   ├── app.py                  # Flask application + all routes
│   ├── custom_nlp.py           # EBayNLP — training + inference
│   ├── enhanced_models.py      # EnhancedBiLSTM_CRF architecture
│   ├── ebay_service.py         # eBay Browse API wrapper
│   ├── config.py               # Configuration from env vars
│   ├── metrics.py              # Analytics helpers
│   ├── utils/                  # Logging, validation, rate-limiting, error handlers
│   ├── models/enhanced/        # Trained model weights (.pth) + model_info.json
│   └── data/                   # Training CSVs, NLP dictionaries
│
├── backend_nextgen/            # NextGen DeBERTa pipeline
│   ├── orchestrator.py         # NextGenAIOrchestrator — full pipeline
│   ├── api/experimental.py     # Flask blueprint — /api/nextgen/* routes
│   ├── nlp/
│   │   ├── transformer_ner.py  # TransformerCRFNER model class
│   │   └── inference.py        # TransformerNERInference wrapper
│   ├── retrieval/dual_encoder.py       # E5 bi-encoder + FAISS
│   ├── ranking/neural_reranker.py      # Cross-encoder reranker
│   ├── rag/
│   │   ├── pipeline.py         # RAGPipeline — context + prompt + generation
│   │   └── generator.py        # GenerativeResponder (LLM wrapper)
│   ├── personalization/contextual_bandit.py  # Thompson Sampling
│   ├── active_learning/loop.py         # UncertaintySampler
│   ├── knowledge/graph_builder.py      # KnowledgeGraph (NetworkX)
│   ├── observability/metrics.py        # MetricSink → SQLite
│   ├── config/
│   │   ├── nextgen_config.yml  # Runtime configuration
│   │   ├── entity_schema.py    # 17 canonical labels + normalisation
│   │   └── loader.py           # Config YAML → NextGenConfig dataclass
│   ├── models/ner/             # Fine-tuned DeBERTa weights (gitignored)
│   └── data/retrieval/         # FAISS index .npy + metadata .npy
│
├── frontend/                   # Vue 3 SPA
│   ├── src/
│   │   ├── components/
│   │   │   ├── FullApp.vue     # Main two-panel layout
│   │   │   ├── LoginView.vue   # eBay OAuth landing page
│   │   │   ├── ChatBox.vue     # Floating chat button
│   │   │   └── OnboardingModal.vue  # Brand/category preference setup
│   │   ├── services/
│   │   │   └── auth.js         # eBay OAuth helpers + session management
│   │   └── main.js
│   ├── vue.config.js           # Dev server + proxy rules
│   └── Dockerfile
│
├── scripts/                    # Training, evaluation, comparison tools
├── run_nextgen.py              # Standalone NextGen Flask server
├── Dockerfile.gpu              # Unified Docker image (both backends)
├── start_backends.sh           # Launches both Flask apps in one container
├── docker-compose.yml          # Full stack orchestration
├── requirements.txt            # Python dependencies
├── docs_ai_techniques.md       # AI/ML explanation for thesis
└── docs_system.md              # This file
```

---

## 3. Legacy Backend

### 3.1 Flask Application (`backend/app.py`)

The main entry point for the legacy engine. Handles authentication, session management, user preferences, and routes search queries through the legacy NLP pipeline.

**All routes:**

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/health` | Health check — returns DB + NextGen service status |
| GET | `/auth/ebay-login` | Initiates eBay OAuth2 flow; generates `client_id` for session tracking |
| GET | `/auth/ebay-callback` | eBay redirects here after user grants permission; exchanges code for token |
| GET | `/auth/poll-status` | Frontend polls this to know when OAuth completed |
| POST | `/auth/check-session` | Validates a session token |
| POST | `/auth/logout` | Invalidates session |
| POST | `/api/classic/search` | Search via legacy NLP + eBay Browse API |
| GET | `/metrics` | HTML analytics dashboard |
| GET | `/metrics/feedback` | JSON feedback analytics |
| GET | `/metrics/users` | JSON user analytics |
| GET | `/` and `/<path>` | Serves the Vue SPA (production static build) |

**Authentication flow:**
1. Frontend hits `/auth/ebay-login` → backend generates a `client_id`, redirects user to eBay's OAuth consent page
2. eBay redirects back to `/auth/ebay-callback` with an authorisation code
3. Backend exchanges the code for an eBay access token, stores session in MongoDB
4. Frontend polls `/auth/poll-status?client_id=X` until the session is ready
5. On success, frontend receives `session_token` for all subsequent requests

### 3.2 NLP Engine (`backend/custom_nlp.py` + `backend/enhanced_models.py`)

**`EBayNLP`** wraps training and inference for the BiLSTM-CRF model.

Key methods:

| Method | What it does |
|--------|-------------|
| `extract_entities(query)` | Full inference pipeline: tokenise → model forward → CRF Viterbi → post-process → return entity dict |
| `train(dataset_path)` | 80/10/10 split, 25 epochs max, AdamW + cosine LR, early stopping on val F1 |
| `_create_aligned_tags()` | Aligns CSV entity spans to spaCy tokens using BIO encoding |
| `_post_process_entities()` | Heuristic enrichment — keyword matching, price regex, size patterns |
| `_evaluate_ner_f1()` | seqeval entity-level F1 on validation set |

**`EnhancedBiLSTM_CRF`** architecture:

```
Input tokens
     │
     ▼
Word embeddings (128-dim)
     │
     ▼
2-layer Bidirectional LSTM (256 hidden units each direction)
     │
     ▼
Multi-head self-attention
     │
     ▼
Linear projection → tag space (one logit per BIO label)
     │
     ▼
CRF decoder (Viterbi at inference, forward algorithm at training)
     │
     ▼
BIO tag sequence → entity spans
```

Training configuration:

| Setting | Value |
|---------|-------|
| Optimizer | AdamW |
| Learning rate | 1 × 10⁻³ |
| LR schedule | Cosine decay with warmup |
| Batch size | 32 |
| Max epochs | 25 (early stop patience = 3) |
| Best epoch | 9 |
| Best val F1 | 0.186 |
| Entity types | 144 (full schema from training data) |

### 3.3 eBay Service (`backend/ebay_service.py`)

Wraps the eBay Browse API v1.

| Method | eBay API call |
|--------|--------------|
| `search(intent)` | `GET /buy/browse/v1/item_summary/search` |
| `_get_bearer_token()` | `POST /identity/v1/oauth2/token` (client credentials) |

The intent dict from the NLP engine is translated into eBay-specific query parameters:
- `q` — main search terms
- `filter` — price range, item condition
- `aspect_filter` — brand, color, size (eBay category-specific facets)
- `category_ids` — maps named categories to eBay numeric IDs (e.g. `9355` = smartphones)

Results are re-ranked locally by brand match, category match, and stored user preference boosts before being returned.

---

## 4. NextGen Backend

### 4.1 Pipeline Overview (`backend_nextgen/orchestrator.py`)

`NextGenAIOrchestrator` composes all AI components in a single `handle_query()` call:

```
User query (string)
        │
        ▼
1. TransformerNERInference.extract_entities()
   → DeBERTa tokenisation + forward pass + CRF Viterbi
   → List of {label, value, score}
        │
        ├──► UncertaintySampler (entropy > threshold → flag for review)
        │
        ▼
2. KnowledgeGraph._kg_expand_intent()
   → Brand node → traverse → expand with related categories
        │
        ▼
3. DualEncoderRetriever.retrieve()
   → E5-base-v2 mean-pool embedding of query
   → FAISS IndexFlatIP cosine search → top-20 candidates
        │
        ▼
4. NeuralReRanker.rerank()
   → Cross-encoder scores (query, item) pairs
   → Re-sorted top-20
        │
        ▼
5. ContextualThompsonSampling.select()
   → Bayesian posterior sample per candidate
   → Personalised ordering
        │
        ▼
6. RAGPipeline.answer()
   → Context from top-5 items
   → LLM generates conversational answer + citations
        │
        ▼
7. MetricSink.record()
   → Logs per-stage latencies, entities, scores → SQLite
        │
        ▼
Response: {answer, items, entities, latencies}
```

### 4.2 NER Inference (`backend_nextgen/nlp/inference.py`)

`TransformerNERInference` auto-detects the model format on load:
- **HuggingFace format** (`AutoModelForTokenClassification`) — used for the main trained model
- **Custom CRF format** (`TransformerCRFNER`) — used for the training pipeline

At inference, subword tokens are mapped back to original words using `word_ids`, then BIO spans are decoded into entity dicts.

**Model:** `microsoft/deberta-v3-base` fine-tuned for 5 epochs on 2 383 labelled product-search queries.

Training results:

| Epoch | Val F1 | Val Precision | Val Recall |
|-------|--------|---------------|------------|
| 1 | 0.550 | — | — |
| 2 | 0.705 | — | — |
| 3 | 0.742 | — | — |
| 4 | 0.754 | — | — |
| **5** | **0.757** | **0.760** | **0.754** |

**Entity types (17 canonical):** `BRAND`, `PRODUCT_TYPE`, `CATEGORY`, `MODEL`, `COLOR`, `SIZE`, `MATERIAL`, `PRICE_RANGE`, `CONDITION`, `SHIPPING`, `FEATURE`, `TECH`, `STORAGE`, `CONNECTIVITY`, `USAGE`, `INCLUSIONS`, `BRAND_EXCLUSION`

### 4.3 Retrieval (`backend_nextgen/retrieval/dual_encoder.py`)

`DualEncoderRetriever` wraps `intfloat/e5-base-v2`:

- **Pooling:** Attention-masked mean pooling (not CLS) — required by E5's training objective
- **Normalisation:** L2 normalised → cosine similarity = dot product
- **Index:** `faiss.IndexFlatIP` (exact search, 768-dim)
- **Index size:** 2 383 product embeddings (~14 MB .npy file)

```python
# Mean pooling (correct for E5)
mask = attention_mask.unsqueeze(-1).float()
embedding = (last_hidden * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
```

Retrieval metrics (self-retrieval on training corpus):

| Metric | Score |
|--------|-------|
| Recall@1 | 1.000 |
| Recall@5 | 1.000 |
| Recall@10 | 1.000 |
| MRR | 1.000 |
| NDCG@5 | 1.000 |

### 4.4 Reranking (`backend_nextgen/ranking/neural_reranker.py`)

`NeuralReRanker` wraps `cross-encoder/ms-marco-MiniLM-L-6-v2`:

- Takes (query, item_text) pairs as joint input
- Full cross-attention between query and item — more precise than bi-encoder
- Scores all top-100 candidates, returns top-20 `RankedItem` objects
- Configuration: `candidate_pool=100`, `rerank_top_k=20`

### 4.5 RAG Pipeline (`backend_nextgen/rag/pipeline.py`)

`RAGPipeline` wraps a generative language model to produce conversational responses:

1. Top-5 retrieved items formatted into a context block (title, price, description)
2. Prompt constructed — "search" mode for product discovery, "explain" mode for item detail
3. Generator called (`backend_nextgen/models/query_rewriter`)
4. Response validated for hallucination: semantic similarity to original query must be ≥ 0.7
5. Returns `RAGResponse(answer, citations)`

### 4.6 Personalisation (`backend_nextgen/personalization/contextual_bandit.py`)

`ContextualThompsonSampling` implements a linear contextual bandit:

**State:** Gram matrix `A` (feature_dim × feature_dim) + reward vector `b` (feature_dim)

**Selection:** For each candidate, sample θ ~ N(A⁻¹b, α²·A⁻¹), compute score = θᵀφ, pick argmax

**Update (on user click):**
```
A ← A + φφᵀ
b ← b + reward · φ
```

**Exploration rate:** 0.1 — ensures new products get shown even if past preferences exist

State persisted to `bandit_model.npz` between sessions.

### 4.7 Active Learning (`backend_nextgen/active_learning/loop.py`)

`UncertaintySampler` monitors NER confidence in real time:

- After each NER prediction, computes Shannon entropy H = -Σ p log p over tag probabilities
- If entropy > 0.25 threshold → wraps as `ActiveLearningExample` and logs for human review
- Creates a flywheel: low-confidence → human labels → retrain → higher confidence

### 4.8 Knowledge Graph (`backend_nextgen/knowledge/graph_builder.py`)

`KnowledgeGraph` is a typed NetworkX `MultiDiGraph`:

- **Nodes:** Entities (brands, categories, products) with label + attribute dict
- **Edges:** Typed relations (`is_brand_of`, `belongs_to`, `related_to`)
- **Seeded on startup** from `known_brands` + `category_keywords` dictionaries
- **Query expansion:** When NER finds a brand, graph is traversed to add implicit category context

Example: query "Nike shoes" → KG expansion adds `CATEGORY=Footwear` even if not in query.

### 4.9 Entity Schema (`backend_nextgen/config/entity_schema.py`)

Defines the 17 canonical labels and maps aliases from both engines to them:

```python
normalise_label("PRICE")          → "PRICE_RANGE"
normalise_label("PRODUCT")        → "PRODUCT_TYPE"
normalise_label("TECH_SPEC")      → "TECH"
normalise_label("STORAGE_CAPACITY") → "STORAGE"
```

Used by `compare_engines.py` to ensure fair A/B comparison.

### 4.10 Observability (`backend_nextgen/observability/metrics.py`)

`MetricSink` writes to a SQLite database at runtime:

- Per-query records: query text, latency breakdown (NER / retrieval / reranking / RAG / total), entity JSON, top item IDs
- `GET /api/nextgen/metrics` returns aggregated stats over a configurable time window

---

## 5. Frontend

### 5.1 Vue SPA Overview

Built with **Vue 3 + Vuetify + Tailwind CSS**, served by Vue CLI dev server (port 8080).

### 5.2 Components

**`LoginView.vue`**
- Animated landing page with floating product icons
- "Login with eBay" button → calls `appAuth.initiateEbayLogin()` → redirects to eBay OAuth
- Polls `/auth/poll-status` after OAuth redirect back
- On success → navigates to `FullApp`

**`FullApp.vue`** — Main application (two-panel layout)

| Panel | Content |
|-------|---------|
| Left (35%) | Chat history, query input box, engine toggle button |
| Right (65%) | Product grid with sorting/filtering, item detail cards |

Key features:
- **Engine toggle** — switches between legacy (`/api/classic/search`) and nextgen (`/api/nextgen/query`) in real time
- **Onboarding modal** — brand/category preference setup saved to backend
- **Responsive** — stacks vertically on mobile

**`ChatBox.vue`** — Floating button with eBay branding that opens the app in a new tab

**`OnboardingModal.vue`** — Multi-select chips for brand + category preferences, POST to `/api/preferences`

### 5.3 Proxy Configuration (`frontend/vue.config.js`)

The Vue dev server proxies API calls to the correct backend:

```
/api/nextgen/*  →  http://backend:5001  (NextGen engine)
/api/*          →  http://backend:5000  (Legacy engine)
/auth/*         →  http://backend:5000
/health         →  http://backend:5000
```

---

## 6. API Reference

### Legacy API (port 5000)

```
POST /api/classic/search
Body: { "query": "red Nike shoes", "user_id": "...", "session_token": "..." }
Response: { "items": [...], "entities": {...}, "intent": "search_product" }
```

### NextGen API (port 5001)

```
POST /api/nextgen/query
Headers: Authorization: Bearer <session_token>
Body: { "query": "red Nike shoes under 100", "user_id": "...", "preferences": {...} }
Response: {
  "answer": "Here are some Nike running shoes...",
  "items": [{ "id", "title", "price", "url", "score" }, ...],
  "entities": [{ "label": "BRAND", "value": "Nike" }, ...],
  "latencies": { "ner_ms": 48, "retrieval_ms": 3, "reranking_ms": 12, ... }
}

POST /api/nextgen/feedback
Body: { "user_id": "...", "item_id": "...", "reward": 1.0 }

GET  /api/nextgen/metrics?window=3600
Response: { "avg_latency_ms": 52, "queries_count": 120, ... }
```

---

## 7. Data & Models

### Datasets

| File | Rows | Used for |
|------|------|---------|
| `backend/data/train_enriched.csv` | 2 383 | Both engines' training + retrieval index |
| `backend/data/test_dataset_fixed.csv` | 265 | A/B evaluation |

CSV columns: `query`, `entities` (list of (start, end, label) tuples), `intent`

### Model Files

| Model | Path | Size | Tracked in git |
|-------|------|------|---------------|
| Legacy BiLSTM-CRF weights | `backend/models/enhanced/enhanced_ner_model.pth` | ~4.8 MB | Yes |
| Legacy model config | `backend/models/enhanced/model_info.json` | tiny | Yes |
| NextGen DeBERTa weights | `backend_nextgen/models/ner/` | ~750 MB | **No** (gitignored) |
| FAISS product index | `backend_nextgen/data/retrieval/product_index.npy` | ~14 MB | Yes |
| FAISS metadata | `backend_nextgen/data/retrieval/product_metadata.npy` | ~500 KB | Yes |
| Bandit model state | `backend_nextgen/personalization/bandit_model.npz` | tiny | Yes |

> DeBERTa weights must be retrained locally (`scripts/train_transformer_ner.py`) or downloaded separately.

---

## 8. Configuration & Environment

### Required environment variables (`backend/.env`)

```bash
# eBay Developer API (https://developer.ebay.com/my/keys)
EBAY_CLIENT_ID=...
EBAY_CLIENT_SECRET=...
EBAY_DEV_ID=...
EBAY_RUNAME=...
EBAY_API_ENVIRONMENT=PRODUCTION   # or SANDBOX

# MongoDB
MONGO_URI=mongodb://localhost:27017/ebay_ai

# Flask
PORT=5000
FLASK_DEBUG=False
FRONTEND_URL=http://localhost:8080
```

### NextGen runtime (`backend_nextgen/config/nextgen_config.yml`)

```yaml
nlp:
  model_name: microsoft/deberta-v3-base
  device: cpu          # change to cuda for GPU
  confidence_threshold: 0.55
  trained_model_path: models/ner

retrieval:
  encoder_name: intfloat/e5-base-v2
  top_k: 20

ranking:
  model_name: cross-encoder/ms-marco-MiniLM-L-6-v2
  rerank_top_k: 20

personalization:
  exploration_rate: 0.1
```

---

## 9. Running the Project

### Docker (recommended)

```bash
# Full stack — both backends + frontend + ngrok
docker compose up --build

# Services:
#   Frontend  → http://localhost:8080
#   Legacy    → http://localhost:5000
#   NextGen   → http://localhost:5001
#   ngrok     → http://localhost:4040
```

### Local

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm

python backend/app.py          # Legacy  → :5000
python run_nextgen.py          # NextGen → :5001
cd frontend && npm run serve   # UI      → :8080
```

### Retrain models

```bash
# Legacy BiLSTM-CRF
python scripts/_train_legacy.py

# NextGen DeBERTa NER
python backend_nextgen/scripts/train_transformer_ner.py \
    --data backend/data/train_enriched.csv \
    --output backend_nextgen/models/ner \
    --epochs 5

# Rebuild FAISS retrieval index
python scripts/build_retrieval_index.py \
    --data backend/data/train_enriched.csv \
    --output backend_nextgen/data/retrieval/
```

---

## 10. Evaluation & Results

### A/B NER Comparison (50 test queries)

| Metric | Legacy BiLSTM-CRF | NextGen DeBERTa |
|--------|-------------------|-----------------|
| F1 vs gold labels | 0.442 | **0.663** (+50%) |
| Avg inference latency | 669 ms | **52 ms** (12.8× faster) |
| Entity-count wins | 17 / 50 | 14 / 50 |
| Ties | 19 / 50 | 19 / 50 |

### Retrieval Quality (E5 + FAISS, n=2 383)

| Metric | Score |
|--------|-------|
| Recall@1 | 1.000 |
| Recall@10 | 1.000 |
| MRR | 1.000 |
| NDCG@5 | 1.000 |

Full metrics: `results/thesis_summary.json`  
Training curves: `results/legacy_training_curve.png`, `results/nextgen_training_curve.png`  
Comparison chart: `results/engine_comparison.png`

### Scripts

| Script | What it measures |
|--------|-----------------|
| `scripts/compare_engines.py` | Side-by-side entity extraction, latency, A/B |
| `scripts/evaluate_retrieval.py` | Recall@k, MRR, NDCG |
| `scripts/evaluate_ai_engines.py` | NER precision / recall / F1 per entity type |
