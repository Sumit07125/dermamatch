<div align="center">

# ✨ DermaMatch AI

### Ingredient-Aware Skincare Recommendation Engine

[![Live Demo](https://img.shields.io/badge/🚀_Live_Demo-dermamatch.streamlit.app-FF4B4B?style=for-the-badge&logo=streamlit)](https://dermamatch.streamlit.app/)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-Cloud-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-Vector_Store-FF6F00?style=for-the-badge)](https://trychroma.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-22C55E?style=for-the-badge)](LICENSE)

> **A production-grade AI application** combining Semantic Vector Search, Deep Ingredient Intelligence, and Review Signal Extraction to deliver explainable skincare product recommendations in real-time.

</div>

---

## 🌐 Live Demo

**Try it now, no setup required:**

### **👉 [https://dermamatch.streamlit.app/](https://dermamatch.streamlit.app/)**

| Mode | Description |
|---|---|
| 💬 **Natural Language** | *"lightweight sunscreen for oily skin under ₹2000"* |
| 📋 **Skincare Quiz** | Structured dropdowns for skin type, concerns, budget, and ingredient preferences |

---

## 🏗️ Architecture

```
╔══════════════════════════════════════════════════════════════════╗
║                     USER  →  STREAMLIT UI                        ║
╠══════════════════════════════════════════════════════════════════╣
║  Natural Language Query            OR  Structured Quiz           ║
║          │                                     │                 ║
╠══════════╪═════════════════════════════════════╪════════════════╣
║          └─────────────► RECOMMENDATION ENGINE ◄────────────────╣
║                                    │                             ║
║          ┌─────────────────────────┼──────────────────────┐     ║
║          ▼                         ▼                      ▼     ║
║   [Semantic Retrieval]    [Ingredient Intelligence]  [Review     ║
║   SentenceTransformer      Canonical Ingredient      Signal      ║
║   + ChromaDB Vector        Matching + Coverage       Extraction] ║
║   Search (BGE model)       Score + Avoidance List               ║
║          │                         │                      │     ║
╠══════════╪═════════════════════════╪══════════════════════╪════╣
║          └─────────────► MULTI-SIGNAL RANKER ◄───────────────── ║
║                                    │                             ║
║          ┌─────────────────────────┼──────────────────────┐     ║
║          ▼                         ▼                      ▼     ║
║   [Semantic Score]        [Ingredient Score]     [Diversity      ║
║   [Budget Filter]         [Review Relevance]      Penalty]       ║
║   [Category Filter]       [Preference Match]     [Rating         ║
║                                                   Quality]       ║
╠══════════════════════════════════════════════════════════════════╣
║             ↓  TOP-K RANKED + EXPLAINABLE RESULTS  ↓            ║
╚══════════════════════════════════════════════════════════════════╝
```

---

## ✨ Features

| Feature | Detail |
|---|---|
| 🧠 **Semantic Search** | BGE sentence embeddings + ChromaDB vector retrieval finds contextually similar products |
| 🧪 **Ingredient Intelligence** | Canonical ingredient matching with alias resolution (e.g., "Vit C" → "ascorbic acid") |
| 🚫 **Hard Filters** | Budget, category, and ingredient avoidance applied before ranking — no "near misses" |
| 💬 **Review Signal Extraction** | Extracts themes (e.g., "good for redness") from historical reviews as ranking evidence |
| 📖 **Explainable AI** | Every recommendation includes deterministic, human-readable reasons with ingredient coverage % |
| ⚡ **Zero-Latency Image Rendering** | Product images deterministically assigned via MD5 hashing — same product, always same image |
| 🌙 **Premium SaaS UI** | Glassmorphism backgrounds, responsive card grid, INR pricing, animated AI diagnostics |
| 📊 **AI Diagnostics Panel** | Live display of retrieval latency (ms) and per-dimension confidence scores |

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **UI** | Streamlit (Cloud) | Hosted frontend with custom HTML/CSS |
| **Embeddings** | `BAAI/bge-small-en-v1.5` | Sentence transformer for semantic search |
| **Vector Store** | ChromaDB | Persistent embedding index, sub-100ms retrieval |
| **Data** | Pandas + NumPy | Catalog management, scoring, ranking |
| **AI Scoring** | Custom multi-signal ranker | 6-dimension weighted final score |
| **Data Pipeline** | Jupyter Notebooks | Reproducible ETL from raw Sephora dataset |

---

## 📁 Project Structure

```
DermaMatch-AI/
│
├── 📂 app/                          # Core recommendation engine
│   ├── recommender.py               #  ← Main hybrid search + scoring logic
│   ├── engine_loader.py             #  ← Singleton loader: catalog, ChromaDB, embedder
│   ├── config.py                    #  ← Environment-aware configuration
│   ├── routes.py                    #  ← Flask REST API endpoints
│   └── schemas.py                   #  ← Request/response validation
│
├── 📂 streamlit_app/                # Streamlit UI layer
│   ├── main.py                      #  ← App entrypoint, tabs, result rendering
│   ├── components.py                #  ← Premium product card components
│   ├── styles.py                    #  ← CSS injection, dynamic background loader
│   └── api_client.py                #  ← Direct engine bridge (no HTTP needed)
│
├── 📂 assets/                       # Static assets
│   ├── backgrounds/                 #  ← 8 premium background images
│   └── product_images/              #  ← 20 skincare product placeholder images
│
├── 📂 data/
│   ├── artifacts/                   #  ← ChromaDB index, embeddings, engine config
│   └── processed/                   #  ← Cleaned catalog, review signals
│
├── 📂 notebooks/                    # Reproducible ML pipeline
│   ├── DermaMatch_AI_Final_Data_Pipeline.ipynb      # Part 1: ETL
│   └── 02_DermaMatch_Recommendation_Engine_FINAL.ipynb  # Part 2: Embeddings
│
├── 📂 tests/                        # Pytest suite
├── requirements.txt
└── run.py                           # Local dev entrypoint
```

---

## 🧠 The Recommendation Algorithm

Every query goes through a 4-stage pipeline:

### Stage 1 — Semantic Retrieval
```
User Query → SentenceTransformer (BGE) → Query Embedding
                                              ↓
                              ChromaDB cosine search (top 50 candidates)
```

### Stage 2 — Hard Constraint Filtering
```
50 candidates → Budget filter → Category filter → Ingredient avoidance filter
                                                          ↓
                                              Remaining valid candidates
```

### Stage 3 — Multi-Signal Scoring
Each candidate receives 6 independent scores:

| Score | Weight | Method |
|---|---|---|
| `semantic_similarity` | 40% | Cosine similarity to query embedding |
| `ingredient_match` | 25% | Canonical ingredient coverage vs. requested terms |
| `review_relevance` | 15% | Review theme extraction matching user concerns |
| `preference_match` | 10% | Match against lightweight/fragrance-free/etc. terms |
| `rating_quality` | 5% | Bayesian-adjusted average rating |
| `diversity` | 5% | Embedding distance from already-selected items |

### Stage 4 — Diversity-Aware Greedy Ranking
```
Candidates → Greedy selection loop → Penalize same brand/category
                                              ↓
                              Final ranked top-K results
```

---

## 🚀 Quick Start (Local)

```bash
# 1. Clone
git clone https://github.com/Sumit07125/dermamatch.git
cd dermamatch

# 2. Install
pip install -r requirements.txt

# 3. Run Streamlit
streamlit run streamlit_app/main.py
```

> **Note:** The pre-built ChromaDB index and processed catalog (`data/`) are included in the repository. No re-training or data pipeline run is required.

---

## 🧪 Example Queries

```
"lightweight moisturizer for dry sensitive skin under ₹1500"
"vitamin C serum for dark spots, fragrance-free"
"non-comedogenic sunscreen for acne-prone oily skin SPF 50"
"anti-aging retinol cream, avoid fragrance and alcohol"
```

---

## 📊 Dataset

- **Source:** Sephora Product & Skincare Reviews Dataset (Kaggle)
- **Scale:** ~8,000 raw products → **2,420 processed skincare products** with full review signals
- **Ingredient Profiles:** INCI-normalized ingredient lists with alias resolution

---

## 🔬 Testing

```bash
pytest tests/ -v
```

Test suite covers: health endpoint, recommendation constraints, budget filtering, ingredient avoidance, and end-to-end quiz flow.

---

## 🔮 Future Improvements

- [ ] Periodically refresh the catalog to add new Sephora products
- [ ] Add API-level caching (Redis) for identical queries
- [ ] Multi-modal input: upload a photo of your current skincare routine
- [ ] Personalized profiles with saved preferences and recommendation history
- [ ] A/B test recommendation weights using implicit feedback

---

<div align="center">

**Built with ❤️ by Sumit Mali**

*DermaMatch AI is a prototype demonstration. Recommendations are not medical advice.*

</div>
