# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Memory retrieval and ranking for ADR-003.

This module provides ranked memory retrieval with:
- Two-stage hybrid retrieval (BM25 + Vector + Fusion + Reranking)
- Similarity-based ranking
- Recency and decay scoring
- Query rewriting for better recall
- Scope-aware retrieval (user > project > global)

Related GitHub Issues:
- #97: Memory Ranking Logic
- #98: Query Rewriting
- #99: Scope-Aware Retrieval
- #100: Memory Decay Scoring

ADR Reference: ADR-003 Memory Architecture
- Phase 1c: Retrieval & Ranking
- Phase 3: Two-Stage Retrieval Architecture
"""

# Phase 1c: Original retrieval components
from src.memory.retrieval.query_rewriter import QueryRewriter
from src.memory.retrieval.ranker import MemoryRanker
from src.memory.retrieval.scoped import MemoryScope, ScopedRetriever

# Phase 3: Two-Stage Retrieval Architecture
from src.memory.retrieval.bm25 import BM25Search
from src.memory.retrieval.fusion import FusedResult, RRFFusion
from src.memory.retrieval.hybrid import (
    HybridResult,
    HybridRetriever,
    RetrievalMetrics,
    create_hybrid_retriever,
)
from src.memory.retrieval.reranker import (
    CrossEncoderReranker,
    FallbackReranker,
    RerankResult,
    get_reranker,
)
from src.memory.retrieval.vector_search import VectorSearch

__all__ = [
    # Phase 1c: Original components
    "MemoryRanker",
    "QueryRewriter",
    "ScopedRetriever",
    "MemoryScope",
    # Phase 3: Two-Stage Retrieval
    "BM25Search",
    "VectorSearch",
    "RRFFusion",
    "FusedResult",
    "CrossEncoderReranker",
    "FallbackReranker",
    "RerankResult",
    "get_reranker",
    "HybridRetriever",
    "HybridResult",
    "RetrievalMetrics",
    "create_hybrid_retriever",
]
