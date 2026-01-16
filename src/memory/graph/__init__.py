# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Knowledge Graph module for multi-hop reasoning.

This module provides knowledge graph capabilities for the memory system,
enabling multi-hop queries like "What services depend on PostgreSQL?"

Related GitHub Issues:
- #122: Define graph types (RelationshipType, GraphNode, GraphEdge)
- #123: Implement KnowledgeGraph with NetworkX backend
- #124: Implement GraphBuilder from Memory entities
- #125: Implement GraphSearch for Stage 1 candidate generation
- #126: Integrate graph into HybridRetriever

ADR Reference: ADR-003 Memory Architecture, Phase 4 (Knowledge Graph)
"""

from src.memory.graph.graph_builder import GraphBuilder
from src.memory.graph.graph_search import GraphSearch
from src.memory.graph.graph_store import KnowledgeGraph
from src.memory.graph.types import GraphEdge, GraphNode, RelationshipType

__all__ = [
    # Types
    "RelationshipType",
    "GraphNode",
    "GraphEdge",
    # Store
    "KnowledgeGraph",
    # Builder
    "GraphBuilder",
    # Search
    "GraphSearch",
]
