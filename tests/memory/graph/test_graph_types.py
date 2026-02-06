# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""TDD: RED Phase - Tests for Knowledge Graph types.

These tests define the expected behavior for graph types including
RelationshipType enum, GraphNode, and GraphEdge dataclasses.

Related GitHub Issues:
- #122: Define graph types (RelationshipType, GraphNode, GraphEdge)

ADR Reference: ADR-003 Memory Architecture, Phase 4 (Knowledge Graph)
"""

from dataclasses import fields
from typing import Any

import pytest


class TestRelationshipTypeExists:
    """TDD: Tests for RelationshipType enum existence."""

    def test_relationship_type_enum_exists(self):
        """RelationshipType enum should be defined.

        GitHub Issue: #122
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.types import RelationshipType

        assert RelationshipType is not None

    def test_relationship_type_is_str_enum(self):
        """RelationshipType should be a string enum.

        GitHub Issue: #122
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from enum import Enum

        from luminescent_cluster.memory.graph.types import RelationshipType

        assert issubclass(RelationshipType, str)
        assert issubclass(RelationshipType, Enum)


class TestRelationshipTypeValues:
    """TDD: Tests for RelationshipType enum values."""

    def test_has_depends_on(self):
        """Should have DEPENDS_ON relationship type.

        GitHub Issue: #122
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.types import RelationshipType

        assert RelationshipType.DEPENDS_ON == "depends_on"

    def test_has_uses(self):
        """Should have USES relationship type.

        GitHub Issue: #122
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.types import RelationshipType

        assert RelationshipType.USES == "uses"

    def test_has_implements(self):
        """Should have IMPLEMENTS relationship type.

        GitHub Issue: #122
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.types import RelationshipType

        assert RelationshipType.IMPLEMENTS == "implements"

    def test_has_calls(self):
        """Should have CALLS relationship type.

        GitHub Issue: #122
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.types import RelationshipType

        assert RelationshipType.CALLS == "calls"

    def test_has_configures(self):
        """Should have CONFIGURES relationship type.

        GitHub Issue: #122
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.types import RelationshipType

        assert RelationshipType.CONFIGURES == "configures"

    def test_has_had_incident(self):
        """Should have HAD_INCIDENT relationship type.

        GitHub Issue: #122
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.types import RelationshipType

        assert RelationshipType.HAD_INCIDENT == "had_incident"

    def test_has_owned_by(self):
        """Should have OWNED_BY relationship type.

        GitHub Issue: #122
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.types import RelationshipType

        assert RelationshipType.OWNED_BY == "owned_by"

    def test_has_exactly_seven_values(self):
        """Should have exactly 7 relationship types.

        GitHub Issue: #122
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.types import RelationshipType

        assert len(RelationshipType) == 7


class TestGraphNodeExists:
    """TDD: Tests for GraphNode dataclass existence."""

    def test_graph_node_exists(self):
        """GraphNode dataclass should be defined.

        GitHub Issue: #122
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.types import GraphNode

        assert GraphNode is not None

    def test_graph_node_is_dataclass(self):
        """GraphNode should be a dataclass.

        GitHub Issue: #122
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from dataclasses import is_dataclass

        from luminescent_cluster.memory.graph.types import GraphNode

        assert is_dataclass(GraphNode)


class TestGraphNodeFields:
    """TDD: Tests for GraphNode dataclass fields."""

    def test_has_id_field(self):
        """GraphNode should have id field.

        GitHub Issue: #122
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.types import GraphNode

        field_names = [f.name for f in fields(GraphNode)]
        assert "id" in field_names

    def test_has_entity_type_field(self):
        """GraphNode should have entity_type field.

        GitHub Issue: #122
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.types import GraphNode

        field_names = [f.name for f in fields(GraphNode)]
        assert "entity_type" in field_names

    def test_has_name_field(self):
        """GraphNode should have name field.

        GitHub Issue: #122
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.types import GraphNode

        field_names = [f.name for f in fields(GraphNode)]
        assert "name" in field_names

    def test_has_memory_ids_field(self):
        """GraphNode should have memory_ids field.

        GitHub Issue: #122
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.types import GraphNode

        field_names = [f.name for f in fields(GraphNode)]
        assert "memory_ids" in field_names

    def test_has_metadata_field(self):
        """GraphNode should have metadata field.

        GitHub Issue: #122
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.types import GraphNode

        field_names = [f.name for f in fields(GraphNode)]
        assert "metadata" in field_names


class TestGraphNodeConstruction:
    """TDD: Tests for GraphNode construction."""

    def test_can_create_with_required_fields(self):
        """Should create GraphNode with required fields.

        GitHub Issue: #122
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.extraction.entities import EntityType
        from luminescent_cluster.memory.graph.types import GraphNode

        node = GraphNode(
            id="node-1",
            entity_type=EntityType.SERVICE,
            name="auth-service",
        )

        assert node.id == "node-1"
        assert node.entity_type == EntityType.SERVICE
        assert node.name == "auth-service"

    def test_memory_ids_defaults_to_empty_list(self):
        """memory_ids should default to empty list.

        GitHub Issue: #122
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.extraction.entities import EntityType
        from luminescent_cluster.memory.graph.types import GraphNode

        node = GraphNode(
            id="node-1",
            entity_type=EntityType.SERVICE,
            name="auth-service",
        )

        assert node.memory_ids == []

    def test_metadata_defaults_to_empty_dict(self):
        """metadata should default to empty dict.

        GitHub Issue: #122
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.extraction.entities import EntityType
        from luminescent_cluster.memory.graph.types import GraphNode

        node = GraphNode(
            id="node-1",
            entity_type=EntityType.SERVICE,
            name="auth-service",
        )

        assert node.metadata == {}

    def test_can_create_with_all_fields(self):
        """Should create GraphNode with all fields specified.

        GitHub Issue: #122
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.extraction.entities import EntityType
        from luminescent_cluster.memory.graph.types import GraphNode

        node = GraphNode(
            id="node-1",
            entity_type=EntityType.SERVICE,
            name="auth-service",
            memory_ids=["mem-1", "mem-2"],
            metadata={"team": "backend"},
        )

        assert node.id == "node-1"
        assert node.entity_type == EntityType.SERVICE
        assert node.name == "auth-service"
        assert node.memory_ids == ["mem-1", "mem-2"]
        assert node.metadata == {"team": "backend"}


class TestGraphEdgeExists:
    """TDD: Tests for GraphEdge dataclass existence."""

    def test_graph_edge_exists(self):
        """GraphEdge dataclass should be defined.

        GitHub Issue: #122
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.types import GraphEdge

        assert GraphEdge is not None

    def test_graph_edge_is_dataclass(self):
        """GraphEdge should be a dataclass.

        GitHub Issue: #122
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from dataclasses import is_dataclass

        from luminescent_cluster.memory.graph.types import GraphEdge

        assert is_dataclass(GraphEdge)


class TestGraphEdgeFields:
    """TDD: Tests for GraphEdge dataclass fields."""

    def test_has_source_id_field(self):
        """GraphEdge should have source_id field.

        GitHub Issue: #122
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.types import GraphEdge

        field_names = [f.name for f in fields(GraphEdge)]
        assert "source_id" in field_names

    def test_has_target_id_field(self):
        """GraphEdge should have target_id field.

        GitHub Issue: #122
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.types import GraphEdge

        field_names = [f.name for f in fields(GraphEdge)]
        assert "target_id" in field_names

    def test_has_relationship_field(self):
        """GraphEdge should have relationship field.

        GitHub Issue: #122
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.types import GraphEdge

        field_names = [f.name for f in fields(GraphEdge)]
        assert "relationship" in field_names

    def test_has_confidence_field(self):
        """GraphEdge should have confidence field.

        GitHub Issue: #122
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.types import GraphEdge

        field_names = [f.name for f in fields(GraphEdge)]
        assert "confidence" in field_names

    def test_has_memory_id_field(self):
        """GraphEdge should have memory_id field.

        GitHub Issue: #122
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.types import GraphEdge

        field_names = [f.name for f in fields(GraphEdge)]
        assert "memory_id" in field_names


class TestGraphEdgeConstruction:
    """TDD: Tests for GraphEdge construction."""

    def test_can_create_with_all_fields(self):
        """Should create GraphEdge with all fields.

        GitHub Issue: #122
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.types import GraphEdge, RelationshipType

        edge = GraphEdge(
            source_id="node-1",
            target_id="node-2",
            relationship=RelationshipType.DEPENDS_ON,
            confidence=0.9,
            memory_id="mem-1",
        )

        assert edge.source_id == "node-1"
        assert edge.target_id == "node-2"
        assert edge.relationship == RelationshipType.DEPENDS_ON
        assert edge.confidence == 0.9
        assert edge.memory_id == "mem-1"

    def test_confidence_defaults_to_one(self):
        """confidence should default to 1.0.

        GitHub Issue: #122
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph.types import GraphEdge, RelationshipType

        edge = GraphEdge(
            source_id="node-1",
            target_id="node-2",
            relationship=RelationshipType.USES,
            memory_id="mem-1",
        )

        assert edge.confidence == 1.0


class TestModuleExports:
    """TDD: Tests for module exports."""

    def test_module_exports_relationship_type(self):
        """Module should export RelationshipType.

        GitHub Issue: #122
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph import RelationshipType

        assert RelationshipType is not None

    def test_module_exports_graph_node(self):
        """Module should export GraphNode.

        GitHub Issue: #122
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph import GraphNode

        assert GraphNode is not None

    def test_module_exports_graph_edge(self):
        """Module should export GraphEdge.

        GitHub Issue: #122
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.graph import GraphEdge

        assert GraphEdge is not None
