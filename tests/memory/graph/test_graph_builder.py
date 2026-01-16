# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""TDD: RED Phase - Tests for GraphBuilder.

These tests define the expected behavior for the GraphBuilder class
that constructs a knowledge graph from Memory entities.

Related GitHub Issues:
- #124: Implement GraphBuilder from Memory entities

ADR Reference: ADR-003 Memory Architecture, Phase 4 (Knowledge Graph)
"""

import pytest

from src.memory.extraction.entities import EntityType
from src.memory.graph.types import GraphNode, RelationshipType
from src.memory.schemas import Memory, MemoryType


class TestGraphBuilderExists:
    """TDD: Tests for GraphBuilder existence."""

    def test_graph_builder_exists(self):
        """GraphBuilder class should be defined.

        GitHub Issue: #124
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from src.memory.graph.graph_builder import GraphBuilder

        assert GraphBuilder is not None

    def test_graph_builder_requires_user_id(self):
        """GraphBuilder should require user_id.

        GitHub Issue: #124
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from src.memory.graph.graph_builder import GraphBuilder

        builder = GraphBuilder(user_id="user-123")
        assert builder.user_id == "user-123"


class TestGraphBuilderAddMemory:
    """TDD: Tests for adding memories to the graph."""

    def test_add_memory_creates_entity_nodes(self):
        """Should create nodes for entities in memory metadata.

        GitHub Issue: #124
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from src.memory.graph.graph_builder import GraphBuilder

        builder = GraphBuilder(user_id="user-123")
        memory = Memory(
            user_id="user-123",
            content="The auth-service uses PostgreSQL",
            memory_type=MemoryType.FACT,
            confidence=0.9,
            source="test",
            metadata={
                "entities": [
                    {"name": "auth-service", "type": "service", "confidence": 0.9},
                    {"name": "PostgreSQL", "type": "dependency", "confidence": 0.8},
                ]
            },
        )

        builder.add_memory(memory, memory_id="mem-1")

        graph = builder.build()
        assert graph.has_node("auth-service")
        assert graph.has_node("postgresql")  # Normalized to lowercase

    def test_add_memory_creates_relationship_edges(self):
        """Should create edges for inferred relationships.

        GitHub Issue: #124
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from src.memory.graph.graph_builder import GraphBuilder

        builder = GraphBuilder(user_id="user-123")
        memory = Memory(
            user_id="user-123",
            content="The auth-service uses PostgreSQL",
            memory_type=MemoryType.FACT,
            confidence=0.9,
            source="test",
            metadata={
                "entities": [
                    {"name": "auth-service", "type": "service", "confidence": 0.9},
                    {"name": "PostgreSQL", "type": "dependency", "confidence": 0.8},
                ]
            },
        )

        builder.add_memory(memory, memory_id="mem-1")

        graph = builder.build()
        # Should have an edge from service to dependency
        assert graph.edge_count > 0

    def test_add_memory_links_to_memory_id(self):
        """Nodes should reference source memory ID.

        GitHub Issue: #124
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from src.memory.graph.graph_builder import GraphBuilder

        builder = GraphBuilder(user_id="user-123")
        memory = Memory(
            user_id="user-123",
            content="FastAPI framework",
            memory_type=MemoryType.FACT,
            confidence=0.9,
            source="test",
            metadata={
                "entities": [
                    {"name": "FastAPI", "type": "framework", "confidence": 0.9},
                ]
            },
        )

        builder.add_memory(memory, memory_id="mem-1")

        graph = builder.build()
        node = graph.get_node("fastapi")
        assert "mem-1" in node.memory_ids

    def test_add_memory_without_entities(self):
        """Should handle memory without entities gracefully.

        GitHub Issue: #124
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from src.memory.graph.graph_builder import GraphBuilder

        builder = GraphBuilder(user_id="user-123")
        memory = Memory(
            user_id="user-123",
            content="No entities here",
            memory_type=MemoryType.FACT,
            confidence=0.9,
            source="test",
            metadata={},
        )

        builder.add_memory(memory, memory_id="mem-1")

        graph = builder.build()
        assert graph.node_count == 0


class TestGraphBuilderRelationshipInference:
    """TDD: Tests for relationship inference from content."""

    def test_infer_depends_on_from_uses_keyword(self):
        """Should infer DEPENDS_ON from 'uses' in content.

        GitHub Issue: #124
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from src.memory.graph.graph_builder import GraphBuilder

        builder = GraphBuilder(user_id="user-123")
        memory = Memory(
            user_id="user-123",
            content="The auth-service uses PostgreSQL for storage",
            memory_type=MemoryType.FACT,
            confidence=0.9,
            source="test",
            metadata={
                "entities": [
                    {"name": "auth-service", "type": "service", "confidence": 0.9},
                    {"name": "PostgreSQL", "type": "dependency", "confidence": 0.8},
                ]
            },
        )

        builder.add_memory(memory, memory_id="mem-1")

        graph = builder.build()
        edge = graph.get_edge("auth-service", "postgresql")
        assert edge is not None
        assert edge.relationship == RelationshipType.DEPENDS_ON

    def test_infer_uses_from_framework(self):
        """Should infer USES for framework entities.

        GitHub Issue: #124
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from src.memory.graph.graph_builder import GraphBuilder

        builder = GraphBuilder(user_id="user-123")
        memory = Memory(
            user_id="user-123",
            content="The payment-api is built with FastAPI",
            memory_type=MemoryType.FACT,
            confidence=0.9,
            source="test",
            metadata={
                "entities": [
                    {"name": "payment-api", "type": "service", "confidence": 0.9},
                    {"name": "FastAPI", "type": "framework", "confidence": 0.8},
                ]
            },
        )

        builder.add_memory(memory, memory_id="mem-1")

        graph = builder.build()
        edge = graph.get_edge("payment-api", "fastapi")
        assert edge is not None
        assert edge.relationship == RelationshipType.USES

    def test_infer_calls_from_api(self):
        """Should infer CALLS for API entities.

        GitHub Issue: #124
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from src.memory.graph.graph_builder import GraphBuilder

        builder = GraphBuilder(user_id="user-123")
        memory = Memory(
            user_id="user-123",
            content="The frontend calls /api/v1/users",
            memory_type=MemoryType.FACT,
            confidence=0.9,
            source="test",
            metadata={
                "entities": [
                    {"name": "frontend", "type": "service", "confidence": 0.9},
                    {"name": "/api/v1/users", "type": "api", "confidence": 0.8},
                ]
            },
        )

        builder.add_memory(memory, memory_id="mem-1")

        graph = builder.build()
        edge = graph.get_edge("frontend", "/api/v1/users")
        assert edge is not None
        assert edge.relationship == RelationshipType.CALLS


class TestGraphBuilderNodeMerging:
    """TDD: Tests for merging nodes from multiple memories."""

    def test_merge_duplicate_entities(self):
        """Should merge entities from multiple memories.

        GitHub Issue: #124
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from src.memory.graph.graph_builder import GraphBuilder

        builder = GraphBuilder(user_id="user-123")

        mem1 = Memory(
            user_id="user-123",
            content="auth-service uses PostgreSQL",
            memory_type=MemoryType.FACT,
            confidence=0.9,
            source="test",
            metadata={
                "entities": [
                    {"name": "auth-service", "type": "service", "confidence": 0.9},
                ]
            },
        )
        mem2 = Memory(
            user_id="user-123",
            content="auth-service connects to Redis",
            memory_type=MemoryType.FACT,
            confidence=0.9,
            source="test",
            metadata={
                "entities": [
                    {"name": "auth-service", "type": "service", "confidence": 0.85},
                ]
            },
        )

        builder.add_memory(mem1, memory_id="mem-1")
        builder.add_memory(mem2, memory_id="mem-2")

        graph = builder.build()
        # Should have one auth-service node
        assert graph.node_count >= 1
        node = graph.get_node("auth-service")
        # Should have both memory IDs
        assert "mem-1" in node.memory_ids
        assert "mem-2" in node.memory_ids


class TestGraphBuilderBuild:
    """TDD: Tests for building the final graph."""

    def test_build_returns_knowledge_graph(self):
        """Should return a KnowledgeGraph.

        GitHub Issue: #124
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from src.memory.graph.graph_builder import GraphBuilder
        from src.memory.graph.graph_store import KnowledgeGraph

        builder = GraphBuilder(user_id="user-123")

        graph = builder.build()

        assert isinstance(graph, KnowledgeGraph)
        assert graph.user_id == "user-123"

    def test_build_can_be_called_multiple_times(self):
        """Should be able to build incrementally.

        GitHub Issue: #124
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from src.memory.graph.graph_builder import GraphBuilder

        builder = GraphBuilder(user_id="user-123")

        # First build
        graph1 = builder.build()
        assert graph1.node_count == 0

        # Add memory
        memory = Memory(
            user_id="user-123",
            content="Test content",
            memory_type=MemoryType.FACT,
            confidence=0.9,
            source="test",
            metadata={
                "entities": [
                    {"name": "test-service", "type": "service", "confidence": 0.9},
                ]
            },
        )
        builder.add_memory(memory, memory_id="mem-1")

        # Second build
        graph2 = builder.build()
        assert graph2.node_count == 1


class TestModuleExports:
    """TDD: Tests for module exports."""

    def test_module_exports_graph_builder(self):
        """Module should export GraphBuilder.

        GitHub Issue: #124
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from src.memory.graph import GraphBuilder

        assert GraphBuilder is not None
