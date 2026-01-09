# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Validation result types for grounded memory ingestion.

Implements the 3-tier provenance model from ADR-003 Phase 2:
- Tier 1: Auto-approve (high confidence)
- Tier 2: Flag for review (medium confidence)
- Tier 3: Block (low confidence)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from src.memory.ingestion.evidence import EvidenceObject


class IngestionTier(str, Enum):
    """Ingestion decision tiers from ADR-003 Phase 2.

    Tier 1 (AUTO_APPROVE):
        Content with explicit ADR/commit/doc links.
        User-stated facts about their own project.
        Decision discussions with clear context.

    Tier 2 (FLAG_REVIEW):
        AI-synthesized claims without citations.
        Factual assertions about external systems/APIs.
        Queued for user confirmation before promotion.

    Tier 3 (BLOCK):
        Speculative content ("maybe", "might", "could be").
        Content that contradicts existing memory.
        Rejected with explanation.
    """

    AUTO_APPROVE = "tier_1"
    FLAG_REVIEW = "tier_2"
    BLOCK = "tier_3"

    @property
    def is_approved(self) -> bool:
        """Return True if this tier allows immediate storage."""
        return self == IngestionTier.AUTO_APPROVE

    @property
    def requires_review(self) -> bool:
        """Return True if this tier requires human review."""
        return self == IngestionTier.FLAG_REVIEW

    @property
    def is_blocked(self) -> bool:
        """Return True if this tier blocks storage."""
        return self == IngestionTier.BLOCK

    @property
    def confidence_level(self) -> str:
        """Map tier to confidence level for EvidenceObject."""
        mapping = {
            IngestionTier.AUTO_APPROVE: "high",
            IngestionTier.FLAG_REVIEW: "medium",
            IngestionTier.BLOCK: "low",
        }
        return mapping[self]


@dataclass
class ValidationResult:
    """Result of memory content validation.

    Contains the ingestion decision (tier), evidence object,
    and details about which checks passed or failed.

    Attributes:
        tier: The ingestion tier decision.
        approved: True if memory can be stored immediately.
        reason: Human-readable explanation of the decision.
        evidence: EvidenceObject with provenance information.
        checks_passed: List of validation checks that passed.
        checks_failed: List of validation checks that failed.
        similarity_score: Similarity to existing memory (if duplicate check ran).
        conflicting_memory_id: ID of conflicting memory (if duplicate/contradiction).

    Example:
        >>> result = ValidationResult(
        ...     tier=IngestionTier.BLOCK,
        ...     approved=False,
        ...     reason="Speculative content detected",
        ...     evidence=evidence,
        ...     checks_passed=["citation_present"],
        ...     checks_failed=["hedge_words_detected: maybe, might"],
        ... )
    """

    tier: IngestionTier
    approved: bool
    reason: str
    evidence: EvidenceObject
    checks_passed: list[str] = field(default_factory=list)
    checks_failed: list[str] = field(default_factory=list)
    similarity_score: Optional[float] = None
    conflicting_memory_id: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate fields after initialization."""
        # Ensure approved matches tier
        if self.tier.is_approved and not self.approved:
            raise ValueError("approved must be True for AUTO_APPROVE tier")
        if self.tier.is_blocked and self.approved:
            raise ValueError("approved must be False for BLOCK tier")

        # Validate similarity score range
        if self.similarity_score is not None:
            if not 0.0 <= self.similarity_score <= 1.0:
                raise ValueError(
                    f"similarity_score must be in [0.0, 1.0], got {self.similarity_score}"
                )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation suitable for JSON serialization.
        """
        result: dict[str, Any] = {
            "tier": self.tier.value,
            "approved": self.approved,
            "reason": self.reason,
            "evidence": self.evidence.to_dict(),
            "checks_passed": self.checks_passed,
            "checks_failed": self.checks_failed,
        }

        if self.similarity_score is not None:
            result["similarity_score"] = self.similarity_score

        if self.conflicting_memory_id:
            result["conflicting_memory_id"] = self.conflicting_memory_id

        return result

    @classmethod
    def approved_result(
        cls,
        evidence: EvidenceObject,
        reason: str = "All validation checks passed",
        checks_passed: Optional[list[str]] = None,
    ) -> "ValidationResult":
        """Create an approved (Tier 1) result.

        Args:
            evidence: Evidence object for the memory.
            reason: Explanation for approval.
            checks_passed: List of passed checks.

        Returns:
            ValidationResult with AUTO_APPROVE tier.
        """
        return cls(
            tier=IngestionTier.AUTO_APPROVE,
            approved=True,
            reason=reason,
            evidence=evidence.with_confidence("high"),
            checks_passed=checks_passed or [],
            checks_failed=[],
        )

    @classmethod
    def flagged_result(
        cls,
        evidence: EvidenceObject,
        reason: str,
        checks_passed: Optional[list[str]] = None,
        checks_failed: Optional[list[str]] = None,
    ) -> "ValidationResult":
        """Create a flagged (Tier 2) result requiring review.

        Args:
            evidence: Evidence object for the memory.
            reason: Explanation for flagging.
            checks_passed: List of passed checks.
            checks_failed: List of failed checks.

        Returns:
            ValidationResult with FLAG_REVIEW tier.
        """
        return cls(
            tier=IngestionTier.FLAG_REVIEW,
            approved=False,
            reason=reason,
            evidence=evidence.with_confidence("medium"),
            checks_passed=checks_passed or [],
            checks_failed=checks_failed or [],
        )

    @classmethod
    def blocked_result(
        cls,
        evidence: EvidenceObject,
        reason: str,
        checks_failed: list[str],
        similarity_score: Optional[float] = None,
        conflicting_memory_id: Optional[str] = None,
    ) -> "ValidationResult":
        """Create a blocked (Tier 3) result.

        Args:
            evidence: Evidence object for the memory.
            reason: Explanation for blocking.
            checks_failed: List of failed checks.
            similarity_score: Similarity to duplicate (if applicable).
            conflicting_memory_id: ID of conflicting memory.

        Returns:
            ValidationResult with BLOCK tier.
        """
        return cls(
            tier=IngestionTier.BLOCK,
            approved=False,
            reason=reason,
            evidence=evidence.with_confidence("low"),
            checks_passed=[],
            checks_failed=checks_failed,
            similarity_score=similarity_score,
            conflicting_memory_id=conflicting_memory_id,
        )

    @property
    def is_duplicate(self) -> bool:
        """Return True if blocked due to duplicate detection."""
        return self.conflicting_memory_id is not None and self.similarity_score is not None

    @property
    def is_speculative(self) -> bool:
        """Return True if blocked due to speculative content."""
        return any("hedge_words" in check for check in self.checks_failed)

    def get_failed_check_details(self) -> list[tuple[str, str]]:
        """Parse failed checks into (check_name, details) tuples.

        Returns:
            List of (check_name, details) tuples.
        """
        result = []
        for check in self.checks_failed:
            if ": " in check:
                name, details = check.split(": ", 1)
                result.append((name, details))
            else:
                result.append((check, ""))
        return result
