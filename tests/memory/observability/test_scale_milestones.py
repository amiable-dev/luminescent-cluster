"""Tests for Scale Milestone Tracking (ADR-003 Phase D).

TDD tests for HNSW recall monitoring at scale milestones:
- 10,000 items: Small scale
- 50,000 items: Medium scale
- 100,000 items: Large scale

Tests verify:
- Milestone detection and callback triggering
- Per-user milestone tracking
- Health check result recording
- Statistics and history retrieval
"""

import pytest
from datetime import datetime, timezone

from luminescent_cluster.memory.observability.scale_milestones import (
    ScaleMilestone,
    MilestoneCheckResult,
    ScaleMilestoneTracker,
    STANDARD_MILESTONES,
)


class TestScaleMilestone:
    """Test ScaleMilestone dataclass."""

    def test_create_milestone(self):
        """Should create a milestone with required fields."""
        milestone = ScaleMilestone(
            name="test",
            item_count=5000,
        )

        assert milestone.name == "test"
        assert milestone.item_count == 5000
        assert milestone.recall_threshold == 0.90  # Default
        assert milestone.latency_threshold_ms == 1000.0  # Default

    def test_create_milestone_with_custom_thresholds(self):
        """Should create milestone with custom thresholds."""
        milestone = ScaleMilestone(
            name="custom",
            item_count=25000,
            recall_threshold=0.95,
            latency_threshold_ms=500.0,
        )

        assert milestone.recall_threshold == 0.95
        assert milestone.latency_threshold_ms == 500.0


class TestStandardMilestones:
    """Test standard milestone definitions."""

    def test_three_standard_milestones(self):
        """Should have three standard milestones."""
        assert len(STANDARD_MILESTONES) == 3

    def test_small_milestone(self):
        """Small milestone at 10k items."""
        small = STANDARD_MILESTONES[0]
        assert small.name == "small"
        assert small.item_count == 10_000
        assert small.recall_threshold == 0.95
        assert small.latency_threshold_ms == 500.0

    def test_medium_milestone(self):
        """Medium milestone at 50k items."""
        medium = STANDARD_MILESTONES[1]
        assert medium.name == "medium"
        assert medium.item_count == 50_000
        assert medium.recall_threshold == 0.92
        assert medium.latency_threshold_ms == 750.0

    def test_large_milestone(self):
        """Large milestone at 100k items."""
        large = STANDARD_MILESTONES[2]
        assert large.name == "large"
        assert large.item_count == 100_000
        assert large.recall_threshold == 0.90
        assert large.latency_threshold_ms == 1000.0

    def test_milestones_sorted_by_size(self):
        """Milestones should be in ascending order."""
        for i in range(len(STANDARD_MILESTONES) - 1):
            assert STANDARD_MILESTONES[i].item_count < STANDARD_MILESTONES[i + 1].item_count


class TestMilestoneCheckResult:
    """Test MilestoneCheckResult dataclass."""

    @pytest.fixture
    def milestone(self):
        """Create a test milestone."""
        return ScaleMilestone(
            name="test",
            item_count=10_000,
            recall_threshold=0.95,
            latency_threshold_ms=500.0,
        )

    def test_create_check_result(self, milestone):
        """Should create a check result."""
        result = MilestoneCheckResult(
            milestone=milestone,
            current_count=10500,
        )

        assert result.milestone == milestone
        assert result.current_count == 10500
        assert result.recall is None
        assert result.latency_ms is None
        assert result.passed_recall is True
        assert result.passed_latency is True

    def test_check_result_with_measurements(self, milestone):
        """Should create result with measurements."""
        result = MilestoneCheckResult(
            milestone=milestone,
            current_count=10500,
            recall=0.93,
            latency_ms=450.0,
            passed_recall=False,
            passed_latency=True,
        )

        assert result.recall == 0.93
        assert result.latency_ms == 450.0
        assert result.passed_recall is False
        assert result.passed_latency is True

    def test_passed_property_all_pass(self, milestone):
        """passed property should be True when all checks pass."""
        result = MilestoneCheckResult(
            milestone=milestone,
            current_count=10500,
            passed_recall=True,
            passed_latency=True,
        )

        assert result.passed is True

    def test_passed_property_recall_fail(self, milestone):
        """passed property should be False when recall fails."""
        result = MilestoneCheckResult(
            milestone=milestone,
            current_count=10500,
            passed_recall=False,
            passed_latency=True,
        )

        assert result.passed is False

    def test_passed_property_latency_fail(self, milestone):
        """passed property should be False when latency fails."""
        result = MilestoneCheckResult(
            milestone=milestone,
            current_count=10500,
            passed_recall=True,
            passed_latency=False,
        )

        assert result.passed is False

    def test_to_dict(self, milestone):
        """Should serialize to dictionary."""
        result = MilestoneCheckResult(
            milestone=milestone,
            current_count=10500,
            recall=0.96,
            latency_ms=400.0,
            passed_recall=True,
            passed_latency=True,
        )

        d = result.to_dict()

        assert d["milestone_name"] == "test"
        assert d["milestone_item_count"] == 10_000
        assert d["current_count"] == 10500
        assert d["recall"] == 0.96
        assert d["recall_threshold"] == 0.95
        assert d["passed_recall"] is True
        assert d["latency_ms"] == 400.0
        assert d["latency_threshold_ms"] == 500.0
        assert d["passed_latency"] is True
        assert d["passed"] is True
        assert d["needs_reindex"] is False
        assert "timestamp" in d


class TestScaleMilestoneTracker:
    """Test ScaleMilestoneTracker class."""

    @pytest.fixture
    def tracker(self):
        """Create a tracker with standard milestones."""
        return ScaleMilestoneTracker()

    @pytest.fixture
    def custom_milestones(self):
        """Create custom milestones for testing."""
        return [
            ScaleMilestone(name="tiny", item_count=100),
            ScaleMilestone(name="small", item_count=1000),
        ]

    def test_default_milestones(self, tracker):
        """Should use standard milestones by default."""
        assert tracker.milestones == STANDARD_MILESTONES

    def test_custom_milestones(self, custom_milestones):
        """Should accept custom milestones."""
        tracker = ScaleMilestoneTracker(milestones=custom_milestones)
        assert tracker.milestones == custom_milestones

    def test_record_item_count_no_milestone(self, tracker):
        """Should return None when no milestone crossed."""
        result = tracker.record_item_count("user-1", 5000)
        assert result is None

    def test_record_item_count_crosses_milestone(self, tracker):
        """Should return milestone when crossed."""
        # First record below milestone
        tracker.record_item_count("user-1", 9000)

        # Then cross the 10k milestone
        result = tracker.record_item_count("user-1", 11000)

        assert result is not None
        assert result.name == "small"
        assert result.item_count == 10_000

    def test_milestone_only_triggered_once(self, tracker):
        """Milestone should only trigger once per user."""
        # Cross 10k milestone
        tracker.record_item_count("user-1", 9000)
        result1 = tracker.record_item_count("user-1", 11000)

        # Record again above 10k
        result2 = tracker.record_item_count("user-1", 12000)

        assert result1 is not None
        assert result2 is None

    def test_callback_triggered_on_milestone(self):
        """Callback should be triggered when milestone crossed."""
        triggered = []

        def callback(user_id, milestone):
            triggered.append((user_id, milestone.name))

        tracker = ScaleMilestoneTracker(on_milestone_reached=callback)
        tracker.record_item_count("user-1", 9000)
        tracker.record_item_count("user-1", 11000)

        assert len(triggered) == 1
        assert triggered[0] == ("user-1", "small")

    def test_callback_not_triggered_when_disabled(self):
        """Callback should not trigger when trigger_check=False."""
        triggered = []

        def callback(user_id, milestone):
            triggered.append((user_id, milestone.name))

        tracker = ScaleMilestoneTracker(on_milestone_reached=callback)
        tracker.record_item_count("user-1", 9000)
        tracker.record_item_count("user-1", 11000, trigger_check=False)

        assert len(triggered) == 0

    def test_different_users_tracked_separately(self, tracker):
        """Users should have independent milestone tracking."""
        # User 1 crosses 10k
        tracker.record_item_count("user-1", 11000)

        # User 2 also crosses 10k
        result = tracker.record_item_count("user-2", 11000)

        assert result is not None
        assert result.name == "small"

    def test_get_current_milestone_none(self, tracker):
        """Should return None when no milestone reached."""
        tracker.record_item_count("user-1", 5000)
        result = tracker.get_current_milestone("user-1")
        assert result is None

    def test_get_current_milestone_small(self, tracker):
        """Should return small milestone."""
        tracker.record_item_count("user-1", 15000)
        result = tracker.get_current_milestone("user-1")
        assert result is not None
        assert result.name == "small"

    def test_get_current_milestone_medium(self, tracker):
        """Should return medium milestone."""
        tracker.record_item_count("user-1", 60000)
        result = tracker.get_current_milestone("user-1")
        assert result is not None
        assert result.name == "medium"

    def test_get_current_milestone_large(self, tracker):
        """Should return large milestone."""
        tracker.record_item_count("user-1", 150000)
        result = tracker.get_current_milestone("user-1")
        assert result is not None
        assert result.name == "large"

    def test_get_next_milestone_first(self, tracker):
        """Should return small when no milestone reached."""
        tracker.record_item_count("user-1", 5000)
        result = tracker.get_next_milestone("user-1")
        assert result is not None
        assert result.name == "small"

    def test_get_next_milestone_after_small(self, tracker):
        """Should return medium after small."""
        tracker.record_item_count("user-1", 15000)
        result = tracker.get_next_milestone("user-1")
        assert result is not None
        assert result.name == "medium"

    def test_get_next_milestone_none_when_all_reached(self, tracker):
        """Should return None when all milestones reached."""
        tracker.record_item_count("user-1", 150000)
        result = tracker.get_next_milestone("user-1")
        assert result is None

    def test_record_check_result(self, tracker):
        """Should record check results."""
        milestone = STANDARD_MILESTONES[0]
        result = MilestoneCheckResult(
            milestone=milestone,
            current_count=11000,
            recall=0.96,
            latency_ms=400.0,
        )

        tracker.record_check_result("user-1", result)

        history = tracker.get_check_history("user-1")
        assert len(history) == 1
        assert history[0].recall == 0.96

    def test_get_check_history_limit(self, tracker):
        """Should respect limit parameter."""
        milestone = STANDARD_MILESTONES[0]

        # Record 5 results
        for i in range(5):
            result = MilestoneCheckResult(
                milestone=milestone,
                current_count=11000 + i * 100,
            )
            tracker.record_check_result("user-1", result)

        history = tracker.get_check_history("user-1", limit=3)
        assert len(history) == 3

    def test_get_check_history_returns_most_recent(self, tracker):
        """Should return most recent results."""
        milestone = STANDARD_MILESTONES[0]

        # Record 5 results with different counts
        for i in range(5):
            result = MilestoneCheckResult(
                milestone=milestone,
                current_count=11000 + i * 100,
            )
            tracker.record_check_result("user-1", result)

        history = tracker.get_check_history("user-1", limit=2)

        # Should be the last 2 (counts 11300 and 11400)
        assert history[0].current_count == 11300
        assert history[1].current_count == 11400

    def test_get_stats(self, tracker):
        """Should return comprehensive stats."""
        tracker.record_item_count("user-1", 9000)
        tracker.record_item_count("user-1", 15000)

        stats = tracker.get_stats("user-1")

        assert stats["user_id"] == "user-1"
        assert stats["current_count"] == 15000
        assert stats["current_milestone"] == "small"
        assert stats["next_milestone"] == "medium"
        assert stats["next_milestone_count"] == 50_000
        assert 10_000 in stats["crossed_milestones"]

    def test_get_stats_unknown_user(self, tracker):
        """Should return stats for unknown user."""
        stats = tracker.get_stats("unknown-user")

        assert stats["user_id"] == "unknown-user"
        assert stats["current_count"] == 0
        assert stats["current_milestone"] is None
        assert stats["next_milestone"] == "small"

    def test_crossing_multiple_milestones_at_once(self, tracker):
        """Should only return the highest crossed milestone."""
        # Jump from 0 to above medium (crosses both small and medium)
        result = tracker.record_item_count("user-1", 60000)

        # Should return medium as it's the last one processed
        assert result is not None
        assert result.name == "medium"

        # Both should be marked as crossed
        stats = tracker.get_stats("user-1")
        assert 10_000 in stats["crossed_milestones"]
        assert 50_000 in stats["crossed_milestones"]


class TestScaleMilestoneTrackerIntegration:
    """Integration tests for milestone-based health checking."""

    def test_health_check_workflow(self):
        """Test complete health check workflow."""
        health_checks_run = []

        def run_health_check(user_id, milestone):
            """Simulate running a health check."""
            # Simulate measuring recall and latency
            recall = 0.94
            latency = 450.0

            result = MilestoneCheckResult(
                milestone=milestone,
                current_count=tracker._counts[user_id],
                recall=recall,
                latency_ms=latency,
                passed_recall=recall >= milestone.recall_threshold,
                passed_latency=latency <= milestone.latency_threshold_ms,
            )

            health_checks_run.append(result)
            tracker.record_check_result(user_id, result)

        tracker = ScaleMilestoneTracker(on_milestone_reached=run_health_check)

        # Simulate index growth
        tracker.record_item_count("user-1", 5000)
        tracker.record_item_count("user-1", 8000)
        tracker.record_item_count("user-1", 11000)  # Crosses 10k milestone

        # Verify health check was run
        assert len(health_checks_run) == 1
        result = health_checks_run[0]
        assert result.milestone.name == "small"
        assert result.passed_recall is False  # 0.94 < 0.95 threshold
        assert result.passed_latency is True  # 450 < 500 threshold

        # Verify result was recorded
        history = tracker.get_check_history("user-1")
        assert len(history) == 1

    def test_multiple_users_independent_tracking(self):
        """Test that multiple users have independent tracking."""
        callbacks = []

        def callback(user_id, milestone):
            callbacks.append((user_id, milestone.name))

        tracker = ScaleMilestoneTracker(on_milestone_reached=callback)

        # User 1 reaches small milestone
        tracker.record_item_count("user-1", 11000)

        # User 2 reaches small and medium milestones
        tracker.record_item_count("user-2", 55000)

        # User 3 reaches all milestones
        tracker.record_item_count("user-3", 120000)

        # Verify callbacks
        assert ("user-1", "small") in callbacks
        assert ("user-2", "small") in callbacks
        assert ("user-2", "medium") in callbacks
        assert ("user-3", "small") in callbacks
        assert ("user-3", "medium") in callbacks
        assert ("user-3", "large") in callbacks

        # Verify stats
        assert tracker.get_stats("user-1")["current_milestone"] == "small"
        assert tracker.get_stats("user-2")["current_milestone"] == "medium"
        assert tracker.get_stats("user-3")["current_milestone"] == "large"
