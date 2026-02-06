"""Integration tests for Hindsight with HybridRetriever (ADR-003 Phase 4.2).

Tests the integration between:
- Timeline temporal storage
- TemporalSearch for time-filtered queries
- HybridRetriever for multi-source retrieval
"""

import pytest
from datetime import datetime, timedelta, timezone


class TestHindsightModuleExports:
    """Test that hindsight module exports are correct."""

    def test_all_types_exported(self):
        """All temporal types should be importable from hindsight module."""
        from luminescent_cluster.memory.hindsight import (
            NetworkType,
            TimeRange,
            TemporalEvent,
            TemporalMemory,
            StateChange,
        )

        assert NetworkType.WORLD is not None
        assert TimeRange is not None
        assert TemporalEvent is not None
        assert TemporalMemory is not None
        assert StateChange is not None

    def test_timeline_exported(self):
        """Timeline should be importable from hindsight module."""
        from luminescent_cluster.memory.hindsight import Timeline

        timeline = Timeline(user_id="test")
        assert timeline is not None

    def test_search_exported(self):
        """Search classes should be importable from hindsight module."""
        from luminescent_cluster.memory.hindsight import (
            TemporalSearch,
            ParsedTemporalQuery,
            TemporalSearchResult,
        )

        assert TemporalSearch is not None
        assert ParsedTemporalQuery is not None
        assert TemporalSearchResult is not None


class TestEndToEndTemporalQuery:
    """End-to-end tests for temporal queries."""

    def test_what_changed_last_month(self):
        """E2E: 'What changed last month?' query."""
        from luminescent_cluster.memory.hindsight import (
            Timeline,
            TemporalSearch,
            TemporalEvent,
            NetworkType,
        )

        # Setup
        timeline = Timeline(user_id="user-123")
        now = datetime.now(timezone.utc)

        # Add events
        events = [
            TemporalEvent(
                id="evt-1",
                content="auth-service deployed v2.0",
                timestamp=now - timedelta(days=5),
                network=NetworkType.OBSERVATION,
                entity_id="auth-service",
            ),
            TemporalEvent(
                id="evt-2",
                content="payment-api rate limit increased",
                timestamp=now - timedelta(days=15),
                network=NetworkType.WORLD,
                entity_id="payment-api",
            ),
            TemporalEvent(
                id="evt-old",
                content="Old event outside window",
                timestamp=now - timedelta(days=60),
                network=NetworkType.OBSERVATION,
                entity_id="legacy-service",
            ),
        ]

        for e in events:
            timeline.add_event(e)

        # Execute query
        search = TemporalSearch(timeline=timeline)
        results = search.search("What changed last month?")

        # Verify
        assert len(results) == 2
        ids = {r.id for r in results}
        assert "evt-1" in ids
        assert "evt-2" in ids
        assert "evt-old" not in ids

    def test_entity_status_before_incident(self):
        """E2E: 'What was auth-service status before incident-123?'"""
        from luminescent_cluster.memory.hindsight import (
            Timeline,
            TemporalSearch,
            TemporalEvent,
            NetworkType,
        )

        # Setup
        timeline = Timeline(user_id="user-123")

        # Add chronological events
        events = [
            TemporalEvent(
                id="status-1",
                content="auth-service status: healthy",
                timestamp=datetime(2025, 6, 1, tzinfo=timezone.utc),
                network=NetworkType.OBSERVATION,
                entity_id="auth-service",
            ),
            TemporalEvent(
                id="status-2",
                content="auth-service status: degraded",
                timestamp=datetime(2025, 6, 10, tzinfo=timezone.utc),
                network=NetworkType.OBSERVATION,
                entity_id="auth-service",
            ),
            TemporalEvent(
                id="incident-123",
                content="auth-service outage incident",
                timestamp=datetime(2025, 6, 15, tzinfo=timezone.utc),
                network=NetworkType.OBSERVATION,
                entity_id="auth-service",
            ),
            TemporalEvent(
                id="status-3",
                content="auth-service status: recovering",
                timestamp=datetime(2025, 6, 16, tzinfo=timezone.utc),
                network=NetworkType.OBSERVATION,
                entity_id="auth-service",
            ),
        ]

        for e in events:
            timeline.add_event(e)

        # Execute query
        search = TemporalSearch(timeline=timeline)
        results = search.search("What was the auth-service status before incident-123?")

        # Verify - should include events up to and including incident time boundary
        # (the "before incident-123" query returns events up to the incident's timestamp)
        assert len(results) >= 1
        # Exclude the incident itself if returned
        non_incident_results = [r for r in results if r.id != "incident-123"]
        assert len(non_incident_results) >= 1
        # All non-incident results should be at or before incident time
        for r in non_incident_results:
            assert r.timestamp <= datetime(2025, 6, 15, tzinfo=timezone.utc)

    def test_decisions_in_quarter(self):
        """E2E: 'Show me decisions made in Q4 2025'"""
        from luminescent_cluster.memory.hindsight import (
            Timeline,
            TemporalSearch,
            TemporalEvent,
            NetworkType,
        )

        # Setup
        timeline = Timeline(user_id="user-123")

        # Add decisions across the year
        events = [
            TemporalEvent(
                id="decision-q1",
                content="Decided to use PostgreSQL",
                timestamp=datetime(2025, 2, 15, tzinfo=timezone.utc),
                network=NetworkType.WORLD,
                entity_id="db-decisions",
                metadata={"memory_type": "decision"},
            ),
            TemporalEvent(
                id="decision-q4-1",
                content="Decided to adopt Kubernetes",
                timestamp=datetime(2025, 10, 15, tzinfo=timezone.utc),
                network=NetworkType.WORLD,
                entity_id="infra-decisions",
                metadata={"memory_type": "decision"},
            ),
            TemporalEvent(
                id="decision-q4-2",
                content="Decided to implement GraphQL",
                timestamp=datetime(2025, 11, 20, tzinfo=timezone.utc),
                network=NetworkType.WORLD,
                entity_id="api-decisions",
                metadata={"memory_type": "decision"},
            ),
            TemporalEvent(
                id="fact-q4",
                content="Service deployed in Q4",
                timestamp=datetime(2025, 12, 1, tzinfo=timezone.utc),
                network=NetworkType.OBSERVATION,
                entity_id="deployment",
                metadata={"memory_type": "fact"},
            ),
        ]

        for e in events:
            timeline.add_event(e)

        # Execute query
        search = TemporalSearch(timeline=timeline)
        results = search.search("Show me decisions made in Q4 2025")

        # Verify - only Q4 decisions
        assert len(results) == 2
        ids = {r.id for r in results}
        assert "decision-q4-1" in ids
        assert "decision-q4-2" in ids
        assert "decision-q1" not in ids
        assert "fact-q4" not in ids


class TestTimelineStateReconstruction:
    """Test state reconstruction capabilities."""

    def test_reconstruct_entity_state_at_time(self):
        """Should reconstruct entity state at any point in time."""
        from luminescent_cluster.memory.hindsight import Timeline, TemporalEvent, NetworkType

        timeline = Timeline(user_id="user-123")

        # Add state evolution
        events = [
            TemporalEvent(
                id="state-1",
                content="auth-service version: 1.0",
                timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
                network=NetworkType.OBSERVATION,
                entity_id="auth-service",
            ),
            TemporalEvent(
                id="state-2",
                content="auth-service version: 2.0",
                timestamp=datetime(2025, 6, 1, tzinfo=timezone.utc),
                network=NetworkType.OBSERVATION,
                entity_id="auth-service",
                supersedes="state-1",
            ),
            TemporalEvent(
                id="state-3",
                content="auth-service version: 3.0",
                timestamp=datetime(2025, 12, 1, tzinfo=timezone.utc),
                network=NetworkType.OBSERVATION,
                entity_id="auth-service",
                supersedes="state-2",
            ),
        ]

        for e in events:
            timeline.add_event(e)

        # Query state at different times
        march_state = timeline.get_entity_state_at(
            entity_id="auth-service",
            at_time=datetime(2025, 3, 1, tzinfo=timezone.utc),
        )
        august_state = timeline.get_entity_state_at(
            entity_id="auth-service",
            at_time=datetime(2025, 8, 1, tzinfo=timezone.utc),
        )

        assert march_state is not None
        assert "1.0" in march_state.content

        assert august_state is not None
        assert "2.0" in august_state.content


class TestFourNetworkArchitecture:
    """Test the four-network memory architecture."""

    def test_world_network_stores_external_facts(self):
        """World network should store external facts."""
        from luminescent_cluster.memory.hindsight import Timeline, TemporalEvent, NetworkType

        timeline = Timeline(user_id="user-123")

        event = TemporalEvent(
            id="world-1",
            content="PostgreSQL 15 released",
            timestamp=datetime(2025, 6, 15, tzinfo=timezone.utc),
            network=NetworkType.WORLD,
            entity_id="postgresql",
        )
        timeline.add_event(event)

        results = timeline.query_by_network(NetworkType.WORLD)
        assert len(results) == 1
        assert results[0].network == NetworkType.WORLD

    def test_bank_network_stores_agent_actions(self):
        """Bank network should store agent's own actions."""
        from luminescent_cluster.memory.hindsight import Timeline, TemporalEvent, NetworkType

        timeline = Timeline(user_id="user-123")

        event = TemporalEvent(
            id="bank-1",
            content="Created PR #123 for auth refactor",
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

    def test_opinion_network_stores_judgments(self):
        """Opinion network should store subjective judgments."""
        from luminescent_cluster.memory.hindsight import Timeline, TemporalEvent, NetworkType

        timeline = Timeline(user_id="user-123")

        event = TemporalEvent(
            id="opinion-1",
            content="Code quality assessment: good",
            timestamp=datetime(2025, 6, 15, tzinfo=timezone.utc),
            network=NetworkType.OPINION,
            entity_id="auth-service",
            confidence=0.85,
            opinion_basis=["test coverage 90%", "no critical bugs"],
        )
        timeline.add_event(event)

        results = timeline.query_by_network(NetworkType.OPINION)
        assert len(results) == 1
        assert results[0].confidence == 0.85
        assert len(results[0].opinion_basis) == 2

    def test_observation_network_stores_neutral_summaries(self):
        """Observation network should store neutral entity summaries."""
        from luminescent_cluster.memory.hindsight import Timeline, TemporalEvent, NetworkType

        timeline = Timeline(user_id="user-123")

        event = TemporalEvent(
            id="obs-1",
            content="auth-service status: healthy",
            timestamp=datetime(2025, 6, 15, tzinfo=timezone.utc),
            network=NetworkType.OBSERVATION,
            entity_id="auth-service",
        )
        timeline.add_event(event)

        results = timeline.query_by_network(NetworkType.OBSERVATION)
        assert len(results) == 1


class TestTemporalSearchWithContext:
    """Test search results with temporal context."""

    def test_results_include_relative_time(self):
        """Search results should include relative time context."""
        from luminescent_cluster.memory.hindsight import (
            Timeline,
            TemporalSearch,
            TemporalEvent,
            NetworkType,
        )

        timeline = Timeline(user_id="user-123")
        now = datetime.now(timezone.utc)

        event = TemporalEvent(
            id="evt-1",
            content="Recent event",
            timestamp=now - timedelta(days=2),
            network=NetworkType.OBSERVATION,
            entity_id="test-entity",
        )
        timeline.add_event(event)

        search = TemporalSearch(timeline=timeline)
        results = search.search_with_context("test")

        assert len(results) >= 1
        assert "relative_time" in results[0].temporal_context
        assert "2 days ago" in results[0].temporal_context["relative_time"]


class TestTimelineSerialization:
    """Test timeline persistence."""

    def test_timeline_round_trip(self):
        """Timeline should serialize and deserialize correctly."""
        from luminescent_cluster.memory.hindsight import Timeline, TemporalEvent, NetworkType

        # Create and populate timeline
        timeline = Timeline(user_id="user-123")
        event = TemporalEvent(
            id="evt-1",
            content="Test event",
            timestamp=datetime(2025, 6, 15, tzinfo=timezone.utc),
            network=NetworkType.WORLD,
            entity_id="test-entity",
        )
        timeline.add_event(event)

        # Serialize
        data = timeline.to_dict()

        # Deserialize
        restored = Timeline.from_dict(data)

        # Verify
        assert restored.user_id == "user-123"
        assert restored.count() == 1
        restored_event = restored.get_event("evt-1")
        assert restored_event is not None
        assert restored_event.content == "Test event"
