# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Knowledge Graph type definitions.

Provides core types for the Knowledge Graph:
- RelationshipType: Enum for edge types between entities
- GraphNode: Represents an entity in the graph
- GraphEdge: Represents a relationship between entities

Related GitHub Issues:
- #122: Define graph types (RelationshipType, GraphNode, GraphEdge)

ADR Reference: ADR-003 Memory Architecture, Phase 4 (Knowledge Graph)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.memory.extraction.entities import EntityType


class RelationshipType(str, Enum):
    """Types of relationships between entities in the knowledge graph.

    These relationship types enable multi-hop queries like:
    - "What services depend on auth that had incidents?"
    - "Which team owns the service that calls this endpoint?"

    Attributes:
        DEPENDS_ON: Service depends on a dependency (e.g., auth-service → PostgreSQL)
        USES: Service uses a framework (e.g., payment-api → FastAPI)
        IMPLEMENTS: Service implements a pattern (e.g., user-service → Repository)
        CALLS: Service calls an API (e.g., frontend → /api/v1/users)
        CONFIGURES: Service configures a config item (e.g., auth → DATABASE_URL)
        HAD_INCIDENT: Service had an incident (e.g., auth-service → incident-123)
        OWNED_BY: Service is owned by a team/user (e.g., auth-service → team-backend)
    """

    DEPENDS_ON = "depends_on"
    USES = "uses"
    IMPLEMENTS = "implements"
    CALLS = "calls"
    CONFIGURES = "configures"
    HAD_INCIDENT = "had_incident"
    OWNED_BY = "owned_by"


@dataclass
class GraphNode:
    """A node in the knowledge graph representing an entity.

    Nodes are created from extracted entities in Memory.metadata["entities"].
    Each node can be linked to multiple source memories.

    Attributes:
        id: Unique identifier for this node.
        entity_type: Type of entity (SERVICE, DEPENDENCY, etc.).
        name: Human-readable name of the entity.
        memory_ids: List of memory IDs that reference this entity.
        metadata: Additional properties for the node.

    Example:
        >>> node = GraphNode(
        ...     id="auth-service",
        ...     entity_type=EntityType.SERVICE,
        ...     name="auth-service",
        ...     memory_ids=["mem-1", "mem-2"],
        ...     metadata={"team": "backend"}
        ... )
    """

    id: str
    entity_type: EntityType
    name: str
    memory_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    """An edge in the knowledge graph representing a relationship.

    Edges connect two nodes with a typed relationship. Each edge
    is traced back to the source memory that established it.

    Attributes:
        source_id: ID of the source node.
        target_id: ID of the target node.
        relationship: Type of relationship between nodes.
        confidence: Confidence score for this relationship (0.0-1.0).
        memory_id: ID of the memory that established this relationship.

    Example:
        >>> edge = GraphEdge(
        ...     source_id="auth-service",
        ...     target_id="PostgreSQL",
        ...     relationship=RelationshipType.DEPENDS_ON,
        ...     confidence=0.95,
        ...     memory_id="mem-1"
        ... )
    """

    source_id: str
    target_id: str
    relationship: RelationshipType
    memory_id: str
    confidence: float = 1.0
