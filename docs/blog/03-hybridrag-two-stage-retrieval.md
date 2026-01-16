# HybridRAG: Two-Stage Retrieval for AI Memory

**Pure vector search isn't enough. Here's how we combine BM25, embeddings, and cross-encoder reranking to achieve accurate memory retrieval.**

---

Vector search revolutionized information retrieval. Embed your documents, embed your query, find the nearest neighbors. Simple, elegant, and... often wrong.

The problem? Vector embeddings excel at semantic similarity but struggle with exact matches. Ask "What's the Redis configuration?" and pure vector search might return documents about "cache settings" or "in-memory databases" while missing the one that literally contains "Redis configuration."

HybridRAG solves this by combining the strengths of multiple retrieval methods, then using a neural reranker to pick the best results.

## The Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Query Input                              │
├─────────────────────────────────────────────────────────────────┤
│ Stage 1: Parallel Candidate Generation                          │
├──────────────────────┬──────────────────────────────────────────┤
│  BM25 Search         │  Vector Search                           │
│  (Sparse Keywords)   │  (Dense Semantics)                       │
│  Top 50              │  Top 50                                  │
└──────────────────────┴──────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Stage 2: Fusion + Reranking                                     │
├────────────────────────────┬────────────────────────────────────┤
│  RRF Fusion                │  Cross-Encoder Reranking           │
│  (Score-agnostic merge)    │  (Deep relevance scoring)          │
└────────────────────────────┴────────────────────────────────────┘
                              │
                              ▼
                      Final Results (Top K)
```

Two stages. Multiple signals. One answer.

## Stage 1: Parallel Candidate Generation

Stage 1 runs two search methods in parallel, each returning 50 candidates.

### BM25: The Keyword Hunter

BM25 (Best Match 25) is a probabilistic ranking function that scores documents based on term frequency and inverse document frequency. It's been the backbone of search engines for decades.

```python
BM25(D, Q) = Σ IDF(qi) * (f(qi, D) * (k1 + 1)) / (f(qi, D) + k1 * (1 - b + b * |D| / avgdl))
```

Translation: Documents score higher when they contain rare query terms (high IDF) that appear frequently in the document (high TF), normalized by document length.

**Why BM25 matters:**

| Query Type | BM25 | Vector Search |
|------------|------|---------------|
| "PostgreSQL 15.2 configuration" | Exact match on version | Semantic drift to "database setup" |
| "REDIS_CONNECTION_TIMEOUT" | Finds the config key | Returns cache-related docs |
| "ADR-003" | Direct hit | Might miss (ADR = rare term) |

BM25 finds the needle. Vector search finds things that look like needles.

### Vector Search: The Semantic Finder

Dense vector search embeds queries and documents into a shared embedding space (typically 384-1536 dimensions depending on the model), then finds nearest neighbors by cosine similarity.

```python
# Using sentence-transformers (e.g., all-MiniLM-L6-v2 = 384 dims)
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')
query_embedding = model.encode("How should I configure caching?")
similarities = np.dot(doc_embeddings, query_embedding)
top_k = np.argsort(similarities)[-50:]
```

**Why vectors matter:**

| Query | Relevant Document | Similarity |
|-------|------------------|------------|
| "How to speed up the app" | "Performance optimization guide" | 0.89 |
| "Authentication best practices" | "Securing user login flows" | 0.87 |
| "Reduce memory usage" | "Heap size tuning for JVM" | 0.82 |

Vectors understand synonyms, paraphrasing, and conceptual relationships that keyword search misses.

### Running in Parallel

Both searches are independent, so we run them concurrently:

```python
async def stage1(query: str, user_id: str):
    bm25_task = asyncio.to_thread(self.bm25.search, user_id, query, 50)
    vector_task = asyncio.to_thread(self.vector.search, user_id, query, 50)

    bm25_results, vector_results = await asyncio.gather(bm25_task, vector_task)
    return bm25_results, vector_results
```

Stage 1 takes ~200-400ms (limited by vector embedding).

## Stage 2: Fusion + Reranking

Now we have two ranked lists. How do we combine them?

### The Naive Approach (Don't Do This)

Normalize scores and average:

```python
# DON'T DO THIS
bm25_normalized = (bm25_score - min) / (max - min)
vector_normalized = (vector_score - min) / (max - min)
combined = (bm25_normalized + vector_normalized) / 2
```

This fails because:
1. Score distributions differ wildly (BM25: 0-20, vectors: 0-1)
2. Outliers dominate after normalization
3. Assumes scores are comparable (they're not)

### Reciprocal Rank Fusion (RRF)

RRF ignores scores entirely and works with ranks:

```
RRF_score(d) = Σ 1 / (k + rank_i(d))
```

Where `k=60` (from the original paper) and `rank_i(d)` is the 1-indexed position of document `d` in list `i`.

**Example:**

```
BM25:   [doc1, doc2, doc3]  (ranks 1, 2, 3)
Vector: [doc2, doc1, doc4]  (ranks 1, 2, 3)

RRF scores (k=60):
doc1: 1/(60+1) + 1/(60+2) = 0.0164 + 0.0161 = 0.0325
doc2: 1/(60+2) + 1/(60+1) = 0.0161 + 0.0164 = 0.0325
doc3: 1/(60+3)            = 0.0159
doc4: 1/(60+3)            = 0.0159
```

Both `doc1` and `doc2` tie because they appeared in both lists at similar ranks.

**Why RRF works:**
- Score-agnostic: Works with any ranking function
- Robust: Not sensitive to outliers or extreme scores
- Empirically strong: Often competitive with learned fusion methods

**Implementation:**

```python
from collections import defaultdict

def reciprocal_rank_fusion(
    *ranked_lists: list[tuple[str, float]],
    k: int = 60
) -> list[tuple[str, float]]:
    """
    Fuse multiple ranked lists using RRF.

    Args:
        ranked_lists: Each list contains (doc_id, score) tuples, sorted by score desc
        k: RRF constant (default 60 from original paper)

    Returns:
        Fused list of (doc_id, rrf_score) sorted by RRF score desc
    """
    scores = defaultdict(float)

    for ranked_list in ranked_lists:
        for rank, (doc_id, _) in enumerate(ranked_list, start=1):
            scores[doc_id] += 1 / (k + rank)

    return sorted(scores.items(), key=lambda x: -x[1])

# Usage
fused = reciprocal_rank_fusion(bm25_results, vector_results, k=60)
```

### Cross-Encoder Reranking

RRF gives us a fused candidate list. But we can do better.

A cross-encoder is a neural model that takes (query, document) pairs and outputs a relevance score. Unlike bi-encoders (vector search), it sees both texts together, enabling deeper semantic understanding.

```python
# Bi-encoder (separate encoding)
query_emb = model.encode(query)
doc_emb = model.encode(doc)
score = cosine(query_emb, doc_emb)  # Approximate

# Cross-encoder (joint encoding)
score = cross_encoder.predict([(query, doc)])  # Precise
```

Cross-encoders are significantly more accurate but much slower per-pair (the exact ratio depends on batching, hardware, and model size). That's why we only use them for reranking the top ~50 candidates, not the entire corpus.

**Model choice:** `cross-encoder/ms-marco-MiniLM-L-6-v2`
- Trained on MS MARCO passage ranking dataset
- Fast (~2ms per pair on CPU, faster with batching/GPU)
- Good balance of speed and accuracy

```python
from sentence_transformers import CrossEncoder

cross_encoder = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

def rerank(query: str, candidates: list, top_k: int = 10):
    """Rerank candidates using cross-encoder relevance scoring."""
    pairs = [(query, doc.content) for doc in candidates]

    # Batch scoring for efficiency
    scores = cross_encoder.predict(pairs, batch_size=32)

    # Sort by cross-encoder score
    ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
    return ranked[:top_k]
```

Stage 2 takes ~50-100ms.

## The Complete Flow

Let's trace a query through the system:

**Query:** "How should I configure database migrations?"

**Stage 1a - BM25** (30ms):
```
Tokens: ["configure", "database", "migrations"]
Results: [("mem-5", 7.3), ("mem-1", 4.2), ("mem-8", 3.1), ...]
```

**Stage 1b - Vector** (200ms):
```
Embedding: [0.12, -0.34, 0.87, ...] (384 dims)
Results: [("mem-1", 0.92), ("mem-5", 0.87), ("mem-12", 0.78), ...]
```

**Stage 2a - RRF Fusion** (5ms):
```
doc  | bm25_rank | vec_rank | RRF score
-----|-----------|----------|----------
mem-1|     2     |    1     | 0.0325
mem-5|     1     |    2     | 0.0325
mem-8|     3     |    -     | 0.0159
mem-12|    -     |    3     | 0.0159
```

**Stage 2b - Reranking** (60ms):
```
Cross-encoder scores:
mem-1:  0.89 ← Best match (specific migration instructions)
mem-5:  0.87
mem-12: 0.72
mem-8:  0.65
```

**Final Results:**
```python
[
    HybridResult(memory_id="mem-1", score=0.89,
                 source_ranks={"bm25": 2, "vector": 1, "reranker": 1}),
    HybridResult(memory_id="mem-5", score=0.87,
                 source_ranks={"bm25": 1, "vector": 2, "reranker": 2}),
    ...
]
```

Total latency: ~350ms.

## Tuning the Weights

Not all retrieval methods are equal for all domains. You can weight them differently in RRF:

```python
# For code/config (keyword-heavy)
retriever = HybridRetriever(bm25_weight=1.5, vector_weight=1.0)

# For conceptual/natural language
retriever = HybridRetriever(bm25_weight=1.0, vector_weight=1.5)
```

Weighted RRF:
```
score(d) = w_bm25/(k + rank_bm25(d)) + w_vec/(k + rank_vec(d))
```

## Provenance Tracking

Every result tracks where it came from:

```python
result = HybridResult(
    memory=Memory(...),
    score=0.89,
    memory_id="mem-1",
    source_scores={"bm25": 4.2, "vector": 0.92, "reranker": 0.89},
    source_ranks={"bm25": 2, "vector": 1, "reranker": 1}
)
```

This lets you debug retrieval issues:
- High BM25, low vector → Keyword match, semantic mismatch
- High vector, low BM25 → Semantic match, missing keywords
- High both, low reranker → False positive (looks relevant but isn't)

## Performance Characteristics

| Stage | Component | Latency | Notes |
|-------|-----------|---------|-------|
| 1a | BM25 Search | 10-50ms | O(n) scoring |
| 1b | Vector Embed | 50-200ms | Model inference |
| 1b | Vector Search | 20-100ms | Vectorized dot product |
| 2a | RRF Fusion | 5-20ms | O(n log n) sort |
| 2b | Reranking | 30-100ms | ~2ms per candidate |
| **Total** | | **~350-500ms** | |

For latency-sensitive applications, you can disable the cross-encoder:

```python
retriever = HybridRetriever(use_cross_encoder=False)
# Saves ~100ms, loses ~5% accuracy
```

## When to Use HybridRAG

**Good fit:**
- Technical documentation (mixed keywords + concepts)
- Code knowledge bases (exact identifiers + semantic queries)
- Decision records (ADR references + natural language)
- Incident histories (error codes + descriptions)

**Overkill for:**
- Pure keyword search (use BM25 alone)
- Pure semantic search (use vectors alone)
- Real-time autocomplete (latency-sensitive)

## Usage Example

```python
from src.memory.retrieval import create_hybrid_retriever

# Initialize
retriever = create_hybrid_retriever(
    use_cross_encoder=True,
    bm25_weight=1.0,
    vector_weight=1.0,
)

# Index your memories
retriever.index_memories("user-1", memories)

# Retrieve
results, metrics = await retriever.retrieve(
    query="How do I configure Redis caching?",
    user_id="user-1",
    top_k=10,
)

# Use results
for result in results:
    print(f"{result.memory_id}: {result.score:.3f}")
    print(f"  Content: {result.memory.content[:100]}...")

# Monitor performance
print(f"Latency: {metrics.total_time_ms:.0f}ms")
print(f"  Stage 1: {metrics.stage1_time_ms:.0f}ms")
print(f"  Stage 2: {metrics.stage2_time_ms:.0f}ms")
```

## The Results

In our benchmarks, HybridRAG outperforms pure vector search by 50%+ on multi-hop queries while maintaining sub-second latency:

| Method | Recall@10 | Latency (p95) |
|--------|-----------|---------------|
| BM25 only | 0.62 | 50ms |
| Vector only | 0.71 | 250ms |
| **HybridRAG** | **0.89** | 450ms |

*Benchmarks: 10K document corpus of technical documentation. Tested on 4-core CPU (no GPU). Embedding model: all-MiniLM-L6-v2. Cross-encoder: ms-marco-MiniLM-L-6-v2. Query set: 500 natural language questions with human-labeled relevance judgments.*

The two-stage architecture gives us the best of both worlds: comprehensive candidate generation followed by precise relevance ranking.

## Recommended Libraries

| Component | Library | Notes |
|-----------|---------|-------|
| BM25 | `rank_bm25` or Elasticsearch | Pure Python or production-grade |
| Embeddings | `sentence-transformers` | Wide model selection |
| Vector Index | `faiss` or `hnswlib` | Fast ANN search |
| Cross-Encoder | `sentence-transformers` | Same library, different models |
| Orchestration | `langchain` or `haystack` | Optional, adds complexity |

**Minimal pip install:**
```bash
pip install sentence-transformers rank-bm25 numpy
```

## Limitations

HybridRAG isn't a silver bullet. Know when it fails:

- **Very short queries** (1-2 words): BM25 dominates; vector adds noise
- **Highly technical identifiers**: UUIDs, hashes, and base64 strings need exact match, not semantic search
- **Multilingual queries**: Embedding model must support target languages
- **Real-time autocomplete**: 450ms is too slow; use BM25 prefix matching instead
- **Adversarial queries**: Prompt injection in documents can poison retrieval

**Tuning tips:**
- Start with k=50 candidates from each source; adjust based on recall/latency tradeoff
- If queries are keyword-heavy (code, configs), boost `bm25_weight`
- If queries are conceptual (natural language), boost `vector_weight`
- The reranker is optional—disable it if latency matters more than precision

---

*HybridRAG is part of ADR-003 Phase 3. See the [full ADR](../adrs/ADR-003-project-intent-persistent-context.md) for implementation details and performance benchmarks.*
