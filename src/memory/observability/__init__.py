# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Memory observability for ADR-003.

This module provides OpenTelemetry-compatible metrics and tracing
for memory operations.

Related GitHub Issues:
- #82: Memory Observability

ADR Reference: ADR-003 Memory Architecture, Phase 0 (Foundations)
"""

from src.memory.observability.metrics import (
    METRIC_PREFIX,
    LatencyStats,
    MemoryMetrics,
)
from src.memory.observability.tracing import (
    TRACER_NAME,
    MemoryTracer,
    SpanContext,
    SpanNames,
)

__all__ = [
    # Metrics
    "METRIC_PREFIX",
    "MemoryMetrics",
    "LatencyStats",
    # Tracing
    "TRACER_NAME",
    "MemoryTracer",
    "SpanContext",
    "SpanNames",
]
