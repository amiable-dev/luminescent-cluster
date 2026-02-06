# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""GraphBuilder for constructing knowledge graphs from Memory entities.

Builds a knowledge graph by extracting entities from Memory objects
and inferring relationships between them based on content patterns.

Related GitHub Issues:
- #124: Implement GraphBuilder from Memory entities

ADR Reference: ADR-003 Memory Architecture, Phase 4 (Knowledge Graph)
"""

import re
from typing import Any

from luminescent_cluster.memory.extraction.entities import EntityType
from luminescent_cluster.memory.graph.graph_store import KnowledgeGraph
from luminescent_cluster.memory.graph.types import GraphEdge, GraphNode, RelationshipType
from luminescent_cluster.memory.schemas import Memory


class GraphBuilder:
    """Builds a knowledge graph from Memory entities.

    Processes Memory objects to extract entities and infer relationships,
    creating a KnowledgeGraph that can be used for multi-hop queries.

    Attributes:
        user_id: Owner of the graph being built.

    Example:
        >>> builder = GraphBuilder(user_id="user-123")
        >>> builder.add_memory(memory, memory_id="mem-1")
        >>> graph = builder.build()
        >>> print(graph.node_count)
    """

    # Patterns for inferring relationships
    USES_PATTERNS = [
        r"\buses\b",
        r"\busing\b",
        r"\bconnects to\b",
        r"\bdepends on\b",
        r"\brequires\b",
    ]

    CALLS_PATTERNS = [
        r"\bcalls\b",
        r"\binvokes\b",
        r"\brequests\b",
        r"\bfetches from\b",
    ]

    IMPLEMENTS_PATTERNS = [
        r"\bimplements\b",
        r"\bfollows\b",
        r"\bapplies\b",
    ]

    def __init__(self, user_id: str) -> None:
        """Initialize the graph builder.

        Args:
            user_id: Owner of the graph.
        """
        self.user_id = user_id
        self._graph = KnowledgeGraph(user_id=user_id)
        self._pending_nodes: dict[str, dict[str, Any]] = {}
        self._pending_edges: list[dict[str, Any]] = []

    def add_memory(self, memory: Memory, memory_id: str) -> None:
        """Add a memory's entities to the graph.

        Extracts entities from the memory's metadata and infers
        relationships based on content patterns.

        Args:
            memory: The memory to process.
            memory_id: ID of the memory.
        """
        entities = memory.metadata.get("entities", [])
        if not entities:
            return

        # Extract and normalize entities
        parsed_entities = []
        for entity_data in entities:
            entity_id = self._normalize_id(entity_data["name"])
            entity_type = EntityType(entity_data["type"])
            confidence = entity_data.get("confidence", 1.0)

            parsed_entities.append({
                "id": entity_id,
                "name": entity_data["name"],
                "type": entity_type,
                "confidence": confidence,
            })

            # Create or update pending node
            if entity_id not in self._pending_nodes:
                self._pending_nodes[entity_id] = {
                    "id": entity_id,
                    "entity_type": entity_type,
                    "name": entity_data["name"],
                    "memory_ids": [memory_id],
                    "metadata": {},
                }
            else:
                if memory_id not in self._pending_nodes[entity_id]["memory_ids"]:
                    self._pending_nodes[entity_id]["memory_ids"].append(memory_id)

        # Infer relationships between entities
        self._infer_relationships(
            parsed_entities, memory.content, memory_id
        )

    def _normalize_id(self, name: str) -> str:
        """Normalize entity name to a node ID.

        Args:
            name: Entity name.

        Returns:
            Normalized ID (lowercase, unless it's an API path).
        """
        # Keep API paths as-is (they start with /)
        if name.startswith("/"):
            return name
        return name.lower()

    def _infer_relationships(
        self,
        entities: list[dict[str, Any]],
        content: str,
        memory_id: str,
    ) -> None:
        """Infer relationships between entities based on content.

        Args:
            entities: List of parsed entities.
            content: Memory content to analyze.
            memory_id: Source memory ID.
        """
        content_lower = content.lower()

        # Find services and other entities
        services = [e for e in entities if e["type"] == EntityType.SERVICE]
        dependencies = [e for e in entities if e["type"] == EntityType.DEPENDENCY]
        frameworks = [e for e in entities if e["type"] == EntityType.FRAMEWORK]
        apis = [e for e in entities if e["type"] == EntityType.API]
        patterns = [e for e in entities if e["type"] == EntityType.PATTERN]
        configs = [e for e in entities if e["type"] == EntityType.CONFIG]

        # Infer relationships
        for service in services:
            # Service → Dependency (DEPENDS_ON)
            for dep in dependencies:
                rel_type = self._detect_relationship_type(
                    content_lower, RelationshipType.DEPENDS_ON
                )
                self._add_pending_edge(
                    service["id"], dep["id"], rel_type, memory_id,
                    min(service["confidence"], dep["confidence"])
                )

            # Service → Framework (USES)
            for fw in frameworks:
                self._add_pending_edge(
                    service["id"], fw["id"], RelationshipType.USES, memory_id,
                    min(service["confidence"], fw["confidence"])
                )

            # Service → API (CALLS)
            for api in apis:
                self._add_pending_edge(
                    service["id"], api["id"], RelationshipType.CALLS, memory_id,
                    min(service["confidence"], api["confidence"])
                )

            # Service → Pattern (IMPLEMENTS)
            for pattern in patterns:
                self._add_pending_edge(
                    service["id"], pattern["id"], RelationshipType.IMPLEMENTS, memory_id,
                    min(service["confidence"], pattern["confidence"])
                )

            # Service → Config (CONFIGURES)
            for config in configs:
                self._add_pending_edge(
                    service["id"], config["id"], RelationshipType.CONFIGURES, memory_id,
                    min(service["confidence"], config["confidence"])
                )

    def _detect_relationship_type(
        self,
        content: str,
        default: RelationshipType,
    ) -> RelationshipType:
        """Detect relationship type from content patterns.

        Args:
            content: Content to analyze (should be lowercased).
            default: Default relationship type.

        Returns:
            Detected relationship type.
        """
        # Check for explicit relationship patterns
        for pattern in self.USES_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                return RelationshipType.DEPENDS_ON

        for pattern in self.CALLS_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                return RelationshipType.CALLS

        for pattern in self.IMPLEMENTS_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                return RelationshipType.IMPLEMENTS

        return default

    def _add_pending_edge(
        self,
        source_id: str,
        target_id: str,
        relationship: RelationshipType,
        memory_id: str,
        confidence: float,
    ) -> None:
        """Add a pending edge to be created on build.

        Args:
            source_id: Source node ID.
            target_id: Target node ID.
            relationship: Relationship type.
            memory_id: Source memory ID.
            confidence: Confidence score.
        """
        self._pending_edges.append({
            "source_id": source_id,
            "target_id": target_id,
            "relationship": relationship,
            "memory_id": memory_id,
            "confidence": confidence,
        })

    def build(self) -> KnowledgeGraph:
        """Build and return the knowledge graph.

        Returns:
            The constructed KnowledgeGraph.
        """
        # Add all pending nodes
        for node_data in self._pending_nodes.values():
            self._graph.add_node(GraphNode(
                id=node_data["id"],
                entity_type=node_data["entity_type"],
                name=node_data["name"],
                memory_ids=node_data["memory_ids"],
                metadata=node_data["metadata"],
            ))

        # Add all pending edges
        for edge_data in self._pending_edges:
            self._graph.add_edge(GraphEdge(
                source_id=edge_data["source_id"],
                target_id=edge_data["target_id"],
                relationship=edge_data["relationship"],
                memory_id=edge_data["memory_id"],
                confidence=edge_data["confidence"],
            ))

        return self._graph
