# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Local in-memory implementation of MemoryProvider.

This is the OSS implementation of the MemoryProvider protocol,
storing memories in-memory with optional two-stage hybrid retrieval
(BM25 + Vector + RRF + Cross-Encoder). For production use with
Pixeltable-backed storage, see the cloud implementation.

Related GitHub Issues:
- #85: Implement LocalMemoryProvider

ADR Reference: ADR-003 Memory Architecture
- Phase 1a: Storage
- Phase 3: Two-Stage Retrieval Architecture
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

from src.memory.schemas import Memory, MemoryType

if TYPE_CHECKING:
    from src.memory.retrieval.hybrid import HybridRetriever, RetrievalMetrics


class LocalMemoryProvider:
    """In-memory implementation of MemoryProvider protocol.

    Provides memory storage and retrieval with optional two-stage
    hybrid retrieval (BM25 + Vector + RRF + Cross-Encoder). Falls
    back to simple substring matching when hybrid retrieval is disabled.

    This implementation is suitable for:
    - Development and testing
    - OSS deployments without Pixeltable
    - Ephemeral memory (data is lost on restart)

    For persistent storage with semantic search, use the cloud
    implementation with Pixeltable backend.

    Example:
        >>> # Simple mode (substring matching)
        >>> provider = LocalMemoryProvider()
        >>> memory_id = await provider.store(memory, {})
        >>> result = await provider.retrieve("tabs", "user-123")

        >>> # Hybrid mode (two-stage retrieval)
        >>> provider = LocalMemoryProvider(use_hybrid_retrieval=True)
        >>> memory_id = await provider.store(memory, {})
        >>> result = await provider.retrieve("coding preferences", "user-123")

    Attributes:
        use_hybrid_retrieval: If True, use two-stage hybrid retrieval.
        use_cross_encoder: If True, use cross-encoder reranking (slower but better).
    """

    def __init__(
        self,
        use_hybrid_retrieval: bool = False,
        use_cross_encoder: bool = True,
        use_query_rewriter: bool = True,
    ):
        """Initialize the local memory provider.

        Args:
            use_hybrid_retrieval: Enable two-stage hybrid retrieval
                (BM25 + Vector + RRF + optional Cross-Encoder).
                Default: False (uses simple substring matching).
            use_cross_encoder: Use cross-encoder reranking in hybrid mode.
                Improves quality but increases latency. Default: True.
            use_query_rewriter: Use query rewriter for expansion in hybrid mode.
                Default: True.
        """
        self._memories: dict[str, Memory] = {}
        self._memory_ids_by_user: dict[str, list[str]] = {}
        self._use_hybrid = use_hybrid_retrieval
        self._use_cross_encoder = use_cross_encoder
        self._use_query_rewriter = use_query_rewriter
        self._hybrid_retriever: Optional["HybridRetriever"] = None

        if use_hybrid_retrieval:
            self._init_hybrid_retriever()

    def _init_hybrid_retriever(self) -> None:
        """Initialize the hybrid retriever lazily."""
        from src.memory.retrieval.hybrid import create_hybrid_retriever

        self._hybrid_retriever = create_hybrid_retriever(
            use_cross_encoder=self._use_cross_encoder,
            use_query_rewriter=self._use_query_rewriter,
        )

    async def store(self, memory: Memory, context: dict) -> str:
        """Store a memory and return its ID.

        Args:
            memory: The memory to store.
            context: Additional context (unused in local implementation).

        Returns:
            A unique memory ID string.
        """
        memory_id = str(uuid.uuid4())
        # Store a copy to prevent external mutation
        stored_memory = memory.model_copy()
        self._memories[memory_id] = stored_memory

        # Track memory IDs by user for hybrid indexing
        user_id = memory.user_id
        if user_id not in self._memory_ids_by_user:
            self._memory_ids_by_user[user_id] = []
        self._memory_ids_by_user[user_id].append(memory_id)

        # Index in hybrid retriever if enabled
        if self._hybrid_retriever is not None:
            self._hybrid_retriever.add_memory(user_id, stored_memory, memory_id)

        return memory_id

    async def retrieve(
        self, query: str, user_id: str, limit: int = 5
    ) -> list[Memory]:
        """Retrieve memories matching a query for a user.

        When hybrid retrieval is enabled, uses two-stage retrieval:
        - Stage 1: BM25 + Vector search (parallel)
        - Stage 2: RRF fusion + optional Cross-Encoder reranking

        Otherwise, uses simple substring matching.

        Args:
            query: Search query string.
            user_id: User ID to filter memories.
            limit: Maximum number of memories to return.

        Returns:
            List of matching Memory objects.
        """
        # Use hybrid retrieval if enabled
        if self._hybrid_retriever is not None:
            return await self._retrieve_hybrid(query, user_id, limit)

        # Fallback to simple substring matching
        return self._retrieve_simple(query, user_id, limit)

    async def _retrieve_hybrid(
        self, query: str, user_id: str, limit: int
    ) -> list[Memory]:
        """Retrieve using two-stage hybrid retrieval.

        Args:
            query: Search query string.
            user_id: User ID to filter memories.
            limit: Maximum number of results.

        Returns:
            List of matching Memory objects.
        """
        assert self._hybrid_retriever is not None

        # Check if user has any indexed memories
        if not self._hybrid_retriever.has_index(user_id):
            return []

        # Perform hybrid retrieval
        results, _metrics = await self._hybrid_retriever.retrieve(
            query=query,
            user_id=user_id,
            top_k=limit,
            expand_query=self._use_query_rewriter,
            use_reranker=self._use_cross_encoder,
        )

        # Filter out invalidated memories and return copies
        valid_results = []
        for result in results:
            memory = result.memory
            if memory.metadata.get("is_valid") is not False:
                valid_results.append(memory.model_copy())

        return valid_results

    def _retrieve_simple(
        self, query: str, user_id: str, limit: int
    ) -> list[Memory]:
        """Retrieve using simple substring matching.

        Args:
            query: Search query string.
            user_id: User ID to filter memories.
            limit: Maximum number of results.

        Returns:
            List of matching Memory objects.
        """
        query_lower = query.lower()
        results = []

        for memory in self._memories.values():
            # Filter by user
            if memory.user_id != user_id:
                continue

            # Skip invalidated memories
            if memory.metadata.get("is_valid") is False:
                continue

            # Simple substring match
            if query_lower in memory.content.lower():
                results.append(memory.model_copy())

                if len(results) >= limit:
                    break

        return results

    async def get_by_id(self, memory_id: str) -> Optional[Memory]:
        """Get a memory by its ID.

        Args:
            memory_id: The memory ID to look up.

        Returns:
            The Memory if found, None otherwise.
        """
        memory = self._memories.get(memory_id)
        if memory:
            return memory.model_copy()
        return None

    async def delete(self, memory_id: str) -> bool:
        """Delete a memory by its ID.

        Args:
            memory_id: The memory ID to delete.

        Returns:
            True if the memory was deleted, False if not found.
        """
        if memory_id not in self._memories:
            return False

        memory = self._memories[memory_id]
        user_id = memory.user_id

        # Remove from main storage
        del self._memories[memory_id]

        # Remove from user tracking
        if user_id in self._memory_ids_by_user:
            try:
                self._memory_ids_by_user[user_id].remove(memory_id)
            except ValueError:
                pass

        # Remove from hybrid retriever if enabled
        if self._hybrid_retriever is not None:
            self._hybrid_retriever.remove_memory(user_id, memory_id)

        return True

    async def search(
        self, user_id: str, filters: dict, limit: int = 10
    ) -> list[Memory]:
        """Search memories with filters.

        Supports filtering by:
        - memory_type: Filter by MemoryType enum
        - source: Filter by source string
        - min_confidence: Filter by minimum confidence

        Args:
            user_id: User ID to filter memories.
            filters: Dictionary of filter criteria.
            limit: Maximum number of memories to return.

        Returns:
            List of matching Memory objects.
        """
        results = []

        memory_type_filter = filters.get("memory_type")
        source_filter = filters.get("source")
        min_confidence = filters.get("min_confidence", 0.0)
        include_invalid = filters.get("include_invalid", False)

        for memory in self._memories.values():
            # Filter by user
            if memory.user_id != user_id:
                continue

            # Skip invalidated memories unless explicitly included
            if not include_invalid and memory.metadata.get("is_valid") is False:
                continue

            # Filter by memory type
            if memory_type_filter is not None:
                if memory.memory_type != memory_type_filter:
                    continue

            # Filter by source
            if source_filter is not None:
                if memory.source != source_filter:
                    continue

            # Filter by confidence
            if memory.confidence < min_confidence:
                continue

            results.append(memory.model_copy())

            if len(results) >= limit:
                break

        return results

    async def update(
        self, memory_id: str, updates: dict[str, Any]
    ) -> Optional[Memory]:
        """Update a memory's fields.

        Args:
            memory_id: The memory ID to update.
            updates: Dictionary of fields to update.

        Returns:
            The updated Memory if found, None otherwise.
        """
        if memory_id not in self._memories:
            return None

        memory = self._memories[memory_id]

        # Track update in metadata
        update_history = memory.metadata.get("update_history", [])
        update_history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "fields": list(updates.keys()),
            "previous_content": memory.content if "content" in updates else None,
            "previous_source": memory.source if "source" in updates else None,
        })

        # Create updated memory
        new_data = memory.model_dump()
        new_data["metadata"] = {**memory.metadata, "update_history": update_history}
        new_data["metadata"]["last_modified_at"] = datetime.now(timezone.utc).isoformat()

        # Apply updates
        for key, value in updates.items():
            if key == "metadata":
                # Merge metadata updates
                new_data["metadata"] = {**new_data["metadata"], **value}
            elif key in new_data:
                new_data[key] = value

        self._memories[memory_id] = Memory(**new_data)
        return self._memories[memory_id].model_copy()

    def clear(self) -> None:
        """Clear all stored memories (for testing)."""
        # Clear hybrid retriever indexes for all users
        if self._hybrid_retriever is not None:
            for user_id in list(self._memory_ids_by_user.keys()):
                self._hybrid_retriever.clear_index(user_id)

        self._memories.clear()
        self._memory_ids_by_user.clear()

    def count(self) -> int:
        """Get the number of stored memories."""
        return len(self._memories)

    @property
    def is_hybrid_enabled(self) -> bool:
        """Check if hybrid retrieval is enabled."""
        return self._hybrid_retriever is not None

    async def retrieve_with_scores(
        self, query: str, user_id: str, limit: int = 5
    ) -> list[tuple[Memory, float]]:
        """Retrieve memories with relevance scores.

        Only available when hybrid retrieval is enabled.

        Args:
            query: Search query string.
            user_id: User ID to filter memories.
            limit: Maximum number of memories to return.

        Returns:
            List of (Memory, score) tuples, sorted by score descending.

        Raises:
            RuntimeError: If hybrid retrieval is not enabled.
        """
        if self._hybrid_retriever is None:
            raise RuntimeError(
                "retrieve_with_scores requires hybrid retrieval. "
                "Initialize with use_hybrid_retrieval=True."
            )

        if not self._hybrid_retriever.has_index(user_id):
            return []

        results, _metrics = await self._hybrid_retriever.retrieve(
            query=query,
            user_id=user_id,
            top_k=limit,
            expand_query=self._use_query_rewriter,
            use_reranker=self._use_cross_encoder,
        )

        # Filter out invalidated memories and return with scores
        valid_results = []
        for result in results:
            memory = result.memory
            if memory.metadata.get("is_valid") is not False:
                valid_results.append((memory.model_copy(), result.score))

        return valid_results

    async def retrieve_with_metrics(
        self, query: str, user_id: str, limit: int = 5
    ) -> tuple[list[Memory], "RetrievalMetrics"]:
        """Retrieve memories with detailed retrieval metrics.

        Only available when hybrid retrieval is enabled.

        Args:
            query: Search query string.
            user_id: User ID to filter memories.
            limit: Maximum number of memories to return.

        Returns:
            Tuple of (memories, metrics).

        Raises:
            RuntimeError: If hybrid retrieval is not enabled.
        """
        if self._hybrid_retriever is None:
            raise RuntimeError(
                "retrieve_with_metrics requires hybrid retrieval. "
                "Initialize with use_hybrid_retrieval=True."
            )

        from src.memory.retrieval.hybrid import RetrievalMetrics

        if not self._hybrid_retriever.has_index(user_id):
            return [], RetrievalMetrics()

        results, metrics = await self._hybrid_retriever.retrieve(
            query=query,
            user_id=user_id,
            top_k=limit,
            expand_query=self._use_query_rewriter,
            use_reranker=self._use_cross_encoder,
        )

        # Filter out invalidated memories
        valid_results = []
        for result in results:
            memory = result.memory
            if memory.metadata.get("is_valid") is not False:
                valid_results.append(memory.model_copy())

        return valid_results, metrics
