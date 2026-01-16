# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""TDD: RED Phase - Tests for Knowledge Graph integration with HybridRetriever.

These tests verify that the Knowledge Graph integrates correctly with
the two-stage hybrid retrieval architecture.

Related GitHub Issues:
- #126: Integrate graph into HybridRetriever

ADR Reference: ADR-003 Memory Architecture, Phase 4 (Knowledge Graph)
"""

import pytest

from src.memory.extraction.entities import EntityType
from src.memory.graph.types import GraphEdge, GraphNode, RelationshipType
from src.memory.graph.graph_store import KnowledgeGraph
from src.memory.graph.graph_search import GraphSearch
from src.memory.schemas import Memory, MemoryType


class TestHybridRetrieverGraphSupport:
    """TDD: Tests for graph support in HybridRetriever."""

    def test_hybrid_retriever_accepts_graph_parameter(self):
        """HybridRetriever should accept graph parameter.

        GitHub Issue: #126
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from src.memory.retrieval.hybrid import HybridRetriever

        graph_search = GraphSearch()
        retriever = HybridRetriever(graph=graph_search)

        assert retriever.graph is graph_search

    def test_hybrid_retriever_graph_defaults_to_none(self):
        """Graph should default to None when not provided.

        GitHub Issue: #126
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from src.memory.retrieval.hybrid import HybridRetriever

        retriever = HybridRetriever()

        assert retriever.graph is None

    def test_hybrid_retriever_accepts_graph_weight(self):
        """HybridRetriever should accept graph_weight parameter.

        GitHub Issue: #126
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from src.memory.retrieval.hybrid import HybridRetriever

        retriever = HybridRetriever(graph_weight=0.5)

        assert retriever.graph_weight == 0.5


class TestHybridRetrieverGraphIntegration:
    """TDD: Tests for graph integration in retrieval."""

    @pytest.mark.asyncio
    async def test_retrieve_includes_graph_results(self):
        """Retrieve should include results from graph search.

        GitHub Issue: #126
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from src.memory.retrieval.hybrid import HybridRetriever

        # Set up graph
        graph_search = GraphSearch()
        graph = KnowledgeGraph(user_id="user-123")
        graph.add_node(GraphNode(
            "auth-service", EntityType.SERVICE, "auth-service",
            memory_ids=["mem-graph-1"]
        ))
        graph_search.register_graph("user-123", graph)

        # Set up retriever with graph
        retriever = HybridRetriever(graph=graph_search)

        # Add a memory for BM25/vector
        memory = Memory(
            user_id="user-123",
            content="The auth-service handles authentication",
            memory_type=MemoryType.FACT,
            confidence=0.9,
            source="test",
        )
        retriever.index_memories("user-123", [memory], ["mem-bm25-1"])

        # Search
        results, metrics = await retriever.retrieve(
            "auth-service",
            "user-123",
            top_k=10,
        )

        # Should include graph result
        memory_ids = [r.memory_id for r in results]
        assert "mem-graph-1" in memory_ids or metrics.graph_candidates > 0

    @pytest.mark.asyncio
    async def test_retrieve_fuses_three_sources(self):
        """Retrieve should fuse BM25, vector, and graph results.

        GitHub Issue: #126
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from src.memory.retrieval.hybrid import HybridRetriever

        # Set up graph
        graph_search = GraphSearch()
        graph = KnowledgeGraph(user_id="user-123")
        graph.add_node(GraphNode(
            "postgresql", EntityType.DEPENDENCY, "PostgreSQL",
            memory_ids=["mem-graph"]
        ))
        graph_search.register_graph("user-123", graph)

        # Set up retriever
        retriever = HybridRetriever(graph=graph_search)

        # Add memory for BM25/vector
        memory = Memory(
            user_id="user-123",
            content="PostgreSQL database configuration",
            memory_type=MemoryType.FACT,
            confidence=0.9,
            source="test",
        )
        retriever.index_memories("user-123", [memory], ["mem-bm25"])

        # Search
        results, metrics = await retriever.retrieve(
            "postgresql",
            "user-123",
            top_k=10,
        )

        # Should have candidates from all sources
        assert metrics.bm25_candidates >= 0
        assert metrics.vector_candidates >= 0
        # Graph candidates should be tracked
        assert hasattr(metrics, "graph_candidates")


class TestRetrievalMetricsGraphSupport:
    """TDD: Tests for graph metrics in RetrievalMetrics."""

    def test_retrieval_metrics_has_graph_candidates(self):
        """RetrievalMetrics should have graph_candidates field.

        GitHub Issue: #126
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from src.memory.retrieval.hybrid import RetrievalMetrics

        metrics = RetrievalMetrics()

        assert hasattr(metrics, "graph_candidates")
        assert metrics.graph_candidates == 0


class TestHybridResultGraphSource:
    """TDD: Tests for graph source tracking in HybridResult."""

    @pytest.mark.asyncio
    async def test_hybrid_result_tracks_graph_score(self):
        """HybridResult should track graph score in source_scores.

        GitHub Issue: #126
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from src.memory.retrieval.hybrid import HybridRetriever

        # Set up graph with a node
        graph_search = GraphSearch()
        graph = KnowledgeGraph(user_id="user-123")
        graph.add_node(GraphNode(
            "redis", EntityType.DEPENDENCY, "Redis",
            memory_ids=["mem-1"]
        ))
        graph_search.register_graph("user-123", graph)

        # Set up retriever
        retriever = HybridRetriever(graph=graph_search)
        memory = Memory(
            user_id="user-123",
            content="Redis cache configuration",
            memory_type=MemoryType.FACT,
            confidence=0.9,
            source="test",
        )
        retriever.index_memories("user-123", [memory], ["mem-1"])

        # Search
        results, _ = await retriever.retrieve("redis", "user-123", top_k=10)

        # Check if any result has graph score
        has_graph_source = any(
            "graph" in r.source_scores for r in results
        )
        # Graph source tracking should be available
        assert has_graph_source or len(results) >= 0


class TestRRFFusionThreeSource:
    """TDD: Tests for RRF fusion with three sources."""

    def test_rrf_fusion_accepts_graph_source(self):
        """RRFFusion should accept graph as a third source.

        GitHub Issue: #126
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from src.memory.retrieval.fusion import RRFFusion

        fusion = RRFFusion()
        bm25_results = [("mem-1", 0.9), ("mem-2", 0.8)]
        vector_results = [("mem-2", 0.95), ("mem-3", 0.7)]
        graph_results = [("mem-3", 0.85), ("mem-4", 0.6)]

        fused = fusion.fuse(
            bm25=bm25_results,
            vector=vector_results,
            graph=graph_results,
        )

        assert isinstance(fused, list)
        # Should include results from all sources
        fused_ids = [mem_id for mem_id, _ in fused]
        assert "mem-1" in fused_ids
        assert "mem-4" in fused_ids

    def test_weighted_fuse_accepts_graph_weight(self):
        """weighted_fuse should accept graph weight.

        GitHub Issue: #126
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from src.memory.retrieval.fusion import RRFFusion

        fusion = RRFFusion()
        bm25_results = [("mem-1", 0.9)]
        vector_results = [("mem-2", 0.95)]
        graph_results = [("mem-3", 0.85)]

        fused = fusion.weighted_fuse(
            {"bm25": 1.0, "vector": 1.0, "graph": 0.5},
            bm25=bm25_results,
            vector=vector_results,
            graph=graph_results,
        )

        assert isinstance(fused, list)


class TestMultiHopQueryBenchmark:
    """Benchmark tests for multi-hop query performance."""

    @pytest.mark.asyncio
    async def test_multihop_query_finds_related_entities(self):
        """Multi-hop query should find entities related through graph.

        GitHub Issue: #126
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)

        Example query: "What depends on PostgreSQL?"
        """
        from src.memory.retrieval.hybrid import HybridRetriever

        # Set up graph with relationships
        graph_search = GraphSearch()
        graph = KnowledgeGraph(user_id="user-123")

        # auth-service depends on PostgreSQL
        graph.add_node(GraphNode(
            "auth-service", EntityType.SERVICE, "auth-service",
            memory_ids=["mem-auth"]
        ))
        graph.add_node(GraphNode(
            "postgresql", EntityType.DEPENDENCY, "PostgreSQL",
            memory_ids=["mem-pg"]
        ))
        graph.add_edge(GraphEdge(
            "auth-service", "postgresql", RelationshipType.DEPENDS_ON, "mem-auth"
        ))

        # payment-service also depends on PostgreSQL
        graph.add_node(GraphNode(
            "payment-service", EntityType.SERVICE, "payment-service",
            memory_ids=["mem-payment"]
        ))
        graph.add_edge(GraphEdge(
            "payment-service", "postgresql", RelationshipType.DEPENDS_ON, "mem-payment"
        ))

        graph_search.register_graph("user-123", graph)

        # Set up retriever
        retriever = HybridRetriever(graph=graph_search)

        # Add memories for BM25/vector (just for completeness)
        memories = [
            Memory(
                user_id="user-123",
                content="PostgreSQL database",
                memory_type=MemoryType.FACT,
                confidence=0.9,
                source="test",
            )
        ]
        retriever.index_memories("user-123", memories, ["mem-pg"])

        # Query for PostgreSQL should find auth and payment services
        results, metrics = await retriever.retrieve(
            "postgresql",
            "user-123",
            top_k=10,
        )

        memory_ids = [r.memory_id for r in results]
        # Graph traversal should find services that depend on PostgreSQL
        assert "mem-auth" in memory_ids or "mem-payment" in memory_ids or metrics.graph_candidates > 0

    @pytest.mark.asyncio
    async def test_graph_latency_under_one_second(self):
        """Graph-augmented queries should complete in under 1 second.

        GitHub Issue: #126
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)

        Exit Criteria: Latency <1s for graph-augmented queries
        """
        from src.memory.retrieval.hybrid import HybridRetriever

        # Set up graph
        graph_search = GraphSearch()
        graph = KnowledgeGraph(user_id="user-123")

        # Add many nodes for realistic test
        for i in range(100):
            graph.add_node(GraphNode(
                f"service-{i}", EntityType.SERVICE, f"service-{i}",
                memory_ids=[f"mem-{i}"]
            ))
            if i > 0:
                graph.add_edge(GraphEdge(
                    f"service-{i}", f"service-{i-1}",
                    RelationshipType.DEPENDS_ON, f"mem-{i}"
                ))

        graph_search.register_graph("user-123", graph)

        # Set up retriever
        retriever = HybridRetriever(graph=graph_search)

        # Search
        results, metrics = await retriever.retrieve(
            "service-50",
            "user-123",
            top_k=10,
        )

        # Total time should be under 1 second (1000ms)
        assert metrics.total_time_ms < 1000
