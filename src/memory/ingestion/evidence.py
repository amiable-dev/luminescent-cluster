# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Evidence Object schema for grounded memory ingestion.

Implements the EvidenceObject schema from ADR-003 Phase 2 for tracking
provenance and validity of memory claims.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Optional

# Confidence levels map to ingestion tiers
ConfidenceLevel = Literal["high", "medium", "low"]


@dataclass
class EvidenceObject:
    """Evidence supporting a memory claim.

    From ADR-003 Phase 2:
    - claim: The memory content being validated
    - source_id: Reference to source (ADR-XXX, commit hash, URL)
    - capture_time: When the claim was captured
    - validity_horizon: Optional expiration for time-bound claims
    - confidence: Validation confidence level (high/medium/low)

    Example:
        >>> evidence = EvidenceObject(
        ...     claim="We use PostgreSQL for the database",
        ...     source_id="ADR-005",
        ...     capture_time=datetime.now(timezone.utc),
        ...     confidence="high",
        ... )
    """

    claim: str
    capture_time: datetime
    confidence: ConfidenceLevel = "medium"
    source_id: Optional[str] = None
    validity_horizon: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate fields after initialization."""
        if not self.claim:
            raise ValueError("claim cannot be empty")

        if self.confidence not in ("high", "medium", "low"):
            raise ValueError(
                f"confidence must be 'high', 'medium', or 'low', got '{self.confidence}'"
            )

        if self.validity_horizon and self.validity_horizon < self.capture_time:
            raise ValueError("validity_horizon cannot be before capture_time")

    @classmethod
    def create(
        cls,
        claim: str,
        source_id: Optional[str] = None,
        confidence: ConfidenceLevel = "medium",
        validity_horizon: Optional[datetime] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> "EvidenceObject":
        """Create an EvidenceObject with current timestamp.

        Args:
            claim: The memory content.
            source_id: Reference to source (ADR-XXX, commit hash, URL).
            confidence: Validation confidence level.
            validity_horizon: Optional expiration datetime.
            metadata: Additional metadata.

        Returns:
            New EvidenceObject instance.
        """
        return cls(
            claim=claim,
            source_id=source_id,
            capture_time=datetime.now(timezone.utc),
            confidence=confidence,
            validity_horizon=validity_horizon,
            metadata=metadata or {},
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation suitable for JSON serialization.
        """
        result: dict[str, Any] = {
            "claim": self.claim,
            "capture_time": self.capture_time.isoformat(),
            "confidence": self.confidence,
        }

        if self.source_id:
            result["source_id"] = self.source_id

        if self.validity_horizon:
            result["validity_horizon"] = self.validity_horizon.isoformat()

        if self.metadata:
            result["metadata"] = self.metadata

        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvidenceObject":
        """Create from dictionary.

        Args:
            data: Dictionary with evidence fields.

        Returns:
            New EvidenceObject instance.
        """
        return cls(
            claim=data["claim"],
            capture_time=datetime.fromisoformat(data["capture_time"]),
            confidence=data.get("confidence", "medium"),
            source_id=data.get("source_id"),
            validity_horizon=(
                datetime.fromisoformat(data["validity_horizon"])
                if data.get("validity_horizon")
                else None
            ),
            metadata=data.get("metadata", {}),
        )

    def is_expired(self, at_time: Optional[datetime] = None) -> bool:
        """Check if the evidence has expired.

        Args:
            at_time: Time to check against (defaults to now).

        Returns:
            True if validity_horizon has passed.
        """
        if not self.validity_horizon:
            return False

        check_time = at_time or datetime.now(timezone.utc)
        return check_time > self.validity_horizon

    def with_source(self, source_id: str) -> "EvidenceObject":
        """Return a copy with updated source_id.

        Args:
            source_id: New source identifier.

        Returns:
            New EvidenceObject with updated source.
        """
        return EvidenceObject(
            claim=self.claim,
            capture_time=self.capture_time,
            confidence=self.confidence,
            source_id=source_id,
            validity_horizon=self.validity_horizon,
            metadata=self.metadata.copy(),
        )

    def with_confidence(self, confidence: ConfidenceLevel) -> "EvidenceObject":
        """Return a copy with updated confidence.

        Args:
            confidence: New confidence level.

        Returns:
            New EvidenceObject with updated confidence.
        """
        return EvidenceObject(
            claim=self.claim,
            capture_time=self.capture_time,
            confidence=confidence,
            source_id=self.source_id,
            validity_horizon=self.validity_horizon,
            metadata=self.metadata.copy(),
        )
