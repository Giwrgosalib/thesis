# Project Improvement Notes

## Goal

Make the eBay AI Chatbot "the best there is".

## Backend Comparison: `backend` vs `backend_nextgen`

### `backend` (Current Active)

- **Architecture**: Monolithic Flask app.
- **NLP**: Custom BiLSTM-CRF (from scratch). Single Intent.
- **Search**: Direct eBay API with rule-based filtering.
- **Personalization**: Simple rule-based boosting (e.g., preferred brands).
- **Pros**: Simple, stable, matches current documentation.
- **Cons**: "Old school" NLP, lacks Generative AI (LLMs/RAG).

### `backend_nextgen` (The "Better" One)

- **Architecture**: Modular Orchestrator pattern.
- **NLP**: **Transformer-based NER** (BERT/RoBERTa likely).
- **Search**: **Hybrid Retrieval** (Vector Search + eBay API).
- **RAG**: **Retrieval-Augmented Generation** for natural language answers.
- **Personalization**: **Contextual Bandits** (Reinforcement Learning) for adaptive ranking.
- **Observability**: Dedicated metrics pipeline.
- **Pros**: State-of-the-art AI stack (RAG, Transformers, RL), much more impressive for a thesis.
- **Cons**: Higher complexity, requires model weights and vector indices.

## Recommendation

**YES, `backend_nextgen` is significantly better.** It represents a modern, "AI-native" architecture compared to the traditional web app structure of `backend`.

## Action Plan (Updated)

To make this "the best there is", we should **switch to `backend_nextgen`** and then add the frontend enhancements.

1.  **Switch Backend**:
    - Verify `backend_nextgen` dependencies and model availability.
    - Update `AGENTS.md` to reflect the new architecture (Transformers, RAG, Bandits).
2.  **Frontend Enhancements** (Still apply):
    - 🎙️ **Voice Interface** (Speech-to-Text & Text-to-Speech).
    - 🌍 **Multi-language Support**.
    - 📊 **Advanced Analytics Dashboard**.

## Immediate Next Steps

1.  **Verify `backend_nextgen` readiness**: Check if it runs and if models are present.
2.  **Migrate**: Point the frontend to use `backend_nextgen` (or replace `backend` content).

---

## 📝 Additional Thesis Notes

### 🚀 Deployment Strategy (DevOps)

For the "System Implementation" chapter, you can discuss how this would be deployed in production:

- **Dockerization**: Containerize the Flask backend (`Dockerfile`) and the Vue frontend (`nginx`).
- **Orchestration**: Use **Kubernetes (K8s)** to manage scaling. The stateless design of the API allows for horizontal autoscaling based on CPU/Memory usage.
- **Model Serving**: In a real-world scenario, heavy models (BERT) would be served via **TorchServe** or **Triton Inference Server** to optimize latency, rather than loading them directly in the Flask app.

### ⚖️ Ethical Considerations & Privacy

A strong thesis often includes a discussion on ethics:

- **Bias in AI**: Discuss how the "Contextual Bandit" might reinforce bias (e.g., if it only shows expensive items to certain users). Mitigation: Add "exploration" noise to ensure diverse results.
- **Data Privacy (GDPR)**: The system stores user preferences. To be GDPR compliant, we must allow users to "Forget Me" (delete their vector profile).
- **Hallucinations**: RAG reduces hallucinations, but they can still happen. We implement a "citation" mechanism (showing the source product) to build trust.

### 🔮 Future Work Ideas

- **Multimodal Search**: Allow users to upload an image of a shoe and find similar eBay listings (using CLIP models).
- **Voice Biometrics**: Identify the user by their voice print for secure login.
- **Federated Learning**: Train the personalization model on the user's device (phone) so their data never leaves their control.
