# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Knowledge Graph store with NetworkX backend.

Provides the KnowledgeGraph class for storing and querying entity
relationships using a directed graph structure.

Related GitHub Issues:
- #123: Implement KnowledgeGraph with NetworkX backend

ADR Reference: ADR-003 Memory Architecture, Phase 4 (Knowledge Graph)
"""

from typing import Any, Optional

import networkx as nx

from luminescent_cluster.memory.extraction.entities import EntityType
from luminescent_cluster.memory.graph.types import GraphEdge, GraphNode, RelationshipType


class KnowledgeGraph:
    """User-scoped knowledge graph with NetworkX backend.

    Stores entities as nodes and relationships as directed edges.
    Designed for multi-hop queries like "What services depend on PostgreSQL?"

    Attributes:
        user_id: Owner of this graph (for multi-tenant isolation).

    Example:
        >>> graph = KnowledgeGraph(user_id="user-123")
        >>> graph.add_node(GraphNode("auth", EntityType.SERVICE, "auth-service"))
        >>> graph.add_edge(GraphEdge("auth", "pg", RelationshipType.DEPENDS_ON, "m1"))
        >>> neighbors = graph.get_neighbors("auth")
    """

    def __init__(self, user_id: str) -> None:
        """Initialize the knowledge graph.

        Args:
            user_id: Owner of this graph.
        """
        self.user_id = user_id
        self._graph: nx.DiGraph = nx.DiGraph()

    @property
    def node_count(self) -> int:
        """Return the number of nodes in the graph."""
        return self._graph.number_of_nodes()

    @property
    def edge_count(self) -> int:
        """Return the number of edges in the graph."""
        return self._graph.number_of_edges()

    def add_node(self, node: GraphNode) -> None:
        """Add a node to the graph.

        If a node with the same ID exists, it will be updated.

        Args:
            node: The node to add.
        """
        self._graph.add_node(
            node.id,
            entity_type=node.entity_type.value,
            name=node.name,
            memory_ids=node.memory_ids,
            metadata=node.metadata,
        )

    def has_node(self, node_id: str) -> bool:
        """Check if a node exists.

        Args:
            node_id: ID of the node to check.

        Returns:
            True if the node exists.
        """
        return self._graph.has_node(node_id)

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        """Get a node by ID.

        Args:
            node_id: ID of the node to get.

        Returns:
            The node if found, None otherwise.
        """
        if not self._graph.has_node(node_id):
            return None

        data = self._graph.nodes[node_id]
        return GraphNode(
            id=node_id,
            entity_type=EntityType(data["entity_type"]),
            name=data["name"],
            memory_ids=data.get("memory_ids", []),
            metadata=data.get("metadata", {}),
        )

    def remove_node(self, node_id: str) -> bool:
        """Remove a node and its edges.

        Args:
            node_id: ID of the node to remove.

        Returns:
            True if the node was removed, False if not found.
        """
        if not self._graph.has_node(node_id):
            return False

        self._graph.remove_node(node_id)
        return True

    def get_all_nodes(self) -> list[GraphNode]:
        """Get all nodes in the graph.

        Returns:
            List of all nodes.
        """
        nodes = []
        for node_id in self._graph.nodes():
            node = self.get_node(node_id)
            if node:
                nodes.append(node)
        return nodes

    def add_edge(self, edge: GraphEdge) -> None:
        """Add an edge to the graph.

        Creates missing nodes with default entity type.

        Args:
            edge: The edge to add.
        """
        # Ensure source and target nodes exist
        if not self._graph.has_node(edge.source_id):
            self._graph.add_node(
                edge.source_id,
                entity_type=EntityType.SERVICE.value,
                name=edge.source_id,
                memory_ids=[],
                metadata={},
            )
        if not self._graph.has_node(edge.target_id):
            self._graph.add_node(
                edge.target_id,
                entity_type=EntityType.DEPENDENCY.value,
                name=edge.target_id,
                memory_ids=[],
                metadata={},
            )

        self._graph.add_edge(
            edge.source_id,
            edge.target_id,
            relationship=edge.relationship.value,
            confidence=edge.confidence,
            memory_id=edge.memory_id,
        )

    def has_edge(self, source_id: str, target_id: str) -> bool:
        """Check if an edge exists.

        Args:
            source_id: Source node ID.
            target_id: Target node ID.

        Returns:
            True if the edge exists.
        """
        return self._graph.has_edge(source_id, target_id)

    def get_edge(self, source_id: str, target_id: str) -> Optional[GraphEdge]:
        """Get an edge by source and target.

        Args:
            source_id: Source node ID.
            target_id: Target node ID.

        Returns:
            The edge if found, None otherwise.
        """
        if not self._graph.has_edge(source_id, target_id):
            return None

        data = self._graph.edges[source_id, target_id]
        return GraphEdge(
            source_id=source_id,
            target_id=target_id,
            relationship=RelationshipType(data["relationship"]),
            confidence=data["confidence"],
            memory_id=data["memory_id"],
        )

    def remove_edge(self, source_id: str, target_id: str) -> bool:
        """Remove an edge.

        Args:
            source_id: Source node ID.
            target_id: Target node ID.

        Returns:
            True if the edge was removed, False if not found.
        """
        if not self._graph.has_edge(source_id, target_id):
            return False

        self._graph.remove_edge(source_id, target_id)
        return True

    def get_edges_from(self, node_id: str) -> list[GraphEdge]:
        """Get all outgoing edges from a node.

        Args:
            node_id: Source node ID.

        Returns:
            List of outgoing edges.
        """
        if not self._graph.has_node(node_id):
            return []

        edges = []
        for _, target_id, data in self._graph.out_edges(node_id, data=True):
            edges.append(GraphEdge(
                source_id=node_id,
                target_id=target_id,
                relationship=RelationshipType(data["relationship"]),
                confidence=data["confidence"],
                memory_id=data["memory_id"],
            ))
        return edges

    def get_edges_to(self, node_id: str) -> list[GraphEdge]:
        """Get all incoming edges to a node.

        Args:
            node_id: Target node ID.

        Returns:
            List of incoming edges.
        """
        if not self._graph.has_node(node_id):
            return []

        edges = []
        for source_id, _, data in self._graph.in_edges(node_id, data=True):
            edges.append(GraphEdge(
                source_id=source_id,
                target_id=node_id,
                relationship=RelationshipType(data["relationship"]),
                confidence=data["confidence"],
                memory_id=data["memory_id"],
            ))
        return edges

    def get_neighbors(
        self,
        node_id: str,
        relationship: Optional[RelationshipType] = None,
    ) -> list[GraphNode]:
        """Get all neighbor nodes (outgoing edges).

        Args:
            node_id: Node to get neighbors for.
            relationship: Optional filter by relationship type.

        Returns:
            List of neighbor nodes.
        """
        if not self._graph.has_node(node_id):
            return []

        neighbors = []
        for edge in self.get_edges_from(node_id):
            if relationship is None or edge.relationship == relationship:
                node = self.get_node(edge.target_id)
                if node:
                    neighbors.append(node)
        return neighbors

    def get_predecessors(
        self,
        node_id: str,
        relationship: Optional[RelationshipType] = None,
    ) -> list[GraphNode]:
        """Get all predecessor nodes (incoming edges).

        Args:
            node_id: Node to get predecessors for.
            relationship: Optional filter by relationship type.

        Returns:
            List of predecessor nodes.
        """
        if not self._graph.has_node(node_id):
            return []

        predecessors = []
        for edge in self.get_edges_to(node_id):
            if relationship is None or edge.relationship == relationship:
                node = self.get_node(edge.source_id)
                if node:
                    predecessors.append(node)
        return predecessors

    def clear(self) -> None:
        """Remove all nodes and edges."""
        self._graph.clear()

    def to_dict(self) -> dict[str, Any]:
        """Serialize the graph to a dictionary.

        Returns:
            Dictionary representation of the graph.
        """
        nodes = []
        for node_id in self._graph.nodes():
            data = self._graph.nodes[node_id]
            nodes.append({
                "id": node_id,
                "entity_type": data["entity_type"],
                "name": data["name"],
                "memory_ids": data.get("memory_ids", []),
                "metadata": data.get("metadata", {}),
            })

        edges = []
        for source_id, target_id, data in self._graph.edges(data=True):
            edges.append({
                "source_id": source_id,
                "target_id": target_id,
                "relationship": data["relationship"],
                "confidence": data["confidence"],
                "memory_id": data["memory_id"],
            })

        return {
            "user_id": self.user_id,
            "nodes": nodes,
            "edges": edges,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KnowledgeGraph":
        """Deserialize a graph from a dictionary.

        Args:
            data: Dictionary representation of the graph.

        Returns:
            Restored KnowledgeGraph instance.
        """
        graph = cls(user_id=data["user_id"])

        for node_data in data.get("nodes", []):
            graph.add_node(GraphNode(
                id=node_data["id"],
                entity_type=EntityType(node_data["entity_type"]),
                name=node_data["name"],
                memory_ids=node_data.get("memory_ids", []),
                metadata=node_data.get("metadata", {}),
            ))

        for edge_data in data.get("edges", []):
            graph.add_edge(GraphEdge(
                source_id=edge_data["source_id"],
                target_id=edge_data["target_id"],
                relationship=RelationshipType(edge_data["relationship"]),
                confidence=edge_data["confidence"],
                memory_id=edge_data["memory_id"],
            ))

        return graph
