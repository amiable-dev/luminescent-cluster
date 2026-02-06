# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Graph query monitoring for Knowledge Graph (ADR-003 Phase D).

Tracks performance metrics for graph queries:
- Latency per hop depth (direct match, neighbor, predecessor)
- Node and edge counts over time
- Query timing statistics

Used to identify performance degradation and optimize graph operations.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class HopLatency:
    """Latency for a single hop in graph traversal.

    Attributes:
        hop_type: Type of hop (direct, neighbor, predecessor).
        latency_ms: Time taken in milliseconds.
        node_count: Number of nodes accessed.
    """

    hop_type: str
    latency_ms: float
    node_count: int


@dataclass
class GraphQueryMetrics:
    """Metrics for a single graph query.

    Attributes:
        query: The search query.
        user_id: User ID for the query.
        total_latency_ms: Total query time in ms.
        hop_latencies: Latency breakdown by hop type.
        matching_nodes: Number of nodes matching query.
        results_count: Number of results returned.
        timestamp: When the query was executed.
    """

    query: str
    user_id: str
    total_latency_ms: float
    hop_latencies: list[HopLatency]
    matching_nodes: int
    results_count: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "query": self.query,
            "user_id": self.user_id,
            "total_latency_ms": self.total_latency_ms,
            "hop_latencies": [
                {
                    "hop_type": h.hop_type,
                    "latency_ms": h.latency_ms,
                    "node_count": h.node_count,
                }
                for h in self.hop_latencies
            ],
            "matching_nodes": self.matching_nodes,
            "results_count": self.results_count,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class GraphSizeSnapshot:
    """Snapshot of graph size at a point in time.

    Attributes:
        user_id: Owner of the graph.
        node_count: Number of nodes.
        edge_count: Number of edges.
        timestamp: When snapshot was taken.
    """

    user_id: str
    node_count: int
    edge_count: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "user_id": self.user_id,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "timestamp": self.timestamp.isoformat(),
        }


class GraphMetricsCollector:
    """Collector for graph query metrics.

    Tracks query latencies, hop timing, and graph sizes over time.
    Provides summary statistics for performance monitoring.

    Example:
        >>> collector = GraphMetricsCollector()
        >>> with collector.measure_query("user-123", "auth-service") as ctx:
        ...     # perform query
        ...     ctx.add_hop("direct", 5.2, 2)
        ...     ctx.add_hop("neighbor", 12.1, 8)
        >>> stats = collector.get_stats("user-123")

    Attributes:
        queries: List of query metrics.
        size_snapshots: List of graph size snapshots.
    """

    def __init__(self, max_queries: int = 1000, max_snapshots: int = 100):
        """Initialize the collector.

        Args:
            max_queries: Maximum number of queries to retain.
            max_snapshots: Maximum number of size snapshots to retain.
        """
        self.max_queries = max_queries
        self.max_snapshots = max_snapshots
        self._queries: list[GraphQueryMetrics] = []
        self._size_snapshots: list[GraphSizeSnapshot] = []
        self._user_queries: dict[str, list[GraphQueryMetrics]] = {}

    def record_query(self, metrics: GraphQueryMetrics) -> None:
        """Record query metrics.

        Args:
            metrics: The query metrics to record.
        """
        self._queries.append(metrics)

        # Track per user
        if metrics.user_id not in self._user_queries:
            self._user_queries[metrics.user_id] = []
        self._user_queries[metrics.user_id].append(metrics)

        # Trim if necessary
        if len(self._queries) > self.max_queries:
            removed = self._queries.pop(0)
            # Also remove from user queries
            if removed.user_id in self._user_queries:
                user_list = self._user_queries[removed.user_id]
                if user_list and user_list[0] == removed:
                    user_list.pop(0)

        logger.debug(
            f"Graph query: user={metrics.user_id} query={metrics.query[:50]} "
            f"latency={metrics.total_latency_ms:.2f}ms results={metrics.results_count}"
        )

    def record_size_snapshot(self, snapshot: GraphSizeSnapshot) -> None:
        """Record a graph size snapshot.

        Args:
            snapshot: The size snapshot to record.
        """
        self._size_snapshots.append(snapshot)

        if len(self._size_snapshots) > self.max_snapshots:
            self._size_snapshots.pop(0)

        logger.debug(
            f"Graph size: user={snapshot.user_id} "
            f"nodes={snapshot.node_count} edges={snapshot.edge_count}"
        )

    def measure_query(
        self,
        user_id: str,
        query: str,
    ) -> "QueryMeasurementContext":
        """Create a context manager for measuring a query.

        Args:
            user_id: User ID for the query.
            query: The search query.

        Returns:
            Context manager for measuring the query.
        """
        return QueryMeasurementContext(self, user_id, query)

    def get_query_history(
        self,
        user_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[GraphQueryMetrics]:
        """Get recent query history.

        Args:
            user_id: Optional filter by user.
            limit: Maximum results to return.

        Returns:
            List of recent query metrics.
        """
        if user_id:
            queries = self._user_queries.get(user_id, [])
        else:
            queries = self._queries

        return queries[-limit:]

    def get_size_history(
        self,
        user_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[GraphSizeSnapshot]:
        """Get graph size history.

        Args:
            user_id: Optional filter by user.
            limit: Maximum results to return.

        Returns:
            List of size snapshots.
        """
        snapshots = self._size_snapshots
        if user_id:
            snapshots = [s for s in snapshots if s.user_id == user_id]

        return snapshots[-limit:]

    def get_stats(self, user_id: Optional[str] = None) -> dict[str, Any]:
        """Get summary statistics.

        Args:
            user_id: Optional filter by user.

        Returns:
            Dictionary with statistics.
        """
        queries = self.get_query_history(user_id, limit=1000)
        if not queries:
            return {
                "query_count": 0,
                "avg_latency_ms": 0.0,
                "p50_latency_ms": 0.0,
                "p95_latency_ms": 0.0,
                "p99_latency_ms": 0.0,
                "avg_results": 0.0,
                "hop_stats": {},
            }

        latencies = [q.total_latency_ms for q in queries]
        latencies.sort()

        # Calculate hop-level statistics
        hop_stats: dict[str, dict[str, float]] = {}
        for query in queries:
            for hop in query.hop_latencies:
                if hop.hop_type not in hop_stats:
                    hop_stats[hop.hop_type] = {
                        "count": 0,
                        "total_latency_ms": 0.0,
                        "total_nodes": 0,
                    }
                hop_stats[hop.hop_type]["count"] += 1
                hop_stats[hop.hop_type]["total_latency_ms"] += hop.latency_ms
                hop_stats[hop.hop_type]["total_nodes"] += hop.node_count

        # Calculate averages for hops
        hop_averages = {}
        for hop_type, stats in hop_stats.items():
            hop_averages[hop_type] = {
                "avg_latency_ms": stats["total_latency_ms"] / stats["count"],
                "avg_nodes": stats["total_nodes"] / stats["count"],
                "query_count": int(stats["count"]),
            }

        return {
            "query_count": len(queries),
            "avg_latency_ms": sum(latencies) / len(latencies),
            "p50_latency_ms": self._percentile(latencies, 50),
            "p95_latency_ms": self._percentile(latencies, 95),
            "p99_latency_ms": self._percentile(latencies, 99),
            "avg_results": sum(q.results_count for q in queries) / len(queries),
            "hop_stats": hop_averages,
        }

    def get_latency_by_hop_type(
        self,
        user_id: Optional[str] = None,
    ) -> dict[str, dict[str, float]]:
        """Get latency breakdown by hop type.

        Args:
            user_id: Optional filter by user.

        Returns:
            Dictionary with latency stats per hop type.
        """
        stats = self.get_stats(user_id)
        return stats.get("hop_stats", {})

    def _percentile(self, values: list[float], percentile: float) -> float:
        """Calculate percentile of sorted values.

        Args:
            values: Sorted list of values.
            percentile: Percentile to calculate (0-100).

        Returns:
            The percentile value.
        """
        if not values:
            return 0.0

        k = (len(values) - 1) * percentile / 100
        f = int(k)
        c = f + 1 if f + 1 < len(values) else f

        if f == c:
            return values[f]

        return values[f] * (c - k) + values[c] * (k - f)

    def clear(self, user_id: Optional[str] = None) -> None:
        """Clear collected metrics.

        Args:
            user_id: Optional filter by user. If None, clears all.
        """
        if user_id:
            if user_id in self._user_queries:
                del self._user_queries[user_id]
            self._queries = [q for q in self._queries if q.user_id != user_id]
            self._size_snapshots = [
                s for s in self._size_snapshots if s.user_id != user_id
            ]
        else:
            self._queries.clear()
            self._user_queries.clear()
            self._size_snapshots.clear()


class QueryMeasurementContext:
    """Context manager for measuring query execution.

    Used via GraphMetricsCollector.measure_query().
    """

    def __init__(
        self,
        collector: GraphMetricsCollector,
        user_id: str,
        query: str,
    ):
        """Initialize the context.

        Args:
            collector: The parent collector.
            user_id: User ID for the query.
            query: The search query.
        """
        self._collector = collector
        self._user_id = user_id
        self._query = query
        self._start_time: float = 0.0
        self._hop_latencies: list[HopLatency] = []
        self._matching_nodes: int = 0
        self._results_count: int = 0

    def __enter__(self) -> "QueryMeasurementContext":
        """Start measuring."""
        self._start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Stop measuring and record metrics."""
        total_latency = (time.perf_counter() - self._start_time) * 1000

        metrics = GraphQueryMetrics(
            query=self._query,
            user_id=self._user_id,
            total_latency_ms=total_latency,
            hop_latencies=self._hop_latencies,
            matching_nodes=self._matching_nodes,
            results_count=self._results_count,
        )

        self._collector.record_query(metrics)

    def add_hop(self, hop_type: str, latency_ms: float, node_count: int) -> None:
        """Add hop latency measurement.

        Args:
            hop_type: Type of hop (e.g., "direct", "neighbor", "predecessor").
            latency_ms: Time taken in milliseconds.
            node_count: Number of nodes accessed.
        """
        self._hop_latencies.append(HopLatency(
            hop_type=hop_type,
            latency_ms=latency_ms,
            node_count=node_count,
        ))

    def set_matching_nodes(self, count: int) -> None:
        """Set the number of matching nodes.

        Args:
            count: Number of nodes matching the query.
        """
        self._matching_nodes = count

    def set_results_count(self, count: int) -> None:
        """Set the number of results.

        Args:
            count: Number of results returned.
        """
        self._results_count = count


def measure_hop(
    collector: GraphMetricsCollector,
    context: QueryMeasurementContext,
    hop_type: str,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to measure hop latency.

    Args:
        collector: The metrics collector.
        context: The measurement context.
        hop_type: Type of hop being measured.

    Returns:
        Decorator function.
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args, **kwargs) -> T:
            start = time.perf_counter()
            result = func(*args, **kwargs)
            latency = (time.perf_counter() - start) * 1000

            # Count nodes if result is iterable
            try:
                node_count = len(result) if hasattr(result, "__len__") else 1
            except TypeError:
                node_count = 1

            context.add_hop(hop_type, latency, node_count)
            return result

        return wrapper

    return decorator
