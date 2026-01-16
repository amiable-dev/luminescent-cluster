# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Memory observability for ADR-003.

This module provides OpenTelemetry-compatible metrics and tracing
for memory operations, plus production monitoring for scale milestones
and graph query performance.

Related GitHub Issues:
- #82: Memory Observability
- #133: HNSW Scale Monitoring
- #134: Graph Query Monitoring

ADR Reference: ADR-003 Memory Architecture, Phase 0 (Foundations), Phase D
"""

from src.memory.observability.graph_metrics import (
    GraphMetricsCollector,
    GraphQueryMetrics,
    GraphSizeSnapshot,
    HopLatency,
    QueryMeasurementContext,
)
from src.memory.observability.metrics import (
    METRIC_PREFIX,
    LatencyStats,
    MemoryMetrics,
)
from src.memory.observability.scale_milestones import (
    MilestoneCheckResult,
    ScaleMilestone,
    ScaleMilestoneTracker,
    STANDARD_MILESTONES,
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
    # Scale Milestones (Phase D)
    "ScaleMilestone",
    "STANDARD_MILESTONES",
    "MilestoneCheckResult",
    "ScaleMilestoneTracker",
    # Graph Metrics (Phase D)
    "GraphMetricsCollector",
    "GraphQueryMetrics",
    "GraphSizeSnapshot",
    "HopLatency",
    "QueryMeasurementContext",
]
