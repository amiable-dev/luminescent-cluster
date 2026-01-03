# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Memory tracing for observability.

Provides OpenTelemetry-compatible tracing for memory operations
with span management and attribute recording.

Related GitHub Issues:
- #82: Memory Observability

ADR Reference: ADR-003 Memory Architecture, Phase 0 (Foundations)
"""

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Generator, Optional

# Tracer name for memory operations
TRACER_NAME: str = "luminescent.memory"


class SpanNames:
    """Standard span names for memory operations.

    Use these constants to ensure consistent naming across
    all memory operation traces.
    """

    STORE: str = "memory.store"
    RETRIEVE: str = "memory.retrieve"
    SEARCH: str = "memory.search"
    DELETE: str = "memory.delete"
    GET_BY_ID: str = "memory.get_by_id"
    EXTRACTION: str = "memory.extraction"
    RANKING: str = "memory.ranking"


@dataclass
class SpanContext:
    """Context for an active span.

    Attributes:
        name: Name of the span.
        start_time: When the span started (unix timestamp).
        attributes: Span attributes.
        events: Recorded events.
        status: Span status ("ok", "error").
        error: Error message if status is "error".
    """

    name: str
    start_time: float = field(default_factory=time.time)
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    status: str = "ok"
    error: Optional[str] = None
    end_time: Optional[float] = None

    @property
    def duration_ms(self) -> float:
        """Duration of the span in milliseconds."""
        end = self.end_time or time.time()
        return (end - self.start_time) * 1000


class MemoryTracer:
    """Tracer for memory operations.

    Provides tracing capabilities for memory operations in an
    OpenTelemetry-compatible format. When no OpenTelemetry tracer
    is configured, operations are tracked in-memory for debugging.

    Example:
        >>> tracer = MemoryTracer()
        >>> with tracer.trace_operation("memory.store") as span:
        ...     span.set_attribute("memory_type", "fact")
        ...     # Do the store operation
    """

    def __init__(self, tracer_name: str = TRACER_NAME):
        """Initialize the memory tracer.

        Args:
            tracer_name: Name for the tracer (default: luminescent.memory).
        """
        self.tracer_name = tracer_name
        self._current_span: Optional[SpanContext] = None
        self._spans: list[SpanContext] = []

    def start_span(
        self,
        name: str,
        attributes: Optional[dict[str, Any]] = None,
    ) -> SpanContext:
        """Start a new span.

        Args:
            name: Name of the span.
            attributes: Initial attributes for the span.

        Returns:
            The created SpanContext.
        """
        span = SpanContext(
            name=name,
            attributes=attributes or {},
        )
        self._current_span = span
        return span

    def end_span(self, span: SpanContext) -> None:
        """End a span and record it.

        Args:
            span: The span to end.
        """
        span.end_time = time.time()
        self._spans.append(span)
        if self._current_span == span:
            self._current_span = None

    @contextmanager
    def trace_operation(
        self,
        name: str,
        attributes: Optional[dict[str, Any]] = None,
    ) -> Generator[SpanContext, None, None]:
        """Context manager for tracing an operation.

        Args:
            name: Name of the span.
            attributes: Initial attributes for the span.

        Yields:
            The SpanContext for the operation.

        Example:
            >>> with tracer.trace_operation("memory.store") as span:
            ...     span.attributes["memory_type"] = "fact"
        """
        span = self.start_span(name, attributes)
        try:
            yield span
            span.status = "ok"
        except Exception as e:
            span.status = "error"
            span.error = str(e)
            raise
        finally:
            self.end_span(span)

    def add_event(
        self,
        name: str,
        attributes: Optional[dict[str, Any]] = None,
    ) -> None:
        """Add an event to the current span.

        Args:
            name: Name of the event.
            attributes: Event attributes.
        """
        if self._current_span:
            self._current_span.events.append(
                {
                    "name": name,
                    "timestamp": time.time(),
                    "attributes": attributes or {},
                }
            )

    def set_attribute(self, key: str, value: Any) -> None:
        """Set an attribute on the current span.

        Args:
            key: Attribute key.
            value: Attribute value.
        """
        if self._current_span:
            self._current_span.attributes[key] = value

    def get_spans(self) -> list[SpanContext]:
        """Get all recorded spans.

        Returns:
            List of recorded SpanContext objects.
        """
        return self._spans.copy()

    def reset(self) -> None:
        """Reset all recorded spans (for testing)."""
        self._spans.clear()
        self._current_span = None
