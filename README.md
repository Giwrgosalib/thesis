# eBay AI Product Search Assistant

A diploma-thesis project comparing two NER-driven search pipelines for eBay product queries:

| Engine | Architecture | NER F1 (vs gold) | Avg Latency |
|--------|-------------|-------------------|-------------|
| **Legacy** | Enhanced BiLSTM-CRF + Attention | 0.442 | 669 ms |
| **NextGen** | DeBERTa-v3-base + CRF head | **0.663** | **52 ms** |

NextGen is **50% more accurate** and **12.8× faster** than the Legacy engine.

---

## Repository Structure

```
.
├── backend/                    # Legacy BiLSTM-CRF engine (Flask API)
│   ├── custom_nlp.py           # Main NLP class (train + inference)
│   ├── enhanced_models.py      # EnhancedBiLSTM_CRF architecture
│   ├── models/enhanced/        # Trained model weights (.pth)
│   └── data/                   # Training datasets and NLP dictionaries
│
├── backend_nextgen/            # NextGen DeBERTa pipeline (Flask API)
│   ├── orchestrator.py         # Main pipeline orchestrator
│   ├── nlp/                    # DeBERTa NER wrapper
│   ├── retrieval/              # E5 encoder + FAISS retrieval
│   ├── reranking/              # Cross-encoder reranker
│   ├── rag/                    # Query rewriting (RAG)
│   ├── personalization/        # Contextual Thompson Sampling bandit
│   ├── active_learning/        # Uncertainty-based sample selection
│   ├── knowledge/              # Knowledge graph (brand→category)
│   ├── config/                 # entity_schema.py, nextgen_config.yml
│   ├── models/ner/             # Fine-tuned DeBERTa weights
│   └── data/retrieval/         # E5 FAISS index + metadata
│
├── frontend/                   # React/Vite UI
├── scripts/                    # Training, evaluation, comparison utilities
├── results/                    # Metrics, charts, A/B comparison output
├── requirements.txt            # Unified Python dependencies
├── docker-compose.yml          # Docker Compose (CPU + GPU variants)
└── Dockerfile.gpu              # GPU-enabled Docker image
```

---

## Architecture Overview

### Legacy Engine (BiLSTM-CRF)
```
Query → spaCy tokenisation → word embeddings (128-dim)
      → 2-layer BiLSTM (256 hidden) + multi-head attention
      → CRF decoding → BIO tag sequence
      → heuristic post-processing → entity dict
```

### NextGen Engine (DeBERTa + Retrieval)
```
Query → DeBERTa-v3-base tokenisation
      → fine-tuned DeBERTa encoder → CRF head → BIO entities
      → Knowledge Graph expansion (brand → category)
      → E5-base-v2 embedding → FAISS (top-20) retrieval
      → cross-encoder reranking (MiniLM-L-6-v2)
      → contextual bandit personalisation
      → RAG query rewriting → ranked product list
```

---

## Results

### NER Performance (50 A/B test queries)

| Metric | Legacy BiLSTM-CRF | NextGen DeBERTa |
|--------|-------------------|-----------------|
| F1 vs gold labels | 0.442 | **0.663** |
| Avg inference latency | 669 ms | **52 ms** |
| Entity-count wins | 17 / 50 | 14 / 50 |
| Ties | 19 / 50 | 19 / 50 |

### NextGen NER Training (5 epochs, DeBERTa fine-tuning)

| Epoch | Val F1 | Val Precision | Val Recall |
|-------|--------|---------------|------------|
| 1 | 0.550 | — | — |
| 2 | 0.705 | — | — |
| 3 | 0.742 | — | — |
| 4 | 0.754 | — | — |
| **5** | **0.757** | **0.760** | **0.754** |

### Retrieval (E5-base-v2 + FAISS, n=2383)

| Metric | Score |
|--------|-------|
| Recall@1 | 1.000 |
| Recall@10 | 1.000 |
| MRR | 1.000 |
| NDCG@5 | 1.000 |

> Training curves and comparison charts: `results/legacy_training_curve.png`, `results/nextgen_training_curve.png`, `results/engine_comparison.png`

---

## Quick Start

### Option 1 — Docker Compose (recommended)

```bash
# CPU-only
docker-compose up

# GPU (requires NVIDIA Docker runtime)
docker-compose -f docker-compose.yml -f docker-compose.gpu.yml up
```

Services started:
- Legacy API → http://localhost:5000
- NextGen API → http://localhost:5001
- Frontend → http://localhost:3000

### Option 2 — Local (Windows/Linux/macOS)

**Prerequisites:** Python 3.10+, Node 18+

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# For CUDA 12.4 GPU acceleration:
pip install torch==2.6.0+cu124 torchvision==0.21.0+cu124 \
    --index-url https://download.pytorch.org/whl/cu124

# 2. Download/verify spaCy model
python -m spacy download en_core_web_sm

# 3. Start Legacy API (port 5000)
python backend/app.py

# 4. Start NextGen API (port 5001)
python run_nextgen.py

# 5. Start Frontend (port 3000)
cd frontend && npm install && npm run dev
```

### Windows shortcut

```bat
setup_windows.bat   # installs deps + verifies setup
start_ngrok.bat     # start ngrok tunnel for demo
```

---

## Training

### Retrain Legacy BiLSTM-CRF

```bash
python scripts/_train_legacy.py
# Writes: backend/models/enhanced/enhanced_ner_model.pth
#         backend/models/enhanced/model_info.json
```

### Retrain NextGen DeBERTa NER

```bash
python backend_nextgen/scripts/train_transformer_ner.py \
    --data backend/data/train_enriched.csv \
    --output backend_nextgen/models/ner \
    --epochs 5
```

### Rebuild Retrieval Index

```bash
python scripts/build_retrieval_index.py \
    --data backend/data/train_enriched.csv \
    --output backend_nextgen/data/retrieval/
```

---

## Evaluation

### A/B Comparison (50 queries)

```bash
python scripts/compare_engines.py \
    --input backend/data/test_dataset_fixed.csv \
    --output results/ab_comparison.json \
    --max_samples 50
```

### Retrieval Metrics

```bash
python scripts/evaluate_retrieval.py
# Output: results/retrieval_metrics.json
```

### Single-query interactive test

```bash
python scripts/compare_engines.py
# Type a query at the prompt, e.g.:
#   Query> red Nike running shoes under $100 size 10
```

---

## Key Files

| File | Purpose |
|------|---------|
| `backend/custom_nlp.py` | Legacy engine — training + inference |
| `backend/enhanced_models.py` | EnhancedBiLSTM_CRF architecture |
| `backend_nextgen/orchestrator.py` | NextGen pipeline orchestrator |
| `backend_nextgen/config/entity_schema.py` | Canonical entity labels + normalisation |
| `backend_nextgen/config/nextgen_config.yml` | NextGen runtime configuration |
| `scripts/compare_engines.py` | A/B comparison harness |
| `results/thesis_summary.json` | All key metrics in one file |

---

## Environment Variables

Copy `.env.example` and fill in:

```bash
cp backend/.env.example backend/.env
```

See `backend/.env.example` for required keys (eBay API credentials, Flask secret).

---

## Dependencies

See `requirements.txt`. Key packages:

- `torch==2.6.0` + `transformers==4.57.3`
- `faiss-cpu==1.12.0`
- `spacy==3.8.5`
- `seqeval==1.2.2` (entity-level F1)
- `torchcrf==1.1.0`
- `flask==2.0.1`
