# CLAUDE.md — Developer Reference

This file documents commands, model locations, and key decisions for contributors and Claude Code.

---

## Project Layout

```
backend/            Legacy BiLSTM-CRF engine (Flask, port 5000)
backend_nextgen/    NextGen DeBERTa pipeline  (Flask, port 5001)
frontend/           React/Vite UI             (port 3000)
scripts/            Standalone training, eval, and comparison tools
results/            Metric outputs and charts
```

---

## Common Commands

### Start APIs

```bash
# Legacy (port 5000)
python backend/app.py

# NextGen (port 5001)
python run_nextgen.py
```

### Training

```bash
# Legacy BiLSTM-CRF (25 epochs, early-stop pat=3, AdamW, cosine LR)
python scripts/_train_legacy.py

# NextGen DeBERTa NER (5 epochs fine-tuning)
python backend_nextgen/scripts/train_transformer_ner.py \
    --data backend/data/train_enriched.csv \
    --output backend_nextgen/models/ner \
    --epochs 5

# Rebuild FAISS retrieval index
python scripts/build_retrieval_index.py \
    --data backend/data/train_enriched.csv \
    --output backend_nextgen/data/retrieval/
```

### Evaluation

```bash
# Full A/B comparison (50 test queries)
python scripts/compare_engines.py \
    --input backend/data/test_dataset_fixed.csv \
    --output results/ab_comparison.json \
    --max_samples 50

# Retrieval recall/MRR/NDCG
python scripts/evaluate_retrieval.py

# Single-query interactive
python scripts/compare_engines.py
```

---

## Model Locations

| Model | Path | Size |
|-------|------|------|
| Legacy enhanced weights | `backend/models/enhanced/enhanced_ner_model.pth` | ~4.8 MB |
| Legacy model config | `backend/models/enhanced/model_info.json` | tiny |
| NextGen DeBERTa weights | `backend_nextgen/models/ner/` | ~750 MB |
| NextGen tokenizer | `backend_nextgen/models/ner/` | ~2 MB |
| FAISS product index | `backend_nextgen/data/retrieval/product_index.npy` | ~14 MB |
| FAISS metadata | `backend_nextgen/data/retrieval/product_metadata.npy` | ~500 KB |

> **Note:** NextGen DeBERTa weights are excluded from git (`.gitignore`). Download or retrain locally.
> The FAISS index IS tracked (under `backend_nextgen/data/retrieval/`).

---

## Datasets

| File | Rows | Purpose |
|------|------|---------|
| `backend/data/train_enriched.csv` | ~2383 | Training + retrieval index |
| `backend/data/test_dataset_fixed.csv` | ~265 | A/B evaluation |

---

## Key Configuration

### NextGen runtime: `backend_nextgen/config/nextgen_config.yml`

- `nlp.trained_model_path: models/ner` — relative to `backend_nextgen/`
- `retrieval.index_path: backend_nextgen/data/retrieval/product_index.npy`
- `nlp.confidence_threshold: 0.55` — below this triggers active learning flag
- `nlp.device: cuda` — change to `cpu` if no GPU

### Legacy entity normalization: `backend_nextgen/config/entity_schema.py`

- `CANONICAL_LABELS` — 17 canonical entity types
- `normalise_label(raw)` — maps aliases to canonical labels
- Used by both engines in `scripts/compare_engines.py`

---

## Architecture Notes

### Legacy training improvements (plan A1–A7, implemented)
- 80/10/10 train/val/test split with early stopping (patience=3)
- Mini-batch (batch=32), AdamW (lr=1e-3), cosine LR schedule
- Uses `EnhancedBiLSTM_CRF` (2-layer, attention, dropout=0.3)
- Entity-level F1 logged each epoch via `seqeval`
- Word-boundary regex for keyword matching (A6)
- spaCy tokenization enforced at both train and inference (A7)

### NextGen improvements (plan B1–B10, implemented)
- Multi-type BIO NER training (not just BRAND) — 17 entity types
- CRF head on top of DeBERTa for coherent sequence decoding
- E5-base-v2 with **mean pooling** (attention-masked), not CLS
- FAISS `IndexFlatIP` on L2-normalised embeddings
- Per-component latency tracking (NER / retrieval / reranking / RAG)
- Active learning: `UncertaintySampler` wired to NER confidence scores
- Knowledge graph seeding + brand→category query expansion
- `eval()` replaced with `json.loads()` in observability metrics (security fix)

---

## Observability / Metrics DB

```bash
# The metrics SQLite DB is runtime-only (gitignored):
backend_nextgen/data/observability/metrics.db

# metrics.py logs: query, latency_ms (real), entities JSON, retrieval results
```

---

## Git Notes

- Branch: `claude/dazzling-tharp`
- PR: https://github.com/Giwrgosalib/thesis/compare/claude/dazzling-tharp
- Large binaries (.pth, .safetensors, .bin) excluded via `.gitignore`
- Use Git LFS if you want to track model weights

---

## Environment Setup (first time)

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# Windows GPU (CUDA 12.4):
pip install torch==2.6.0+cu124 --index-url https://download.pytorch.org/whl/cu124
```
