# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
Hot Memory Latency Benchmark - Exit Criteria Test.

Verifies that hot memory retrieval meets the <50ms p95 latency target
as specified in ADR-003.

Related GitHub Issues:
- #90: Hot Memory Latency Benchmark

ADR Reference: ADR-003 Memory Architecture, Phase 1a (Exit Criteria)
"""

import asyncio
import statistics
import time
from typing import List

import pytest

from luminescent_cluster.memory.providers.local import LocalMemoryProvider
from luminescent_cluster.memory.schemas import Memory, MemoryType


class TestHotMemoryLatency:
    """Benchmark tests for hot memory latency requirements."""

    # Exit criteria from ADR-003
    TARGET_P95_LATENCY_MS = 50.0
    TARGET_P50_LATENCY_MS = 20.0

    @pytest.fixture
    def provider(self):
        """Create a fresh LocalMemoryProvider for benchmarks."""
        return LocalMemoryProvider()

    @pytest.fixture
    def populated_provider(self, provider):
        """Create a provider with sample data for benchmarking."""
        # Synchronously populate with sample memories
        loop = asyncio.get_event_loop()

        async def populate():
            for i in range(100):
                memory = Memory(
                    user_id="benchmark-user",
                    content=f"Benchmark memory {i} with some additional content for realistic size",
                    memory_type=MemoryType.FACT,
                    source="benchmark",
                    confidence=0.9,
                    metadata={"index": i},
                )
                await provider.store(memory, {})

        loop.run_until_complete(populate())
        return provider

    @pytest.mark.asyncio
    async def test_store_latency_under_target(self, provider):
        """Store operation should complete under target latency.

        GitHub Issue: #90
        ADR Reference: ADR-003 Phase 1a (Exit Criteria)
        Target: p95 < 50ms
        """
        latencies: List[float] = []

        for i in range(100):
            memory = Memory(
                user_id="latency-test-user",
                content=f"Latency test memory {i}",
                memory_type=MemoryType.PREFERENCE,
                source="benchmark",
            )

            start = time.perf_counter()
            await provider.store(memory, {})
            end = time.perf_counter()

            latencies.append((end - start) * 1000)  # Convert to ms

        p50 = statistics.median(latencies)
        p95 = statistics.quantiles(latencies, n=20)[18]  # 95th percentile
        p99 = statistics.quantiles(latencies, n=100)[98]  # 99th percentile

        print(f"\nStore Latency (100 ops):")
        print(f"  p50: {p50:.2f}ms")
        print(f"  p95: {p95:.2f}ms")
        print(f"  p99: {p99:.2f}ms")

        assert p95 < self.TARGET_P95_LATENCY_MS, (
            f"Store p95 latency {p95:.2f}ms exceeds target {self.TARGET_P95_LATENCY_MS}ms"
        )

    @pytest.mark.asyncio
    async def test_retrieve_latency_under_target(self, populated_provider):
        """Retrieve operation should complete under target latency.

        GitHub Issue: #90
        ADR Reference: ADR-003 Phase 1a (Exit Criteria)
        Target: p95 < 50ms
        """
        provider = populated_provider
        latencies: List[float] = []

        queries = [
            "benchmark",
            "memory",
            "content",
            "realistic",
            "additional",
        ]

        for _ in range(100):
            query = queries[_ % len(queries)]

            start = time.perf_counter()
            await provider.retrieve(query, "benchmark-user", limit=5)
            end = time.perf_counter()

            latencies.append((end - start) * 1000)

        p50 = statistics.median(latencies)
        p95 = statistics.quantiles(latencies, n=20)[18]
        p99 = statistics.quantiles(latencies, n=100)[98]

        print(f"\nRetrieve Latency (100 ops, 100 memories):")
        print(f"  p50: {p50:.2f}ms")
        print(f"  p95: {p95:.2f}ms")
        print(f"  p99: {p99:.2f}ms")

        assert p95 < self.TARGET_P95_LATENCY_MS, (
            f"Retrieve p95 latency {p95:.2f}ms exceeds target {self.TARGET_P95_LATENCY_MS}ms"
        )

    @pytest.mark.asyncio
    async def test_get_by_id_latency_under_target(self, provider):
        """Get by ID operation should complete under target latency.

        GitHub Issue: #90
        ADR Reference: ADR-003 Phase 1a (Exit Criteria)
        Target: p95 < 50ms
        """
        # First, store memories and collect their IDs
        memory_ids: List[str] = []
        for i in range(50):
            memory = Memory(
                user_id="id-test-user",
                content=f"ID test memory {i}",
                memory_type=MemoryType.DECISION,
                source="benchmark",
            )
            memory_id = await provider.store(memory, {})
            memory_ids.append(memory_id)

        latencies: List[float] = []

        for _ in range(100):
            memory_id = memory_ids[_ % len(memory_ids)]

            start = time.perf_counter()
            await provider.get_by_id(memory_id)
            end = time.perf_counter()

            latencies.append((end - start) * 1000)

        p50 = statistics.median(latencies)
        p95 = statistics.quantiles(latencies, n=20)[18]
        p99 = statistics.quantiles(latencies, n=100)[98]

        print(f"\nGet by ID Latency (100 ops):")
        print(f"  p50: {p50:.2f}ms")
        print(f"  p95: {p95:.2f}ms")
        print(f"  p99: {p99:.2f}ms")

        assert p95 < self.TARGET_P95_LATENCY_MS, (
            f"Get by ID p95 latency {p95:.2f}ms exceeds target {self.TARGET_P95_LATENCY_MS}ms"
        )

    @pytest.mark.asyncio
    async def test_delete_latency_under_target(self, provider):
        """Delete operation should complete under target latency.

        GitHub Issue: #90
        ADR Reference: ADR-003 Phase 1a (Exit Criteria)
        Target: p95 < 50ms
        """
        # First, store memories
        memory_ids: List[str] = []
        for i in range(100):
            memory = Memory(
                user_id="delete-test-user",
                content=f"Delete test memory {i}",
                memory_type=MemoryType.FACT,
                source="benchmark",
            )
            memory_id = await provider.store(memory, {})
            memory_ids.append(memory_id)

        latencies: List[float] = []

        for memory_id in memory_ids:
            start = time.perf_counter()
            await provider.delete(memory_id)
            end = time.perf_counter()

            latencies.append((end - start) * 1000)

        p50 = statistics.median(latencies)
        p95 = statistics.quantiles(latencies, n=20)[18]
        p99 = statistics.quantiles(latencies, n=100)[98]

        print(f"\nDelete Latency (100 ops):")
        print(f"  p50: {p50:.2f}ms")
        print(f"  p95: {p95:.2f}ms")
        print(f"  p99: {p99:.2f}ms")

        assert p95 < self.TARGET_P95_LATENCY_MS, (
            f"Delete p95 latency {p95:.2f}ms exceeds target {self.TARGET_P95_LATENCY_MS}ms"
        )

    @pytest.mark.asyncio
    async def test_search_latency_under_target(self, populated_provider):
        """Search operation should complete under target latency.

        GitHub Issue: #90
        ADR Reference: ADR-003 Phase 1a (Exit Criteria)
        Target: p95 < 50ms
        """
        provider = populated_provider
        latencies: List[float] = []

        for _ in range(100):
            start = time.perf_counter()
            await provider.search(
                "benchmark-user",
                {"memory_type": MemoryType.FACT},
                limit=10,
            )
            end = time.perf_counter()

            latencies.append((end - start) * 1000)

        p50 = statistics.median(latencies)
        p95 = statistics.quantiles(latencies, n=20)[18]
        p99 = statistics.quantiles(latencies, n=100)[98]

        print(f"\nSearch Latency (100 ops, with filter):")
        print(f"  p50: {p50:.2f}ms")
        print(f"  p95: {p95:.2f}ms")
        print(f"  p99: {p99:.2f}ms")

        assert p95 < self.TARGET_P95_LATENCY_MS, (
            f"Search p95 latency {p95:.2f}ms exceeds target {self.TARGET_P95_LATENCY_MS}ms"
        )


class TestLatencyReportGeneration:
    """Tests for latency report generation utilities."""

    def test_latency_report_structure(self):
        """Latency report should have expected structure.

        GitHub Issue: #90
        ADR Reference: ADR-003 Phase 1a (Exit Criteria)
        """
        from luminescent_cluster.memory.observability.metrics import MemoryMetrics

        metrics = MemoryMetrics()

        # Record some latencies
        for i in range(10):
            metrics.record_latency("store", i * 2.0)
            metrics.record_latency("retrieve", i * 1.5)

        stats = metrics.get_stats()

        assert "latencies" in stats
        assert "store" in stats["latencies"]
        assert "retrieve" in stats["latencies"]
        assert "avg_ms" in stats["latencies"]["store"]
        assert "count" in stats["latencies"]["store"]
