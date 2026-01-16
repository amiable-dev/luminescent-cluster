"""Temporal types for Hindsight memory (ADR-003 Phase 4.2).

Four-network architecture from ADR-003:
- World Network: External facts about the world
- Bank Network: Agent's own experiences and actions
- Opinion Network: Subjective judgments with confidence
- Observation Network: Neutral entity summaries

Design decisions:
- All timestamps are timezone-aware (UTC preferred)
- Events are immutable after creation
- State changes are tracked explicitly for auditing
- Causal relationships enable "why" queries
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional


class NetworkType(Enum):
    """Four-network classification for temporal memory.

    From ADR-003 Hindsight architecture:
    - WORLD: External facts about the world (e.g., "PostgreSQL version 15 released")
    - BANK: Agent's own experiences and actions (e.g., "Created PR #123")
    - OPINION: Subjective judgments with confidence (e.g., "Code quality: good")
    - OBSERVATION: Neutral entity summaries (e.g., "auth-service status: healthy")
    """

    WORLD = "world"
    BANK = "bank"
    OPINION = "opinion"
    OBSERVATION = "observation"


@dataclass
class TimeRange:
    """Represents a time range for temporal queries.

    Supports:
    - Bounded ranges (start to end)
    - Open-ended ranges (start to present/future)
    - Relative ranges ("last 30 days")
    - Quarter-based ranges ("Q4 2025")

    All datetimes should be timezone-aware.
    """

    start: datetime
    end: Optional[datetime] = None

    def __post_init__(self) -> None:
        """Validate time range."""
        if self.end is not None and self.end < self.start:
            raise ValueError(
                f"end ({self.end}) must not be before start ({self.start})"
            )

    def contains(self, dt: datetime) -> bool:
        """Check if a datetime falls within this range.

        Args:
            dt: Datetime to check (must be timezone-aware)

        Returns:
            True if dt is within [start, end], or [start, infinity) if end is None
        """
        if dt < self.start:
            return False
        if self.end is not None and dt > self.end:
            return False
        return True

    def overlaps(self, other: "TimeRange") -> bool:
        """Check if this range overlaps with another.

        Args:
            other: Another TimeRange to check against

        Returns:
            True if the ranges overlap
        """
        # If either is open-ended, they overlap if the other starts before end
        if self.end is None:
            return other.end is None or other.end >= self.start
        if other.end is None:
            return self.end >= other.start

        # Both are bounded
        return self.start <= other.end and other.start <= self.end

    @classmethod
    def last_n_days(cls, days: int) -> "TimeRange":
        """Create a range for the last N days.

        Args:
            days: Number of days to look back

        Returns:
            TimeRange from N days ago to now
        """
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=days)
        return cls(start=start, end=now)

    @classmethod
    def quarter(cls, year: int, q: int) -> "TimeRange":
        """Create a range for a specific quarter.

        Args:
            year: Year (e.g., 2025)
            q: Quarter number (1-4)

        Returns:
            TimeRange for the specified quarter

        Raises:
            ValueError: If quarter is not 1-4
        """
        if not 1 <= q <= 4:
            raise ValueError(f"Quarter must be 1-4, got {q}")

        # Quarter start months: Q1=1, Q2=4, Q3=7, Q4=10
        start_month = (q - 1) * 3 + 1
        start = datetime(year, start_month, 1, tzinfo=timezone.utc)

        # Quarter end: last day of the quarter
        if q == 4:
            end = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        else:
            # First day of next quarter minus 1 second
            end_month = start_month + 3
            end = datetime(year, end_month, 1, tzinfo=timezone.utc) - timedelta(
                seconds=1
            )

        return cls(start=start, end=end)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary.

        Returns:
            Dictionary with ISO-formatted timestamps
        """
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat() if self.end else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TimeRange":
        """Deserialize from dictionary.

        Args:
            data: Dictionary with start and optional end timestamps

        Returns:
            TimeRange instance
        """
        start = datetime.fromisoformat(data["start"])
        end = datetime.fromisoformat(data["end"]) if data.get("end") else None
        return cls(start=start, end=end)


@dataclass
class StateChange:
    """Captures an attribute state change for auditing.

    Used to track how entities evolve over time:
    - Version updates
    - Status changes
    - Configuration modifications

    Supports None for initial creation (from_value=None)
    or deletion (to_value=None).
    """

    attribute: str
    from_value: Optional[str]
    to_value: Optional[str]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "attribute": self.attribute,
            "from_value": self.from_value,
            "to_value": self.to_value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StateChange":
        """Deserialize from dictionary."""
        return cls(
            attribute=data["attribute"],
            from_value=data.get("from_value"),
            to_value=data.get("to_value"),
        )


@dataclass
class TemporalEvent:
    """Represents an event in the temporal timeline.

    Core fields:
    - id: Unique identifier
    - content: Event description
    - timestamp: When the event occurred
    - network: Which of the four networks this belongs to
    - entity_id: The entity this event is about

    Optional fields for rich context:
    - source: Where this information came from (ADR, commit, etc.)
    - confidence: How confident we are (0.0-1.0)
    - supersedes: ID of event this supersedes (for updates)
    - valid_from/valid_until: Validity period
    - action_type/action_target: For BANK network actions
    - opinion_basis: For OPINION network justifications
    - metadata: Additional unstructured data
    """

    id: str
    content: str
    timestamp: datetime
    network: NetworkType
    entity_id: str

    # Optional provenance
    source: Optional[str] = None
    confidence: Optional[float] = None
    supersedes: Optional[str] = None

    # Validity period (when was this true?)
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None

    # BANK network: agent actions
    action_type: Optional[str] = None
    action_target: Optional[str] = None

    # OPINION network: basis for judgment
    opinion_basis: list[str] = field(default_factory=list)

    # Additional metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_valid_at(self, dt: datetime) -> bool:
        """Check if this event was valid at a given time.

        Args:
            dt: Datetime to check

        Returns:
            True if the event was valid at dt
        """
        if self.valid_from is not None and dt < self.valid_from:
            return False
        if self.valid_until is not None and dt > self.valid_until:
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        result = {
            "id": self.id,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "network": self.network.value,
            "entity_id": self.entity_id,
        }

        # Optional fields
        if self.source:
            result["source"] = self.source
        if self.confidence is not None:
            result["confidence"] = self.confidence
        if self.supersedes:
            result["supersedes"] = self.supersedes
        if self.valid_from:
            result["valid_from"] = self.valid_from.isoformat()
        if self.valid_until:
            result["valid_until"] = self.valid_until.isoformat()
        if self.action_type:
            result["action_type"] = self.action_type
        if self.action_target:
            result["action_target"] = self.action_target
        if self.opinion_basis:
            result["opinion_basis"] = self.opinion_basis
        if self.metadata:
            result["metadata"] = self.metadata

        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TemporalEvent":
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            network=NetworkType(data["network"]),
            entity_id=data["entity_id"],
            source=data.get("source"),
            confidence=data.get("confidence"),
            supersedes=data.get("supersedes"),
            valid_from=(
                datetime.fromisoformat(data["valid_from"])
                if data.get("valid_from")
                else None
            ),
            valid_until=(
                datetime.fromisoformat(data["valid_until"])
                if data.get("valid_until")
                else None
            ),
            action_type=data.get("action_type"),
            action_target=data.get("action_target"),
            opinion_basis=data.get("opinion_basis", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class TemporalMemory:
    """Wraps a Memory with temporal context.

    Adds temporal metadata to existing Memory objects:
    - network: Which Hindsight network this belongs to
    - event_time: When this happened
    - entity_id: What entity this is about
    - state_change: What changed (optional)
    - caused_by/causes: Causal relationships

    This enables queries like:
    - "What changed last month?"
    - "What was the status before incident-123?"
    - "Show me decisions made in Q4 2025"
    """

    from src.memory.schemas import Memory

    memory: Memory
    network: NetworkType
    event_time: datetime
    entity_id: str

    # State tracking
    state_change: Optional[StateChange] = None

    # Causal relationships
    caused_by: list[str] = field(default_factory=list)
    causes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        result = {
            "memory_id": self.memory.id,
            "network": self.network.value,
            "event_time": self.event_time.isoformat(),
            "entity_id": self.entity_id,
        }

        if self.state_change:
            result["state_change"] = self.state_change.to_dict()
        if self.caused_by:
            result["caused_by"] = self.caused_by
        if self.causes:
            result["causes"] = self.causes

        return result
