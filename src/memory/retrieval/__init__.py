# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Memory retrieval and ranking for ADR-003.

This module provides ranked memory retrieval with:
- Similarity-based ranking
- Recency and decay scoring
- Query rewriting for better recall
- Scope-aware retrieval (user > project > global)

Related GitHub Issues:
- #97: Memory Ranking Logic
- #98: Query Rewriting
- #99: Scope-Aware Retrieval
- #100: Memory Decay Scoring

ADR Reference: ADR-003 Memory Architecture, Phase 1c (Retrieval & Ranking)
"""

from src.memory.retrieval.query_rewriter import QueryRewriter
from src.memory.retrieval.ranker import MemoryRanker
from src.memory.retrieval.scoped import MemoryScope, ScopedRetriever

__all__ = [
    "MemoryRanker",
    "QueryRewriter",
    "ScopedRetriever",
    "MemoryScope",
]
