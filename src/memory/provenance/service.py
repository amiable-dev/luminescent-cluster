# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
Provenance Service for tracking source attribution (ADR-003 Phase 2).

This service tracks provenance for all memory operations, meeting the
ADR-003 Phase 2 exit criterion: "Provenance available for all retrieved items"

Features:
- Create provenance records for memories
- Attach provenance to memory IDs
- Track retrieval events with scores
- Maintain retrieval history for audit

Related GitHub Issues:
- #116: Phase 2: Memory Blocks Architecture

ADR Reference: ADR-003 Memory Architecture, Phase 2 (Context Engineering)
"""

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Optional

from src.memory.blocks.schemas import Provenance


@dataclass
class RetrievalEvent:
    """Record of a memory retrieval event."""

    memory_id: str
    retrieval_score: float
    retrieved_by: str
    timestamp: datetime


class ProvenanceService:
    """
    Service for tracking provenance of memories.

    Provides methods to create, attach, and retrieve provenance records,
    as well as track retrieval events for audit purposes.

    Security Note (Council Round 9/10): All storage is bounded to prevent
    memory leaks:
    - _provenance_store: Uses LRU eviction at MAX_PROVENANCE_ENTRIES
    - _retrieval_history: Bounded per-memory at MAX_RETRIEVAL_HISTORY_PER_MEMORY
    """

    # Maximum retrieval events to keep per memory (Council Round 9 fix)
    MAX_RETRIEVAL_HISTORY_PER_MEMORY = 100

    # Maximum provenance entries to keep (Council Round 10 fix)
    # Uses LRU eviction to prevent unbounded memory growth
    MAX_PROVENANCE_ENTRIES = 10000

    def __init__(self) -> None:
        """Initialize the provenance service with bounded in-memory storage."""
        # Map of memory_id -> Provenance (LRU bounded)
        # Using OrderedDict would be more elegant but dict insertion order
        # is preserved in Python 3.7+ so we track access manually
        self._provenance_store: dict[str, Provenance] = {}
        # Track access order for LRU eviction
        self._provenance_access_order: list[str] = []
        # Map of memory_id -> list of RetrievalEvents (bounded)
        self._retrieval_history: dict[str, list[RetrievalEvent]] = {}

    async def create_provenance(
        self,
        source_id: str,
        source_type: str,
        confidence: float,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Provenance:
        """
        Create a new provenance record.

        Args:
            source_id: Unique identifier of the source
            source_type: Type of source ("memory", "adr", "conversation", etc.)
            confidence: Confidence score (0.0-1.0)
            metadata: Optional additional metadata

        Returns:
            New Provenance instance with created_at timestamp and metadata
        """
        return Provenance(
            source_id=source_id,
            source_type=source_type,
            confidence=confidence,
            created_at=datetime.now(timezone.utc),
            retrieval_score=None,
            metadata=metadata,
        )

    async def attach_to_memory(
        self,
        memory_id: str,
        provenance: Provenance,
    ) -> None:
        """
        Attach provenance to a memory by ID.

        Uses LRU eviction when MAX_PROVENANCE_ENTRIES is exceeded.

        Args:
            memory_id: ID of the memory to attach provenance to
            provenance: Provenance record to attach
        """
        # Update access order (move to end if exists, or add)
        if memory_id in self._provenance_access_order:
            self._provenance_access_order.remove(memory_id)
        self._provenance_access_order.append(memory_id)

        self._provenance_store[memory_id] = provenance

        # Enforce LRU bound (Council Round 10 fix)
        while len(self._provenance_store) > self.MAX_PROVENANCE_ENTRIES:
            # Evict least recently used (first in access order)
            lru_key = self._provenance_access_order.pop(0)
            self._provenance_store.pop(lru_key, None)
            # Also clean up retrieval history for evicted entries
            self._retrieval_history.pop(lru_key, None)

    async def get_provenance(
        self,
        memory_id: str,
    ) -> Optional[Provenance]:
        """
        Get provenance for a memory by ID.

        Updates access order for LRU tracking.

        Args:
            memory_id: ID of the memory to get provenance for

        Returns:
            Provenance if found, None otherwise
        """
        result = self._provenance_store.get(memory_id)
        if result is not None:
            # Update access order (move to end for LRU)
            if memory_id in self._provenance_access_order:
                self._provenance_access_order.remove(memory_id)
                self._provenance_access_order.append(memory_id)
        return result

    async def track_retrieval(
        self,
        memory_id: str,
        retrieval_score: float,
        retrieved_by: str,
    ) -> None:
        """
        Track a retrieval event for a memory.

        Updates the provenance with the retrieval score and records
        the retrieval event in history.

        Args:
            memory_id: ID of the retrieved memory
            retrieval_score: Relevance score from retrieval
            retrieved_by: User or system that performed retrieval
        """
        # Update provenance with retrieval score if it exists
        if memory_id in self._provenance_store:
            existing = self._provenance_store[memory_id]
            # Use dataclass replace to create updated copy
            updated = replace(existing, retrieval_score=retrieval_score)
            self._provenance_store[memory_id] = updated

        # Record retrieval event in history
        event = RetrievalEvent(
            memory_id=memory_id,
            retrieval_score=retrieval_score,
            retrieved_by=retrieved_by,
            timestamp=datetime.now(timezone.utc),
        )

        if memory_id not in self._retrieval_history:
            self._retrieval_history[memory_id] = []
        self._retrieval_history[memory_id].append(event)

        # Enforce bound to prevent memory leak (Council Round 9 fix)
        if len(self._retrieval_history[memory_id]) > self.MAX_RETRIEVAL_HISTORY_PER_MEMORY:
            # Keep most recent events, drop oldest
            self._retrieval_history[memory_id] = self._retrieval_history[memory_id][
                -self.MAX_RETRIEVAL_HISTORY_PER_MEMORY:
            ]

    async def get_retrieval_history(
        self,
        memory_id: str,
    ) -> list[dict[str, Any]]:
        """
        Get retrieval history for a memory.

        Args:
            memory_id: ID of the memory to get history for

        Returns:
            List of retrieval events as dictionaries
        """
        events = self._retrieval_history.get(memory_id, [])
        return [
            {
                "memory_id": event.memory_id,
                "retrieval_score": event.retrieval_score,
                "retrieved_by": event.retrieved_by,
                "timestamp": event.timestamp.isoformat(),
            }
            for event in events
        ]
