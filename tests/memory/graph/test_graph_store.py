# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""TDD: RED Phase - Tests for KnowledgeGraph store.

These tests define the expected behavior for the KnowledgeGraph class
that provides graph storage and traversal using NetworkX.

Related GitHub Issues:
- #123: Implement KnowledgeGraph with NetworkX backend

ADR Reference: ADR-003 Memory Architecture, Phase 4 (Knowledge Graph)
"""

import pytest

from luminescent_cluster.memory.extraction.entities import EntityType
from luminescent_cluster.memory.graph.types import GraphEdge, GraphNode, RelationshipType


class TestKnowledgeGraphExists:
    """TDD: Tests for KnowledgeGraph existence."""

    def test_knowledge_graph_exists(self):
        """KnowledgeGraph class should be defined.

        GitHub Issue: #123
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.graph_store import KnowledgeGraph

        assert KnowledgeGraph is not None

    def test_knowledge_graph_requires_user_id(self):
        """KnowledgeGraph should require user_id.

        GitHub Issue: #123
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.graph_store import KnowledgeGraph

        graph = KnowledgeGraph(user_id="user-123")
        assert graph.user_id == "user-123"


class TestKnowledgeGraphNodeOperations:
    """TDD: Tests for node operations."""

    def test_add_node(self):
        """Should add a node to the graph.

        GitHub Issue: #123
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.graph_store import KnowledgeGraph

        graph = KnowledgeGraph(user_id="user-123")
        node = GraphNode(
            id="auth-service",
            entity_type=EntityType.SERVICE,
            name="auth-service",
        )

        graph.add_node(node)

        assert graph.has_node("auth-service")

    def test_get_node(self):
        """Should get a node by ID.

        GitHub Issue: #123
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.graph_store import KnowledgeGraph

        graph = KnowledgeGraph(user_id="user-123")
        node = GraphNode(
            id="auth-service",
            entity_type=EntityType.SERVICE,
            name="auth-service",
            memory_ids=["mem-1"],
        )
        graph.add_node(node)

        retrieved = graph.get_node("auth-service")

        assert retrieved is not None
        assert retrieved.id == "auth-service"
        assert retrieved.name == "auth-service"
        assert retrieved.entity_type == EntityType.SERVICE

    def test_get_node_returns_none_for_missing(self):
        """Should return None for missing node.

        GitHub Issue: #123
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.graph_store import KnowledgeGraph

        graph = KnowledgeGraph(user_id="user-123")

        retrieved = graph.get_node("nonexistent")

        assert retrieved is None

    def test_remove_node(self):
        """Should remove a node from the graph.

        GitHub Issue: #123
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.graph_store import KnowledgeGraph

        graph = KnowledgeGraph(user_id="user-123")
        node = GraphNode(
            id="auth-service",
            entity_type=EntityType.SERVICE,
            name="auth-service",
        )
        graph.add_node(node)

        result = graph.remove_node("auth-service")

        assert result is True
        assert not graph.has_node("auth-service")

    def test_remove_node_returns_false_for_missing(self):
        """Should return False when removing missing node.

        GitHub Issue: #123
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.graph_store import KnowledgeGraph

        graph = KnowledgeGraph(user_id="user-123")

        result = graph.remove_node("nonexistent")

        assert result is False

    def test_node_count(self):
        """Should return correct node count.

        GitHub Issue: #123
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.graph_store import KnowledgeGraph

        graph = KnowledgeGraph(user_id="user-123")
        assert graph.node_count == 0

        graph.add_node(GraphNode(id="n1", entity_type=EntityType.SERVICE, name="n1"))
        assert graph.node_count == 1

        graph.add_node(GraphNode(id="n2", entity_type=EntityType.DEPENDENCY, name="n2"))
        assert graph.node_count == 2

    def test_get_all_nodes(self):
        """Should return all nodes.

        GitHub Issue: #123
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.graph_store import KnowledgeGraph

        graph = KnowledgeGraph(user_id="user-123")
        graph.add_node(GraphNode(id="n1", entity_type=EntityType.SERVICE, name="n1"))
        graph.add_node(GraphNode(id="n2", entity_type=EntityType.DEPENDENCY, name="n2"))

        nodes = graph.get_all_nodes()

        assert len(nodes) == 2
        node_ids = {n.id for n in nodes}
        assert node_ids == {"n1", "n2"}


class TestKnowledgeGraphEdgeOperations:
    """TDD: Tests for edge operations."""

    def test_add_edge(self):
        """Should add an edge to the graph.

        GitHub Issue: #123
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.graph_store import KnowledgeGraph

        graph = KnowledgeGraph(user_id="user-123")
        graph.add_node(GraphNode(id="auth", entity_type=EntityType.SERVICE, name="auth"))
        graph.add_node(GraphNode(id="pg", entity_type=EntityType.DEPENDENCY, name="pg"))

        edge = GraphEdge(
            source_id="auth",
            target_id="pg",
            relationship=RelationshipType.DEPENDS_ON,
            memory_id="mem-1",
        )
        graph.add_edge(edge)

        assert graph.has_edge("auth", "pg")

    def test_add_edge_creates_missing_nodes(self):
        """Should create missing nodes when adding edge.

        GitHub Issue: #123
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.graph_store import KnowledgeGraph

        graph = KnowledgeGraph(user_id="user-123")

        edge = GraphEdge(
            source_id="auth",
            target_id="pg",
            relationship=RelationshipType.DEPENDS_ON,
            memory_id="mem-1",
        )
        graph.add_edge(edge)

        assert graph.has_node("auth")
        assert graph.has_node("pg")

    def test_get_edge(self):
        """Should get an edge by source and target.

        GitHub Issue: #123
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.graph_store import KnowledgeGraph

        graph = KnowledgeGraph(user_id="user-123")
        edge = GraphEdge(
            source_id="auth",
            target_id="pg",
            relationship=RelationshipType.DEPENDS_ON,
            confidence=0.9,
            memory_id="mem-1",
        )
        graph.add_edge(edge)

        retrieved = graph.get_edge("auth", "pg")

        assert retrieved is not None
        assert retrieved.source_id == "auth"
        assert retrieved.target_id == "pg"
        assert retrieved.relationship == RelationshipType.DEPENDS_ON
        assert retrieved.confidence == 0.9

    def test_get_edge_returns_none_for_missing(self):
        """Should return None for missing edge.

        GitHub Issue: #123
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.graph_store import KnowledgeGraph

        graph = KnowledgeGraph(user_id="user-123")

        retrieved = graph.get_edge("auth", "pg")

        assert retrieved is None

    def test_remove_edge(self):
        """Should remove an edge from the graph.

        GitHub Issue: #123
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.graph_store import KnowledgeGraph

        graph = KnowledgeGraph(user_id="user-123")
        edge = GraphEdge(
            source_id="auth",
            target_id="pg",
            relationship=RelationshipType.DEPENDS_ON,
            memory_id="mem-1",
        )
        graph.add_edge(edge)

        result = graph.remove_edge("auth", "pg")

        assert result is True
        assert not graph.has_edge("auth", "pg")

    def test_edge_count(self):
        """Should return correct edge count.

        GitHub Issue: #123
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.graph_store import KnowledgeGraph

        graph = KnowledgeGraph(user_id="user-123")
        assert graph.edge_count == 0

        graph.add_edge(GraphEdge("a", "b", RelationshipType.DEPENDS_ON, "m1"))
        assert graph.edge_count == 1

        graph.add_edge(GraphEdge("b", "c", RelationshipType.USES, "m2"))
        assert graph.edge_count == 2

    def test_get_edges_from_node(self):
        """Should get all outgoing edges from a node.

        GitHub Issue: #123
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.graph_store import KnowledgeGraph

        graph = KnowledgeGraph(user_id="user-123")
        graph.add_edge(GraphEdge("auth", "pg", RelationshipType.DEPENDS_ON, "m1"))
        graph.add_edge(GraphEdge("auth", "redis", RelationshipType.DEPENDS_ON, "m2"))
        graph.add_edge(GraphEdge("other", "pg", RelationshipType.USES, "m3"))

        edges = graph.get_edges_from("auth")

        assert len(edges) == 2
        targets = {e.target_id for e in edges}
        assert targets == {"pg", "redis"}

    def test_get_edges_to_node(self):
        """Should get all incoming edges to a node.

        GitHub Issue: #123
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.graph_store import KnowledgeGraph

        graph = KnowledgeGraph(user_id="user-123")
        graph.add_edge(GraphEdge("auth", "pg", RelationshipType.DEPENDS_ON, "m1"))
        graph.add_edge(GraphEdge("payment", "pg", RelationshipType.DEPENDS_ON, "m2"))
        graph.add_edge(GraphEdge("auth", "redis", RelationshipType.USES, "m3"))

        edges = graph.get_edges_to("pg")

        assert len(edges) == 2
        sources = {e.source_id for e in edges}
        assert sources == {"auth", "payment"}


class TestKnowledgeGraphNeighbors:
    """TDD: Tests for neighbor queries."""

    def test_get_neighbors(self):
        """Should get all neighbor nodes.

        GitHub Issue: #123
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.graph_store import KnowledgeGraph

        graph = KnowledgeGraph(user_id="user-123")
        graph.add_node(GraphNode("auth", EntityType.SERVICE, "auth"))
        graph.add_node(GraphNode("pg", EntityType.DEPENDENCY, "pg"))
        graph.add_node(GraphNode("redis", EntityType.DEPENDENCY, "redis"))
        graph.add_edge(GraphEdge("auth", "pg", RelationshipType.DEPENDS_ON, "m1"))
        graph.add_edge(GraphEdge("auth", "redis", RelationshipType.DEPENDS_ON, "m2"))

        neighbors = graph.get_neighbors("auth")

        assert len(neighbors) == 2
        names = {n.name for n in neighbors}
        assert names == {"pg", "redis"}

    def test_get_neighbors_with_relationship_filter(self):
        """Should filter neighbors by relationship type.

        GitHub Issue: #123
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.graph_store import KnowledgeGraph

        graph = KnowledgeGraph(user_id="user-123")
        graph.add_node(GraphNode("auth", EntityType.SERVICE, "auth"))
        graph.add_node(GraphNode("pg", EntityType.DEPENDENCY, "pg"))
        graph.add_node(GraphNode("fastapi", EntityType.FRAMEWORK, "fastapi"))
        graph.add_edge(GraphEdge("auth", "pg", RelationshipType.DEPENDS_ON, "m1"))
        graph.add_edge(GraphEdge("auth", "fastapi", RelationshipType.USES, "m2"))

        neighbors = graph.get_neighbors("auth", relationship=RelationshipType.DEPENDS_ON)

        assert len(neighbors) == 1
        assert neighbors[0].name == "pg"

    def test_get_predecessors(self):
        """Should get nodes that point to this node.

        GitHub Issue: #123
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.graph_store import KnowledgeGraph

        graph = KnowledgeGraph(user_id="user-123")
        graph.add_node(GraphNode("auth", EntityType.SERVICE, "auth"))
        graph.add_node(GraphNode("payment", EntityType.SERVICE, "payment"))
        graph.add_node(GraphNode("pg", EntityType.DEPENDENCY, "pg"))
        graph.add_edge(GraphEdge("auth", "pg", RelationshipType.DEPENDS_ON, "m1"))
        graph.add_edge(GraphEdge("payment", "pg", RelationshipType.DEPENDS_ON, "m2"))

        predecessors = graph.get_predecessors("pg")

        assert len(predecessors) == 2
        names = {n.name for n in predecessors}
        assert names == {"auth", "payment"}


class TestKnowledgeGraphSerialization:
    """TDD: Tests for serialization."""

    def test_to_dict(self):
        """Should serialize graph to dict.

        GitHub Issue: #123
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.graph_store import KnowledgeGraph

        graph = KnowledgeGraph(user_id="user-123")
        graph.add_node(GraphNode("auth", EntityType.SERVICE, "auth"))
        graph.add_edge(GraphEdge("auth", "pg", RelationshipType.DEPENDS_ON, "m1"))

        data = graph.to_dict()

        assert "user_id" in data
        assert data["user_id"] == "user-123"
        assert "nodes" in data
        assert "edges" in data

    def test_from_dict(self):
        """Should deserialize graph from dict.

        GitHub Issue: #123
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.graph_store import KnowledgeGraph

        original = KnowledgeGraph(user_id="user-123")
        original.add_node(GraphNode("auth", EntityType.SERVICE, "auth"))
        original.add_edge(GraphEdge("auth", "pg", RelationshipType.DEPENDS_ON, "m1"))

        data = original.to_dict()
        restored = KnowledgeGraph.from_dict(data)

        assert restored.user_id == "user-123"
        assert restored.has_node("auth")
        assert restored.has_node("pg")
        assert restored.has_edge("auth", "pg")

    def test_roundtrip_preserves_data(self):
        """Serialization roundtrip should preserve all data.

        GitHub Issue: #123
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.graph_store import KnowledgeGraph

        original = KnowledgeGraph(user_id="user-123")
        original.add_node(
            GraphNode(
                "auth",
                EntityType.SERVICE,
                "auth-service",
                memory_ids=["m1", "m2"],
                metadata={"team": "backend"},
            )
        )
        original.add_edge(
            GraphEdge("auth", "pg", RelationshipType.DEPENDS_ON, "m1", confidence=0.9)
        )

        data = original.to_dict()
        restored = KnowledgeGraph.from_dict(data)

        node = restored.get_node("auth")
        assert node.name == "auth-service"
        assert node.memory_ids == ["m1", "m2"]
        assert node.metadata == {"team": "backend"}

        edge = restored.get_edge("auth", "pg")
        assert edge.confidence == 0.9


class TestKnowledgeGraphClear:
    """TDD: Tests for clearing graph."""

    def test_clear_removes_all(self):
        """Should remove all nodes and edges.

        GitHub Issue: #123
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.graph_store import KnowledgeGraph

        graph = KnowledgeGraph(user_id="user-123")
        graph.add_node(GraphNode("auth", EntityType.SERVICE, "auth"))
        graph.add_edge(GraphEdge("auth", "pg", RelationshipType.DEPENDS_ON, "m1"))

        graph.clear()

        assert graph.node_count == 0
        assert graph.edge_count == 0


class TestModuleExports:
    """TDD: Tests for module exports."""

    def test_module_exports_knowledge_graph(self):
        """Module should export KnowledgeGraph.

        GitHub Issue: #123
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph import KnowledgeGraph

        assert KnowledgeGraph is not None
