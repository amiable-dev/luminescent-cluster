# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""MaaS Agent Handoff - ADR-003 Phase 4.2 (Issues #156-161).

Agent handoff for task transfer between specialized agents:
- Create handoff requests with context
- Accept/reject/complete handoffs
- TTL-based expiration
- Query pending handoffs

Design follows thread-safe singleton pattern.
"""

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, ClassVar, Optional

from src.memory.maas.registry import AgentRegistry
from src.memory.maas.types import AgentCapability

# Default limits for DoS prevention
DEFAULT_MAX_HANDOFFS = 50000
DEFAULT_MAX_PENDING_PER_TARGET = 100


class HandoffCapacityError(Exception):
    """Raised when handoff capacity is exceeded (DoS prevention)."""

    def __init__(self, resource: str, limit: int):
        self.resource = resource
        self.limit = limit
        super().__init__(f"Handoff capacity exceeded: {resource} limit is {limit}")


class HandoffStatus(str, Enum):
    """Status of a handoff request."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    COMPLETED = "completed"
    EXPIRED = "expired"

    def __str__(self) -> str:
        return self.value


@dataclass
class HandoffContext:
    """Context transferred during a handoff.

    Attributes:
        task_description: Description of the task being handed off.
        current_state: Current state/progress of the task.
        relevant_memories: List of memory IDs relevant to the task.
        relevant_files: List of file paths relevant to the task.
    """

    task_description: str
    current_state: dict[str, Any] = field(default_factory=dict)
    relevant_memories: list[str] = field(default_factory=list)
    relevant_files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "task_description": self.task_description,
            "current_state": self.current_state,
            "relevant_memories": self.relevant_memories,
            "relevant_files": self.relevant_files,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HandoffContext":
        """Deserialize from dictionary."""
        return cls(
            task_description=data["task_description"],
            current_state=data.get("current_state", {}),
            relevant_memories=data.get("relevant_memories", []),
            relevant_files=data.get("relevant_files", []),
        )

    def copy(self) -> "HandoffContext":
        """Create a defensive copy of this context.

        Returns:
            A new HandoffContext instance with copied data.
        """
        return HandoffContext(
            task_description=self.task_description,
            current_state=self.current_state.copy(),
            relevant_memories=self.relevant_memories.copy(),
            relevant_files=self.relevant_files.copy(),
        )


@dataclass
class Handoff:
    """A handoff request between agents.

    Attributes:
        id: Unique handoff identifier.
        source_agent_id: Agent initiating the handoff.
        target_agent_id: Agent receiving the handoff.
        context: Handoff context with task details.
        status: Current handoff status.
        created_at: When the handoff was created.
        expires_at: When the handoff expires (optional).
        accepted_at: When the handoff was accepted (if accepted).
        completed_at: When the handoff was completed (if completed).
        rejection_reason: Reason for rejection (if rejected).
        result: Result of the handoff (if completed).
    """

    id: str
    source_agent_id: str
    target_agent_id: str
    context: HandoffContext
    status: HandoffStatus = HandoffStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    result: Optional[dict[str, Any]] = None

    def is_expired(self) -> bool:
        """Check if the handoff has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def copy(self) -> "Handoff":
        """Create a defensive copy of this handoff.

        Returns a new Handoff instance with copied context and result
        to prevent external mutation of internal state.

        Returns:
            A new Handoff instance with the same data.
        """
        return Handoff(
            id=self.id,
            source_agent_id=self.source_agent_id,
            target_agent_id=self.target_agent_id,
            context=self.context.copy(),
            status=self.status,
            created_at=self.created_at,
            expires_at=self.expires_at,
            accepted_at=self.accepted_at,
            completed_at=self.completed_at,
            rejection_reason=self.rejection_reason,
            result=self.result.copy() if self.result else None,
        )


class HandoffManager:
    """Singleton manager for agent handoffs.

    The HandoffManager coordinates task handoffs between agents,
    tracking their lifecycle from initiation to completion.

    Thread-safe: All operations use RLock for synchronization.

    Usage:
        manager = HandoffManager.get()
        handoff_id = manager.initiate_handoff(
            source_agent_id="agent-1",
            target_agent_id="agent-2",
            context=HandoffContext(task_description="Complete the task"),
        )
    """

    # Singleton management
    _instance: ClassVar[Optional["HandoffManager"]] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()
    _audit_logger: ClassVar[Optional[Any]] = None  # MaaSAuditLogger

    def __init__(
        self,
        max_handoffs: int = DEFAULT_MAX_HANDOFFS,
        max_pending_per_target: int = DEFAULT_MAX_PENDING_PER_TARGET,
    ):
        """Initialize the manager (internal use only).

        Args:
            max_handoffs: Maximum total handoffs (DoS prevention).
            max_pending_per_target: Maximum pending handoffs per target agent.
        """
        self._handoffs: dict[str, Handoff] = {}
        self._pending_by_target: dict[str, set[str]] = {}  # target_id -> set of handoff_ids
        self._by_source: dict[str, set[str]] = {}  # source_id -> set of handoff_ids
        self._by_target: dict[str, set[str]] = {}  # target_id -> set of handoff_ids
        self._rlock = threading.RLock()
        self._max_handoffs = max_handoffs
        self._max_pending_per_target = max_pending_per_target

    @classmethod
    def get(cls) -> "HandoffManager":
        """Get the singleton HandoffManager instance.

        Thread-safe: Uses double-checked locking pattern.

        Returns:
            The singleton HandoffManager instance.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance (for testing only)."""
        with cls._lock:
            cls._instance = None
            cls._audit_logger = None

    @classmethod
    def set_audit_logger(cls, logger: Any) -> None:
        """Set the audit logger for the manager.

        Args:
            logger: MaaSAuditLogger instance.
        """
        cls._audit_logger = logger

    def _log_event(
        self,
        event_type: str,
        agent_id: str,
        action: str,
        outcome: str,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """Log an event if audit logger is configured.

        Thread-safe: Captures logger reference to prevent TOCTOU race.
        """
        # Capture reference to prevent race condition (TOCTOU)
        logger = self._audit_logger
        if logger is not None:
            logger.log_agent_operation(
                event_type=event_type,
                agent_id=agent_id,
                action=action,
                outcome=outcome,
                details=details,
            )

    def initiate_handoff(
        self,
        source_agent_id: str,
        target_agent_id: str,
        context: HandoffContext,
        ttl_seconds: Optional[int] = None,
    ) -> Optional[str]:
        """Initiate a handoff from source to target agent.

        Args:
            source_agent_id: Agent initiating the handoff.
            target_agent_id: Agent receiving the handoff.
            context: Handoff context with task details.
            ttl_seconds: Optional TTL in seconds.

        Returns:
            Handoff ID if successful, None if capabilities check fails.

        Raises:
            HandoffCapacityError: If handoff limits are exceeded.
        """
        with self._rlock:
            agent_registry = AgentRegistry.get()

            # Check source has HANDOFF_INITIATE capability
            source = agent_registry.get_agent(source_agent_id)
            if source is None or not source.has_capability(AgentCapability.HANDOFF_INITIATE):
                self._log_event(
                    event_type="HANDOFF",
                    agent_id=source_agent_id,
                    action="initiate_handoff",
                    outcome="denied",
                    details={"reason": "missing_capability", "capability": "HANDOFF_INITIATE"},
                )
                return None

            # Check target has HANDOFF_RECEIVE capability
            target = agent_registry.get_agent(target_agent_id)
            if target is None or not target.has_capability(AgentCapability.HANDOFF_RECEIVE):
                self._log_event(
                    event_type="HANDOFF",
                    agent_id=source_agent_id,
                    action="initiate_handoff",
                    outcome="denied",
                    details={
                        "reason": "target_missing_capability",
                        "target_agent_id": target_agent_id,
                        "capability": "HANDOFF_RECEIVE",
                    },
                )
                return None

            # Check total handoff capacity (DoS prevention)
            if len(self._handoffs) >= self._max_handoffs:
                self._log_event(
                    event_type="HANDOFF",
                    agent_id=source_agent_id,
                    action="initiate_handoff",
                    outcome="denied",
                    details={"reason": "capacity_exceeded", "limit": self._max_handoffs},
                )
                raise HandoffCapacityError("handoffs", self._max_handoffs)

            # Check per-target pending limit (DoS prevention)
            pending_count = len(self._pending_by_target.get(target_agent_id, set()))
            if pending_count >= self._max_pending_per_target:
                self._log_event(
                    event_type="HANDOFF",
                    agent_id=source_agent_id,
                    action="initiate_handoff",
                    outcome="denied",
                    details={
                        "reason": "pending_limit_exceeded",
                        "target_agent_id": target_agent_id,
                        "limit": self._max_pending_per_target,
                    },
                )
                raise HandoffCapacityError("pending_per_target", self._max_pending_per_target)

            # Create handoff
            handoff_id = f"handoff-{uuid.uuid4().hex}"

            expires_at = None
            if ttl_seconds is not None:
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)

            # Copy context to prevent external mutation
            handoff = Handoff(
                id=handoff_id,
                source_agent_id=source_agent_id,
                target_agent_id=target_agent_id,
                context=context.copy(),  # Defensive copy of input
                expires_at=expires_at,
            )

            # Store handoff
            self._handoffs[handoff_id] = handoff

            # Update indexes
            if target_agent_id not in self._pending_by_target:
                self._pending_by_target[target_agent_id] = set()
            self._pending_by_target[target_agent_id].add(handoff_id)

            if source_agent_id not in self._by_source:
                self._by_source[source_agent_id] = set()
            self._by_source[source_agent_id].add(handoff_id)

            if target_agent_id not in self._by_target:
                self._by_target[target_agent_id] = set()
            self._by_target[target_agent_id].add(handoff_id)

            # Log success
            self._log_event(
                event_type="HANDOFF",
                agent_id=source_agent_id,
                action="initiate_handoff",
                outcome="success",
                details={
                    "handoff_id": handoff_id,
                    "target_agent_id": target_agent_id,
                    "task_description": context.task_description[:100],  # Truncate for logging
                },
            )

            return handoff_id

    def accept_handoff(self, handoff_id: str, agent_id: str) -> bool:
        """Accept a handoff.

        Args:
            handoff_id: The handoff to accept.
            agent_id: The agent accepting (must be target).

        Returns:
            True if accepted, False otherwise.
        """
        with self._rlock:
            handoff = self._handoffs.get(handoff_id)
            if handoff is None:
                self._log_event(
                    event_type="HANDOFF",
                    agent_id=agent_id,
                    action="accept_handoff",
                    outcome="failed",
                    details={"reason": "handoff_not_found", "handoff_id": handoff_id},
                )
                return False

            if handoff.target_agent_id != agent_id:
                self._log_event(
                    event_type="PERMISSION_DENIED",
                    agent_id=agent_id,
                    action="accept_handoff",
                    outcome="denied",
                    details={
                        "reason": "not_target_agent",
                        "handoff_id": handoff_id,
                        "actual_target": handoff.target_agent_id,
                    },
                )
                return False

            if handoff.status != HandoffStatus.PENDING:
                self._log_event(
                    event_type="HANDOFF",
                    agent_id=agent_id,
                    action="accept_handoff",
                    outcome="failed",
                    details={"reason": "invalid_status", "handoff_id": handoff_id, "status": str(handoff.status)},
                )
                return False

            if handoff.is_expired():
                handoff.status = HandoffStatus.EXPIRED
                self._log_event(
                    event_type="HANDOFF",
                    agent_id=agent_id,
                    action="accept_handoff",
                    outcome="failed",
                    details={"reason": "expired", "handoff_id": handoff_id},
                )
                return False

            handoff.status = HandoffStatus.ACCEPTED
            handoff.accepted_at = datetime.now(timezone.utc)

            # Remove from pending
            if handoff.target_agent_id in self._pending_by_target:
                self._pending_by_target[handoff.target_agent_id].discard(handoff_id)

            # Log cross-agent handoff acceptance
            self._log_event(
                event_type="CROSS_AGENT_READ",
                agent_id=agent_id,
                action="accept_handoff",
                outcome="success",
                details={
                    "handoff_id": handoff_id,
                    "source_agent_id": handoff.source_agent_id,
                },
            )

            return True

    def reject_handoff(
        self,
        handoff_id: str,
        agent_id: str,
        reason: Optional[str] = None,
    ) -> bool:
        """Reject a handoff.

        Args:
            handoff_id: The handoff to reject.
            agent_id: The agent rejecting (must be target).
            reason: Optional rejection reason.

        Returns:
            True if rejected, False otherwise.
        """
        with self._rlock:
            handoff = self._handoffs.get(handoff_id)
            if handoff is None:
                self._log_event(
                    event_type="HANDOFF",
                    agent_id=agent_id,
                    action="reject_handoff",
                    outcome="failed",
                    details={"reason": "handoff_not_found", "handoff_id": handoff_id},
                )
                return False

            if handoff.target_agent_id != agent_id:
                self._log_event(
                    event_type="PERMISSION_DENIED",
                    agent_id=agent_id,
                    action="reject_handoff",
                    outcome="denied",
                    details={
                        "reason": "not_target_agent",
                        "handoff_id": handoff_id,
                        "actual_target": handoff.target_agent_id,
                    },
                )
                return False

            if handoff.status != HandoffStatus.PENDING:
                self._log_event(
                    event_type="HANDOFF",
                    agent_id=agent_id,
                    action="reject_handoff",
                    outcome="failed",
                    details={"reason": "invalid_status", "handoff_id": handoff_id, "status": str(handoff.status)},
                )
                return False

            handoff.status = HandoffStatus.REJECTED
            handoff.rejection_reason = reason

            # Remove from pending
            if handoff.target_agent_id in self._pending_by_target:
                self._pending_by_target[handoff.target_agent_id].discard(handoff_id)

            # Log rejection
            self._log_event(
                event_type="HANDOFF",
                agent_id=agent_id,
                action="reject_handoff",
                outcome="success",
                details={
                    "handoff_id": handoff_id,
                    "source_agent_id": handoff.source_agent_id,
                    "rejection_reason": reason,
                },
            )

            return True

    def complete_handoff(
        self,
        handoff_id: str,
        agent_id: str,
        result: Optional[dict[str, Any]] = None,
    ) -> bool:
        """Complete a handoff.

        Args:
            handoff_id: The handoff to complete.
            agent_id: The agent completing (must be target).
            result: Optional result data.

        Returns:
            True if completed, False otherwise.
        """
        with self._rlock:
            handoff = self._handoffs.get(handoff_id)
            if handoff is None:
                self._log_event(
                    event_type="HANDOFF",
                    agent_id=agent_id,
                    action="complete_handoff",
                    outcome="failed",
                    details={"reason": "handoff_not_found", "handoff_id": handoff_id},
                )
                return False

            if handoff.target_agent_id != agent_id:
                self._log_event(
                    event_type="PERMISSION_DENIED",
                    agent_id=agent_id,
                    action="complete_handoff",
                    outcome="denied",
                    details={
                        "reason": "not_target_agent",
                        "handoff_id": handoff_id,
                        "actual_target": handoff.target_agent_id,
                    },
                )
                return False

            if handoff.status != HandoffStatus.ACCEPTED:
                self._log_event(
                    event_type="HANDOFF",
                    agent_id=agent_id,
                    action="complete_handoff",
                    outcome="failed",
                    details={"reason": "invalid_status", "handoff_id": handoff_id, "status": str(handoff.status)},
                )
                return False

            handoff.status = HandoffStatus.COMPLETED
            handoff.completed_at = datetime.now(timezone.utc)
            handoff.result = result.copy() if result else None  # Defensive copy of input

            # Log completion
            self._log_event(
                event_type="HANDOFF",
                agent_id=agent_id,
                action="complete_handoff",
                outcome="success",
                details={
                    "handoff_id": handoff_id,
                    "source_agent_id": handoff.source_agent_id,
                },
            )

            return True

    def get_handoff(self, handoff_id: str) -> Optional[Handoff]:
        """Get a handoff by ID.

        Returns a defensive copy to prevent external mutation of internal state.

        Args:
            handoff_id: The handoff ID.

        Returns:
            Defensive copy of Handoff if found, None otherwise.
        """
        with self._rlock:
            handoff = self._handoffs.get(handoff_id)
            if handoff is None:
                return None
            return handoff.copy()

    def get_pending_handoffs(self, agent_id: str) -> list[Handoff]:
        """Get pending handoffs for an agent.

        Returns defensive copies to prevent external mutation of internal state.

        Args:
            agent_id: The target agent ID.

        Returns:
            List of pending Handoff copies.
        """
        with self._rlock:
            handoff_ids = self._pending_by_target.get(agent_id, set())
            return [
                self._handoffs[hid].copy()
                for hid in handoff_ids
                if hid in self._handoffs and self._handoffs[hid].status == HandoffStatus.PENDING
            ]

    def get_handoffs_by_agent(
        self,
        agent_id: str,
        as_source: bool = True,
    ) -> list[Handoff]:
        """Get handoffs involving an agent.

        Returns defensive copies to prevent external mutation of internal state.

        Args:
            agent_id: The agent ID.
            as_source: If True, get handoffs where agent is source.
                      If False, get handoffs where agent is target.

        Returns:
            List of Handoff copies.
        """
        with self._rlock:
            if as_source:
                handoff_ids = self._by_source.get(agent_id, set())
            else:
                handoff_ids = self._by_target.get(agent_id, set())

            return [self._handoffs[hid].copy() for hid in handoff_ids if hid in self._handoffs]

    def expire_old_handoffs(self) -> int:
        """Expire handoffs that have passed their TTL.

        Returns:
            Number of handoffs expired.
        """
        with self._rlock:
            expired_count = 0
            now = datetime.now(timezone.utc)

            for handoff in self._handoffs.values():
                if handoff.status == HandoffStatus.PENDING and handoff.is_expired():
                    handoff.status = HandoffStatus.EXPIRED

                    # Remove from pending
                    if handoff.target_agent_id in self._pending_by_target:
                        self._pending_by_target[handoff.target_agent_id].discard(handoff.id)

                    expired_count += 1

            return expired_count
