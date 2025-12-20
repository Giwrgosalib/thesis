# 🧠 **System Context: Unified eBay AI Repository**

> **For AI Agents:** This file allows you to instantly understand the structure, architecture, and capabilities of this codebase. Read this first to ground your context.

---

## 1. 🎯 **Project Identity**

**Name:** Unified eBay AI Assistant
**Purpose:** A dual-backend e-commerce assistant demonstrating the evolution from "Traditional NLP" to "Generative AI".
**Key Value:** Compares **Legacy** (Regex/CRF) vs **NextGen** (Transformers/RAG) approaches for product search.
**Environment:**

- **OS:** Windows (PowerShell)
- **GPU:** NVIDIA RTX 4070 Laptop (CUDA 12.1 Enabled)
- **Frameworks:** Flask, Vue.js 3, PyTorch 2.5+, Vuetify.

---

## 2. 🗺️ **Repository Map**

```text
unified-repo/
├── backend/                   # 🏛️ LEGACY Backend (Stable)
│   ├── app.py                # Main Flask Entrypoint (Gatekeeper)
│   ├── custom_nlp.py         # Legacy EBayNLP (BiLSTM-CRF) service
│   └── ebay_service.py       # Shared eBay API Adapter
│
├── backend_nextgen/           # 🚀 NEXTGEN Backend (Experimental/GPU)
│   ├── orchestrator.py       # The "Brain" (Wires all AI modules)
│   ├── api/routes.py         # Blueprint definitions
│   ├── config/               # YAML configs (nextgen_config.yml)
│   ├── nlp/                  # TransformerNER (DeBERTa-v3)
│   ├── rag/                  # RAG Pipeline (LLM + Context)
│   ├── retrieval/            # DualEncoder (E5 Embeddings)
│   └── ranking/              # NeuralReRanker (Cross-Encoder)
│
├── frontend/                  # 💻 Unified Frontend
│   └── src/components/
│       └── FullApp.vue       # Main UI (Toggles between architectures)
│
├── scripts/                   # 🛠️ Operational Tools
│   ├── start_dev.py          # Development Launcher
│   ├── verify_nextgen.py     # Health Check
│   └── benchmark_*.py        # Performance & Quality Testing
│
└── docs_notes/                # 📚 Documentation & Artifacts
    ├── GPU_BENCHMARKS.md     # Performance reports
    └── GPU_FIXES.md          # Setup guides
```

---

## 3. 🏗️ **Architecture: The Dual Core**

The `app.py` acts as a **Gateway**. It hosts the Legacy endpoints directly and mounts the NextGen blueprint. The frontend chooses which API to call.

### **A. Legacy Architecture ("The Reliable CLI")**

- **Path:** `/api/classic/search`
- **Logic:** `app.py` -> `custom_nlp.py` -> `ebay_service.py`
- **Model:** Lightweight BiLSTM-CRF + Regex.
- **Capabilities:** Fast keyword extraction. No semantic understanding.
- **Latency:** ~3.9s.

### **B. NextGen Architecture ("The AI Brain")**

- **Path:** `/api/nextgen/query`
- **Logic:** `app.py` -> `orchestrator.py` -> [Pipeline]
- **Pipeline:**
  1.  **NER**: Extract entities (Brand, User, Price) using DeBERTa.
  2.  **Retrieval**: Fetch candidates via Vector Search (DualEncoder) + eBay API.
  3.  **Reranking**: Neural Cross-Encoder to sort by semantic relevance.
  4.  **RAG**: Generative Responder (LLM) synthesizes a natural answer.
  5.  **Bandit**: Personalization layer (Thompson Sampling).
- **Capabilities:** Multi-turn context, semantic search ("gaming laptop under 1000"), RAG.
- **Latency:** ~4.9s (GPU Accelerated).

---

## 4. 🔌 **Key Components & Files**

### **The Orchestrator (`backend_nextgen/orchestrator.py`)**

The central nervous system. It:

- Initializes all heavy models (NER, RAG, Reranker).
- Manages `history` for conversational context (rewrying queries).
- Merges User Context + NLP Entities.
- Returns a rich JSON with `items`, `entities`, and `answer`.

### **The Frontend (`frontend/src/components/FullApp.vue`)**

A reactive Vue.js application.

- **Toggle:** Users switch "NextGen Mode" ON/OFF.
- **State:** Manages `conversationHistory` and sends it to the backend.
- **Display:** Renders Product Cards, AI Answers, and reasoned "Why I chose this" text.

---

## 5. 💡 **Current Status (Dec 2025)**

- **GPU Status:** ✅ Fully Enabled. Inference <1s.
- **Quality:** ✅ Verified. NextGen extracts 4x more entities than Legacy on complex queries.
- **Chat:** ✅ Working. Supports "Show me laptops" -> "under 1000" -> "Make them Lenovo".
- **Documentation:** See `docs_notes/GPU_BENCHMARKS.md` for proof of performace.

---

> **Instruction for Agents:** When asked to edit code, determine if the request targets the **Legacy** stability layer or the **NextGen** innovation layer. **Do not mix dependencies** (e.g., don't import Torch in Legacy).
