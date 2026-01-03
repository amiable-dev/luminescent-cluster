# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Memory metrics for observability.

Provides OpenTelemetry-compatible metrics for memory operations
including counters, latency histograms, and operation tracking.

Related GitHub Issues:
- #82: Memory Observability

ADR Reference: ADR-003 Memory Architecture, Phase 0 (Foundations)
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

# Metric name prefix for all memory metrics
METRIC_PREFIX: str = "memory"


@dataclass
class LatencyStats:
    """Statistics for latency measurements.

    Attributes:
        count: Number of measurements.
        total_ms: Total latency in milliseconds.
        min_ms: Minimum latency in milliseconds.
        max_ms: Maximum latency in milliseconds.
    """

    count: int = 0
    total_ms: float = 0.0
    min_ms: float = float("inf")
    max_ms: float = 0.0

    def record(self, latency_ms: float) -> None:
        """Record a latency measurement."""
        self.count += 1
        self.total_ms += latency_ms
        self.min_ms = min(self.min_ms, latency_ms)
        self.max_ms = max(self.max_ms, latency_ms)

    @property
    def avg_ms(self) -> float:
        """Average latency in milliseconds."""
        if self.count == 0:
            return 0.0
        return self.total_ms / self.count


class MemoryMetrics:
    """Metrics collector for memory operations.

    Provides methods for recording metrics about memory operations
    in an OpenTelemetry-compatible format.

    Example:
        >>> metrics = MemoryMetrics()
        >>> metrics.record_store(memory_type="fact", user_id="user-123")
        >>> metrics.record_latency("store", 45.2)
        >>> stats = metrics.get_stats()
    """

    def __init__(self):
        """Initialize the metrics collector."""
        self._counters: dict[str, int] = defaultdict(int)
        self._latencies: dict[str, LatencyStats] = defaultdict(LatencyStats)
        self._labels: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    def record_store(
        self,
        memory_type: str = "unknown",
        user_id: Optional[str] = None,
        success: bool = True,
    ) -> None:
        """Record a memory store operation.

        Args:
            memory_type: Type of memory stored (fact, preference, decision).
            user_id: User ID for the operation.
            success: Whether the operation succeeded.
        """
        self._counters["store_total"] += 1
        if success:
            self._counters["store_success"] += 1
        else:
            self._counters["store_error"] += 1
        self._labels["store_by_type"][memory_type] += 1

    def record_retrieve(
        self,
        user_id: Optional[str] = None,
        result_count: int = 0,
        success: bool = True,
    ) -> None:
        """Record a memory retrieve operation.

        Args:
            user_id: User ID for the operation.
            result_count: Number of memories retrieved.
            success: Whether the operation succeeded.
        """
        self._counters["retrieve_total"] += 1
        if success:
            self._counters["retrieve_success"] += 1
        else:
            self._counters["retrieve_error"] += 1
        self._counters["retrieve_results"] += result_count

    def record_latency(self, operation: str, latency_ms: float) -> None:
        """Record latency for an operation.

        Args:
            operation: Name of the operation (store, retrieve, search, delete).
            latency_ms: Latency in milliseconds.
        """
        self._latencies[operation].record(latency_ms)

    def increment_counter(
        self,
        name: str,
        value: int = 1,
        labels: Optional[dict[str, str]] = None,
    ) -> None:
        """Increment a counter metric.

        Args:
            name: Name of the counter.
            value: Amount to increment by.
            labels: Optional labels for the metric.
        """
        self._counters[name] += value
        if labels:
            for label_key, label_value in labels.items():
                self._labels[f"{name}_{label_key}"][label_value] += value

    def get_stats(self) -> dict[str, Any]:
        """Get all collected statistics.

        Returns:
            Dictionary containing all metrics and statistics.
        """
        latency_stats = {}
        for op, stats in self._latencies.items():
            latency_stats[op] = {
                "count": stats.count,
                "avg_ms": stats.avg_ms,
                "min_ms": stats.min_ms if stats.count > 0 else 0.0,
                "max_ms": stats.max_ms,
            }

        return {
            "counters": dict(self._counters),
            "latencies": latency_stats,
            "labels": {k: dict(v) for k, v in self._labels.items()},
        }

    def reset(self) -> None:
        """Reset all metrics (for testing)."""
        self._counters.clear()
        self._latencies.clear()
        self._labels.clear()
