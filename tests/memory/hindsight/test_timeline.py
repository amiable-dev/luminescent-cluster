"""Tests for Timeline storage and indexing (ADR-003 Phase 4.2).

TDD RED phase: These tests define the expected API for timeline management.

Timeline responsibilities:
- Store temporal events chronologically
- Index by entity, network, and time range
- Support efficient temporal queries
- Enable state reconstruction at any point in time
"""

import pytest
from datetime import datetime, timedelta, timezone
from typing import Optional


class TestTimelineCreation:
    """Test Timeline instantiation and configuration."""

    def test_timeline_creation(self):
        """Timeline should be instantiated with a user_id scope."""
        from src.memory.hindsight.timeline import Timeline

        timeline = Timeline(user_id="user-123")

        assert timeline.user_id == "user-123"
        assert timeline.count() == 0

    def test_timeline_with_entity_filter(self):
        """Timeline can be scoped to specific entities."""
        from src.memory.hindsight.timeline import Timeline

        timeline = Timeline(user_id="user-123", entity_filter=["auth-service"])

        assert "auth-service" in timeline.entity_filter


class TestTimelineEventStorage:
    """Test adding and retrieving events."""

    def test_add_event(self):
        """Timeline should accept TemporalEvent."""
        from src.memory.hindsight.timeline import Timeline
        from src.memory.hindsight.types import TemporalEvent, NetworkType

        timeline = Timeline(user_id="user-123")
        event = TemporalEvent(
            id="evt-001",
            content="auth-service deployed v2.0",
            timestamp=datetime(2025, 6, 15, tzinfo=timezone.utc),
            network=NetworkType.OBSERVATION,
            entity_id="auth-service",
        )

        timeline.add_event(event)

        assert timeline.count() == 1

    def test_add_multiple_events(self):
        """Timeline should store multiple events in order."""
        from src.memory.hindsight.timeline import Timeline
        from src.memory.hindsight.types import TemporalEvent, NetworkType

        timeline = Timeline(user_id="user-123")

        for i in range(5):
            event = TemporalEvent(
                id=f"evt-{i:03d}",
                content=f"Event {i}",
                timestamp=datetime(2025, 1, i + 1, tzinfo=timezone.utc),
                network=NetworkType.OBSERVATION,
                entity_id="test-entity",
            )
            timeline.add_event(event)

        assert timeline.count() == 5

    def test_get_event_by_id(self):
        """Timeline should retrieve event by ID."""
        from src.memory.hindsight.timeline import Timeline
        from src.memory.hindsight.types import TemporalEvent, NetworkType

        timeline = Timeline(user_id="user-123")
        event = TemporalEvent(
            id="evt-unique",
            content="Unique event",
            timestamp=datetime(2025, 6, 15, tzinfo=timezone.utc),
            network=NetworkType.WORLD,
            entity_id="test-entity",
        )
        timeline.add_event(event)

        retrieved = timeline.get_event("evt-unique")

        assert retrieved is not None
        assert retrieved.content == "Unique event"

    def test_get_nonexistent_event_returns_none(self):
        """Timeline should return None for missing event."""
        from src.memory.hindsight.timeline import Timeline

        timeline = Timeline(user_id="user-123")

        result = timeline.get_event("nonexistent")

        assert result is None

    def test_remove_event(self):
        """Timeline should allow removing events."""
        from src.memory.hindsight.timeline import Timeline
        from src.memory.hindsight.types import TemporalEvent, NetworkType

        timeline = Timeline(user_id="user-123")
        event = TemporalEvent(
            id="evt-remove",
            content="To be removed",
            timestamp=datetime(2025, 6, 15, tzinfo=timezone.utc),
            network=NetworkType.OBSERVATION,
            entity_id="test-entity",
        )
        timeline.add_event(event)

        removed = timeline.remove_event("evt-remove")

        assert removed is True
        assert timeline.count() == 0
        assert timeline.get_event("evt-remove") is None


class TestTimelineTimeQueries:
    """Test time-based queries."""

    def test_query_by_time_range(self):
        """Timeline should return events within a time range."""
        from src.memory.hindsight.timeline import Timeline
        from src.memory.hindsight.types import TemporalEvent, NetworkType, TimeRange

        timeline = Timeline(user_id="user-123")

        # Add events across different times
        for month in range(1, 13):
            event = TemporalEvent(
                id=f"evt-{month:02d}",
                content=f"Event in month {month}",
                timestamp=datetime(2025, month, 15, tzinfo=timezone.utc),
                network=NetworkType.OBSERVATION,
                entity_id="test-entity",
            )
            timeline.add_event(event)

        # Query Q2 (April-June)
        q2 = TimeRange.quarter(2025, 2)
        results = timeline.query_by_time(q2)

        assert len(results) == 3
        months = [r.timestamp.month for r in results]
        assert months == [4, 5, 6]

    def test_query_last_n_days(self):
        """Timeline should support 'last N days' queries."""
        from src.memory.hindsight.timeline import Timeline
        from src.memory.hindsight.types import TemporalEvent, NetworkType, TimeRange

        timeline = Timeline(user_id="user-123")
        now = datetime.now(timezone.utc)

        # Add recent events
        for i in range(10):
            event = TemporalEvent(
                id=f"evt-{i}",
                content=f"Recent event {i}",
                timestamp=now - timedelta(days=i),
                network=NetworkType.OBSERVATION,
                entity_id="test-entity",
            )
            timeline.add_event(event)

        # Query last 5 days
        time_range = TimeRange.last_n_days(5)
        results = timeline.query_by_time(time_range)

        # Should include events from days 0-5 (6 events)
        assert len(results) >= 5

    def test_query_events_sorted_chronologically(self):
        """Events should be returned in chronological order."""
        from src.memory.hindsight.timeline import Timeline
        from src.memory.hindsight.types import TemporalEvent, NetworkType, TimeRange

        timeline = Timeline(user_id="user-123")

        # Add events out of order
        timestamps = [
            datetime(2025, 3, 1, tzinfo=timezone.utc),
            datetime(2025, 1, 1, tzinfo=timezone.utc),
            datetime(2025, 2, 1, tzinfo=timezone.utc),
        ]

        for i, ts in enumerate(timestamps):
            event = TemporalEvent(
                id=f"evt-{i}",
                content=f"Event {i}",
                timestamp=ts,
                network=NetworkType.OBSERVATION,
                entity_id="test-entity",
            )
            timeline.add_event(event)

        # Query all
        time_range = TimeRange(
            start=datetime(2025, 1, 1, tzinfo=timezone.utc),
            end=datetime(2025, 12, 31, tzinfo=timezone.utc),
        )
        results = timeline.query_by_time(time_range)

        # Should be in chronological order
        assert results[0].timestamp.month == 1
        assert results[1].timestamp.month == 2
        assert results[2].timestamp.month == 3


class TestTimelineEntityQueries:
    """Test entity-based queries."""

    def test_query_by_entity(self):
        """Timeline should filter by entity_id."""
        from src.memory.hindsight.timeline import Timeline
        from src.memory.hindsight.types import TemporalEvent, NetworkType

        timeline = Timeline(user_id="user-123")

        # Add events for different entities
        for entity in ["auth-service", "payment-api", "auth-service"]:
            event = TemporalEvent(
                id=f"evt-{entity}-{timeline.count()}",
                content=f"Event for {entity}",
                timestamp=datetime(2025, 6, 15, tzinfo=timezone.utc),
                network=NetworkType.OBSERVATION,
                entity_id=entity,
            )
            timeline.add_event(event)

        results = timeline.query_by_entity("auth-service")

        assert len(results) == 2
        assert all(r.entity_id == "auth-service" for r in results)

    def test_query_by_multiple_entities(self):
        """Timeline should filter by multiple entities."""
        from src.memory.hindsight.timeline import Timeline
        from src.memory.hindsight.types import TemporalEvent, NetworkType

        timeline = Timeline(user_id="user-123")

        for entity in ["auth-service", "payment-api", "user-service"]:
            event = TemporalEvent(
                id=f"evt-{entity}",
                content=f"Event for {entity}",
                timestamp=datetime(2025, 6, 15, tzinfo=timezone.utc),
                network=NetworkType.OBSERVATION,
                entity_id=entity,
            )
            timeline.add_event(event)

        results = timeline.query_by_entities(["auth-service", "user-service"])

        assert len(results) == 2
        entity_ids = {r.entity_id for r in results}
        assert entity_ids == {"auth-service", "user-service"}


class TestTimelineNetworkQueries:
    """Test network-based queries."""

    def test_query_by_network(self):
        """Timeline should filter by network type."""
        from src.memory.hindsight.timeline import Timeline
        from src.memory.hindsight.types import TemporalEvent, NetworkType

        timeline = Timeline(user_id="user-123")

        # Add events for different networks
        networks = [NetworkType.WORLD, NetworkType.BANK, NetworkType.OPINION]
        for i, network in enumerate(networks):
            event = TemporalEvent(
                id=f"evt-{i}",
                content=f"Event for {network.value}",
                timestamp=datetime(2025, 6, 15, tzinfo=timezone.utc),
                network=network,
                entity_id="test-entity",
            )
            timeline.add_event(event)

        results = timeline.query_by_network(NetworkType.WORLD)

        assert len(results) == 1
        assert results[0].network == NetworkType.WORLD

    def test_query_bank_network_actions(self):
        """Should be able to query agent actions (BANK network)."""
        from src.memory.hindsight.timeline import Timeline
        from src.memory.hindsight.types import TemporalEvent, NetworkType

        timeline = Timeline(user_id="user-123")

        # Add agent actions
        event = TemporalEvent(
            id="evt-action",
            content="Created PR #123",
            timestamp=datetime(2025, 6, 15, tzinfo=timezone.utc),
            network=NetworkType.BANK,
            entity_id="agent-claude",
            action_type="pr_created",
            action_target="PR #123",
        )
        timeline.add_event(event)

        results = timeline.query_by_network(NetworkType.BANK)

        assert len(results) == 1
        assert results[0].action_type == "pr_created"


class TestTimelineStateReconstruction:
    """Test state reconstruction at a point in time."""

    def test_get_entity_state_at_time(self):
        """Timeline should reconstruct entity state at a given time."""
        from src.memory.hindsight.timeline import Timeline
        from src.memory.hindsight.types import TemporalEvent, NetworkType

        timeline = Timeline(user_id="user-123")

        # Add state changes over time
        events = [
            TemporalEvent(
                id="evt-1",
                content="auth-service status: healthy",
                timestamp=datetime(2025, 6, 1, tzinfo=timezone.utc),
                network=NetworkType.OBSERVATION,
                entity_id="auth-service",
                valid_from=datetime(2025, 6, 1, tzinfo=timezone.utc),
            ),
            TemporalEvent(
                id="evt-2",
                content="auth-service status: degraded",
                timestamp=datetime(2025, 6, 10, tzinfo=timezone.utc),
                network=NetworkType.OBSERVATION,
                entity_id="auth-service",
                valid_from=datetime(2025, 6, 10, tzinfo=timezone.utc),
                supersedes="evt-1",
            ),
            TemporalEvent(
                id="evt-3",
                content="auth-service status: healthy",
                timestamp=datetime(2025, 6, 15, tzinfo=timezone.utc),
                network=NetworkType.OBSERVATION,
                entity_id="auth-service",
                valid_from=datetime(2025, 6, 15, tzinfo=timezone.utc),
                supersedes="evt-2",
            ),
        ]

        for event in events:
            timeline.add_event(event)

        # Get state at June 12 (should be degraded)
        state = timeline.get_entity_state_at(
            entity_id="auth-service",
            at_time=datetime(2025, 6, 12, tzinfo=timezone.utc),
        )

        assert state is not None
        assert "degraded" in state.content

    def test_get_entity_state_before_first_event(self):
        """Should return None if querying before any events."""
        from src.memory.hindsight.timeline import Timeline
        from src.memory.hindsight.types import TemporalEvent, NetworkType

        timeline = Timeline(user_id="user-123")

        event = TemporalEvent(
            id="evt-1",
            content="auth-service created",
            timestamp=datetime(2025, 6, 1, tzinfo=timezone.utc),
            network=NetworkType.OBSERVATION,
            entity_id="auth-service",
        )
        timeline.add_event(event)

        state = timeline.get_entity_state_at(
            entity_id="auth-service",
            at_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )

        assert state is None


class TestTimelineCombinedQueries:
    """Test combined queries (time + entity + network)."""

    def test_combined_time_and_entity_query(self):
        """Should filter by both time range and entity."""
        from src.memory.hindsight.timeline import Timeline
        from src.memory.hindsight.types import TemporalEvent, NetworkType, TimeRange

        timeline = Timeline(user_id="user-123")

        # Add events for different entities at different times
        for entity in ["auth-service", "payment-api"]:
            for month in [3, 6, 9]:
                event = TemporalEvent(
                    id=f"evt-{entity}-{month}",
                    content=f"{entity} event in month {month}",
                    timestamp=datetime(2025, month, 15, tzinfo=timezone.utc),
                    network=NetworkType.OBSERVATION,
                    entity_id=entity,
                )
                timeline.add_event(event)

        # Query Q2 for auth-service only
        q2 = TimeRange.quarter(2025, 2)
        results = timeline.query(
            time_range=q2,
            entity_id="auth-service",
        )

        assert len(results) == 1
        assert results[0].entity_id == "auth-service"
        assert results[0].timestamp.month == 6

    def test_combined_all_filters(self):
        """Should filter by time, entity, and network."""
        from src.memory.hindsight.timeline import Timeline
        from src.memory.hindsight.types import TemporalEvent, NetworkType, TimeRange

        timeline = Timeline(user_id="user-123")

        # Add various events
        event1 = TemporalEvent(
            id="evt-1",
            content="World event",
            timestamp=datetime(2025, 6, 15, tzinfo=timezone.utc),
            network=NetworkType.WORLD,
            entity_id="auth-service",
        )
        event2 = TemporalEvent(
            id="evt-2",
            content="Observation event",
            timestamp=datetime(2025, 6, 15, tzinfo=timezone.utc),
            network=NetworkType.OBSERVATION,
            entity_id="auth-service",
        )
        event3 = TemporalEvent(
            id="evt-3",
            content="Observation for payment",
            timestamp=datetime(2025, 6, 15, tzinfo=timezone.utc),
            network=NetworkType.OBSERVATION,
            entity_id="payment-api",
        )

        for e in [event1, event2, event3]:
            timeline.add_event(e)

        q2 = TimeRange.quarter(2025, 2)
        results = timeline.query(
            time_range=q2,
            entity_id="auth-service",
            network=NetworkType.OBSERVATION,
        )

        assert len(results) == 1
        assert results[0].id == "evt-2"


class TestTimelineSerialization:
    """Test timeline persistence."""

    def test_timeline_to_dict(self):
        """Timeline should serialize to dictionary."""
        from src.memory.hindsight.timeline import Timeline
        from src.memory.hindsight.types import TemporalEvent, NetworkType

        timeline = Timeline(user_id="user-123")
        event = TemporalEvent(
            id="evt-1",
            content="Test event",
            timestamp=datetime(2025, 6, 15, tzinfo=timezone.utc),
            network=NetworkType.WORLD,
            entity_id="test-entity",
        )
        timeline.add_event(event)

        data = timeline.to_dict()

        assert data["user_id"] == "user-123"
        assert len(data["events"]) == 1

    def test_timeline_from_dict(self):
        """Timeline should deserialize from dictionary."""
        from src.memory.hindsight.timeline import Timeline

        data = {
            "user_id": "user-123",
            "entity_filter": None,
            "events": [
                {
                    "id": "evt-1",
                    "content": "Test event",
                    "timestamp": "2025-06-15T00:00:00+00:00",
                    "network": "world",
                    "entity_id": "test-entity",
                }
            ],
        }

        timeline = Timeline.from_dict(data)

        assert timeline.user_id == "user-123"
        assert timeline.count() == 1
        assert timeline.get_event("evt-1") is not None
