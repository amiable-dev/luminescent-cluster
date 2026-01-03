# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Local in-memory implementation of MemoryProvider.

This is the OSS implementation of the MemoryProvider protocol,
storing memories in-memory with basic semantic search using
string matching. For production use with Pixeltable-backed
storage, see the cloud implementation.

Related GitHub Issues:
- #85: Implement LocalMemoryProvider

ADR Reference: ADR-003 Memory Architecture, Phase 1a (Storage)
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from src.memory.schemas import Memory, MemoryType


class LocalMemoryProvider:
    """In-memory implementation of MemoryProvider protocol.

    Provides basic memory storage and retrieval without external
    dependencies. Uses simple substring matching for search.

    This implementation is suitable for:
    - Development and testing
    - OSS deployments without Pixeltable
    - Ephemeral memory (data is lost on restart)

    For persistent storage with semantic search, use the cloud
    implementation with Pixeltable backend.

    Example:
        >>> provider = LocalMemoryProvider()
        >>> memory = Memory(
        ...     user_id="user-123",
        ...     content="Prefers tabs",
        ...     memory_type=MemoryType.PREFERENCE,
        ...     source="conversation"
        ... )
        >>> memory_id = await provider.store(memory, {})
        >>> result = await provider.retrieve("tabs", "user-123")
    """

    def __init__(self):
        """Initialize the local memory provider."""
        self._memories: dict[str, Memory] = {}

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
        self._memories[memory_id] = memory.model_copy()
        return memory_id

    async def retrieve(
        self, query: str, user_id: str, limit: int = 5
    ) -> list[Memory]:
        """Retrieve memories matching a query for a user.

        Uses simple substring matching for search. For production
        use with semantic search, use the cloud implementation.

        Args:
            query: Search query string.
            user_id: User ID to filter memories.
            limit: Maximum number of memories to return.

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
        if memory_id in self._memories:
            del self._memories[memory_id]
            return True
        return False

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
            if key in new_data and key != "metadata":
                new_data[key] = value

        self._memories[memory_id] = Memory(**new_data)
        return self._memories[memory_id].model_copy()

    def clear(self) -> None:
        """Clear all stored memories (for testing)."""
        self._memories.clear()

    def count(self) -> int:
        """Get the number of stored memories."""
        return len(self._memories)
