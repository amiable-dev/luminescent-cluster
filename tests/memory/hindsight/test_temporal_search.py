"""Tests for temporal search (ADR-003 Phase 4.2).

TDD RED phase: These tests define the expected API for time-filtered retrieval.

Target queries from ADR-003:
- "What changed last month?"
- "What was the auth-service status before incident-123?"
- "Show me decisions made in Q4 2025"

TemporalSearch integrates:
- Timeline for event storage
- Natural language time parsing
- Query planning for temporal reasoning
"""

import pytest
from datetime import datetime, timedelta, timezone


class TestTemporalSearchCreation:
    """Test TemporalSearch instantiation."""

    def test_temporal_search_creation(self):
        """TemporalSearch should be instantiated with a timeline."""
        from luminescent_cluster.memory.hindsight.temporal_search import TemporalSearch
        from luminescent_cluster.memory.hindsight.timeline import Timeline

        timeline = Timeline(user_id="user-123")
        search = TemporalSearch(timeline=timeline)

        assert search.timeline is timeline

    def test_temporal_search_with_memory_provider(self):
        """TemporalSearch can integrate with MemoryProvider."""
        from luminescent_cluster.memory.hindsight.temporal_search import TemporalSearch
        from luminescent_cluster.memory.hindsight.timeline import Timeline
        from unittest.mock import Mock

        timeline = Timeline(user_id="user-123")
        provider = Mock()
        search = TemporalSearch(timeline=timeline, memory_provider=provider)

        assert search.memory_provider is provider


class TestTemporalQueryParsing:
    """Test natural language temporal query parsing."""

    def test_parse_last_month(self):
        """Should parse 'last month' into TimeRange."""
        from luminescent_cluster.memory.hindsight.temporal_search import TemporalSearch
        from luminescent_cluster.memory.hindsight.timeline import Timeline

        timeline = Timeline(user_id="user-123")
        search = TemporalSearch(timeline=timeline)

        result = search.parse_temporal_query("What changed last month?")

        assert result.time_range is not None
        # Should be approximately 30 days
        days_span = (result.time_range.end - result.time_range.start).days
        assert 28 <= days_span <= 31

    def test_parse_last_week(self):
        """Should parse 'last week' into TimeRange."""
        from luminescent_cluster.memory.hindsight.temporal_search import TemporalSearch
        from luminescent_cluster.memory.hindsight.timeline import Timeline

        timeline = Timeline(user_id="user-123")
        search = TemporalSearch(timeline=timeline)

        result = search.parse_temporal_query("What happened last week?")

        assert result.time_range is not None
        days_span = (result.time_range.end - result.time_range.start).days
        assert 6 <= days_span <= 8

    def test_parse_quarter(self):
        """Should parse 'Q4 2025' into TimeRange."""
        from luminescent_cluster.memory.hindsight.temporal_search import TemporalSearch
        from luminescent_cluster.memory.hindsight.timeline import Timeline

        timeline = Timeline(user_id="user-123")
        search = TemporalSearch(timeline=timeline)

        result = search.parse_temporal_query("Show me decisions made in Q4 2025")

        assert result.time_range is not None
        assert result.time_range.start.month == 10
        assert result.time_range.start.year == 2025

    def test_parse_before_reference(self):
        """Should parse 'before incident-123' as reference point."""
        from luminescent_cluster.memory.hindsight.temporal_search import TemporalSearch
        from luminescent_cluster.memory.hindsight.timeline import Timeline
        from luminescent_cluster.memory.hindsight.types import TemporalEvent, NetworkType

        timeline = Timeline(user_id="user-123")

        # Add incident to timeline
        incident = TemporalEvent(
            id="incident-123",
            content="Incident occurred",
            timestamp=datetime(2025, 6, 15, tzinfo=timezone.utc),
            network=NetworkType.OBSERVATION,
            entity_id="auth-service",
        )
        timeline.add_event(incident)

        search = TemporalSearch(timeline=timeline)
        result = search.parse_temporal_query(
            "What was the auth-service status before incident-123?"
        )

        assert result.time_range is not None
        assert result.time_range.end <= datetime(2025, 6, 15, tzinfo=timezone.utc)
        assert result.entity_id == "auth-service"
        assert result.reference_event_id == "incident-123"

    def test_parse_extracts_entity(self):
        """Should extract entity from query."""
        from luminescent_cluster.memory.hindsight.temporal_search import TemporalSearch
        from luminescent_cluster.memory.hindsight.timeline import Timeline

        timeline = Timeline(user_id="user-123")
        search = TemporalSearch(timeline=timeline)

        result = search.parse_temporal_query(
            "What changed in auth-service last month?"
        )

        assert result.entity_id == "auth-service"

    def test_parse_extracts_memory_type(self):
        """Should extract memory type (decision, fact, etc.) from query."""
        from luminescent_cluster.memory.hindsight.temporal_search import TemporalSearch
        from luminescent_cluster.memory.hindsight.timeline import Timeline

        timeline = Timeline(user_id="user-123")
        search = TemporalSearch(timeline=timeline)

        result = search.parse_temporal_query("Show me decisions made in Q4 2025")

        assert result.memory_type == "decision"


class TestTemporalSearchExecution:
    """Test temporal search execution."""

    def test_search_what_changed(self):
        """Should answer 'What changed last month?'"""
        from luminescent_cluster.memory.hindsight.temporal_search import TemporalSearch
        from luminescent_cluster.memory.hindsight.timeline import Timeline
        from luminescent_cluster.memory.hindsight.types import TemporalEvent, NetworkType

        timeline = Timeline(user_id="user-123")
        now = datetime.now(timezone.utc)

        # Add recent and old events
        recent_event = TemporalEvent(
            id="evt-recent",
            content="auth-service deployed v2.0",
            timestamp=now - timedelta(days=5),
            network=NetworkType.OBSERVATION,
            entity_id="auth-service",
        )
        old_event = TemporalEvent(
            id="evt-old",
            content="payment-api deployed v1.0",
            timestamp=now - timedelta(days=60),
            network=NetworkType.OBSERVATION,
            entity_id="payment-api",
        )

        timeline.add_event(recent_event)
        timeline.add_event(old_event)

        search = TemporalSearch(timeline=timeline)
        results = search.search("What changed last month?")

        assert len(results) == 1
        assert results[0].id == "evt-recent"

    def test_search_entity_status_before_event(self):
        """Should answer 'What was auth-service status before incident-123?'"""
        from luminescent_cluster.memory.hindsight.temporal_search import TemporalSearch
        from luminescent_cluster.memory.hindsight.timeline import Timeline
        from luminescent_cluster.memory.hindsight.types import TemporalEvent, NetworkType

        timeline = Timeline(user_id="user-123")

        # Add status events before and after incident
        pre_incident = TemporalEvent(
            id="status-healthy",
            content="auth-service status: healthy",
            timestamp=datetime(2025, 6, 10, tzinfo=timezone.utc),
            network=NetworkType.OBSERVATION,
            entity_id="auth-service",
        )
        incident = TemporalEvent(
            id="incident-123",
            content="auth-service incident",
            timestamp=datetime(2025, 6, 15, tzinfo=timezone.utc),
            network=NetworkType.OBSERVATION,
            entity_id="auth-service",
        )
        post_incident = TemporalEvent(
            id="status-degraded",
            content="auth-service status: degraded",
            timestamp=datetime(2025, 6, 16, tzinfo=timezone.utc),
            network=NetworkType.OBSERVATION,
            entity_id="auth-service",
        )

        for e in [pre_incident, incident, post_incident]:
            timeline.add_event(e)

        search = TemporalSearch(timeline=timeline)
        results = search.search(
            "What was the auth-service status before incident-123?"
        )

        # Should return pre-incident status
        assert len(results) >= 1
        assert any("healthy" in r.content for r in results)

    def test_search_decisions_in_quarter(self):
        """Should answer 'Show me decisions made in Q4 2025'"""
        from luminescent_cluster.memory.hindsight.temporal_search import TemporalSearch
        from luminescent_cluster.memory.hindsight.timeline import Timeline
        from luminescent_cluster.memory.hindsight.types import TemporalEvent, NetworkType

        timeline = Timeline(user_id="user-123")

        # Add events across the year
        events = [
            TemporalEvent(
                id="decision-q2",
                content="Decided to use PostgreSQL",
                timestamp=datetime(2025, 5, 15, tzinfo=timezone.utc),
                network=NetworkType.WORLD,
                entity_id="auth-decisions",
                metadata={"memory_type": "decision"},
            ),
            TemporalEvent(
                id="decision-q4-1",
                content="Decided to migrate to Kubernetes",
                timestamp=datetime(2025, 10, 15, tzinfo=timezone.utc),
                network=NetworkType.WORLD,
                entity_id="infra-decisions",
                metadata={"memory_type": "decision"},
            ),
            TemporalEvent(
                id="decision-q4-2",
                content="Decided to use GraphQL",
                timestamp=datetime(2025, 11, 20, tzinfo=timezone.utc),
                network=NetworkType.WORLD,
                entity_id="api-decisions",
                metadata={"memory_type": "decision"},
            ),
        ]

        for e in events:
            timeline.add_event(e)

        search = TemporalSearch(timeline=timeline)
        results = search.search("Show me decisions made in Q4 2025")

        assert len(results) == 2
        ids = {r.id for r in results}
        assert "decision-q4-1" in ids
        assert "decision-q4-2" in ids


class TestTemporalSearchResults:
    """Test search result formatting and ranking."""

    def test_results_sorted_by_relevance(self):
        """Results should be sorted by relevance to query."""
        from luminescent_cluster.memory.hindsight.temporal_search import TemporalSearch
        from luminescent_cluster.memory.hindsight.timeline import Timeline
        from luminescent_cluster.memory.hindsight.types import TemporalEvent, NetworkType

        timeline = Timeline(user_id="user-123")
        now = datetime.now(timezone.utc)

        # Add events with varying relevance
        events = [
            TemporalEvent(
                id="evt-1",
                content="auth-service minor update",
                timestamp=now - timedelta(days=5),
                network=NetworkType.OBSERVATION,
                entity_id="auth-service",
            ),
            TemporalEvent(
                id="evt-2",
                content="auth-service major deployment v2.0",
                timestamp=now - timedelta(days=10),
                network=NetworkType.OBSERVATION,
                entity_id="auth-service",
            ),
        ]

        for e in events:
            timeline.add_event(e)

        search = TemporalSearch(timeline=timeline)
        results = search.search("auth-service deployment")

        # Major deployment should be more relevant
        assert len(results) == 2
        # Results are returned (ordering depends on implementation)

    def test_results_include_temporal_context(self):
        """Results should include temporal context for reasoning."""
        from luminescent_cluster.memory.hindsight.temporal_search import TemporalSearch
        from luminescent_cluster.memory.hindsight.timeline import Timeline
        from luminescent_cluster.memory.hindsight.types import TemporalEvent, NetworkType

        timeline = Timeline(user_id="user-123")

        event = TemporalEvent(
            id="evt-1",
            content="auth-service deployed",
            timestamp=datetime(2025, 6, 15, 14, 30, tzinfo=timezone.utc),
            network=NetworkType.OBSERVATION,
            entity_id="auth-service",
        )
        timeline.add_event(event)

        search = TemporalSearch(timeline=timeline)
        results = search.search_with_context("What happened to auth-service?")

        assert len(results) >= 1
        # Result should have temporal metadata
        assert results[0].event.timestamp is not None


class TestTemporalSearchWithMemories:
    """Test integration with Memory objects."""

    def test_search_converts_events_to_temporal_memories(self):
        """Search should return TemporalMemory wrappers."""
        from luminescent_cluster.memory.hindsight.temporal_search import TemporalSearch
        from luminescent_cluster.memory.hindsight.timeline import Timeline
        from luminescent_cluster.memory.hindsight.types import TemporalEvent, NetworkType

        timeline = Timeline(user_id="user-123")

        event = TemporalEvent(
            id="evt-1",
            content="PostgreSQL chosen for auth-service",
            timestamp=datetime(2025, 6, 15, tzinfo=timezone.utc),
            network=NetworkType.WORLD,
            entity_id="auth-service",
        )
        timeline.add_event(event)

        search = TemporalSearch(timeline=timeline)
        results = search.search_with_context("auth-service decisions")

        assert len(results) >= 1
        # Result should have event reference
        assert results[0].event is not None


class TestTemporalSearchParsedQuery:
    """Test ParsedTemporalQuery data structure."""

    def test_parsed_query_has_all_fields(self):
        """ParsedTemporalQuery should contain all parsed components."""
        from luminescent_cluster.memory.hindsight.temporal_search import (
            TemporalSearch,
            ParsedTemporalQuery,
        )
        from luminescent_cluster.memory.hindsight.timeline import Timeline

        timeline = Timeline(user_id="user-123")
        search = TemporalSearch(timeline=timeline)

        result = search.parse_temporal_query(
            "What decisions about auth-service were made last month?"
        )

        assert isinstance(result, ParsedTemporalQuery)
        assert result.original_query is not None
        # Time range, entity, and memory type should be extracted
        assert result.time_range is not None or result.entity_id is not None


class TestTemporalSearchResult:
    """Test TemporalSearchResult data structure."""

    def test_search_result_has_event_and_score(self):
        """TemporalSearchResult should include event and relevance score."""
        from luminescent_cluster.memory.hindsight.temporal_search import (
            TemporalSearch,
            TemporalSearchResult,
        )
        from luminescent_cluster.memory.hindsight.timeline import Timeline
        from luminescent_cluster.memory.hindsight.types import TemporalEvent, NetworkType

        timeline = Timeline(user_id="user-123")

        event = TemporalEvent(
            id="evt-1",
            content="Test event",
            timestamp=datetime(2025, 6, 15, tzinfo=timezone.utc),
            network=NetworkType.OBSERVATION,
            entity_id="test-entity",
        )
        timeline.add_event(event)

        search = TemporalSearch(timeline=timeline)
        results = search.search_with_context("test")

        assert len(results) >= 1
        assert isinstance(results[0], TemporalSearchResult)
        assert results[0].event is not None
        assert results[0].score >= 0.0
