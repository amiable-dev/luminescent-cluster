"""Scale milestone tracking for memory system (ADR-003 Phase D).

Tracks when indexes reach significant scale milestones:
- 10,000 items: First major scale point
- 50,000 items: Medium scale
- 100,000 items: Large scale

Triggers recall health checks at milestones to detect degradation.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class ScaleMilestone:
    """A scale milestone with monitoring thresholds.

    Attributes:
        name: Human-readable milestone name
        item_count: Number of items at this milestone
        recall_threshold: Minimum acceptable recall at this scale
        latency_threshold_ms: Maximum acceptable latency in ms
    """

    name: str
    item_count: int
    recall_threshold: float = 0.90
    latency_threshold_ms: float = 1000.0


# Standard milestones from ADR-003
STANDARD_MILESTONES = [
    ScaleMilestone(
        name="small",
        item_count=10_000,
        recall_threshold=0.95,
        latency_threshold_ms=500.0,
    ),
    ScaleMilestone(
        name="medium",
        item_count=50_000,
        recall_threshold=0.92,
        latency_threshold_ms=750.0,
    ),
    ScaleMilestone(
        name="large",
        item_count=100_000,
        recall_threshold=0.90,
        latency_threshold_ms=1000.0,
    ),
]


@dataclass
class MilestoneCheckResult:
    """Result of a milestone health check.

    Attributes:
        milestone: The milestone that was checked
        current_count: Current item count
        recall: Measured recall (if checked)
        latency_ms: Measured latency (if checked)
        passed_recall: Whether recall meets threshold
        passed_latency: Whether latency meets threshold
        timestamp: When the check was performed
        needs_reindex: Whether reindexing is recommended
    """

    milestone: ScaleMilestone
    current_count: int
    recall: Optional[float] = None
    latency_ms: Optional[float] = None
    passed_recall: bool = True
    passed_latency: bool = True
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    needs_reindex: bool = False

    @property
    def passed(self) -> bool:
        """Return True if all checks passed."""
        return self.passed_recall and self.passed_latency

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "milestone_name": self.milestone.name,
            "milestone_item_count": self.milestone.item_count,
            "current_count": self.current_count,
            "recall": self.recall,
            "recall_threshold": self.milestone.recall_threshold,
            "passed_recall": self.passed_recall,
            "latency_ms": self.latency_ms,
            "latency_threshold_ms": self.milestone.latency_threshold_ms,
            "passed_latency": self.passed_latency,
            "passed": self.passed,
            "needs_reindex": self.needs_reindex,
            "timestamp": self.timestamp.isoformat(),
        }


class ScaleMilestoneTracker:
    """Tracks scale milestones and triggers health checks.

    Monitors index sizes and triggers recall/latency checks when
    significant scale milestones are reached.

    Example:
        >>> tracker = ScaleMilestoneTracker()
        >>> tracker.on_milestone_reached = lambda m: run_health_check(m)
        >>> tracker.record_item_count("user-123", 10500)
        # Triggers check for 10k milestone

    Attributes:
        milestones: List of milestones to track
        on_milestone_reached: Callback when milestone is crossed
    """

    def __init__(
        self,
        milestones: list[ScaleMilestone] | None = None,
        on_milestone_reached: Optional[Callable[[str, ScaleMilestone], None]] = None,
    ):
        """Initialize the tracker.

        Args:
            milestones: Custom milestones or use STANDARD_MILESTONES
            on_milestone_reached: Callback when a milestone is crossed.
                Receives (user_id, milestone).
        """
        self.milestones = milestones or STANDARD_MILESTONES
        self.on_milestone_reached = on_milestone_reached

        # Track counts and crossed milestones per user
        self._counts: dict[str, int] = {}
        self._crossed: dict[str, set[int]] = {}
        self._check_results: dict[str, list[MilestoneCheckResult]] = {}

    def record_item_count(
        self,
        user_id: str,
        count: int,
        trigger_check: bool = True,
    ) -> Optional[ScaleMilestone]:
        """Record current item count for a user.

        If the count crosses a new milestone and trigger_check is True,
        the on_milestone_reached callback is called.

        Args:
            user_id: User ID
            count: Current item count
            trigger_check: Whether to trigger milestone callback

        Returns:
            The crossed milestone if any, None otherwise
        """
        old_count = self._counts.get(user_id, 0)
        self._counts[user_id] = count

        if user_id not in self._crossed:
            self._crossed[user_id] = set()

        # Check for newly crossed milestones
        crossed_milestone = None
        for milestone in self.milestones:
            if (
                milestone.item_count not in self._crossed[user_id]
                and old_count < milestone.item_count <= count
            ):
                self._crossed[user_id].add(milestone.item_count)
                crossed_milestone = milestone

                logger.info(
                    f"Scale milestone reached: {milestone.name} ({milestone.item_count} items) "
                    f"for user {user_id}"
                )

                if trigger_check and self.on_milestone_reached:
                    self.on_milestone_reached(user_id, milestone)

        return crossed_milestone

    def get_current_milestone(self, user_id: str) -> Optional[ScaleMilestone]:
        """Get the current milestone for a user.

        Returns the highest milestone that has been crossed.

        Args:
            user_id: User ID

        Returns:
            The highest crossed milestone, or None
        """
        count = self._counts.get(user_id, 0)
        current = None

        for milestone in self.milestones:
            if count >= milestone.item_count:
                current = milestone

        return current

    def get_next_milestone(self, user_id: str) -> Optional[ScaleMilestone]:
        """Get the next milestone for a user.

        Args:
            user_id: User ID

        Returns:
            The next milestone to reach, or None if all reached
        """
        count = self._counts.get(user_id, 0)

        for milestone in self.milestones:
            if count < milestone.item_count:
                return milestone

        return None

    def record_check_result(
        self,
        user_id: str,
        result: MilestoneCheckResult,
    ) -> None:
        """Record a milestone check result.

        Args:
            user_id: User ID
            result: The check result
        """
        if user_id not in self._check_results:
            self._check_results[user_id] = []

        self._check_results[user_id].append(result)

        if not result.passed:
            logger.warning(
                f"Milestone check failed for user {user_id}: "
                f"{result.milestone.name} - "
                f"recall={result.recall}, latency_ms={result.latency_ms}"
            )

    def get_check_history(
        self,
        user_id: str,
        limit: int = 10,
    ) -> list[MilestoneCheckResult]:
        """Get recent check results for a user.

        Args:
            user_id: User ID
            limit: Maximum results to return

        Returns:
            List of recent check results
        """
        results = self._check_results.get(user_id, [])
        return results[-limit:]

    def get_stats(self, user_id: str) -> dict[str, Any]:
        """Get scale tracking stats for a user.

        Args:
            user_id: User ID

        Returns:
            Dictionary with stats
        """
        current = self.get_current_milestone(user_id)
        next_milestone = self.get_next_milestone(user_id)
        check_history = self.get_check_history(user_id, limit=5)

        return {
            "user_id": user_id,
            "current_count": self._counts.get(user_id, 0),
            "current_milestone": current.name if current else None,
            "next_milestone": next_milestone.name if next_milestone else None,
            "next_milestone_count": (next_milestone.item_count if next_milestone else None),
            "crossed_milestones": list(self._crossed.get(user_id, set())),
            "recent_checks": [r.to_dict() for r in check_history],
        }
