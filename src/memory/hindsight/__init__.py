"""Hindsight temporal memory module (ADR-003 Phase 4.2).

Implements four-network temporal memory architecture:
- World Network: Entity state over time
- Bank Network: Relationship evolution (agent actions)
- Opinion Network: Belief changes with confidence
- Observation Network: Event timeline (neutral summaries)

Target queries:
- "What changed last month?"
- "What was the auth-service status before incident-123?"
- "Show me decisions made in Q4 2025"
"""

from src.memory.hindsight.types import (
    NetworkType,
    TimeRange,
    TemporalEvent,
    TemporalMemory,
    StateChange,
)
from src.memory.hindsight.timeline import Timeline
from src.memory.hindsight.temporal_search import (
    TemporalSearch,
    ParsedTemporalQuery,
    TemporalSearchResult,
)

__all__ = [
    # Types
    "NetworkType",
    "TimeRange",
    "TemporalEvent",
    "TemporalMemory",
    "StateChange",
    # Timeline
    "Timeline",
    # Search
    "TemporalSearch",
    "ParsedTemporalQuery",
    "TemporalSearchResult",
]
