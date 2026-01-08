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

from collections import OrderedDict
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

    # Maximum metadata size in bytes (Council Round 12 fix)
    # Prevents DoS via oversized metadata payloads
    MAX_METADATA_SIZE_BYTES = 10000

    # Maximum string identifier length (Council Round 13 fix)
    # Prevents memory exhaustion via oversized string identifiers
    MAX_STRING_ID_LENGTH = 256

    # Maximum metadata key count (Council Round 13 fix)
    # Prevents DoS by checking bounds before json.dumps serialization
    MAX_METADATA_KEYS = 100

    def __init__(self) -> None:
        """Initialize the provenance service with bounded in-memory storage."""
        # Map of memory_id -> Provenance (LRU bounded)
        # Using OrderedDict for O(1) move_to_end LRU operations (Council Round 12 fix)
        self._provenance_store: OrderedDict[str, Provenance] = OrderedDict()
        # Map of memory_id -> list of RetrievalEvents (bounded)
        self._retrieval_history: dict[str, list[RetrievalEvent]] = {}

    def _validate_string_id(self, value: str, field_name: str) -> None:
        """
        Validate string identifier length (Council Round 13 fix).

        Prevents memory exhaustion attacks via oversized string identifiers.

        Args:
            value: String value to validate
            field_name: Name of the field for error message

        Raises:
            ValueError: If string exceeds MAX_STRING_ID_LENGTH
        """
        if len(value) > self.MAX_STRING_ID_LENGTH:
            raise ValueError(
                f"{field_name} length ({len(value)}) exceeds limit "
                f"({self.MAX_STRING_ID_LENGTH})"
            )

    def _validate_metadata_bounds(self, metadata: dict[str, Any]) -> None:
        """
        Validate metadata bounds before serialization (Council Round 13 fix).

        Checks metadata structure bounds BEFORE calling json.dumps to prevent
        DoS via massive object serialization.

        Args:
            metadata: Metadata dict to validate

        Raises:
            ValueError: If metadata exceeds bounds
        """
        # Check type first
        if not isinstance(metadata, dict):
            raise ValueError("Metadata must be a dictionary")

        # Check key count before serialization (prevents deep recursion attack)
        if len(metadata) > self.MAX_METADATA_KEYS:
            raise ValueError(
                f"Metadata key count ({len(metadata)}) exceeds limit "
                f"({self.MAX_METADATA_KEYS})"
            )

        # Check individual key and value string lengths
        for key, value in metadata.items():
            if len(str(key)) > self.MAX_STRING_ID_LENGTH:
                raise ValueError(
                    f"Metadata key length ({len(str(key))}) exceeds limit "
                    f"({self.MAX_STRING_ID_LENGTH})"
                )
            # For string values, check length directly
            if isinstance(value, str) and len(value) > self.MAX_METADATA_SIZE_BYTES:
                raise ValueError(
                    f"Metadata value length ({len(value)}) exceeds limit "
                    f"({self.MAX_METADATA_SIZE_BYTES})"
                )

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
            metadata: Optional additional metadata (size-limited)

        Returns:
            New Provenance instance with created_at timestamp and metadata

        Raises:
            ValueError: If string identifiers exceed MAX_STRING_ID_LENGTH
            ValueError: If metadata exceeds bounds (key count, value sizes, total size)
        """
        # Validate string identifier lengths (Council Round 13 fix - DoS prevention)
        self._validate_string_id(source_id, "source_id")
        self._validate_string_id(source_type, "source_type")

        # Validate metadata bounds BEFORE serialization (Council Round 13 fix)
        # This prevents DoS by catching oversized payloads before json.dumps
        if metadata is not None:
            self._validate_metadata_bounds(metadata)

            # Now safe to serialize for total size check (Council Round 12 fix)
            import json
            metadata_size = len(json.dumps(metadata, default=str))
            if metadata_size > self.MAX_METADATA_SIZE_BYTES:
                raise ValueError(
                    f"Metadata size ({metadata_size} bytes) exceeds limit "
                    f"({self.MAX_METADATA_SIZE_BYTES} bytes)"
                )

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
        OrderedDict provides O(1) move_to_end for LRU tracking.

        Args:
            memory_id: ID of the memory to attach provenance to
            provenance: Provenance record to attach

        Raises:
            ValueError: If memory_id exceeds MAX_STRING_ID_LENGTH
        """
        # Validate memory_id length (Council Round 13 fix)
        self._validate_string_id(memory_id, "memory_id")

        # Remove if exists (will re-add at end for LRU ordering)
        if memory_id in self._provenance_store:
            del self._provenance_store[memory_id]

        # Add at end (most recently used)
        self._provenance_store[memory_id] = provenance

        # Enforce LRU bound (Council Round 10 fix)
        while len(self._provenance_store) > self.MAX_PROVENANCE_ENTRIES:
            # Evict least recently used (first item in OrderedDict)
            lru_key, _ = self._provenance_store.popitem(last=False)
            # Also clean up retrieval history for evicted entries
            self._retrieval_history.pop(lru_key, None)

    async def get_provenance(
        self,
        memory_id: str,
    ) -> Optional[Provenance]:
        """
        Get provenance for a memory by ID.

        Updates access order for LRU tracking using OrderedDict.move_to_end (O(1)).

        Args:
            memory_id: ID of the memory to get provenance for

        Returns:
            Provenance if found, None otherwise

        Raises:
            ValueError: If memory_id exceeds MAX_STRING_ID_LENGTH
        """
        # Validate memory_id length (Council Round 13 fix)
        self._validate_string_id(memory_id, "memory_id")

        result = self._provenance_store.get(memory_id)
        if result is not None:
            # Update access order (move to end for LRU) - O(1) operation
            self._provenance_store.move_to_end(memory_id)
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

        Security Note (Council Round 11): Only tracks retrieval for memory IDs
        that have provenance attached. This prevents orphan entries in
        _retrieval_history from causing unbounded memory growth.

        Args:
            memory_id: ID of the retrieved memory
            retrieval_score: Relevance score from retrieval
            retrieved_by: User or system that performed retrieval

        Raises:
            ValueError: If memory_id or retrieved_by exceed MAX_STRING_ID_LENGTH
        """
        # Validate string identifier lengths (Council Round 13 fix)
        self._validate_string_id(memory_id, "memory_id")
        self._validate_string_id(retrieved_by, "retrieved_by")

        # Only track retrieval for known memory IDs (Council Round 11 fix)
        # This prevents orphan entries in _retrieval_history
        if memory_id not in self._provenance_store:
            return

        # Update provenance with retrieval score
        existing = self._provenance_store[memory_id]
        # Use dataclass replace to create updated copy
        updated = replace(existing, retrieval_score=retrieval_score)
        self._provenance_store[memory_id] = updated

        # Update access order for LRU (accessing = recently used) - O(1) operation
        self._provenance_store.move_to_end(memory_id)

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

        # Enforce per-memory bound (Council Round 9 fix)
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

        Raises:
            ValueError: If memory_id exceeds MAX_STRING_ID_LENGTH
        """
        # Validate memory_id length (Council Round 13 fix)
        self._validate_string_id(memory_id, "memory_id")

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
