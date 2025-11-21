# Installation & Bootstrap Guide

This document explains how to bring the eBay AI Shopping Assistant online from a clean machine. It covers backend/frontend dependencies, model initialization, and the data pipelines required for the NextGen AI stack.

## 1. Prerequisites

- **Python 3.10+** (project tested with 3.11) and `pip`
- **Node.js 18+** with `npm`
- **MongoDB** (local or remote)
- **Git**
- (Optional) CUDA-capable GPU for model training

## 2. Clone the repository

```bash
git clone https://github.com/<your-org>/unified-repo.git
cd unified-repo
```

## 3. Python environment

```bash
python -m venv .venv
./.venv/Scripts/activate      # PowerShell
# source .venv/bin/activate   # macOS/Linux
pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Frontend dependencies

```bash
cd frontend
npm install
cd ..
```

## 5. Environment configuration

1. Copy `backend/.env.example` (or create `backend/.env`) and set:
   - `MONGO_URI`, `MONGO_DB_NAME`, `PREF_COLLECTION`
   - `EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET`, `EBAY_DEV_ID`, `EBAY_REDIRECT_URI`
   - `APP_BASE_URL`, `FRONTEND_URL`, and any OAuth scopes.
2. Ensure MongoDB is reachable at the configured URI.
3. (Optional) Update `backend_nextgen/config/nextgen_config.yml` to point to your preferred transformer/checkpoint paths.

## 6. Initialize the enhanced BiLSTM-CRF model

This step builds the single-intent NER model used by the classical pipeline. Place your refined dataset at `backend/data/refined_balanced_dataset_train.csv` (or adjust inside the script) and run:

```bash
python backend/initialize_enhanced_models.py
```

Outputs:
- `backend/models/enhanced/enhanced_ner_model.pth`
- `backend/models/enhanced/enhanced_ner_model_vocab.pkl`
- `backend/models/enhanced/model_info.json`

## 7. NextGen vector store & knowledge graph

The NextGen stack requires embeddings, metadata, and a simple knowledge graph. Sample data lives in `backend_nextgen/data/`. Run:

```bash
python backend_nextgen/scripts/run_pipelines.py
```

This script launches:
- `embedding_pipeline` (produces `data/vector_store/faiss_index.faiss` and `.npy` companions)
- `knowledge_graph_pipeline` (creates `data/knowledge_graph/triples.txt`)
- `metrics_pipeline` (seeds observability metrics for dashboards)

For real data, replace the sample CSV/JSONL files and rerun the script.

## 8. (Optional) Fine-tune the transformer NER

If you want the transformer-based NER used by `/api/nextgen/query` to reflect your dataset:

```bash
python backend_nextgen/scripts/train_transformer_ner.py \
    --train backend/data/refined_balanced_dataset_train.csv \
    --val backend/data/refined_balanced_dataset_val.csv \
    --output_dir backend_nextgen/models/ner
```

This writes checkpoints and tokenizer files that are automatically loaded by the orchestrator.

## 9. Run the backend

```bash
./.venv/Scripts/activate
python backend/app.py
```

The backend exposes:
- `http://localhost:5000/health`
- `http://localhost:5000/api/nextgen/query`
- `http://localhost:5000/api/nextgen/metrics`

## 10. Run the frontend

```bash
cd frontend
npm run serve    # Vue CLI dev server
```

Visit `http://localhost:8080` (Vue CLI default). The frontend proxies `/api` requests to the Flask backend when both run locally.

## 11. One-command demo helper

A helper script starts both services for you:

```bash
python scripts/start_demo.py
```

Options:

- `--python` — custom Python interpreter (defaults to the one running the script)
- `--npm` — override the npm binary if needed (e.g., `--npm pnpm`)

The script launches the backend and `npm run serve` concurrently and shuts them down when you press `Ctrl+C`.

## 12. Demo checklist

1. **Health check** – `curl http://localhost:5000/health` must return `"status": "healthy"` with `nextgen_ai`.
2. **Test query** – send a POST request:
   ```bash
   curl -X POST http://localhost:5000/api/nextgen/query \
        -H "Content-Type: application/json" \
        -d '{"query": "iphone 15 pro under 1200", "user_context": {"client": "cli"}}'
   ```
3. **Preferences** – log in via the frontend and issue a few queries; verify the Mongo `preferences_collection` records update and `/api/nextgen/metrics` reflects response latency and error counts.
4. **Frontend build (production)** – when ready to deploy:
   ```bash
   cd frontend
   npm run build
   ```
   Serve `frontend/dist/` via your preferred static host.

Following the above sequence, a fresh machine with no pre-existing models can train/initialize the NLP stack, build the vector store, and run both the backend and frontend needed for your demos or thesis defense.
