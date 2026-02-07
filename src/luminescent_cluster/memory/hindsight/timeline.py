"""Timeline storage and indexing for Hindsight (ADR-003 Phase 4.2).

Timeline is the core storage component for temporal memory:
- Stores TemporalEvents chronologically
- Indexes by entity, network, and time range
- Supports state reconstruction at any point in time

Design decisions:
- In-memory storage for Phase 4.2 (persistence in Phase 4.3)
- Events are stored in a sorted list by timestamp
- Multiple indexes (by entity, by network) for efficient queries
- State reconstruction uses supersedes chain
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from luminescent_cluster.memory.hindsight.types import NetworkType, TemporalEvent, TimeRange


@dataclass
class Timeline:
    """Timeline storage for temporal events.

    Stores events chronologically with efficient queries by:
    - Time range
    - Entity ID
    - Network type

    Supports state reconstruction at any point in time.
    """

    user_id: str
    entity_filter: Optional[list[str]] = None

    # Internal storage
    _events: dict[str, TemporalEvent] = field(default_factory=dict)
    _events_by_entity: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    _events_by_network: dict[NetworkType, list[str]] = field(
        default_factory=lambda: defaultdict(list)
    )
    _supersedes_index: dict[str, str] = field(default_factory=dict)

    def count(self) -> int:
        """Return the number of events in the timeline."""
        return len(self._events)

    def add_event(self, event: TemporalEvent) -> None:
        """Add an event to the timeline.

        Args:
            event: The TemporalEvent to add
        """
        # Store the event
        self._events[event.id] = event

        # Index by entity
        self._events_by_entity[event.entity_id].append(event.id)

        # Index by network
        self._events_by_network[event.network].append(event.id)

        # Index supersedes relationship
        if event.supersedes:
            self._supersedes_index[event.supersedes] = event.id

    def get_event(self, event_id: str) -> Optional[TemporalEvent]:
        """Get an event by ID.

        Args:
            event_id: The event ID to retrieve

        Returns:
            The event if found, None otherwise
        """
        return self._events.get(event_id)

    def remove_event(self, event_id: str) -> bool:
        """Remove an event from the timeline.

        Args:
            event_id: The event ID to remove

        Returns:
            True if removed, False if not found
        """
        event = self._events.get(event_id)
        if event is None:
            return False

        # Remove from main storage
        del self._events[event_id]

        # Remove from entity index
        if event_id in self._events_by_entity[event.entity_id]:
            self._events_by_entity[event.entity_id].remove(event_id)

        # Remove from network index
        if event_id in self._events_by_network[event.network]:
            self._events_by_network[event.network].remove(event_id)

        # Remove from supersedes index
        if event.supersedes and event.supersedes in self._supersedes_index:
            if self._supersedes_index[event.supersedes] == event_id:
                del self._supersedes_index[event.supersedes]

        return True

    def query_by_time(self, time_range: TimeRange) -> list[TemporalEvent]:
        """Query events within a time range.

        Args:
            time_range: The TimeRange to filter by

        Returns:
            List of events within the time range, sorted chronologically
        """
        results = [event for event in self._events.values() if time_range.contains(event.timestamp)]

        # Sort by timestamp
        results.sort(key=lambda e: e.timestamp)
        return results

    def query_by_entity(self, entity_id: str) -> list[TemporalEvent]:
        """Query events for a specific entity.

        Args:
            entity_id: The entity ID to filter by

        Returns:
            List of events for the entity, sorted chronologically
        """
        event_ids = self._events_by_entity.get(entity_id, [])
        results = [self._events[eid] for eid in event_ids if eid in self._events]
        results.sort(key=lambda e: e.timestamp)
        return results

    def query_by_entities(self, entity_ids: list[str]) -> list[TemporalEvent]:
        """Query events for multiple entities.

        Args:
            entity_ids: List of entity IDs to filter by

        Returns:
            List of events for the entities, sorted chronologically
        """
        results = []
        for entity_id in entity_ids:
            results.extend(self.query_by_entity(entity_id))

        # Deduplicate and sort
        seen = set()
        unique_results = []
        for event in results:
            if event.id not in seen:
                seen.add(event.id)
                unique_results.append(event)

        unique_results.sort(key=lambda e: e.timestamp)
        return unique_results

    def query_by_network(self, network: NetworkType) -> list[TemporalEvent]:
        """Query events by network type.

        Args:
            network: The NetworkType to filter by

        Returns:
            List of events for the network, sorted chronologically
        """
        event_ids = self._events_by_network.get(network, [])
        results = [self._events[eid] for eid in event_ids if eid in self._events]
        results.sort(key=lambda e: e.timestamp)
        return results

    def query(
        self,
        time_range: Optional[TimeRange] = None,
        entity_id: Optional[str] = None,
        network: Optional[NetworkType] = None,
    ) -> list[TemporalEvent]:
        """Combined query with multiple filters.

        Args:
            time_range: Optional time range filter
            entity_id: Optional entity ID filter
            network: Optional network type filter

        Returns:
            List of events matching all filters, sorted chronologically
        """
        # Start with all events
        results = list(self._events.values())

        # Apply time range filter
        if time_range:
            results = [e for e in results if time_range.contains(e.timestamp)]

        # Apply entity filter
        if entity_id:
            results = [e for e in results if e.entity_id == entity_id]

        # Apply network filter
        if network:
            results = [e for e in results if e.network == network]

        # Sort by timestamp
        results.sort(key=lambda e: e.timestamp)
        return results

    def get_entity_state_at(
        self,
        entity_id: str,
        at_time: datetime,
    ) -> Optional[TemporalEvent]:
        """Get the state of an entity at a specific point in time.

        This finds the most recent event for the entity that was valid
        at the given time, following the supersedes chain.

        Args:
            entity_id: The entity to get state for
            at_time: The point in time to query

        Returns:
            The event representing the state, or None if no state exists
        """
        # Get all events for this entity that occurred before at_time
        entity_events = self.query_by_entity(entity_id)
        candidates = [
            e
            for e in entity_events
            if e.timestamp <= at_time and (e.valid_from is None or e.valid_from <= at_time)
        ]

        if not candidates:
            return None

        # Find the most recent event that wasn't superseded before at_time
        # Sort by timestamp descending
        candidates.sort(key=lambda e: e.timestamp, reverse=True)

        for candidate in candidates:
            # Check if this event was superseded by something before at_time
            superseding_id = self._supersedes_index.get(candidate.id)
            if superseding_id:
                superseding = self._events.get(superseding_id)
                if superseding and superseding.timestamp <= at_time:
                    # This event was superseded, skip it
                    continue

            # Check valid_until
            if candidate.valid_until and candidate.valid_until < at_time:
                continue

            return candidate

        return None

    def to_dict(self) -> dict[str, Any]:
        """Serialize timeline to dictionary.

        Returns:
            Dictionary representation of the timeline
        """
        return {
            "user_id": self.user_id,
            "entity_filter": self.entity_filter,
            "events": [event.to_dict() for event in self._events.values()],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Timeline":
        """Deserialize timeline from dictionary.

        Args:
            data: Dictionary representation

        Returns:
            Timeline instance
        """
        timeline = cls(
            user_id=data["user_id"],
            entity_filter=data.get("entity_filter"),
        )

        for event_data in data.get("events", []):
            event = TemporalEvent.from_dict(event_data)
            timeline.add_event(event)

        return timeline
