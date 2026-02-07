# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
TDD: RED Phase - Retrieval Latency Benchmark.

Verifies that memory retrieval meets the <200ms p95 latency target
as specified in ADR-003.

Related GitHub Issues:
- #101: Retrieval Latency Benchmark

ADR Reference: ADR-003 Memory Architecture, Phase 1c (Exit Criteria)
"""

import asyncio
import statistics
import time
from datetime import datetime, timedelta, timezone
from typing import List

import pytest

from luminescent_cluster.memory.providers.local import LocalMemoryProvider
from luminescent_cluster.memory.schemas import Memory, MemoryType


class TestRetrievalLatency:
    """Benchmark tests for retrieval latency."""

    # Exit criteria from ADR-003
    TARGET_P95_LATENCY_MS = 200.0

    @pytest.fixture
    async def populated_provider(self) -> LocalMemoryProvider:
        """Create provider with sample data for benchmarking."""
        provider = LocalMemoryProvider()
        now = datetime.now(timezone.utc)

        # Create 100 memories for realistic benchmarking
        for i in range(100):
            memory = Memory(
                user_id="benchmark-user",
                content=f"Memory content {i} about various topics like Python, JavaScript, databases, APIs",
                memory_type=MemoryType.FACT
                if i % 3 == 0
                else (MemoryType.PREFERENCE if i % 3 == 1 else MemoryType.DECISION),
                confidence=0.8 + (i % 20) * 0.01,
                source="benchmark",
                raw_source=f"Original text {i}",
                extraction_version=1,
                created_at=now - timedelta(days=i),
                last_accessed_at=now - timedelta(hours=i),
            )
            await provider.store(memory, {})

        return provider

    @pytest.fixture
    def ranker(self):
        """Create ranker for benchmarking."""
        from luminescent_cluster.memory.retrieval.ranker import MemoryRanker

        return MemoryRanker()

    @pytest.fixture
    async def scoped_retriever(self, populated_provider):
        """Create scoped retriever for benchmarking."""
        from luminescent_cluster.memory.retrieval.scoped import ScopedRetriever

        return ScopedRetriever(populated_provider)

    async def _measure_latency(self, operation, iterations: int = 50) -> List[float]:
        """Measure latency of an operation over multiple iterations."""
        latencies = []
        for _ in range(iterations):
            start = time.perf_counter()
            await operation()
            end = time.perf_counter()
            latencies.append((end - start) * 1000)  # Convert to ms
        return latencies

    @pytest.mark.asyncio
    async def test_retrieve_latency_p95(self, populated_provider):
        """Retrieve operation should meet p95 latency target.

        Exit Criteria: <200ms p95 latency
        GitHub Issue: #101
        ADR Reference: ADR-003 Phase 1c
        """

        async def retrieve_operation():
            await populated_provider.retrieve("Python databases", "benchmark-user", limit=5)

        latencies = await self._measure_latency(retrieve_operation)

        p95 = statistics.quantiles(latencies, n=20)[18]  # 95th percentile
        mean = statistics.mean(latencies)
        max_latency = max(latencies)

        print(f"\nRetrieve Latency Benchmark:")
        print(f"  Mean: {mean:.2f}ms")
        print(f"  P95: {p95:.2f}ms")
        print(f"  Max: {max_latency:.2f}ms")
        print(f"  Target: <{self.TARGET_P95_LATENCY_MS}ms")

        assert p95 < self.TARGET_P95_LATENCY_MS, (
            f"Retrieve p95 latency {p95:.2f}ms exceeds target {self.TARGET_P95_LATENCY_MS}ms"
        )

    @pytest.mark.asyncio
    async def test_ranked_retrieval_latency_p95(self, populated_provider, ranker):
        """Ranked retrieval should meet p95 latency target.

        Exit Criteria: <200ms p95 latency
        GitHub Issue: #101
        """

        async def ranked_retrieve():
            results = await populated_provider.retrieve(
                "Python JavaScript", "benchmark-user", limit=10
            )
            ranker.rank("Python JavaScript", results, limit=5)

        latencies = await self._measure_latency(ranked_retrieve)

        p95 = statistics.quantiles(latencies, n=20)[18]
        mean = statistics.mean(latencies)

        print(f"\nRanked Retrieval Latency Benchmark:")
        print(f"  Mean: {mean:.2f}ms")
        print(f"  P95: {p95:.2f}ms")
        print(f"  Target: <{self.TARGET_P95_LATENCY_MS}ms")

        assert p95 < self.TARGET_P95_LATENCY_MS, (
            f"Ranked retrieval p95 latency {p95:.2f}ms exceeds target"
        )

    @pytest.mark.asyncio
    async def test_scoped_retrieval_latency_p95(self, scoped_retriever):
        """Scoped retrieval should meet p95 latency target.

        Exit Criteria: <200ms p95 latency
        GitHub Issue: #101
        """

        async def scoped_retrieve():
            await scoped_retriever.retrieve(
                query="databases APIs",
                user_id="benchmark-user",
                scope="user",
                limit=5,
            )

        latencies = await self._measure_latency(scoped_retrieve)

        p95 = statistics.quantiles(latencies, n=20)[18]
        mean = statistics.mean(latencies)

        print(f"\nScoped Retrieval Latency Benchmark:")
        print(f"  Mean: {mean:.2f}ms")
        print(f"  P95: {p95:.2f}ms")
        print(f"  Target: <{self.TARGET_P95_LATENCY_MS}ms")

        assert p95 < self.TARGET_P95_LATENCY_MS, (
            f"Scoped retrieval p95 latency {p95:.2f}ms exceeds target"
        )

    @pytest.mark.asyncio
    async def test_cascading_retrieval_latency_p95(self, scoped_retriever):
        """Cascading retrieval across scopes should meet p95 latency target.

        Exit Criteria: <200ms p95 latency
        GitHub Issue: #101
        """

        async def cascading_retrieve():
            await scoped_retriever.retrieve(
                query="Python project",
                user_id="benchmark-user",
                scope="user",
                cascade=True,  # Enable cascade through hierarchy
                limit=5,
            )

        latencies = await self._measure_latency(cascading_retrieve)

        p95 = statistics.quantiles(latencies, n=20)[18]
        mean = statistics.mean(latencies)

        print(f"\nCascading Retrieval Latency Benchmark:")
        print(f"  Mean: {mean:.2f}ms")
        print(f"  P95: {p95:.2f}ms")
        print(f"  Target: <{self.TARGET_P95_LATENCY_MS}ms")

        assert p95 < self.TARGET_P95_LATENCY_MS, (
            f"Cascading retrieval p95 latency {p95:.2f}ms exceeds target"
        )

    @pytest.mark.asyncio
    async def test_search_with_filters_latency_p95(self, populated_provider):
        """Search with filters should meet p95 latency target.

        Exit Criteria: <200ms p95 latency
        GitHub Issue: #101
        """

        async def filtered_search():
            await populated_provider.search(
                user_id="benchmark-user",
                filters={"memory_type": "fact"},
                limit=10,
            )

        latencies = await self._measure_latency(filtered_search)

        p95 = statistics.quantiles(latencies, n=20)[18]
        mean = statistics.mean(latencies)

        print(f"\nFiltered Search Latency Benchmark:")
        print(f"  Mean: {mean:.2f}ms")
        print(f"  P95: {p95:.2f}ms")
        print(f"  Target: <{self.TARGET_P95_LATENCY_MS}ms")

        assert p95 < self.TARGET_P95_LATENCY_MS, (
            f"Filtered search p95 latency {p95:.2f}ms exceeds target"
        )

    @pytest.mark.asyncio
    async def test_concurrent_retrieval_latency(self, populated_provider):
        """Concurrent retrievals should maintain acceptable latency.

        GitHub Issue: #101
        """

        async def concurrent_batch():
            tasks = [
                populated_provider.retrieve("Python", "benchmark-user", limit=5),
                populated_provider.retrieve("JavaScript", "benchmark-user", limit=5),
                populated_provider.retrieve("databases", "benchmark-user", limit=5),
            ]
            await asyncio.gather(*tasks)

        latencies = await self._measure_latency(concurrent_batch, iterations=30)

        p95 = statistics.quantiles(latencies, n=20)[18]
        mean = statistics.mean(latencies)

        print(f"\nConcurrent Retrieval Latency Benchmark:")
        print(f"  Mean: {mean:.2f}ms")
        print(f"  P95: {p95:.2f}ms")
        print(f"  Target: <{self.TARGET_P95_LATENCY_MS}ms")

        # Allow slightly higher for concurrent operations
        assert p95 < self.TARGET_P95_LATENCY_MS * 1.5, (
            f"Concurrent retrieval p95 latency {p95:.2f}ms exceeds target"
        )
