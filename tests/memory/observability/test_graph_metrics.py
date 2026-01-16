"""Tests for Graph Query Monitoring (ADR-003 Phase D).

Tests for graph performance metrics:
- Query latency tracking
- Hop-level timing (direct, neighbor, predecessor)
- Node/edge count tracking
- Statistics calculation
"""

import pytest
import time
from datetime import datetime, timezone

from src.memory.observability.graph_metrics import (
    GraphMetricsCollector,
    GraphQueryMetrics,
    GraphSizeSnapshot,
    HopLatency,
    QueryMeasurementContext,
)


class TestHopLatency:
    """Test HopLatency dataclass."""

    def test_create_hop_latency(self):
        """Should create a hop latency measurement."""
        hop = HopLatency(
            hop_type="direct",
            latency_ms=5.2,
            node_count=3,
        )

        assert hop.hop_type == "direct"
        assert hop.latency_ms == 5.2
        assert hop.node_count == 3

    def test_hop_types(self):
        """Should support different hop types."""
        direct = HopLatency(hop_type="direct", latency_ms=1.0, node_count=1)
        neighbor = HopLatency(hop_type="neighbor", latency_ms=2.0, node_count=5)
        predecessor = HopLatency(hop_type="predecessor", latency_ms=3.0, node_count=3)

        assert direct.hop_type == "direct"
        assert neighbor.hop_type == "neighbor"
        assert predecessor.hop_type == "predecessor"


class TestGraphQueryMetrics:
    """Test GraphQueryMetrics dataclass."""

    def test_create_query_metrics(self):
        """Should create query metrics."""
        metrics = GraphQueryMetrics(
            query="auth-service",
            user_id="user-123",
            total_latency_ms=25.5,
            hop_latencies=[
                HopLatency("direct", 5.0, 2),
                HopLatency("neighbor", 15.0, 8),
            ],
            matching_nodes=2,
            results_count=10,
        )

        assert metrics.query == "auth-service"
        assert metrics.user_id == "user-123"
        assert metrics.total_latency_ms == 25.5
        assert len(metrics.hop_latencies) == 2
        assert metrics.matching_nodes == 2
        assert metrics.results_count == 10
        assert isinstance(metrics.timestamp, datetime)

    def test_to_dict(self):
        """Should serialize to dictionary."""
        metrics = GraphQueryMetrics(
            query="test-query",
            user_id="user-1",
            total_latency_ms=10.0,
            hop_latencies=[HopLatency("direct", 3.0, 1)],
            matching_nodes=1,
            results_count=5,
        )

        d = metrics.to_dict()

        assert d["query"] == "test-query"
        assert d["user_id"] == "user-1"
        assert d["total_latency_ms"] == 10.0
        assert len(d["hop_latencies"]) == 1
        assert d["hop_latencies"][0]["hop_type"] == "direct"
        assert d["matching_nodes"] == 1
        assert d["results_count"] == 5
        assert "timestamp" in d


class TestGraphSizeSnapshot:
    """Test GraphSizeSnapshot dataclass."""

    def test_create_snapshot(self):
        """Should create a size snapshot."""
        snapshot = GraphSizeSnapshot(
            user_id="user-123",
            node_count=1500,
            edge_count=3200,
        )

        assert snapshot.user_id == "user-123"
        assert snapshot.node_count == 1500
        assert snapshot.edge_count == 3200
        assert isinstance(snapshot.timestamp, datetime)

    def test_to_dict(self):
        """Should serialize to dictionary."""
        snapshot = GraphSizeSnapshot(
            user_id="user-1",
            node_count=100,
            edge_count=250,
        )

        d = snapshot.to_dict()

        assert d["user_id"] == "user-1"
        assert d["node_count"] == 100
        assert d["edge_count"] == 250
        assert "timestamp" in d


class TestGraphMetricsCollector:
    """Test GraphMetricsCollector class."""

    @pytest.fixture
    def collector(self):
        """Create a metrics collector."""
        return GraphMetricsCollector()

    def test_record_query(self, collector):
        """Should record query metrics."""
        metrics = GraphQueryMetrics(
            query="test-query",
            user_id="user-1",
            total_latency_ms=15.0,
            hop_latencies=[],
            matching_nodes=3,
            results_count=7,
        )

        collector.record_query(metrics)

        history = collector.get_query_history()
        assert len(history) == 1
        assert history[0].query == "test-query"

    def test_record_multiple_queries(self, collector):
        """Should record multiple queries."""
        for i in range(5):
            metrics = GraphQueryMetrics(
                query=f"query-{i}",
                user_id="user-1",
                total_latency_ms=10.0 + i,
                hop_latencies=[],
                matching_nodes=1,
                results_count=i,
            )
            collector.record_query(metrics)

        history = collector.get_query_history()
        assert len(history) == 5

    def test_query_history_limit(self, collector):
        """Should respect history limit."""
        for i in range(10):
            metrics = GraphQueryMetrics(
                query=f"query-{i}",
                user_id="user-1",
                total_latency_ms=10.0,
                hop_latencies=[],
                matching_nodes=1,
                results_count=1,
            )
            collector.record_query(metrics)

        history = collector.get_query_history(limit=3)
        assert len(history) == 3
        # Should be the last 3 queries
        assert history[0].query == "query-7"
        assert history[2].query == "query-9"

    def test_query_history_by_user(self, collector):
        """Should filter history by user."""
        for user in ["user-1", "user-2"]:
            for i in range(3):
                metrics = GraphQueryMetrics(
                    query=f"query-{i}",
                    user_id=user,
                    total_latency_ms=10.0,
                    hop_latencies=[],
                    matching_nodes=1,
                    results_count=1,
                )
                collector.record_query(metrics)

        history = collector.get_query_history(user_id="user-1")
        assert len(history) == 3
        assert all(m.user_id == "user-1" for m in history)

    def test_record_size_snapshot(self, collector):
        """Should record size snapshots."""
        snapshot = GraphSizeSnapshot(
            user_id="user-1",
            node_count=500,
            edge_count=1200,
        )

        collector.record_size_snapshot(snapshot)

        history = collector.get_size_history()
        assert len(history) == 1
        assert history[0].node_count == 500

    def test_size_history_by_user(self, collector):
        """Should filter size history by user."""
        for user in ["user-1", "user-2"]:
            snapshot = GraphSizeSnapshot(
                user_id=user,
                node_count=100,
                edge_count=200,
            )
            collector.record_size_snapshot(snapshot)

        history = collector.get_size_history(user_id="user-1")
        assert len(history) == 1
        assert history[0].user_id == "user-1"

    def test_max_queries_limit(self):
        """Should respect max_queries limit."""
        collector = GraphMetricsCollector(max_queries=5)

        for i in range(10):
            metrics = GraphQueryMetrics(
                query=f"query-{i}",
                user_id="user-1",
                total_latency_ms=10.0,
                hop_latencies=[],
                matching_nodes=1,
                results_count=1,
            )
            collector.record_query(metrics)

        history = collector.get_query_history()
        assert len(history) == 5
        # Should be the last 5
        assert history[0].query == "query-5"

    def test_max_snapshots_limit(self):
        """Should respect max_snapshots limit."""
        collector = GraphMetricsCollector(max_snapshots=3)

        for i in range(5):
            snapshot = GraphSizeSnapshot(
                user_id="user-1",
                node_count=100 * i,
                edge_count=200 * i,
            )
            collector.record_size_snapshot(snapshot)

        history = collector.get_size_history()
        assert len(history) == 3

    def test_clear_all(self, collector):
        """Should clear all metrics."""
        for i in range(3):
            metrics = GraphQueryMetrics(
                query=f"query-{i}",
                user_id="user-1",
                total_latency_ms=10.0,
                hop_latencies=[],
                matching_nodes=1,
                results_count=1,
            )
            collector.record_query(metrics)

        collector.clear()

        assert len(collector.get_query_history()) == 0
        assert len(collector.get_size_history()) == 0

    def test_clear_by_user(self, collector):
        """Should clear metrics for specific user."""
        for user in ["user-1", "user-2"]:
            metrics = GraphQueryMetrics(
                query="test",
                user_id=user,
                total_latency_ms=10.0,
                hop_latencies=[],
                matching_nodes=1,
                results_count=1,
            )
            collector.record_query(metrics)

        collector.clear(user_id="user-1")

        history = collector.get_query_history()
        assert len(history) == 1
        assert history[0].user_id == "user-2"


class TestGraphMetricsStats:
    """Test statistics calculation."""

    @pytest.fixture
    def collector_with_data(self):
        """Create collector with sample data."""
        collector = GraphMetricsCollector()

        # Add queries with varying latencies
        latencies = [10.0, 15.0, 20.0, 25.0, 100.0]  # Last one is outlier
        for i, latency in enumerate(latencies):
            metrics = GraphQueryMetrics(
                query=f"query-{i}",
                user_id="user-1",
                total_latency_ms=latency,
                hop_latencies=[
                    HopLatency("direct", latency * 0.2, 2),
                    HopLatency("neighbor", latency * 0.6, 10),
                    HopLatency("predecessor", latency * 0.2, 5),
                ],
                matching_nodes=2,
                results_count=10 + i,
            )
            collector.record_query(metrics)

        return collector

    def test_get_stats_basic(self, collector_with_data):
        """Should return basic statistics."""
        stats = collector_with_data.get_stats()

        assert stats["query_count"] == 5
        assert stats["avg_latency_ms"] == 34.0  # (10+15+20+25+100)/5
        assert stats["avg_results"] == 12.0  # (10+11+12+13+14)/5

    def test_get_stats_percentiles(self, collector_with_data):
        """Should calculate percentiles."""
        stats = collector_with_data.get_stats()

        # p50 should be median
        assert stats["p50_latency_ms"] == 20.0
        # p95 and p99 should be close to max for small datasets
        assert stats["p95_latency_ms"] >= 25.0
        assert stats["p99_latency_ms"] >= 25.0

    def test_get_stats_hop_breakdown(self, collector_with_data):
        """Should include hop-level statistics."""
        stats = collector_with_data.get_stats()

        assert "hop_stats" in stats
        hop_stats = stats["hop_stats"]

        assert "direct" in hop_stats
        assert "neighbor" in hop_stats
        assert "predecessor" in hop_stats

        # Check averages
        assert hop_stats["direct"]["query_count"] == 5
        assert hop_stats["neighbor"]["avg_nodes"] == 10.0
        assert hop_stats["predecessor"]["avg_latency_ms"] > 0

    def test_get_stats_empty(self):
        """Should handle empty collector."""
        collector = GraphMetricsCollector()
        stats = collector.get_stats()

        assert stats["query_count"] == 0
        assert stats["avg_latency_ms"] == 0.0
        assert stats["p50_latency_ms"] == 0.0

    def test_get_latency_by_hop_type(self, collector_with_data):
        """Should return hop-level latency breakdown."""
        hop_latencies = collector_with_data.get_latency_by_hop_type()

        assert "direct" in hop_latencies
        assert "neighbor" in hop_latencies
        assert "predecessor" in hop_latencies

        # Neighbor should have highest latency (60% of total)
        assert hop_latencies["neighbor"]["avg_latency_ms"] > hop_latencies["direct"]["avg_latency_ms"]


class TestQueryMeasurementContext:
    """Test QueryMeasurementContext class."""

    @pytest.fixture
    def collector(self):
        """Create a metrics collector."""
        return GraphMetricsCollector()

    def test_measure_query_context_manager(self, collector):
        """Should measure query via context manager."""
        with collector.measure_query("user-1", "test-query") as ctx:
            # Simulate some work
            time.sleep(0.01)
            ctx.add_hop("direct", 5.0, 2)
            ctx.set_matching_nodes(2)
            ctx.set_results_count(5)

        history = collector.get_query_history()
        assert len(history) == 1
        assert history[0].query == "test-query"
        assert history[0].user_id == "user-1"
        assert history[0].total_latency_ms >= 10.0  # At least 10ms from sleep
        assert len(history[0].hop_latencies) == 1
        assert history[0].matching_nodes == 2
        assert history[0].results_count == 5

    def test_add_multiple_hops(self, collector):
        """Should record multiple hop latencies."""
        with collector.measure_query("user-1", "query") as ctx:
            ctx.add_hop("direct", 3.0, 2)
            ctx.add_hop("neighbor", 10.0, 8)
            ctx.add_hop("predecessor", 5.0, 4)
            ctx.set_results_count(14)

        history = collector.get_query_history()
        assert len(history[0].hop_latencies) == 3

    def test_context_captures_timing(self, collector):
        """Should capture total timing automatically."""
        with collector.measure_query("user-1", "slow-query") as ctx:
            time.sleep(0.05)  # 50ms
            ctx.set_results_count(1)

        history = collector.get_query_history()
        # Should be at least 50ms
        assert history[0].total_latency_ms >= 50.0

    def test_context_handles_exception(self, collector):
        """Should still record metrics on exception."""
        with pytest.raises(ValueError):
            with collector.measure_query("user-1", "failing-query") as ctx:
                ctx.add_hop("direct", 1.0, 1)
                raise ValueError("Test error")

        # Metrics should still be recorded
        history = collector.get_query_history()
        assert len(history) == 1
        assert history[0].query == "failing-query"


class TestGraphMetricsIntegration:
    """Integration tests for graph metrics."""

    def test_full_monitoring_workflow(self):
        """Test complete monitoring workflow."""
        collector = GraphMetricsCollector()

        # Simulate graph queries over time
        for i in range(10):
            with collector.measure_query("user-1", f"entity-{i}") as ctx:
                # Simulate hop latencies
                ctx.add_hop("direct", 2.0 + i * 0.5, 2)
                ctx.add_hop("neighbor", 8.0 + i, 5 + i)
                ctx.set_matching_nodes(2)
                ctx.set_results_count(7 + i)

            # Record size periodically
            if i % 3 == 0:
                collector.record_size_snapshot(GraphSizeSnapshot(
                    user_id="user-1",
                    node_count=100 + i * 10,
                    edge_count=200 + i * 20,
                ))

        # Get statistics
        stats = collector.get_stats("user-1")

        assert stats["query_count"] == 10
        assert stats["avg_results"] > 0
        assert "direct" in stats["hop_stats"]
        assert "neighbor" in stats["hop_stats"]

        # Check size history
        size_history = collector.get_size_history("user-1")
        assert len(size_history) == 4  # i=0,3,6,9

    def test_multi_user_isolation(self):
        """Test metrics isolation between users."""
        collector = GraphMetricsCollector()

        # User 1 queries
        for i in range(5):
            with collector.measure_query("user-1", f"query-{i}") as ctx:
                ctx.add_hop("direct", 5.0, 2)
                ctx.set_results_count(5)

        # User 2 queries with different patterns
        for i in range(3):
            with collector.measure_query("user-2", f"query-{i}") as ctx:
                ctx.add_hop("direct", 10.0, 5)
                ctx.set_results_count(10)

        # Check isolation
        user1_stats = collector.get_stats("user-1")
        user2_stats = collector.get_stats("user-2")

        assert user1_stats["query_count"] == 5
        assert user2_stats["query_count"] == 3
        assert user1_stats["avg_results"] == 5.0
        assert user2_stats["avg_results"] == 10.0
