"""Temporal search for Hindsight (ADR-003 Phase 4.2).

TemporalSearch enables time-filtered retrieval for queries like:
- "What changed last month?"
- "What was the auth-service status before incident-123?"
- "Show me decisions made in Q4 2025"

Design:
- Parses natural language temporal references
- Integrates with Timeline for event retrieval
- Returns scored results with temporal context
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Protocol

from src.memory.hindsight.timeline import Timeline
from src.memory.hindsight.types import NetworkType, TemporalEvent, TimeRange


class MemoryProvider(Protocol):
    """Protocol for memory provider integration."""

    def retrieve(
        self, user_id: str, query: str, limit: int = 10
    ) -> list[Any]: ...


@dataclass
class ParsedTemporalQuery:
    """Result of parsing a temporal query.

    Contains all extracted temporal and semantic components:
    - time_range: When to search
    - entity_id: What entity to filter by
    - memory_type: What type of memory (decision, fact, etc.)
    - reference_event_id: Event to use as temporal anchor
    - original_query: The original query text
    """

    original_query: str
    time_range: Optional[TimeRange] = None
    entity_id: Optional[str] = None
    memory_type: Optional[str] = None
    reference_event_id: Optional[str] = None
    network: Optional[NetworkType] = None
    keywords: list[str] = field(default_factory=list)


@dataclass
class TemporalSearchResult:
    """A search result with temporal context.

    Contains:
    - event: The matching TemporalEvent
    - score: Relevance score (0.0-1.0)
    - temporal_context: Additional temporal metadata
    """

    event: TemporalEvent
    score: float = 1.0
    temporal_context: dict[str, Any] = field(default_factory=dict)


class TemporalSearch:
    """Time-filtered retrieval for Hindsight.

    Parses natural language temporal queries and retrieves
    relevant events from the timeline.
    """

    # Patterns for temporal reference parsing
    LAST_MONTH_PATTERN = re.compile(r"\blast\s+month\b", re.IGNORECASE)
    LAST_WEEK_PATTERN = re.compile(r"\blast\s+week\b", re.IGNORECASE)
    LAST_N_DAYS_PATTERN = re.compile(r"\blast\s+(\d+)\s+days?\b", re.IGNORECASE)
    QUARTER_PATTERN = re.compile(r"\bQ([1-4])\s+(\d{4})\b", re.IGNORECASE)
    BEFORE_EVENT_PATTERN = re.compile(
        r"\bbefore\s+(\w+-\d+|\w+#\d+)\b", re.IGNORECASE
    )

    # Entity patterns (service names, common patterns)
    ENTITY_PATTERN = re.compile(
        r"\b(\w+-(?:service|api|db|cache|queue|gateway))\b", re.IGNORECASE
    )

    # Memory type patterns
    MEMORY_TYPE_PATTERNS = {
        "decision": re.compile(r"\bdecisions?\b", re.IGNORECASE),
        "fact": re.compile(r"\bfacts?\b", re.IGNORECASE),
        "preference": re.compile(r"\bpreferences?\b", re.IGNORECASE),
    }

    def __init__(
        self,
        timeline: Timeline,
        memory_provider: Optional[MemoryProvider] = None,
    ) -> None:
        """Initialize temporal search.

        Args:
            timeline: The Timeline to search
            memory_provider: Optional MemoryProvider for hybrid search
        """
        self.timeline = timeline
        self.memory_provider = memory_provider

    def parse_temporal_query(self, query: str) -> ParsedTemporalQuery:
        """Parse a natural language temporal query.

        Extracts:
        - Time range (last month, Q4 2025, before event-123)
        - Entity ID (auth-service, payment-api)
        - Memory type (decision, fact, preference)
        - Reference events (before incident-123)

        Args:
            query: Natural language query

        Returns:
            ParsedTemporalQuery with extracted components
        """
        parsed = ParsedTemporalQuery(original_query=query)
        now = datetime.now(timezone.utc)

        # Parse "last month"
        if self.LAST_MONTH_PATTERN.search(query):
            parsed.time_range = TimeRange.last_n_days(30)

        # Parse "last week"
        elif self.LAST_WEEK_PATTERN.search(query):
            parsed.time_range = TimeRange.last_n_days(7)

        # Parse "last N days"
        elif match := self.LAST_N_DAYS_PATTERN.search(query):
            days = int(match.group(1))
            parsed.time_range = TimeRange.last_n_days(days)

        # Parse "Q4 2025"
        elif match := self.QUARTER_PATTERN.search(query):
            quarter = int(match.group(1))
            year = int(match.group(2))
            parsed.time_range = TimeRange.quarter(year, quarter)

        # Parse "before incident-123"
        if match := self.BEFORE_EVENT_PATTERN.search(query):
            ref_id = match.group(1)
            parsed.reference_event_id = ref_id

            # Look up the reference event
            ref_event = self.timeline.get_event(ref_id)
            if ref_event:
                # Set time range to before the reference event
                parsed.time_range = TimeRange(
                    start=datetime(2000, 1, 1, tzinfo=timezone.utc),
                    end=ref_event.timestamp,
                )

        # Extract entity ID
        if match := self.ENTITY_PATTERN.search(query):
            parsed.entity_id = match.group(1)

        # Extract memory type
        for mem_type, pattern in self.MEMORY_TYPE_PATTERNS.items():
            if pattern.search(query):
                parsed.memory_type = mem_type
                break

        # Extract keywords (non-stopwords, non-temporal)
        words = query.lower().split()
        stopwords = {
            "what", "when", "where", "how", "the", "a", "an", "in", "on",
            "at", "to", "for", "of", "was", "were", "is", "are", "last",
            "month", "week", "days", "before", "after", "show", "me",
            "made", "changed", "happened", "status",
        }
        parsed.keywords = [w for w in words if w not in stopwords and len(w) > 2]

        return parsed

    def search(self, query: str, limit: int = 10) -> list[TemporalEvent]:
        """Search for events matching a temporal query.

        Args:
            query: Natural language query
            limit: Maximum number of results

        Returns:
            List of matching TemporalEvents
        """
        parsed = self.parse_temporal_query(query)
        return self._execute_search(parsed, limit)

    def search_with_context(
        self, query: str, limit: int = 10
    ) -> list[TemporalSearchResult]:
        """Search with full temporal context.

        Args:
            query: Natural language query
            limit: Maximum number of results

        Returns:
            List of TemporalSearchResult with scores and context
        """
        parsed = self.parse_temporal_query(query)
        events = self._execute_search(parsed, limit)

        results = []
        for i, event in enumerate(events):
            score = self._calculate_relevance(event, parsed)
            context = self._build_temporal_context(event, parsed)
            results.append(
                TemporalSearchResult(
                    event=event,
                    score=score,
                    temporal_context=context,
                )
            )

        # Sort by score descending
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    def _execute_search(
        self, parsed: ParsedTemporalQuery, limit: int
    ) -> list[TemporalEvent]:
        """Execute the parsed query against the timeline.

        Args:
            parsed: Parsed query
            limit: Maximum results

        Returns:
            List of matching events
        """
        # Build query parameters
        results = self.timeline.query(
            time_range=parsed.time_range,
            entity_id=parsed.entity_id,
            network=parsed.network,
        )

        # Filter by memory type if specified
        if parsed.memory_type:
            results = [
                e
                for e in results
                if e.metadata.get("memory_type") == parsed.memory_type
            ]

        # Filter by keywords if no other filters matched
        if parsed.keywords and not results:
            all_events = list(self.timeline._events.values())
            results = [
                e
                for e in all_events
                if any(kw in e.content.lower() for kw in parsed.keywords)
            ]

            # Apply time range if specified
            if parsed.time_range:
                results = [
                    e for e in results if parsed.time_range.contains(e.timestamp)
                ]

        return results[:limit]

    def _calculate_relevance(
        self, event: TemporalEvent, parsed: ParsedTemporalQuery
    ) -> float:
        """Calculate relevance score for an event.

        Args:
            event: The event to score
            parsed: The parsed query

        Returns:
            Relevance score (0.0-1.0)
        """
        score = 0.5  # Base score

        # Boost for entity match
        if parsed.entity_id and event.entity_id == parsed.entity_id:
            score += 0.2

        # Boost for memory type match
        if (
            parsed.memory_type
            and event.metadata.get("memory_type") == parsed.memory_type
        ):
            score += 0.2

        # Boost for keyword matches
        if parsed.keywords:
            content_lower = event.content.lower()
            matches = sum(1 for kw in parsed.keywords if kw in content_lower)
            score += min(0.1 * matches, 0.3)

        # Boost for recency (newer events slightly preferred)
        if parsed.time_range:
            range_duration = (
                parsed.time_range.end - parsed.time_range.start
            ).total_seconds()
            if range_duration > 0:
                event_offset = (
                    event.timestamp - parsed.time_range.start
                ).total_seconds()
                recency = event_offset / range_duration
                score += 0.1 * recency

        return min(score, 1.0)

    def _build_temporal_context(
        self, event: TemporalEvent, parsed: ParsedTemporalQuery
    ) -> dict[str, Any]:
        """Build temporal context for a result.

        Args:
            event: The event
            parsed: The parsed query

        Returns:
            Dictionary with temporal context
        """
        context = {
            "timestamp": event.timestamp.isoformat(),
            "network": event.network.value,
            "entity_id": event.entity_id,
        }

        # Add relative time context
        now = datetime.now(timezone.utc)
        delta = now - event.timestamp
        if delta.days == 0:
            context["relative_time"] = "today"
        elif delta.days == 1:
            context["relative_time"] = "yesterday"
        elif delta.days < 7:
            context["relative_time"] = f"{delta.days} days ago"
        elif delta.days < 30:
            context["relative_time"] = f"{delta.days // 7} weeks ago"
        else:
            context["relative_time"] = f"{delta.days // 30} months ago"

        # Add reference context if applicable
        if parsed.reference_event_id:
            ref_event = self.timeline.get_event(parsed.reference_event_id)
            if ref_event:
                context["reference_event"] = ref_event.content
                context["time_before_reference"] = str(
                    ref_event.timestamp - event.timestamp
                )

        return context
