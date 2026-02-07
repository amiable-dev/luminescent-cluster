# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
TDD: RED Phase - Janitor Performance Benchmark.

Verifies that janitor completes within <10 minutes for 10k memories
as specified in ADR-003.

Related GitHub Issues:
- #106: Janitor Performance Benchmark

ADR Reference: ADR-003 Memory Architecture, Phase 1d (Exit Criteria)
"""

import time
from datetime import datetime, timedelta, timezone

import pytest

from luminescent_cluster.memory.providers.local import LocalMemoryProvider
from luminescent_cluster.memory.schemas import Memory, MemoryType


class TestJanitorPerformance:
    """Benchmark tests for janitor performance."""

    # Exit criteria from ADR-003
    # <10 min = 600,000 ms for 10k memories
    # For testing, we use 1k memories and scale the target proportionally
    TARGET_TIME_MS_PER_1K = 60_000  # 60 seconds per 1k (scaled from 10 min per 10k)

    @pytest.fixture
    async def large_provider(self) -> LocalMemoryProvider:
        """Create provider with 1000 memories for performance testing."""
        provider = LocalMemoryProvider()
        now = datetime.now(timezone.utc)

        # Create 1000 memories with varying characteristics
        for i in range(1000):
            # Mix of expired, duplicate, and valid memories
            expires_at = None
            if i % 10 == 0:
                # 10% expired
                expires_at = now - timedelta(days=10)
            elif i % 5 == 0:
                # Another 20% expiring soon
                expires_at = now + timedelta(days=5)

            memory = Memory(
                user_id="benchmark-user",
                content=f"Memory content {i % 100} about topic {i // 100}",  # Some duplicates
                memory_type=MemoryType.FACT
                if i % 3 == 0
                else (MemoryType.PREFERENCE if i % 3 == 1 else MemoryType.DECISION),
                confidence=0.7 + (i % 30) * 0.01,
                source="benchmark",
                raw_source=f"Original text {i}",
                extraction_version=1,
                created_at=now - timedelta(days=i % 90),
                last_accessed_at=now - timedelta(hours=i % 720),
                expires_at=expires_at,
            )
            await provider.store(memory, {})

        return provider

    @pytest.mark.asyncio
    async def test_full_janitor_run_performance(self, large_provider):
        """Full janitor run should complete within time limit.

        Exit Criteria: <10 min for 10k memories (scaled: <60s for 1k)
        GitHub Issue: #106
        ADR Reference: ADR-003 Phase 1d
        """
        from luminescent_cluster.memory.janitor.runner import JanitorRunner

        janitor = JanitorRunner(large_provider)

        start = time.perf_counter()
        result = await janitor.run_all(user_id="benchmark-user")
        end = time.perf_counter()

        duration_ms = (end - start) * 1000

        print(f"\nJanitor Full Run Performance:")
        print(f"  Memories processed: {result['total_processed']}")
        print(f"  Memories removed: {result['total_removed']}")
        print(f"  Duration: {duration_ms:.2f}ms")
        print(f"  Target: <{self.TARGET_TIME_MS_PER_1K}ms")

        assert duration_ms < self.TARGET_TIME_MS_PER_1K, (
            f"Janitor run took {duration_ms:.0f}ms, exceeds target {self.TARGET_TIME_MS_PER_1K}ms"
        )

    @pytest.mark.asyncio
    async def test_deduplication_performance(self, large_provider):
        """Deduplication should complete within time limit.

        GitHub Issue: #106
        """
        from luminescent_cluster.memory.janitor.deduplication import Deduplicator

        dedup = Deduplicator(similarity_threshold=0.85)

        start = time.perf_counter()
        result = await dedup.run(large_provider, "benchmark-user")
        end = time.perf_counter()

        duration_ms = (end - start) * 1000

        print(f"\nDeduplication Performance:")
        print(f"  Processed: {result['processed']}")
        print(f"  Removed: {result['removed']}")
        print(f"  Duration: {duration_ms:.2f}ms")

        # Deduplication should be less than 1/3 of total time
        assert duration_ms < self.TARGET_TIME_MS_PER_1K / 3

    @pytest.mark.asyncio
    async def test_contradiction_handling_performance(self, large_provider):
        """Contradiction handling should complete within time limit.

        GitHub Issue: #106
        """
        from luminescent_cluster.memory.janitor.contradiction import ContradictionHandler

        handler = ContradictionHandler()

        start = time.perf_counter()
        result = await handler.run(large_provider, "benchmark-user")
        end = time.perf_counter()

        duration_ms = (end - start) * 1000

        print(f"\nContradiction Handling Performance:")
        print(f"  Processed: {result['processed']}")
        print(f"  Resolved: {result['resolved']}")
        print(f"  Duration: {duration_ms:.2f}ms")

        # Contradiction handling should be less than 1/3 of total time
        assert duration_ms < self.TARGET_TIME_MS_PER_1K / 3

    @pytest.mark.asyncio
    async def test_expiration_cleanup_performance(self, large_provider):
        """Expiration cleanup should complete within time limit.

        GitHub Issue: #106
        """
        from luminescent_cluster.memory.janitor.expiration import ExpirationCleaner

        cleaner = ExpirationCleaner()

        start = time.perf_counter()
        result = await cleaner.run(large_provider, "benchmark-user")
        end = time.perf_counter()

        duration_ms = (end - start) * 1000

        print(f"\nExpiration Cleanup Performance:")
        print(f"  Processed: {result['processed']}")
        print(f"  Removed: {result['removed']}")
        print(f"  Duration: {duration_ms:.2f}ms")

        # Expiration cleanup should be less than 1/3 of total time
        assert duration_ms < self.TARGET_TIME_MS_PER_1K / 3

    @pytest.mark.asyncio
    async def test_incremental_janitor_performance(self, large_provider):
        """Incremental janitor run should be faster than full run.

        GitHub Issue: #106
        """
        from luminescent_cluster.memory.janitor.runner import JanitorRunner

        janitor = JanitorRunner(large_provider)

        # First run (full)
        first_start = time.perf_counter()
        await janitor.run_all(user_id="benchmark-user")
        first_end = time.perf_counter()
        first_duration = (first_end - first_start) * 1000

        # Second run (should be faster - less to clean)
        second_start = time.perf_counter()
        await janitor.run_all(user_id="benchmark-user")
        second_end = time.perf_counter()
        second_duration = (second_end - second_start) * 1000

        print(f"\nIncremental Janitor Performance:")
        print(f"  First run: {first_duration:.2f}ms")
        print(f"  Second run: {second_duration:.2f}ms")

        # Second run should be faster or similar (not worse)
        assert second_duration <= first_duration * 1.5  # Allow some variance
