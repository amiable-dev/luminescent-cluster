# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Benchmark tests for MaaS Exit Criteria - ADR-003 Phase 4.2 (Issues #162-167).

Exit Criteria Benchmarks:
- Sync latency: <500ms p95
- Handoff latency: <2s p95
- Registry lookup: <50ms
- Pool query latency: <200ms p95
- Concurrent writers: 10+ agents
"""

import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from src.memory.maas.handoff import HandoffContext, HandoffManager
from src.memory.maas.pool import PoolRegistry
from src.memory.maas.registry import AgentRegistry
from src.memory.maas.scope import PermissionModel, SharedScope
from src.memory.maas.types import AgentCapability, AgentType


class TestSyncLatencyBenchmark:
    """Benchmark tests for sync latency (<500ms p95)."""

    def setup_method(self):
        """Reset registries before each test."""
        AgentRegistry.reset()
        PoolRegistry.reset()
        HandoffManager.reset()

    def teardown_method(self):
        """Reset registries after each test."""
        AgentRegistry.reset()
        PoolRegistry.reset()
        HandoffManager.reset()

    def test_memory_share_latency(self):
        """Verify memory sharing meets latency target."""
        agent_registry = AgentRegistry.get()
        pool_registry = PoolRegistry.get()

        # Setup
        agent_id = agent_registry.register_agent(
            agent_type=AgentType.CLAUDE_CODE,
            owner_id="user-bench",
        )
        pool_id = pool_registry.create_pool(
            name="bench-pool",
            owner_id="user-bench",
            scope=SharedScope.PROJECT,
        )
        pool_registry.join_pool(pool_id, agent_id, PermissionModel.WRITE)

        # Benchmark
        latencies = []
        for i in range(100):
            start = time.perf_counter()
            pool_registry.share_memory(pool_id, f"mem-{i}", agent_id, SharedScope.PROJECT)
            latencies.append((time.perf_counter() - start) * 1000)  # Convert to ms

        p95 = sorted(latencies)[int(len(latencies) * 0.95)]

        # Target: <500ms p95 (should be much faster in-memory)
        assert p95 < 500, f"Sync latency p95: {p95:.2f}ms exceeds 500ms target"
        print(f"Sync latency p95: {p95:.2f}ms, mean: {statistics.mean(latencies):.2f}ms")


class TestHandoffLatencyBenchmark:
    """Benchmark tests for handoff latency (<2s p95)."""

    def setup_method(self):
        """Reset registries before each test."""
        AgentRegistry.reset()
        PoolRegistry.reset()
        HandoffManager.reset()

    def teardown_method(self):
        """Reset registries after each test."""
        AgentRegistry.reset()
        PoolRegistry.reset()
        HandoffManager.reset()

    def test_handoff_initiate_latency(self):
        """Verify handoff initiation meets latency target."""
        agent_registry = AgentRegistry.get()
        handoff_manager = HandoffManager.get()

        # Setup agents
        source_id = agent_registry.register_agent(
            agent_type=AgentType.CLAUDE_CODE,
            owner_id="user-bench",
            capabilities={AgentCapability.HANDOFF_INITIATE, AgentCapability.MEMORY_READ},
        )
        target_id = agent_registry.register_agent(
            agent_type=AgentType.GPT_AGENT,
            owner_id="user-bench",
            capabilities={AgentCapability.HANDOFF_RECEIVE, AgentCapability.MEMORY_READ},
        )

        # Benchmark
        latencies = []
        for i in range(100):
            context = HandoffContext(task_description=f"Task {i}")
            start = time.perf_counter()
            handoff_id = handoff_manager.initiate_handoff(
                source_agent_id=source_id,
                target_agent_id=target_id,
                context=context,
            )
            latencies.append((time.perf_counter() - start) * 1000)

        p95 = sorted(latencies)[int(len(latencies) * 0.95)]

        # Target: <2s p95 (should be much faster in-memory)
        assert p95 < 2000, f"Handoff latency p95: {p95:.2f}ms exceeds 2000ms target"
        print(f"Handoff latency p95: {p95:.2f}ms, mean: {statistics.mean(latencies):.2f}ms")

    def test_full_handoff_cycle_latency(self):
        """Verify full handoff cycle (init + accept + complete) meets target."""
        agent_registry = AgentRegistry.get()
        handoff_manager = HandoffManager.get()

        source_id = agent_registry.register_agent(
            agent_type=AgentType.CLAUDE_CODE,
            owner_id="user-bench",
            capabilities={AgentCapability.HANDOFF_INITIATE, AgentCapability.MEMORY_READ},
        )
        target_id = agent_registry.register_agent(
            agent_type=AgentType.GPT_AGENT,
            owner_id="user-bench",
            capabilities={AgentCapability.HANDOFF_RECEIVE, AgentCapability.MEMORY_READ},
        )

        latencies = []
        for i in range(50):
            context = HandoffContext(task_description=f"Full cycle task {i}")

            start = time.perf_counter()
            handoff_id = handoff_manager.initiate_handoff(
                source_agent_id=source_id,
                target_agent_id=target_id,
                context=context,
            )
            handoff_manager.accept_handoff(handoff_id, target_id)
            handoff_manager.complete_handoff(handoff_id, target_id, result={"status": "done"})
            latencies.append((time.perf_counter() - start) * 1000)

        p95 = sorted(latencies)[int(len(latencies) * 0.95)]

        # Target: <2s p95 for full cycle
        assert p95 < 2000, f"Full handoff cycle p95: {p95:.2f}ms exceeds 2000ms target"
        print(f"Full handoff cycle p95: {p95:.2f}ms, mean: {statistics.mean(latencies):.2f}ms")


class TestRegistryLookupBenchmark:
    """Benchmark tests for registry lookup (<50ms)."""

    def setup_method(self):
        """Reset registries before each test."""
        AgentRegistry.reset()

    def teardown_method(self):
        """Reset registries after each test."""
        AgentRegistry.reset()

    def test_registry_lookup_latency(self):
        """Verify registry lookup meets latency target."""
        agent_registry = AgentRegistry.get()

        # Pre-populate registry
        agent_ids = []
        for i in range(1000):
            agent_id = agent_registry.register_agent(
                agent_type=AgentType.CLAUDE_CODE,
                owner_id=f"user-{i}",
            )
            agent_ids.append(agent_id)

        # Benchmark lookups
        latencies = []
        for agent_id in agent_ids[:100]:
            start = time.perf_counter()
            agent = agent_registry.get_agent(agent_id)
            latencies.append((time.perf_counter() - start) * 1000)

        p95 = sorted(latencies)[int(len(latencies) * 0.95)]

        # Target: <50ms
        assert p95 < 50, f"Registry lookup p95: {p95:.2f}ms exceeds 50ms target"
        print(f"Registry lookup p95: {p95:.2f}ms, mean: {statistics.mean(latencies):.4f}ms")


class TestPoolQueryLatencyBenchmark:
    """Benchmark tests for pool query latency (<200ms p95)."""

    def setup_method(self):
        """Reset registries before each test."""
        AgentRegistry.reset()
        PoolRegistry.reset()

    def teardown_method(self):
        """Reset registries after each test."""
        AgentRegistry.reset()
        PoolRegistry.reset()

    def test_pool_query_latency(self):
        """Verify pool query meets latency target."""
        agent_registry = AgentRegistry.get()
        pool_registry = PoolRegistry.get()

        # Setup
        agent_id = agent_registry.register_agent(
            agent_type=AgentType.CLAUDE_CODE,
            owner_id="user-bench",
        )
        pool_id = pool_registry.create_pool(
            name="query-pool",
            owner_id="user-bench",
            scope=SharedScope.PROJECT,
        )
        pool_registry.join_pool(pool_id, agent_id, PermissionModel.WRITE)

        # Populate pool with memories
        for i in range(500):
            pool_registry.share_memory(pool_id, f"mem-{i}", agent_id, SharedScope.PROJECT)

        # Benchmark queries
        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            memories = pool_registry.query_shared(pool_id, agent_id, SharedScope.PROJECT)
            latencies.append((time.perf_counter() - start) * 1000)

        p95 = sorted(latencies)[int(len(latencies) * 0.95)]

        # Target: <200ms p95
        assert p95 < 200, f"Pool query p95: {p95:.2f}ms exceeds 200ms target"
        print(f"Pool query p95: {p95:.2f}ms, mean: {statistics.mean(latencies):.2f}ms")


class TestConcurrentWriteBenchmark:
    """Benchmark tests for concurrent writers (10+ agents)."""

    def setup_method(self):
        """Reset registries before each test."""
        AgentRegistry.reset()
        PoolRegistry.reset()

    def teardown_method(self):
        """Reset registries after each test."""
        AgentRegistry.reset()
        PoolRegistry.reset()

    def test_concurrent_writers(self):
        """Verify 10+ concurrent writers work correctly."""
        agent_registry = AgentRegistry.get()
        pool_registry = PoolRegistry.get()

        num_writers = 15  # Test with more than 10
        writes_per_agent = 20

        # Create pool
        pool_id = pool_registry.create_pool(
            name="concurrent-pool",
            owner_id="pool-owner",
            scope=SharedScope.PROJECT,
        )

        # Create agents
        agent_ids = []
        for i in range(num_writers):
            agent_id = agent_registry.register_agent(
                agent_type=AgentType.CLAUDE_CODE,
                owner_id=f"user-{i}",
            )
            pool_registry.join_pool(pool_id, agent_id, PermissionModel.WRITE)
            agent_ids.append(agent_id)

        errors = []
        successful_writes = []
        lock = threading.Lock()

        def writer(agent_id, agent_idx):
            try:
                for j in range(writes_per_agent):
                    result = pool_registry.share_memory(
                        pool_id,
                        f"mem-{agent_idx}-{j}",
                        agent_id,
                        SharedScope.PROJECT,
                    )
                    if result:
                        with lock:
                            successful_writes.append(f"mem-{agent_idx}-{j}")
            except Exception as e:
                with lock:
                    errors.append(e)

        # Run concurrent writers
        with ThreadPoolExecutor(max_workers=num_writers) as executor:
            futures = [
                executor.submit(writer, agent_id, idx)
                for idx, agent_id in enumerate(agent_ids)
            ]
            for future in as_completed(futures):
                future.result()  # Raise any exceptions

        # Verify
        assert len(errors) == 0, f"Errors during concurrent writes: {errors}"
        expected_writes = num_writers * writes_per_agent
        assert len(successful_writes) == expected_writes, (
            f"Expected {expected_writes} writes, got {len(successful_writes)}"
        )

        # Verify data integrity
        memories = pool_registry.get_shared_memories(pool_id)
        assert len(memories) == expected_writes

        print(f"Concurrent writers: {num_writers} agents, {expected_writes} total writes - SUCCESS")
