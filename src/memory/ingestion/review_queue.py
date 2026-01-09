# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Review queue for Tier 2 memories awaiting human approval.

Tier 2 memories (AI-synthesized claims without citations) are queued
for review before promotion to permanent storage.

From ADR-003 Phase 2:
> TIER 2: Flag for review (medium confidence)
>   - AI-synthesized claims without citations
>   - Factual assertions about external systems/APIs
>   - Queue for user confirmation before promotion
"""

import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from src.memory.ingestion.evidence import EvidenceObject
from src.memory.ingestion.result import ValidationResult


@dataclass
class PendingMemory:
    """A memory pending human review.

    Attributes:
        queue_id: Unique identifier for this pending item.
        user_id: User who owns the memory.
        content: The memory content.
        memory_type: Type of memory (preference, fact, decision).
        source: Source of the memory.
        evidence: Evidence object with provenance.
        validation_result: Full validation result.
        submitted_at: When the memory was submitted.
        metadata: Additional metadata.
    """

    queue_id: str
    user_id: str
    content: str
    memory_type: str
    source: str
    evidence: EvidenceObject
    validation_result: ValidationResult
    submitted_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "queue_id": self.queue_id,
            "user_id": self.user_id,
            "content": self.content,
            "memory_type": self.memory_type,
            "source": self.source,
            "evidence": self.evidence.to_dict(),
            "validation_result": self.validation_result.to_dict(),
            "submitted_at": self.submitted_at.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class ReviewAction:
    """Record of a review action.

    Attributes:
        queue_id: The pending memory that was reviewed.
        action: Either "approved" or "rejected".
        reviewer: Who performed the review.
        timestamp: When the review happened.
        reason: Optional reason for rejection.
        memory_id: ID of created memory (if approved).
    """

    queue_id: str
    action: str
    reviewer: str
    timestamp: datetime
    reason: Optional[str] = None
    memory_id: Optional[str] = None


class ReviewQueue:
    """Queue for Tier 2 memories awaiting human review.

    Provides in-memory storage for pending memories with
    operations to enqueue, review, approve, and reject.

    Example:
        >>> queue = ReviewQueue()
        >>> queue_id = await queue.enqueue(pending)
        >>> pending_list = await queue.get_pending("user-1")
        >>> memory_id = await queue.approve(queue_id, "reviewer-1")
    """

    # Maximum pending items per user
    MAX_PENDING_PER_USER = 100

    # Maximum total pending items
    MAX_TOTAL_PENDING = 10000

    def __init__(
        self,
        store_callback: Optional[Any] = None,
        max_pending_per_user: int = MAX_PENDING_PER_USER,
    ):
        """Initialize the review queue.

        Args:
            store_callback: Optional callback to store approved memories.
                           Signature: async (content, memory_type, source, user_id, evidence) -> memory_id
            max_pending_per_user: Maximum pending items per user.
        """
        self._pending: OrderedDict[str, PendingMemory] = OrderedDict()
        self._user_pending: dict[str, list[str]] = {}
        self._review_history: list[ReviewAction] = []
        self._store_callback = store_callback
        self.max_pending_per_user = max_pending_per_user

    async def enqueue(
        self,
        user_id: str,
        content: str,
        memory_type: str,
        source: str,
        evidence: EvidenceObject,
        validation_result: ValidationResult,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """Add a memory to the review queue.

        Args:
            user_id: User who owns the memory.
            content: The memory content.
            memory_type: Type of memory.
            source: Source of the memory.
            evidence: Evidence object.
            validation_result: Full validation result.
            metadata: Optional additional metadata.

        Returns:
            Queue ID for the pending memory.

        Raises:
            ValueError: If user has too many pending items.
        """
        # Check user limit
        user_queue = self._user_pending.get(user_id, [])
        if len(user_queue) >= self.max_pending_per_user:
            raise ValueError(
                f"User {user_id} has reached maximum pending items ({self.max_pending_per_user})"
            )

        # Check total limit
        if len(self._pending) >= self.MAX_TOTAL_PENDING:
            # Evict oldest item
            oldest_id = next(iter(self._pending))
            await self._remove_pending(oldest_id)

        # Create pending memory
        queue_id = str(uuid.uuid4())
        pending = PendingMemory(
            queue_id=queue_id,
            user_id=user_id,
            content=content,
            memory_type=memory_type,
            source=source,
            evidence=evidence,
            validation_result=validation_result,
            submitted_at=datetime.now(timezone.utc),
            metadata=metadata or {},
        )

        # Store
        self._pending[queue_id] = pending
        if user_id not in self._user_pending:
            self._user_pending[user_id] = []
        self._user_pending[user_id].append(queue_id)

        return queue_id

    async def get_pending(
        self,
        user_id: str,
        limit: int = 10,
    ) -> list[PendingMemory]:
        """Get pending memories for a user.

        Args:
            user_id: User ID to filter by.
            limit: Maximum items to return.

        Returns:
            List of pending memories, newest first.
        """
        queue_ids = self._user_pending.get(user_id, [])
        result = []

        # Return newest first
        for queue_id in reversed(queue_ids):
            if queue_id in self._pending:
                result.append(self._pending[queue_id])
                if len(result) >= limit:
                    break

        return result

    async def get_by_id(self, queue_id: str) -> Optional[PendingMemory]:
        """Get a specific pending memory.

        Args:
            queue_id: Queue ID to look up.

        Returns:
            PendingMemory or None if not found.
        """
        return self._pending.get(queue_id)

    async def approve(
        self,
        queue_id: str,
        reviewer: str,
    ) -> Optional[str]:
        """Approve a pending memory.

        Removes from queue and optionally stores via callback.

        Args:
            queue_id: Queue ID to approve.
            reviewer: Who is approving.

        Returns:
            Memory ID if stored, queue_id otherwise.

        Raises:
            ValueError: If queue_id not found.
        """
        pending = self._pending.get(queue_id)
        if not pending:
            raise ValueError(f"Pending memory not found: {queue_id}")

        memory_id: Optional[str] = None

        # Store via callback if available
        if self._store_callback:
            memory_id = await self._store_callback(
                content=pending.content,
                memory_type=pending.memory_type,
                source=pending.source,
                user_id=pending.user_id,
                evidence=pending.evidence,
            )

        # Record action
        action = ReviewAction(
            queue_id=queue_id,
            action="approved",
            reviewer=reviewer,
            timestamp=datetime.now(timezone.utc),
            memory_id=memory_id,
        )
        self._review_history.append(action)

        # Remove from queue
        await self._remove_pending(queue_id)

        return memory_id or queue_id

    async def reject(
        self,
        queue_id: str,
        reviewer: str,
        reason: str,
    ) -> None:
        """Reject a pending memory.

        Args:
            queue_id: Queue ID to reject.
            reviewer: Who is rejecting.
            reason: Reason for rejection.

        Raises:
            ValueError: If queue_id not found.
        """
        pending = self._pending.get(queue_id)
        if not pending:
            raise ValueError(f"Pending memory not found: {queue_id}")

        # Record action
        action = ReviewAction(
            queue_id=queue_id,
            action="rejected",
            reviewer=reviewer,
            timestamp=datetime.now(timezone.utc),
            reason=reason,
        )
        self._review_history.append(action)

        # Remove from queue
        await self._remove_pending(queue_id)

    async def _remove_pending(self, queue_id: str) -> None:
        """Remove a pending item from all indexes.

        Args:
            queue_id: Queue ID to remove.
        """
        pending = self._pending.pop(queue_id, None)
        if pending:
            user_queue = self._user_pending.get(pending.user_id, [])
            if queue_id in user_queue:
                user_queue.remove(queue_id)

    async def get_review_history(
        self,
        user_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[ReviewAction]:
        """Get review action history.

        Args:
            user_id: Optional user ID filter.
            limit: Maximum actions to return.

        Returns:
            List of review actions, newest first.
        """
        history = self._review_history.copy()
        history.reverse()

        if user_id:
            # Filter by user - need to check pending memory user_id
            # Since pending is removed, we can't filter accurately
            # Just return all for now
            pass

        return history[:limit]

    def pending_count(self, user_id: Optional[str] = None) -> int:
        """Get count of pending items.

        Args:
            user_id: Optional user ID filter.

        Returns:
            Number of pending items.
        """
        if user_id:
            return len(self._user_pending.get(user_id, []))
        return len(self._pending)

    async def clear_user(self, user_id: str) -> int:
        """Clear all pending items for a user.

        Args:
            user_id: User ID to clear.

        Returns:
            Number of items cleared.
        """
        queue_ids = self._user_pending.get(user_id, []).copy()
        for queue_id in queue_ids:
            await self._remove_pending(queue_id)
        return len(queue_ids)

    async def bulk_approve(
        self,
        queue_ids: list[str],
        reviewer: str,
    ) -> list[str]:
        """Approve multiple pending memories.

        Args:
            queue_ids: List of queue IDs to approve.
            reviewer: Who is approving.

        Returns:
            List of memory IDs (or queue IDs if no callback).
        """
        results = []
        for queue_id in queue_ids:
            try:
                memory_id = await self.approve(queue_id, reviewer)
                if memory_id:
                    results.append(memory_id)
            except ValueError:
                # Skip not found
                continue
        return results

    async def bulk_reject(
        self,
        queue_ids: list[str],
        reviewer: str,
        reason: str,
    ) -> int:
        """Reject multiple pending memories.

        Args:
            queue_ids: List of queue IDs to reject.
            reviewer: Who is rejecting.
            reason: Reason for rejection.

        Returns:
            Number of items rejected.
        """
        count = 0
        for queue_id in queue_ids:
            try:
                await self.reject(queue_id, reviewer, reason)
                count += 1
            except ValueError:
                continue
        return count
