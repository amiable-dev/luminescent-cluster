# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Graph-based search for HybridRetriever Stage 1.

Provides GraphSearch class for finding memories through graph traversal,
designed to integrate with the two-stage hybrid retrieval architecture.

Related GitHub Issues:
- #125: Implement GraphSearch for Stage 1 candidate generation

ADR Reference: ADR-003 Memory Architecture, Phase 4 (Knowledge Graph)
"""

from typing import Optional

from luminescent_cluster.memory.graph.graph_store import KnowledgeGraph
from luminescent_cluster.memory.graph.types import GraphNode


class GraphSearch:
    """Graph-based candidate generation for HybridRetriever Stage 1.

    Searches the knowledge graph for entities matching the query and
    returns memory IDs from matching nodes and their neighbors.

    This provides a search interface matching BM25 and VectorSearch,
    returning list of (memory_id, score) tuples.

    Example:
        >>> search = GraphSearch()
        >>> search.register_graph("user-123", graph)
        >>> results = search.search("user-123", "auth-service", top_k=10)
        >>> for memory_id, score in results:
        ...     print(f"{memory_id}: {score:.4f}")
    """

    # Score decay for traversed nodes
    DIRECT_MATCH_SCORE = 1.0
    NEIGHBOR_SCORE = 0.7
    PREDECESSOR_SCORE = 0.6

    def __init__(self) -> None:
        """Initialize the graph search."""
        self._graphs: dict[str, KnowledgeGraph] = {}

    def register_graph(self, user_id: str, graph: KnowledgeGraph) -> None:
        """Register a graph for a user.

        Args:
            user_id: User ID.
            graph: The user's knowledge graph.
        """
        self._graphs[user_id] = graph

    def has_graph(self, user_id: str) -> bool:
        """Check if a graph is registered for a user.

        Args:
            user_id: User ID.

        Returns:
            True if graph is registered.
        """
        return user_id in self._graphs

    def search(
        self,
        user_id: str,
        query: str,
        top_k: int = 50,
    ) -> list[tuple[str, float]]:
        """Search for memories related to query via graph traversal.

        Finds nodes matching query terms, then traverses to collect
        memory IDs from the node and its neighbors.

        Args:
            user_id: User ID to search for.
            query: Search query.
            top_k: Maximum number of results.

        Returns:
            List of (memory_id, score) tuples sorted by score descending.
        """
        if user_id not in self._graphs:
            return []

        graph = self._graphs[user_id]

        # Find matching nodes
        matching_nodes = self._find_matching_nodes(graph, query)
        if not matching_nodes:
            return []

        # Collect memories with scores
        memory_scores: dict[str, float] = {}

        for node, match_score in matching_nodes:
            # Add memories from direct match
            for memory_id in node.memory_ids:
                current_score = self.DIRECT_MATCH_SCORE * match_score
                if memory_id not in memory_scores or memory_scores[memory_id] < current_score:
                    memory_scores[memory_id] = current_score

            # Add memories from neighbors (outgoing edges)
            for neighbor in graph.get_neighbors(node.id):
                for memory_id in neighbor.memory_ids:
                    current_score = self.NEIGHBOR_SCORE * match_score
                    if memory_id not in memory_scores or memory_scores[memory_id] < current_score:
                        memory_scores[memory_id] = current_score

            # Add memories from predecessors (incoming edges)
            for predecessor in graph.get_predecessors(node.id):
                for memory_id in predecessor.memory_ids:
                    current_score = self.PREDECESSOR_SCORE * match_score
                    if memory_id not in memory_scores or memory_scores[memory_id] < current_score:
                        memory_scores[memory_id] = current_score

        # Sort by score descending and limit to top_k
        results = sorted(
            memory_scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:top_k]

        return results

    def _find_matching_nodes(
        self,
        graph: KnowledgeGraph,
        query: str,
    ) -> list[tuple[GraphNode, float]]:
        """Find nodes matching the query.

        Args:
            graph: Knowledge graph to search.
            query: Search query.

        Returns:
            List of (node, match_score) tuples.
        """
        query_lower = query.lower()
        query_terms = set(query_lower.split())

        matches = []
        for node in graph.get_all_nodes():
            # Check for exact match (case-insensitive)
            if node.id.lower() == query_lower or node.name.lower() == query_lower:
                matches.append((node, 1.0))
                continue

            # Check for partial match (node ID in query terms or query contains node ID)
            node_id_lower = node.id.lower()
            node_name_lower = node.name.lower()

            # Check if node ID appears in query
            if node_id_lower in query_lower or node_name_lower in query_lower:
                matches.append((node, 0.8))
                continue

            # Check if any query term matches node ID
            for term in query_terms:
                if term in node_id_lower or term in node_name_lower:
                    matches.append((node, 0.6))
                    break

        return matches

    def clear(self, user_id: str) -> None:
        """Clear the graph for a user.

        Args:
            user_id: User ID.
        """
        if user_id in self._graphs:
            del self._graphs[user_id]
