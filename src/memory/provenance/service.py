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
    """

    def __init__(self) -> None:
        """Initialize the provenance service with in-memory storage."""
        # Map of memory_id -> Provenance
        self._provenance_store: dict[str, Provenance] = {}
        # Map of memory_id -> list of RetrievalEvents
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
            New Provenance instance with created_at timestamp
        """
        return Provenance(
            source_id=source_id,
            source_type=source_type,
            confidence=confidence,
            created_at=datetime.now(timezone.utc),
            retrieval_score=None,
        )

    async def attach_to_memory(
        self,
        memory_id: str,
        provenance: Provenance,
    ) -> None:
        """
        Attach provenance to a memory by ID.

        Args:
            memory_id: ID of the memory to attach provenance to
            provenance: Provenance record to attach
        """
        self._provenance_store[memory_id] = provenance

    async def get_provenance(
        self,
        memory_id: str,
    ) -> Optional[Provenance]:
        """
        Get provenance for a memory by ID.

        Args:
            memory_id: ID of the memory to get provenance for

        Returns:
            Provenance if found, None otherwise
        """
        return self._provenance_store.get(memory_id)

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
