# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""MCP tools for memory CRUD operations.

Provides MCP-compatible tool functions for creating, reading,
searching, and deleting memories.

Related GitHub Issues:
- #86: create_memory MCP Tool
- #87: get_memories MCP Tool
- #88: search_memories MCP Tool
- #89: delete_memory MCP Tool

ADR Reference: ADR-003 Memory Architecture, Phase 1a (Storage)
"""

from typing import Any, Optional

from src.extensions.registry import ExtensionRegistry
from src.memory.providers.local import LocalMemoryProvider
from src.memory.schemas import Memory, MemoryType

# Module-level provider instance for OSS mode
# In cloud mode, this would be replaced by registry lookup
_local_provider: Optional[LocalMemoryProvider] = None


def _get_provider() -> LocalMemoryProvider:
    """Get the memory provider instance.

    In cloud mode, checks the registry first.
    Falls back to local provider for OSS mode.
    """
    global _local_provider

    # Check registry for cloud provider
    registry = ExtensionRegistry.get()
    if registry.memory_provider is not None:
        return registry.memory_provider  # type: ignore

    # Fall back to local provider
    if _local_provider is None:
        _local_provider = LocalMemoryProvider()

    return _local_provider


async def create_memory(
    user_id: str,
    content: str,
    memory_type: str,
    source: str,
    confidence: float = 1.0,
    raw_source: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Create a new memory.

    MCP Tool for storing a memory in the memory system.

    Args:
        user_id: User who owns this memory.
        content: The memory content.
        memory_type: Type of memory (preference, fact, decision).
        source: Where this memory came from.
        confidence: Extraction confidence score (0.0-1.0).
        raw_source: Original text for re-extraction.
        metadata: Additional metadata.

    Returns:
        Dict with memory_id of the created memory.

    Example:
        >>> result = await create_memory(
        ...     user_id="user-123",
        ...     content="Prefers tabs over spaces",
        ...     memory_type="preference",
        ...     source="conversation"
        ... )
        >>> print(result["memory_id"])
    """
    # Validate and convert memory_type
    try:
        mem_type = MemoryType(memory_type)
    except ValueError:
        return {"error": f"Invalid memory_type: {memory_type}"}

    # Create Memory object
    memory = Memory(
        user_id=user_id,
        content=content,
        memory_type=mem_type,
        source=source,
        confidence=confidence,
        raw_source=raw_source,
        metadata=metadata or {},
    )

    # Store using provider
    provider = _get_provider()
    memory_id = await provider.store(memory, {})

    return {
        "memory_id": memory_id,
        "message": f"Memory created successfully",
    }


async def get_memories(
    query: str,
    user_id: str,
    limit: int = 5,
) -> dict[str, Any]:
    """Retrieve memories matching a query.

    MCP Tool for semantic search of memories.

    Args:
        query: Search query string.
        user_id: User ID to filter memories.
        limit: Maximum number of memories to return.

    Returns:
        Dict with list of matching memories and count.

    Example:
        >>> result = await get_memories(
        ...     query="coding style preferences",
        ...     user_id="user-123",
        ...     limit=5
        ... )
        >>> for memory in result["memories"]:
        ...     print(memory["content"])
    """
    provider = _get_provider()
    memories = await provider.retrieve(query, user_id, limit=limit)

    return {
        "memories": [_memory_to_dict(m) for m in memories],
        "count": len(memories),
        "query": query,
    }


async def get_memory_by_id(memory_id: str) -> dict[str, Any]:
    """Get a memory by its ID.

    MCP Tool for retrieving a specific memory.

    Args:
        memory_id: The memory ID to look up.

    Returns:
        Dict with memory data or error.

    Example:
        >>> result = await get_memory_by_id("mem-123")
        >>> print(result["content"])
    """
    provider = _get_provider()
    memory = await provider.get_by_id(memory_id)

    if memory is None:
        return {"error": f"Memory not found: {memory_id}", "memory": None}

    return _memory_to_dict(memory)


async def search_memories(
    user_id: str,
    memory_type: Optional[str] = None,
    source: Optional[str] = None,
    min_confidence: float = 0.0,
    limit: int = 10,
) -> dict[str, Any]:
    """Search memories with filters.

    MCP Tool for filtered memory search.

    Args:
        user_id: User ID to filter memories.
        memory_type: Filter by memory type (preference, fact, decision).
        source: Filter by source.
        min_confidence: Minimum confidence threshold.
        limit: Maximum number of memories to return.

    Returns:
        Dict with list of matching memories.

    Example:
        >>> result = await search_memories(
        ...     user_id="user-123",
        ...     memory_type="preference"
        ... )
    """
    filters: dict[str, Any] = {}

    if memory_type is not None:
        try:
            filters["memory_type"] = MemoryType(memory_type)
        except ValueError:
            return {"error": f"Invalid memory_type: {memory_type}"}

    if source is not None:
        filters["source"] = source

    if min_confidence > 0:
        filters["min_confidence"] = min_confidence

    provider = _get_provider()
    memories = await provider.search(user_id, filters, limit=limit)

    return {
        "memories": [_memory_to_dict(m) for m in memories],
        "count": len(memories),
        "filters": {
            "memory_type": memory_type,
            "source": source,
            "min_confidence": min_confidence,
        },
    }


async def delete_memory(memory_id: str) -> dict[str, Any]:
    """Delete a memory by its ID.

    MCP Tool for deleting a memory.

    Args:
        memory_id: The memory ID to delete.

    Returns:
        Dict with success status.

    Example:
        >>> result = await delete_memory("mem-123")
        >>> print(result["success"])
    """
    provider = _get_provider()
    success = await provider.delete(memory_id)

    return {
        "success": success,
        "memory_id": memory_id,
        "message": "Memory deleted" if success else "Memory not found",
    }


async def update_memory(
    memory_id: str,
    content: str,
    source: str,
) -> dict[str, Any]:
    """Update an existing memory.

    MCP Tool for updating a memory's content and source.
    ADR-003 Interface Contract: update_memory(key, value, source)

    Args:
        memory_id: The memory ID to update.
        content: The new memory content.
        source: The source of this update.

    Returns:
        Dict with success status.

    Example:
        >>> result = await update_memory(
        ...     memory_id="mem-123",
        ...     content="Now prefers spaces over tabs",
        ...     source="user-correction"
        ... )
    """
    provider = _get_provider()

    # Check if memory exists
    existing = await provider.get_by_id(memory_id)
    if existing is None:
        return {
            "success": False,
            "error": f"Memory not found: {memory_id}",
        }

    # Update the memory
    updated = await provider.update(memory_id, {
        "content": content,
        "source": source,
    })

    if updated is None:
        return {
            "success": False,
            "error": f"Failed to update memory: {memory_id}",
        }

    return {
        "success": True,
        "memory_id": memory_id,
        "message": "Memory updated successfully",
    }


async def invalidate_memory(
    memory_id: str,
    reason: str,
) -> dict[str, Any]:
    """Invalidate a memory with a reason.

    MCP Tool for marking a memory as invalid/deprecated.
    ADR-003 Interface Contract: invalidate_memory(key, reason)

    Invalidated memories are excluded from normal retrieval
    but can still be accessed directly by ID for audit purposes.

    Args:
        memory_id: The memory ID to invalidate.
        reason: The reason for invalidation.

    Returns:
        Dict with success status.

    Example:
        >>> result = await invalidate_memory(
        ...     memory_id="mem-123",
        ...     reason="User corrected this preference"
        ... )
    """
    provider = _get_provider()

    # Check if memory exists
    existing = await provider.get_by_id(memory_id)
    if existing is None:
        return {
            "success": False,
            "error": f"Memory not found: {memory_id}",
        }

    # Get current metadata and update with invalidation info
    from datetime import datetime, timezone

    updated = await provider.update(memory_id, {})  # Trigger update to access metadata
    if updated is None:
        return {
            "success": False,
            "error": f"Failed to invalidate memory: {memory_id}",
        }

    # Set invalidation metadata directly on provider's internal storage
    if hasattr(provider, '_memories') and memory_id in provider._memories:
        memory = provider._memories[memory_id]
        new_metadata = {
            **memory.metadata,
            "is_valid": False,
            "invalidation_reason": reason,
            "invalidated_at": datetime.now(timezone.utc).isoformat(),
        }
        new_data = memory.model_dump()
        new_data["metadata"] = new_metadata
        provider._memories[memory_id] = Memory(**new_data)

    return {
        "success": True,
        "memory_id": memory_id,
        "reason": reason,
        "message": "Memory invalidated successfully",
    }


async def get_memory_provenance(memory_id: str) -> dict[str, Any]:
    """Get the provenance (history) of a memory.

    MCP Tool for retrieving a memory's full history including
    creation, updates, and invalidation events.
    ADR-003 Interface Contract: get_memory_provenance(key)

    Args:
        memory_id: The memory ID to get provenance for.

    Returns:
        Dict with provenance information.

    Example:
        >>> result = await get_memory_provenance("mem-123")
        >>> print(result["source"])  # Original source
        >>> print(result["update_history"])  # List of updates
    """
    provider = _get_provider()

    memory = await provider.get_by_id(memory_id)
    if memory is None:
        return {
            "error": f"Memory not found: {memory_id}",
            "provenance": None,
        }

    # Build provenance response
    provenance = {
        # Origin information
        "source": memory.source,
        "raw_source": memory.raw_source,
        "extraction_version": memory.extraction_version,

        # Timestamps
        "created_at": memory.created_at.isoformat(),
        "last_accessed_at": memory.last_accessed_at.isoformat(),

        # Update history from metadata
        "update_history": memory.metadata.get("update_history", []),
        "last_modified_at": memory.metadata.get("last_modified_at"),

        # Invalidation info
        "is_valid": memory.metadata.get("is_valid", True),
        "invalidation_reason": memory.metadata.get("invalidation_reason"),
        "invalidated_at": memory.metadata.get("invalidated_at"),

        # Current state
        "current_content": memory.content,
        "memory_type": memory.memory_type.value,
        "confidence": memory.confidence,
    }

    return provenance


def _memory_to_dict(memory: Memory) -> dict[str, Any]:
    """Convert a Memory object to a dict for MCP response."""
    result = {
        "user_id": memory.user_id,
        "content": memory.content,
        "memory_type": memory.memory_type.value,
        "confidence": memory.confidence,
        "source": memory.source,
        "raw_source": memory.raw_source,
        "extraction_version": memory.extraction_version,
        "created_at": memory.created_at.isoformat(),
        "last_accessed_at": memory.last_accessed_at.isoformat(),
        "expires_at": memory.expires_at.isoformat() if memory.expires_at else None,
        "metadata": memory.metadata,
    }

    # Include invalidation info if present
    if "is_valid" in memory.metadata:
        result["is_valid"] = memory.metadata["is_valid"]
    if "invalidation_reason" in memory.metadata:
        result["invalidation_reason"] = memory.metadata["invalidation_reason"]

    return result


def reset_provider() -> None:
    """Reset the provider instance (for testing)."""
    global _local_provider
    if _local_provider is not None:
        _local_provider.clear()
    _local_provider = None
