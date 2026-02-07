"""Tests for Hindsight temporal types (ADR-003 Phase 4.2).

TDD RED phase: These tests define the expected API for temporal memory types.

Four-network architecture from ADR-003:
- World Network: Entity state over time
- Bank Network: Relationship evolution (agent's own experiences)
- Opinion Network: Belief changes with confidence
- Observation Network: Event timeline (neutral summaries)

Target queries:
- "What changed last month?"
- "What was the auth-service status before incident-123?"
- "Show me decisions made in Q4 2025"
"""

import pytest
from datetime import datetime, timedelta, timezone
from typing import Optional


class TestNetworkType:
    """Test NetworkType enum for four-network classification."""

    def test_network_type_enum_exists(self):
        """NetworkType enum should define all four networks."""
        from luminescent_cluster.memory.hindsight.types import NetworkType

        assert hasattr(NetworkType, "WORLD")
        assert hasattr(NetworkType, "BANK")
        assert hasattr(NetworkType, "OPINION")
        assert hasattr(NetworkType, "OBSERVATION")

    def test_network_type_values(self):
        """Each network type should have a distinct string value."""
        from luminescent_cluster.memory.hindsight.types import NetworkType

        assert NetworkType.WORLD.value == "world"
        assert NetworkType.BANK.value == "bank"
        assert NetworkType.OPINION.value == "opinion"
        assert NetworkType.OBSERVATION.value == "observation"

    def test_network_type_all_values(self):
        """Should be able to iterate all network types."""
        from luminescent_cluster.memory.hindsight.types import NetworkType

        all_types = list(NetworkType)
        assert len(all_types) == 4


class TestTimeRange:
    """Test TimeRange for temporal queries."""

    def test_time_range_creation(self):
        """TimeRange should accept start and end datetime."""
        from luminescent_cluster.memory.hindsight.types import TimeRange

        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 12, 31, tzinfo=timezone.utc)

        tr = TimeRange(start=start, end=end)

        assert tr.start == start
        assert tr.end == end

    def test_time_range_optional_end(self):
        """TimeRange should allow None end (open-ended)."""
        from luminescent_cluster.memory.hindsight.types import TimeRange

        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        tr = TimeRange(start=start, end=None)

        assert tr.start == start
        assert tr.end is None

    def test_time_range_contains_datetime(self):
        """TimeRange should test if a datetime is contained."""
        from luminescent_cluster.memory.hindsight.types import TimeRange

        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 12, 31, tzinfo=timezone.utc)
        tr = TimeRange(start=start, end=end)

        inside = datetime(2025, 6, 15, tzinfo=timezone.utc)
        before = datetime(2024, 12, 31, tzinfo=timezone.utc)
        after = datetime(2026, 1, 1, tzinfo=timezone.utc)

        assert tr.contains(inside) is True
        assert tr.contains(before) is False
        assert tr.contains(after) is False

    def test_time_range_contains_open_ended(self):
        """Open-ended TimeRange should include all future dates."""
        from luminescent_cluster.memory.hindsight.types import TimeRange

        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        tr = TimeRange(start=start, end=None)

        future = datetime(2099, 12, 31, tzinfo=timezone.utc)
        assert tr.contains(future) is True

    def test_time_range_overlaps(self):
        """TimeRange should detect overlapping ranges."""
        from luminescent_cluster.memory.hindsight.types import TimeRange

        tr1 = TimeRange(
            start=datetime(2025, 1, 1, tzinfo=timezone.utc),
            end=datetime(2025, 6, 30, tzinfo=timezone.utc),
        )
        tr2 = TimeRange(
            start=datetime(2025, 4, 1, tzinfo=timezone.utc),
            end=datetime(2025, 9, 30, tzinfo=timezone.utc),
        )
        tr3 = TimeRange(
            start=datetime(2025, 7, 1, tzinfo=timezone.utc),
            end=datetime(2025, 12, 31, tzinfo=timezone.utc),
        )

        assert tr1.overlaps(tr2) is True
        assert tr1.overlaps(tr3) is False

    def test_time_range_from_relative(self):
        """TimeRange should support relative time creation."""
        from luminescent_cluster.memory.hindsight.types import TimeRange

        # "last month"
        tr = TimeRange.last_n_days(30)
        now = datetime.now(timezone.utc)

        assert tr.end is not None
        assert (now - tr.start).days <= 31
        assert (now - tr.end).total_seconds() < 60  # within a minute

    def test_time_range_from_quarter(self):
        """TimeRange should support quarter-based creation."""
        from luminescent_cluster.memory.hindsight.types import TimeRange

        # Q4 2025
        tr = TimeRange.quarter(2025, 4)

        assert tr.start == datetime(2025, 10, 1, tzinfo=timezone.utc)
        assert tr.end == datetime(2025, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

    def test_time_range_invalid_raises(self):
        """TimeRange should reject invalid ranges (end before start)."""
        from luminescent_cluster.memory.hindsight.types import TimeRange

        with pytest.raises(ValueError, match="end.*before.*start"):
            TimeRange(
                start=datetime(2025, 12, 31, tzinfo=timezone.utc),
                end=datetime(2025, 1, 1, tzinfo=timezone.utc),
            )


class TestTemporalEvent:
    """Test TemporalEvent for event timeline."""

    def test_temporal_event_creation(self):
        """TemporalEvent should capture event with timestamp."""
        from luminescent_cluster.memory.hindsight.types import TemporalEvent, NetworkType

        event = TemporalEvent(
            id="evt-001",
            content="auth-service deployed v2.0",
            timestamp=datetime(2025, 6, 15, 14, 30, tzinfo=timezone.utc),
            network=NetworkType.OBSERVATION,
            entity_id="auth-service",
        )

        assert event.id == "evt-001"
        assert event.content == "auth-service deployed v2.0"
        assert event.network == NetworkType.OBSERVATION
        assert event.entity_id == "auth-service"

    def test_temporal_event_optional_fields(self):
        """TemporalEvent should have optional metadata fields."""
        from luminescent_cluster.memory.hindsight.types import TemporalEvent, NetworkType

        event = TemporalEvent(
            id="evt-002",
            content="Decided to use JWT",
            timestamp=datetime(2025, 3, 1, tzinfo=timezone.utc),
            network=NetworkType.WORLD,
            entity_id="auth-decisions",
            source="ADR-005",
            confidence=0.95,
            supersedes="evt-001",
            metadata={"participants": ["alice", "bob"]},
        )

        assert event.source == "ADR-005"
        assert event.confidence == 0.95
        assert event.supersedes == "evt-001"
        assert event.metadata["participants"] == ["alice", "bob"]

    def test_temporal_event_valid_at(self):
        """TemporalEvent should have validity period."""
        from luminescent_cluster.memory.hindsight.types import TemporalEvent, NetworkType

        event = TemporalEvent(
            id="evt-003",
            content="auth-service status: healthy",
            timestamp=datetime(2025, 6, 1, tzinfo=timezone.utc),
            network=NetworkType.OBSERVATION,
            entity_id="auth-service",
            valid_from=datetime(2025, 6, 1, tzinfo=timezone.utc),
            valid_until=datetime(2025, 6, 15, tzinfo=timezone.utc),
        )

        # Valid on June 10
        assert event.is_valid_at(datetime(2025, 6, 10, tzinfo=timezone.utc)) is True
        # Not valid on June 20 (after valid_until)
        assert event.is_valid_at(datetime(2025, 6, 20, tzinfo=timezone.utc)) is False

    def test_temporal_event_bank_network_action(self):
        """Bank network events should capture agent actions."""
        from luminescent_cluster.memory.hindsight.types import TemporalEvent, NetworkType

        event = TemporalEvent(
            id="evt-004",
            content="Created PR #123 for auth refactor",
            timestamp=datetime(2025, 7, 1, tzinfo=timezone.utc),
            network=NetworkType.BANK,
            entity_id="agent-claude",
            action_type="pr_created",
            action_target="PR #123",
        )

        assert event.network == NetworkType.BANK
        assert event.action_type == "pr_created"
        assert event.action_target == "PR #123"

    def test_temporal_event_opinion_network_confidence(self):
        """Opinion network events should have confidence scores."""
        from luminescent_cluster.memory.hindsight.types import TemporalEvent, NetworkType

        event = TemporalEvent(
            id="evt-005",
            content="auth-service code quality: good",
            timestamp=datetime(2025, 8, 1, tzinfo=timezone.utc),
            network=NetworkType.OPINION,
            entity_id="auth-service",
            confidence=0.85,
            opinion_basis=["test coverage 90%", "no critical bugs"],
        )

        assert event.network == NetworkType.OPINION
        assert event.confidence == 0.85
        assert len(event.opinion_basis) == 2


class TestTemporalMemory:
    """Test TemporalMemory wrapper for Memory with temporal context."""

    def test_temporal_memory_wraps_memory(self):
        """TemporalMemory should wrap existing Memory with temporal fields."""
        from luminescent_cluster.memory.hindsight.types import TemporalMemory, NetworkType
        from luminescent_cluster.memory.schemas import Memory

        base_memory = Memory(
            user_id="user-123",
            content="PostgreSQL chosen for auth-service",
            memory_type="decision",
            source="ADR-005",
        )

        temporal = TemporalMemory(
            memory=base_memory,
            network=NetworkType.WORLD,
            event_time=datetime(2025, 3, 15, tzinfo=timezone.utc),
            entity_id="auth-service",
        )

        assert temporal.memory.user_id == "user-123"
        assert temporal.network == NetworkType.WORLD
        assert temporal.event_time.year == 2025
        assert temporal.entity_id == "auth-service"

    def test_temporal_memory_state_change(self):
        """TemporalMemory should track state changes over time."""
        from luminescent_cluster.memory.hindsight.types import (
            TemporalMemory,
            NetworkType,
            StateChange,
        )
        from luminescent_cluster.memory.schemas import Memory

        base = Memory(
            user_id="user-123",
            content="auth-service status changed",
            memory_type="fact",
            source="monitoring",
        )

        temporal = TemporalMemory(
            memory=base,
            network=NetworkType.OBSERVATION,
            event_time=datetime(2025, 6, 15, 10, 0, tzinfo=timezone.utc),
            entity_id="auth-service",
            state_change=StateChange(
                attribute="status",
                from_value="healthy",
                to_value="degraded",
            ),
        )

        assert temporal.state_change is not None
        assert temporal.state_change.attribute == "status"
        assert temporal.state_change.from_value == "healthy"
        assert temporal.state_change.to_value == "degraded"

    def test_temporal_memory_causation(self):
        """TemporalMemory should track causal relationships."""
        from luminescent_cluster.memory.hindsight.types import TemporalMemory, NetworkType
        from luminescent_cluster.memory.schemas import Memory

        base = Memory(
            user_id="user-123",
            content="incident-123 resolved",
            memory_type="fact",
            source="incident-tracker",
        )

        temporal = TemporalMemory(
            memory=base,
            network=NetworkType.OBSERVATION,
            event_time=datetime(2025, 6, 16, tzinfo=timezone.utc),
            entity_id="incident-123",
            caused_by=["mem-002"],  # The status change caused this
            causes=["mem-004"],  # This causes a follow-up
        )

        assert "mem-002" in temporal.caused_by
        assert "mem-004" in temporal.causes


class TestStateChange:
    """Test StateChange for tracking attribute changes."""

    def test_state_change_creation(self):
        """StateChange should capture attribute transitions."""
        from luminescent_cluster.memory.hindsight.types import StateChange

        change = StateChange(
            attribute="version",
            from_value="1.0.0",
            to_value="2.0.0",
        )

        assert change.attribute == "version"
        assert change.from_value == "1.0.0"
        assert change.to_value == "2.0.0"

    def test_state_change_initial_value(self):
        """StateChange should allow None from_value for initial state."""
        from luminescent_cluster.memory.hindsight.types import StateChange

        change = StateChange(
            attribute="created",
            from_value=None,
            to_value="true",
        )

        assert change.from_value is None
        assert change.to_value == "true"

    def test_state_change_deletion(self):
        """StateChange should allow None to_value for deletions."""
        from luminescent_cluster.memory.hindsight.types import StateChange

        change = StateChange(
            attribute="deprecated",
            from_value="active",
            to_value=None,
        )

        assert change.from_value == "active"
        assert change.to_value is None


class TestTemporalTypesSerialization:
    """Test serialization/deserialization of temporal types."""

    def test_time_range_to_dict(self):
        """TimeRange should serialize to dict."""
        from luminescent_cluster.memory.hindsight.types import TimeRange

        tr = TimeRange(
            start=datetime(2025, 1, 1, tzinfo=timezone.utc),
            end=datetime(2025, 12, 31, tzinfo=timezone.utc),
        )

        data = tr.to_dict()

        assert data["start"] == "2025-01-01T00:00:00+00:00"
        assert data["end"] == "2025-12-31T00:00:00+00:00"

    def test_time_range_from_dict(self):
        """TimeRange should deserialize from dict."""
        from luminescent_cluster.memory.hindsight.types import TimeRange

        data = {
            "start": "2025-01-01T00:00:00+00:00",
            "end": "2025-12-31T00:00:00+00:00",
        }

        tr = TimeRange.from_dict(data)

        assert tr.start.year == 2025
        assert tr.start.month == 1
        assert tr.end.month == 12

    def test_temporal_event_to_dict(self):
        """TemporalEvent should serialize to dict."""
        from luminescent_cluster.memory.hindsight.types import TemporalEvent, NetworkType

        event = TemporalEvent(
            id="evt-001",
            content="test event",
            timestamp=datetime(2025, 6, 15, tzinfo=timezone.utc),
            network=NetworkType.WORLD,
            entity_id="test-entity",
        )

        data = event.to_dict()

        assert data["id"] == "evt-001"
        assert data["content"] == "test event"
        assert data["network"] == "world"
        assert data["entity_id"] == "test-entity"

    def test_temporal_event_from_dict(self):
        """TemporalEvent should deserialize from dict."""
        from luminescent_cluster.memory.hindsight.types import TemporalEvent, NetworkType

        data = {
            "id": "evt-001",
            "content": "test event",
            "timestamp": "2025-06-15T00:00:00+00:00",
            "network": "world",
            "entity_id": "test-entity",
        }

        event = TemporalEvent.from_dict(data)

        assert event.id == "evt-001"
        assert event.network == NetworkType.WORLD
