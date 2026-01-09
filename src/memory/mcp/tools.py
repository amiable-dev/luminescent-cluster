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
ADR Reference: ADR-003 Memory Architecture, Phase 2 (Grounded Ingestion)
"""

from typing import Any, Optional

from src.extensions.registry import ExtensionRegistry
from src.memory.ingestion import (
    IngestionTier,
    IngestionValidator,
    ReviewQueue,
)
from src.memory.providers.local import LocalMemoryProvider
from src.memory.schemas import Memory, MemoryType

# Module-level provider instance for OSS mode
# In cloud mode, this would be replaced by registry lookup
_local_provider: Optional[LocalMemoryProvider] = None

# Module-level ingestion validator and review queue (ADR-003 Phase 2)
_ingestion_validator: Optional[IngestionValidator] = None
_review_queue: Optional[ReviewQueue] = None


def _log_audit_event(
    actor: str,
    resource: str,
    action: str,
    outcome: str,
    details: Optional[dict[str, Any]] = None,
) -> None:
    """Log an audit event if audit logger is configured.

    This is a no-op in OSS mode. In cloud mode, logs to the configured
    audit logger for compliance (SOC2, HIPAA).

    Args:
        actor: Who performed the action (user_id)
        resource: What was acted upon (memory ID or query)
        action: What was done (create, read, delete, etc.)
        outcome: Result ("success", "failure")
        details: Additional context
    """
    registry = ExtensionRegistry.get()
    if registry.audit_logger is not None:
        registry.audit_logger.log_event(
            event_type="memory_operation",
            actor=actor,
            resource=resource,
            action=action,
            outcome=outcome,
            details=details,
        )


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


def _get_validator() -> IngestionValidator:
    """Get the ingestion validator instance.

    ADR-003 Phase 2: Grounded Memory Ingestion.
    Lazily initializes with the current provider.
    """
    global _ingestion_validator

    if _ingestion_validator is None:
        provider = _get_provider()
        _ingestion_validator = IngestionValidator(
            provider=provider,
            enable_dedup=True,
        )

    return _ingestion_validator


def _get_review_queue() -> ReviewQueue:
    """Get the review queue instance for Tier 2 memories.

    ADR-003 Phase 2: Memories flagged for review are queued
    for human approval before promotion to permanent storage.
    """
    global _review_queue

    if _review_queue is None:
        # Create store callback that stores approved memories
        async def store_approved(
            content: str,
            memory_type: str,
            source: str,
            user_id: str,
            evidence: Any,
        ) -> str:
            """Store an approved memory with evidence attached."""
            provider = _get_provider()
            memory = Memory(
                user_id=user_id,
                content=content,
                memory_type=MemoryType(memory_type),
                source=source,
                confidence=1.0,  # User-approved
                metadata={
                    "evidence": evidence.to_dict() if evidence else {},
                    "approved_from_review": True,
                },
            )
            return await provider.store(memory, {})

        _review_queue = ReviewQueue(store_callback=store_approved)

    return _review_queue


async def create_memory(
    user_id: str,
    content: str,
    memory_type: str,
    source: str,
    confidence: float = 1.0,
    raw_source: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
    bypass_validation: bool = False,
) -> dict[str, Any]:
    """Create a new memory with grounded ingestion validation.

    MCP Tool for storing a memory in the memory system.
    ADR-003 Phase 2: Validates content before storage using 3-tier model.

    Validation Tiers:
    - Tier 1 (AUTO_APPROVE): Content with citations, trusted sources
    - Tier 2 (FLAG_REVIEW): AI-synthesized claims without sources
    - Tier 3 (BLOCK): Speculative content, duplicates

    Args:
        user_id: User who owns this memory.
        content: The memory content.
        memory_type: Type of memory (preference, fact, decision).
        source: Where this memory came from.
        confidence: Extraction confidence score (0.0-1.0).
        raw_source: Original text for re-extraction.
        metadata: Additional metadata.
        bypass_validation: Skip validation (for internal/trusted sources).

    Returns:
        Dict with memory_id of the created memory, or error/pending status.

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

    # === ADR-003 Phase 2: Grounded Ingestion Validation ===
    if not bypass_validation:
        validator = _get_validator()
        validation_result = await validator.validate(
            content=content,
            memory_type=memory_type,
            source=source,
            user_id=user_id,
            metadata=metadata,
        )

        # Tier 3: Block speculative/duplicate content
        if validation_result.tier == IngestionTier.BLOCK:
            _log_audit_event(
                actor=user_id,
                resource="memory:blocked",
                action="create",
                outcome="blocked",
                details={
                    "memory_type": memory_type,
                    "source": source,
                    "reason": validation_result.reason,
                    "checks_failed": validation_result.checks_failed,
                },
            )
            return {
                "error": "blocked",
                "reason": validation_result.reason,
                "tier": validation_result.tier.value,
                "checks_failed": validation_result.checks_failed,
            }

        # Tier 2: Queue for human review
        if validation_result.tier == IngestionTier.FLAG_REVIEW:
            review_queue = _get_review_queue()
            queue_id = await review_queue.enqueue(
                user_id=user_id,
                content=content,
                memory_type=memory_type,
                source=source,
                evidence=validation_result.evidence,
                validation_result=validation_result,
                metadata=metadata,
            )

            _log_audit_event(
                actor=user_id,
                resource=f"memory:pending:{queue_id}",
                action="create",
                outcome="pending_review",
                details={
                    "memory_type": memory_type,
                    "source": source,
                    "queue_id": queue_id,
                },
            )
            return {
                "status": "pending_review",
                "queue_id": queue_id,
                "reason": validation_result.reason,
                "tier": validation_result.tier.value,
                "message": "Memory queued for review. Use approve_pending_memory() to approve.",
            }

        # Tier 1: Auto-approve - continue to storage
        # Attach evidence to metadata
        metadata = metadata or {}
        metadata["evidence"] = validation_result.evidence.to_dict()
        metadata["validation_tier"] = validation_result.tier.value

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

    # Audit log the creation
    _log_audit_event(
        actor=user_id,
        resource=f"memory:{memory_id}",
        action="create",
        outcome="success",
        details={"memory_type": memory_type, "source": source},
    )

    return {
        "memory_id": memory_id,
        "message": "Memory created successfully",
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

    # Audit log the retrieval
    _log_audit_event(
        actor=user_id,
        resource=f"memories:search",
        action="read",
        outcome="success",
        details={"query": query, "results_count": len(memories), "limit": limit},
    )

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

    # Audit log the deletion
    _log_audit_event(
        actor="system",  # Delete doesn't have user_id in signature
        resource=f"memory:{memory_id}",
        action="delete",
        outcome="success" if success else "failure",
        details={"memory_id": memory_id},
    )

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
        _log_audit_event(
            actor="system",
            resource=f"memory:{memory_id}",
            action="update",
            outcome="failure",
            details={"memory_id": memory_id, "source": source},
        )
        return {
            "success": False,
            "error": f"Failed to update memory: {memory_id}",
        }

    # Audit log the update
    _log_audit_event(
        actor="system",
        resource=f"memory:{memory_id}",
        action="update",
        outcome="success",
        details={"memory_id": memory_id, "source": source},
    )

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


async def assemble_context(
    user_id: str,
    query: Optional[str] = None,
    task_context: Optional[str] = None,
    max_tokens: int = 5000,
) -> dict[str, Any]:
    """Assemble context blocks for LLM consumption.

    MCP Tool for structured context assembly using Memory Blocks architecture.
    ADR-003 Phase 2: Context Engineering

    Args:
        user_id: User ID for personalized context.
        query: Optional search query for knowledge retrieval.
        task_context: Optional current task description.
        max_tokens: Maximum total tokens (default 5000).

    Returns:
        Dict with assembled blocks, total tokens, and provenance.

    Example:
        >>> result = await assemble_context(
        ...     user_id="user-123",
        ...     query="authentication patterns",
        ...     task_context="Implementing OAuth2"
        ... )
        >>> print(result["total_tokens"])
    """
    from src.memory.blocks.assembler import BlockAssembler
    from src.memory.evaluation.token_efficiency import TokenEfficiencyMetric

    assembler = BlockAssembler(token_budget=max_tokens)
    blocks = await assembler.assemble(
        user_id=user_id,
        query=query,
        task_context=task_context,
    )

    # Calculate efficiency metrics
    metric = TokenEfficiencyMetric(baseline_tokens=max_tokens)
    efficiency = metric.calculate_efficiency(blocks)

    # Audit log the assembly
    _log_audit_event(
        actor=user_id,
        resource="context:assembly",
        action="assemble",
        outcome="success",
        details={
            "total_tokens": efficiency["total_tokens"],
            "block_count": len(blocks),
            "query": query,
        },
    )

    return {
        "blocks": [block.to_dict() for block in blocks],
        "total_tokens": efficiency["total_tokens"],
        "efficiency": efficiency,
        "provenance": [
            block.provenance.to_dict()
            for block in blocks
            if block.provenance is not None
        ],
    }


async def get_pending_memories(
    user_id: str,
    limit: int = 10,
) -> dict[str, Any]:
    """Get pending memories awaiting review.

    MCP Tool for listing Tier 2 memories that need human approval.
    ADR-003 Phase 2: Grounded Memory Ingestion review queue.

    Args:
        user_id: User ID to filter pending memories.
        limit: Maximum number of pending memories to return.

    Returns:
        Dict with list of pending memories and count.

    Example:
        >>> result = await get_pending_memories("user-123")
        >>> for pending in result["pending"]:
        ...     print(pending["content"])
    """
    review_queue = _get_review_queue()
    pending = await review_queue.get_pending(user_id, limit=limit)

    return {
        "pending": [p.to_dict() for p in pending],
        "count": len(pending),
        "total_pending": review_queue.pending_count(user_id),
    }


async def approve_pending_memory(
    queue_id: str,
    reviewer: str,
) -> dict[str, Any]:
    """Approve a pending memory from the review queue.

    MCP Tool for approving Tier 2 memories.
    Approved memories are promoted to permanent storage.

    Args:
        queue_id: Queue ID of the pending memory.
        reviewer: Who is approving (user_id or "system").

    Returns:
        Dict with memory_id of the stored memory.

    Example:
        >>> result = await approve_pending_memory(
        ...     queue_id="abc-123",
        ...     reviewer="user-123"
        ... )
        >>> print(result["memory_id"])
    """
    review_queue = _get_review_queue()

    try:
        memory_id = await review_queue.approve(queue_id, reviewer)

        _log_audit_event(
            actor=reviewer,
            resource=f"memory:{memory_id}",
            action="approve",
            outcome="success",
            details={"queue_id": queue_id},
        )

        return {
            "success": True,
            "memory_id": memory_id,
            "message": "Memory approved and stored successfully",
        }
    except ValueError as e:
        return {
            "success": False,
            "error": str(e),
        }


async def reject_pending_memory(
    queue_id: str,
    reviewer: str,
    reason: str,
) -> dict[str, Any]:
    """Reject a pending memory from the review queue.

    MCP Tool for rejecting Tier 2 memories.
    Rejected memories are discarded.

    Args:
        queue_id: Queue ID of the pending memory.
        reviewer: Who is rejecting (user_id or "system").
        reason: Reason for rejection.

    Returns:
        Dict with success status.

    Example:
        >>> result = await reject_pending_memory(
        ...     queue_id="abc-123",
        ...     reviewer="user-123",
        ...     reason="Incorrect information"
        ... )
    """
    review_queue = _get_review_queue()

    try:
        await review_queue.reject(queue_id, reviewer, reason)

        _log_audit_event(
            actor=reviewer,
            resource=f"memory:pending:{queue_id}",
            action="reject",
            outcome="success",
            details={"reason": reason},
        )

        return {
            "success": True,
            "queue_id": queue_id,
            "message": "Memory rejected",
        }
    except ValueError as e:
        return {
            "success": False,
            "error": str(e),
        }


def reset_provider() -> None:
    """Reset the provider and validator instances (for testing)."""
    global _local_provider, _ingestion_validator, _review_queue
    if _local_provider is not None:
        _local_provider.clear()
    _local_provider = None
    _ingestion_validator = None
    _review_queue = None
