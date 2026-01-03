# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Memory Provider Protocol following ADR-007 patterns.

Defines the MemoryProvider protocol for memory storage implementations.

Related GitHub Issues:
- #80: Define MemoryProvider Protocol

ADR Reference: ADR-003 Memory Architecture, ADR-007 Extension Points
"""

from typing import Any, Optional, Protocol, List, runtime_checkable

from src.memory.schemas import Memory


# Protocol version for compatibility tracking
MEMORY_PROVIDER_VERSION = "1.0.0"


@runtime_checkable
class MemoryProvider(Protocol):
    """Protocol for memory storage providers.

    Implementations must provide async methods for CRUD operations
    on memories with user isolation.

    Methods:
        store: Store a new memory.
        retrieve: Retrieve memories matching a query.
        get_by_id: Get a specific memory by ID.
        delete: Delete a memory.
        search: Search memories with filters.

    Example:
        >>> class MyProvider(MemoryProvider):
        ...     async def store(self, memory, context):
        ...         # Implementation
        ...         return "memory-id"
    """

    async def store(self, memory: Memory, context: dict[str, Any]) -> str:
        """Store a memory.

        Args:
            memory: The Memory object to store.
            context: Additional context (session info, etc.).

        Returns:
            The ID of the stored memory.
        """
        ...

    async def retrieve(
        self, query: str, user_id: str, limit: int = 5
    ) -> List[Memory]:
        """Retrieve memories matching a query.

        Args:
            query: Search query text.
            user_id: User ID to filter by.
            limit: Maximum number of results.

        Returns:
            List of matching memories.
        """
        ...

    async def get_by_id(self, memory_id: str) -> Optional[Memory]:
        """Get a memory by its ID.

        Args:
            memory_id: The memory ID.

        Returns:
            The Memory if found, None otherwise.
        """
        ...

    async def delete(self, memory_id: str) -> bool:
        """Delete a memory.

        Args:
            memory_id: The memory ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        ...

    async def search(
        self, user_id: str, filters: dict[str, Any], limit: int = 10
    ) -> List[Memory]:
        """Search memories with filters.

        Args:
            user_id: User ID to filter by.
            filters: Filter criteria (memory_type, source, etc.).
            limit: Maximum number of results.

        Returns:
            List of matching memories.
        """
        ...
