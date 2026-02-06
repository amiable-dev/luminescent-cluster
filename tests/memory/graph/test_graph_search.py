# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""TDD: RED Phase - Tests for GraphSearch.

These tests define the expected behavior for the GraphSearch class
that provides graph-based candidate generation for HybridRetriever.

Related GitHub Issues:
- #125: Implement GraphSearch for Stage 1 candidate generation

ADR Reference: ADR-003 Memory Architecture, Phase 4 (Knowledge Graph)
"""

import pytest

from luminescent_cluster.memory.extraction.entities import EntityType
from luminescent_cluster.memory.graph.types import GraphEdge, GraphNode, RelationshipType
from luminescent_cluster.memory.graph.graph_store import KnowledgeGraph


class TestGraphSearchExists:
    """TDD: Tests for GraphSearch existence."""

    def test_graph_search_exists(self):
        """GraphSearch class should be defined.

        GitHub Issue: #125
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.graph_search import GraphSearch

        assert GraphSearch is not None


class TestGraphSearchConstruction:
    """TDD: Tests for GraphSearch construction."""

    def test_can_create_graph_search(self):
        """Should create GraphSearch instance.

        GitHub Issue: #125
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.graph_search import GraphSearch

        search = GraphSearch()
        assert search is not None

    def test_can_register_graph_for_user(self):
        """Should register a graph for a user.

        GitHub Issue: #125
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.graph_search import GraphSearch

        search = GraphSearch()
        graph = KnowledgeGraph(user_id="user-123")

        search.register_graph("user-123", graph)

        assert search.has_graph("user-123")


class TestGraphSearchInterface:
    """TDD: Tests for search interface matching BM25/Vector."""

    def test_search_returns_list_of_tuples(self):
        """Search should return list of (memory_id, score) tuples.

        GitHub Issue: #125
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.graph_search import GraphSearch

        search = GraphSearch()
        graph = KnowledgeGraph(user_id="user-123")
        graph.add_node(GraphNode(
            "auth-service", EntityType.SERVICE, "auth-service",
            memory_ids=["mem-1", "mem-2"]
        ))
        search.register_graph("user-123", graph)

        results = search.search("user-123", "auth-service", top_k=10)

        assert isinstance(results, list)
        for item in results:
            assert isinstance(item, tuple)
            assert len(item) == 2
            assert isinstance(item[0], str)  # memory_id
            assert isinstance(item[1], float)  # score

    def test_search_returns_memory_ids_from_matching_node(self):
        """Should return memory IDs from nodes matching query.

        GitHub Issue: #125
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.graph_search import GraphSearch

        search = GraphSearch()
        graph = KnowledgeGraph(user_id="user-123")
        graph.add_node(GraphNode(
            "auth-service", EntityType.SERVICE, "auth-service",
            memory_ids=["mem-1", "mem-2"]
        ))
        search.register_graph("user-123", graph)

        results = search.search("user-123", "auth-service", top_k=10)

        memory_ids = [r[0] for r in results]
        assert "mem-1" in memory_ids
        assert "mem-2" in memory_ids

    def test_search_returns_empty_for_no_match(self):
        """Should return empty list when no nodes match.

        GitHub Issue: #125
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.graph_search import GraphSearch

        search = GraphSearch()
        graph = KnowledgeGraph(user_id="user-123")
        search.register_graph("user-123", graph)

        results = search.search("user-123", "unknown-query", top_k=10)

        assert results == []

    def test_search_returns_empty_for_missing_user(self):
        """Should return empty list for unregistered user.

        GitHub Issue: #125
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.graph_search import GraphSearch

        search = GraphSearch()

        results = search.search("unknown-user", "query", top_k=10)

        assert results == []


class TestGraphSearchTraversal:
    """TDD: Tests for graph traversal in search."""

    def test_search_includes_neighbor_memories(self):
        """Should include memories from related nodes.

        GitHub Issue: #125
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.graph_search import GraphSearch

        search = GraphSearch()
        graph = KnowledgeGraph(user_id="user-123")
        graph.add_node(GraphNode(
            "auth-service", EntityType.SERVICE, "auth-service",
            memory_ids=["mem-1"]
        ))
        graph.add_node(GraphNode(
            "postgresql", EntityType.DEPENDENCY, "PostgreSQL",
            memory_ids=["mem-2"]
        ))
        graph.add_edge(GraphEdge(
            "auth-service", "postgresql", RelationshipType.DEPENDS_ON, "mem-1"
        ))
        search.register_graph("user-123", graph)

        # Search for auth-service should also return postgresql's memory
        results = search.search("user-123", "auth-service", top_k=10)

        memory_ids = [r[0] for r in results]
        assert "mem-1" in memory_ids
        assert "mem-2" in memory_ids

    def test_search_includes_predecessor_memories(self):
        """Should include memories from nodes pointing to match.

        GitHub Issue: #125
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.graph_search import GraphSearch

        search = GraphSearch()
        graph = KnowledgeGraph(user_id="user-123")
        graph.add_node(GraphNode(
            "auth-service", EntityType.SERVICE, "auth-service",
            memory_ids=["mem-1"]
        ))
        graph.add_node(GraphNode(
            "payment-service", EntityType.SERVICE, "payment-service",
            memory_ids=["mem-2"]
        ))
        graph.add_node(GraphNode(
            "postgresql", EntityType.DEPENDENCY, "PostgreSQL",
            memory_ids=["mem-3"]
        ))
        graph.add_edge(GraphEdge(
            "auth-service", "postgresql", RelationshipType.DEPENDS_ON, "mem-1"
        ))
        graph.add_edge(GraphEdge(
            "payment-service", "postgresql", RelationshipType.DEPENDS_ON, "mem-2"
        ))
        search.register_graph("user-123", graph)

        # Search for postgresql should return services that depend on it
        results = search.search("user-123", "postgresql", top_k=10)

        memory_ids = [r[0] for r in results]
        assert "mem-1" in memory_ids
        assert "mem-2" in memory_ids
        assert "mem-3" in memory_ids

    def test_search_respects_top_k(self):
        """Should respect top_k limit.

        GitHub Issue: #125
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.graph_search import GraphSearch

        search = GraphSearch()
        graph = KnowledgeGraph(user_id="user-123")
        graph.add_node(GraphNode(
            "service", EntityType.SERVICE, "service",
            memory_ids=["m1", "m2", "m3", "m4", "m5"]
        ))
        search.register_graph("user-123", graph)

        results = search.search("user-123", "service", top_k=3)

        assert len(results) <= 3


class TestGraphSearchScoring:
    """TDD: Tests for scoring in graph search."""

    def test_direct_match_scores_higher(self):
        """Direct matches should score higher than traversed.

        GitHub Issue: #125
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.graph_search import GraphSearch

        search = GraphSearch()
        graph = KnowledgeGraph(user_id="user-123")
        graph.add_node(GraphNode(
            "auth-service", EntityType.SERVICE, "auth-service",
            memory_ids=["mem-direct"]
        ))
        graph.add_node(GraphNode(
            "postgresql", EntityType.DEPENDENCY, "PostgreSQL",
            memory_ids=["mem-neighbor"]
        ))
        graph.add_edge(GraphEdge(
            "auth-service", "postgresql", RelationshipType.DEPENDS_ON, "mem-direct"
        ))
        search.register_graph("user-123", graph)

        results = search.search("user-123", "auth-service", top_k=10)

        # Results are sorted by score descending
        result_dict = {r[0]: r[1] for r in results}
        assert result_dict["mem-direct"] > result_dict["mem-neighbor"]


class TestGraphSearchFuzzyMatching:
    """TDD: Tests for fuzzy entity matching in queries."""

    def test_case_insensitive_matching(self):
        """Should match entities case-insensitively.

        GitHub Issue: #125
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.graph_search import GraphSearch

        search = GraphSearch()
        graph = KnowledgeGraph(user_id="user-123")
        graph.add_node(GraphNode(
            "auth-service", EntityType.SERVICE, "auth-service",
            memory_ids=["mem-1"]
        ))
        search.register_graph("user-123", graph)

        results = search.search("user-123", "AUTH-SERVICE", top_k=10)

        assert len(results) > 0

    def test_partial_matching(self):
        """Should match partial entity names.

        GitHub Issue: #125
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.graph_search import GraphSearch

        search = GraphSearch()
        graph = KnowledgeGraph(user_id="user-123")
        graph.add_node(GraphNode(
            "auth-service", EntityType.SERVICE, "auth-service",
            memory_ids=["mem-1"]
        ))
        search.register_graph("user-123", graph)

        results = search.search("user-123", "what uses auth", top_k=10)

        memory_ids = [r[0] for r in results]
        assert "mem-1" in memory_ids


class TestModuleExports:
    """TDD: Tests for module exports."""

    def test_module_exports_graph_search(self):
        """Module should export GraphSearch.

        GitHub Issue: #125
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph import GraphSearch

        assert GraphSearch is not None
