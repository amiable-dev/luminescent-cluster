# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Two-Stage Hybrid Retrieval Architecture.

Orchestrates the complete two-stage retrieval pipeline:

Stage 1 - Candidate Generation (Parallel):
  - BM25 sparse keyword search
  - Vector dense semantic search
  - (Graph traversal - Phase 4)

Stage 2 - Fusion + Reranking:
  - RRF fusion of Stage 1 results
  - Cross-encoder reranking for final quality

This implements ADR-003 Phase 3 Two-Stage Retrieval Architecture with
exit criteria: multi-hop queries outperform pure vector by >50%,
end-to-end latency <1s.

ADR Reference: ADR-003 Memory Architecture, Phase 3 (Two-Stage Retrieval)
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from luminescent_cluster.memory.retrieval.bm25 import BM25Search
from luminescent_cluster.memory.retrieval.fusion import RRFFusion
from luminescent_cluster.memory.retrieval.query_rewriter import QueryRewriter
from luminescent_cluster.memory.retrieval.reranker import (
    CrossEncoderReranker,
    FallbackReranker,
    RerankResult,
)
from luminescent_cluster.memory.retrieval.vector_search import VectorSearch
from luminescent_cluster.memory.schemas import Memory

logger = logging.getLogger(__name__)


@dataclass
class RetrievalMetrics:
    """Metrics for a retrieval operation.

    Attributes:
        total_time_ms: Total retrieval time in milliseconds.
        stage1_time_ms: Stage 1 (candidate generation) time.
        stage2_time_ms: Stage 2 (fusion + reranking) time.
        bm25_candidates: Number of BM25 candidates.
        vector_candidates: Number of vector candidates.
        graph_candidates: Number of graph candidates.
        fused_candidates: Number of candidates after fusion.
        final_results: Number of final results.
        query_expanded: Whether query was expanded.
        reranker_used: Whether cross-encoder was used.
    """

    total_time_ms: float = 0.0
    stage1_time_ms: float = 0.0
    stage2_time_ms: float = 0.0
    bm25_candidates: int = 0
    vector_candidates: int = 0
    graph_candidates: int = 0
    fused_candidates: int = 0
    final_results: int = 0
    query_expanded: bool = False
    reranker_used: bool = False


@dataclass
class HybridResult:
    """Result from hybrid retrieval.

    Attributes:
        memory: The retrieved Memory.
        score: Final relevance score.
        memory_id: ID of the memory.
        source_scores: Scores from each source (bm25, vector, reranker).
        source_ranks: Ranks from each source.
    """

    memory: Memory
    score: float
    memory_id: str
    source_scores: dict[str, float] = field(default_factory=dict)
    source_ranks: dict[str, int] = field(default_factory=dict)


class HybridRetriever:
    """Two-stage hybrid retrieval orchestrator.

    Combines BM25, vector search, and optional graph traversal with RRF
    fusion and optional cross-encoder reranking for high-quality retrieval.

    Example:
        >>> retriever = HybridRetriever()
        >>> retriever.index_memories("user-1", memories)
        >>> results, metrics = await retriever.retrieve(
        ...     "database configuration",
        ...     "user-1",
        ...     top_k=10
        ... )
        >>> for result in results:
        ...     print(f"{result.memory_id}: {result.score:.4f}")

    Attributes:
        bm25: BM25 search component.
        vector: Vector search component.
        graph: Optional graph search component for Phase 4.
        fusion: RRF fusion component.
        reranker: Cross-encoder reranker (or fallback).
        query_rewriter: Optional query expansion.
    """

    # Default Stage 1 candidate limits
    DEFAULT_BM25_TOP_K = 50
    DEFAULT_VECTOR_TOP_K = 50
    DEFAULT_GRAPH_TOP_K = 50

    # Default RRF k parameter
    DEFAULT_RRF_K = 60

    def __init__(
        self,
        bm25: Optional[BM25Search] = None,
        vector: Optional[VectorSearch] = None,
        graph: Optional["GraphSearch"] = None,
        fusion: Optional[RRFFusion] = None,
        reranker: Optional[CrossEncoderReranker | FallbackReranker] = None,
        query_rewriter: Optional[QueryRewriter] = None,
        use_cross_encoder: bool = True,
        bm25_weight: float = 1.0,
        vector_weight: float = 1.0,
        graph_weight: float = 1.0,
    ):
        """Initialize the hybrid retriever.

        Args:
            bm25: BM25 search instance. Created if not provided.
            vector: Vector search instance. Created if not provided.
            graph: Optional graph search instance for Phase 4 Knowledge Graph.
            fusion: RRF fusion instance. Created if not provided.
            reranker: Reranker instance. Created based on use_cross_encoder.
            query_rewriter: Query rewriter for expansion.
            use_cross_encoder: If True, use cross-encoder. If False, use fallback.
            bm25_weight: Weight for BM25 in RRF fusion.
            vector_weight: Weight for vector in RRF fusion.
            graph_weight: Weight for graph in RRF fusion.
        """
        self.bm25 = bm25 or BM25Search()
        self.vector = vector or VectorSearch(lazy_load=True)
        self.graph = graph  # Optional - Phase 4 Knowledge Graph
        self.fusion = fusion or RRFFusion(k=self.DEFAULT_RRF_K)
        self.query_rewriter = query_rewriter

        if reranker is not None:
            self.reranker = reranker
        elif use_cross_encoder:
            self.reranker = CrossEncoderReranker(lazy_load=True)
        else:
            self.reranker = FallbackReranker()

        self.bm25_weight = bm25_weight
        self.vector_weight = vector_weight
        self.graph_weight = graph_weight

    def index_memories(
        self,
        user_id: str,
        memories: list[Memory],
        memory_ids: Optional[list[str]] = None,
    ) -> None:
        """Index memories for a user.

        Builds both BM25 and vector indexes.

        Args:
            user_id: User ID to index for.
            memories: List of memories to index.
            memory_ids: Optional list of memory IDs.
        """
        # Index in both BM25 and vector
        self.bm25.index_memories(user_id, memories, memory_ids)
        self.vector.index_memories(user_id, memories, memory_ids)

    def add_memory(
        self,
        user_id: str,
        memory: Memory,
        memory_id: str,
    ) -> None:
        """Add a single memory to both indexes.

        Args:
            user_id: User ID.
            memory: Memory to add.
            memory_id: ID for the memory.
        """
        self.bm25.add_memory(user_id, memory, memory_id)
        self.vector.add_memory(user_id, memory, memory_id)

    def remove_memory(self, user_id: str, memory_id: str) -> bool:
        """Remove a memory from both indexes.

        Args:
            user_id: User ID.
            memory_id: ID of memory to remove.

        Returns:
            True if memory was removed from at least one index.
        """
        bm25_removed = self.bm25.remove_memory(user_id, memory_id)
        vector_removed = self.vector.remove_memory(user_id, memory_id)
        return bm25_removed or vector_removed

    def clear_index(self, user_id: str) -> None:
        """Clear both indexes for a user.

        Args:
            user_id: User ID to clear.
        """
        self.bm25.clear_index(user_id)
        self.vector.clear_index(user_id)

    async def retrieve(
        self,
        query: str,
        user_id: str,
        top_k: int = 10,
        expand_query: bool = True,
        use_reranker: bool = True,
        bm25_top_k: int = DEFAULT_BM25_TOP_K,
        vector_top_k: int = DEFAULT_VECTOR_TOP_K,
        graph_top_k: int = DEFAULT_GRAPH_TOP_K,
    ) -> tuple[list[HybridResult], RetrievalMetrics]:
        """Perform two-stage hybrid retrieval.

        Stage 1: Parallel BM25 + Vector + Graph candidate generation
        Stage 2: RRF fusion + Cross-encoder reranking

        Args:
            query: Search query.
            user_id: User ID to search for.
            top_k: Number of final results to return.
            expand_query: Whether to expand query using query rewriter.
            use_reranker: Whether to use cross-encoder reranking.
            bm25_top_k: Number of BM25 candidates.
            vector_top_k: Number of vector candidates.
            graph_top_k: Number of graph candidates.

        Returns:
            Tuple of (results, metrics).
        """
        start_time = time.perf_counter()
        metrics = RetrievalMetrics()

        # Query expansion
        effective_query = query
        if expand_query and self.query_rewriter:
            effective_query = self.query_rewriter.rewrite(query)
            metrics.query_expanded = effective_query != query

        # Stage 1: Parallel candidate generation
        stage1_start = time.perf_counter()

        # Build list of search coroutines
        search_tasks = [
            asyncio.to_thread(
                self.bm25.search, user_id, effective_query, bm25_top_k
            ),
            asyncio.to_thread(
                self.vector.search, user_id, effective_query, vector_top_k
            ),
        ]

        # Add graph search if available
        if self.graph is not None:
            search_tasks.append(
                asyncio.to_thread(
                    self.graph.search, user_id, effective_query, graph_top_k
                )
            )

        # Run all searches in parallel
        search_results = await asyncio.gather(*search_tasks)

        bm25_results = search_results[0]
        vector_results = search_results[1]
        graph_results = search_results[2] if len(search_results) > 2 else []

        metrics.bm25_candidates = len(bm25_results)
        metrics.vector_candidates = len(vector_results)
        metrics.graph_candidates = len(graph_results)
        metrics.stage1_time_ms = (time.perf_counter() - stage1_start) * 1000

        # Stage 2: Fusion + Reranking
        stage2_start = time.perf_counter()

        # Build fusion arguments
        fusion_sources = {
            "bm25": bm25_results,
            "vector": vector_results,
        }
        if graph_results:
            fusion_sources["graph"] = graph_results

        # Fuse results using RRF with optional weights
        weights_differ = (
            self.bm25_weight != 1.0 or
            self.vector_weight != 1.0 or
            self.graph_weight != 1.0
        )
        if weights_differ:
            weights = {
                "bm25": self.bm25_weight,
                "vector": self.vector_weight,
            }
            if graph_results:
                weights["graph"] = self.graph_weight
            fused = self.fusion.weighted_fuse(weights, **fusion_sources)
        else:
            fused = self.fusion.fuse(**fusion_sources)

        metrics.fused_candidates = len(fused)

        # Prepare candidates for reranking
        candidates: list[tuple[str, Memory, float]] = []
        for mem_id, rrf_score in fused:
            # Get memory from either index
            memory = self.bm25.get_memory(user_id, mem_id)
            if memory is None:
                memory = self.vector.get_memory(user_id, mem_id)
            if memory is not None:
                candidates.append((mem_id, memory, rrf_score))

        # Rerank if enabled and we have a cross-encoder
        if use_reranker and isinstance(self.reranker, CrossEncoderReranker):
            rerank_results = self.reranker.rerank(query, candidates, top_k=top_k)
            metrics.reranker_used = True
        else:
            # Use fallback (sort by RRF score)
            fallback = FallbackReranker()
            rerank_results = fallback.rerank(query, candidates, top_k=top_k)
            metrics.reranker_used = False

        metrics.stage2_time_ms = (time.perf_counter() - stage2_start) * 1000

        # Build final results with source tracking
        results = self._build_results(
            rerank_results, bm25_results, vector_results, graph_results
        )

        metrics.final_results = len(results)
        metrics.total_time_ms = (time.perf_counter() - start_time) * 1000

        return results, metrics

    def _build_results(
        self,
        rerank_results: list[RerankResult],
        bm25_results: list[tuple[str, float]],
        vector_results: list[tuple[str, float]],
        graph_results: list[tuple[str, float]] | None = None,
    ) -> list[HybridResult]:
        """Build HybridResult objects with source tracking.

        Args:
            rerank_results: Results from reranker.
            bm25_results: Original BM25 results.
            vector_results: Original vector results.
            graph_results: Optional graph results.

        Returns:
            List of HybridResult objects.
        """
        # Build lookup maps
        bm25_map = {mem_id: (rank + 1, score) for rank, (mem_id, score) in enumerate(bm25_results)}
        vector_map = {mem_id: (rank + 1, score) for rank, (mem_id, score) in enumerate(vector_results)}
        graph_map = {mem_id: (rank + 1, score) for rank, (mem_id, score) in enumerate(graph_results or [])}

        results: list[HybridResult] = []
        for rr in rerank_results:
            source_scores: dict[str, float] = {"reranker": rr.score}
            source_ranks: dict[str, int] = {"reranker": 0}  # Placeholder

            if rr.memory_id in bm25_map:
                rank, score = bm25_map[rr.memory_id]
                source_scores["bm25"] = score
                source_ranks["bm25"] = rank

            if rr.memory_id in vector_map:
                rank, score = vector_map[rr.memory_id]
                source_scores["vector"] = score
                source_ranks["vector"] = rank

            if rr.memory_id in graph_map:
                rank, score = graph_map[rr.memory_id]
                source_scores["graph"] = score
                source_ranks["graph"] = rank

            results.append(
                HybridResult(
                    memory=rr.memory,
                    score=rr.score,
                    memory_id=rr.memory_id,
                    source_scores=source_scores,
                    source_ranks=source_ranks,
                )
            )

        return results

    async def retrieve_simple(
        self,
        query: str,
        user_id: str,
        top_k: int = 10,
    ) -> list[tuple[Memory, float]]:
        """Simplified retrieval returning (Memory, score) tuples.

        Args:
            query: Search query.
            user_id: User ID to search for.
            top_k: Number of results to return.

        Returns:
            List of (Memory, score) tuples.
        """
        results, _ = await self.retrieve(query, user_id, top_k)
        return [(r.memory, r.score) for r in results]

    def has_index(self, user_id: str) -> bool:
        """Check if indexes exist for a user.

        Args:
            user_id: User ID to check.

        Returns:
            True if both BM25 and vector indexes exist.
        """
        return self.bm25.has_index(user_id) and self.vector.has_index(user_id)

    def index_stats(self, user_id: str) -> dict[str, int | float | bool]:
        """Get combined index statistics.

        Args:
            user_id: User ID.

        Returns:
            Dictionary with combined stats from both indexes.
        """
        bm25_stats = self.bm25.index_stats(user_id)
        vector_stats = self.vector.index_stats(user_id)

        return {
            "bm25_docs": bm25_stats["total_docs"],
            "bm25_vocab_size": bm25_stats["vocabulary_size"],
            "vector_docs": vector_stats["total_docs"],
            "vector_dim": vector_stats["embedding_dim"],
            "vector_model_loaded": vector_stats["model_loaded"],
            "reranker_loaded": self.reranker.is_loaded(),
        }


def create_hybrid_retriever(
    use_cross_encoder: bool = True,
    use_query_rewriter: bool = True,
    bm25_weight: float = 1.0,
    vector_weight: float = 1.0,
) -> HybridRetriever:
    """Factory function to create a HybridRetriever.

    Args:
        use_cross_encoder: If True, use cross-encoder reranking.
        use_query_rewriter: If True, include query rewriter.
        bm25_weight: Weight for BM25 in RRF fusion.
        vector_weight: Weight for vector in RRF fusion.

    Returns:
        Configured HybridRetriever instance.
    """
    query_rewriter = QueryRewriter() if use_query_rewriter else None

    return HybridRetriever(
        query_rewriter=query_rewriter,
        use_cross_encoder=use_cross_encoder,
        bm25_weight=bm25_weight,
        vector_weight=vector_weight,
    )
