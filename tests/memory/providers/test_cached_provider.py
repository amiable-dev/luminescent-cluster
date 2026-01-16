"""Tests for LocalMemoryProvider with cache integration (ADR-003 Option G).

TDD RED phase: These tests define the expected behavior for cached retrieval.

Cache integration:
- Optional caching via use_cache parameter
- Cache invalidation on store/delete/clear
- Hit rate metrics exposure
"""

import pytest
from datetime import datetime, timezone


class TestLocalMemoryProviderCacheIntegration:
    """Test cache integration in LocalMemoryProvider."""

    @pytest.fixture
    def provider_with_cache(self):
        """Create provider with caching enabled."""
        from src.memory.providers.local import LocalMemoryProvider

        return LocalMemoryProvider(use_cache=True, cache_ttl_seconds=60)

    @pytest.fixture
    def provider_without_cache(self):
        """Create provider without caching (default)."""
        from src.memory.providers.local import LocalMemoryProvider

        return LocalMemoryProvider(use_cache=False)

    @pytest.fixture
    def sample_memory(self):
        """Create a sample memory for testing."""
        from src.memory.schemas import Memory, MemoryType

        return Memory(
            user_id="user-123",
            content="Test memory content",
            memory_type=MemoryType.FACT,
            source="test",
        )

    def test_cache_disabled_by_default(self):
        """Cache should be disabled by default."""
        from src.memory.providers.local import LocalMemoryProvider

        provider = LocalMemoryProvider()
        assert provider.use_cache is False

    def test_cache_enabled_with_parameter(self):
        """Cache should be enabled with use_cache=True."""
        from src.memory.providers.local import LocalMemoryProvider

        provider = LocalMemoryProvider(use_cache=True)
        assert provider.use_cache is True

    @pytest.mark.asyncio
    async def test_retrieve_caches_results(self, provider_with_cache, sample_memory):
        """Retrieved results should be cached."""
        # Store a memory
        await provider_with_cache.store(sample_memory, {})

        # First retrieval - cache miss
        results1 = await provider_with_cache.retrieve(
            user_id="user-123",
            query="test memory",
            limit=10,
        )

        # Second retrieval - should be cache hit
        results2 = await provider_with_cache.retrieve(
            user_id="user-123",
            query="test memory",
            limit=10,
        )

        # Results should be the same
        assert results1 == results2

        # Cache should report hit
        metrics = provider_with_cache.get_cache_metrics()
        assert metrics["hits"] >= 1

    @pytest.mark.asyncio
    async def test_cache_invalidated_on_store(self, provider_with_cache, sample_memory):
        """Cache should be invalidated when storing new memory."""
        from src.memory.schemas import Memory, MemoryType

        # Store initial memory
        await provider_with_cache.store(sample_memory, {})

        # Retrieve to populate cache
        await provider_with_cache.retrieve(
            user_id="user-123",
            query="test memory",
            limit=10,
        )

        # Store new memory - should invalidate cache
        new_memory = Memory(
            user_id="user-123",
            content="New memory content",
            memory_type=MemoryType.FACT,
            source="test",
        )
        await provider_with_cache.store(new_memory, {})

        # Cache for user should be invalidated
        # Next retrieve should be a miss
        metrics_before = provider_with_cache.get_cache_metrics()
        misses_before = metrics_before["misses"]

        await provider_with_cache.retrieve(
            user_id="user-123",
            query="test memory",
            limit=10,
        )

        metrics_after = provider_with_cache.get_cache_metrics()
        # Should have at least one more miss
        assert metrics_after["misses"] > misses_before

    @pytest.mark.asyncio
    async def test_cache_invalidated_on_delete(self, provider_with_cache, sample_memory):
        """Cache should be invalidated when deleting memory."""
        # Store memory
        memory_id = await provider_with_cache.store(sample_memory, {})

        # Retrieve to populate cache
        await provider_with_cache.retrieve(
            user_id="user-123",
            query="test memory",
            limit=10,
        )

        # Delete memory - should invalidate cache
        await provider_with_cache.delete(memory_id)

        # Next retrieve should be a cache miss
        # (cache was invalidated for user)

    @pytest.mark.asyncio
    async def test_cache_cleared_on_clear(self, provider_with_cache, sample_memory):
        """Cache should be cleared when clearing all memories."""
        # Store memory
        await provider_with_cache.store(sample_memory, {})

        # Retrieve to populate cache
        await provider_with_cache.retrieve(
            user_id="user-123",
            query="test memory",
            limit=10,
        )

        # Clear all memories
        provider_with_cache.clear()

        # Cache should be empty
        metrics = provider_with_cache.get_cache_metrics()
        assert metrics["size"] == 0

    @pytest.mark.asyncio
    async def test_no_cache_when_disabled(self, provider_without_cache, sample_memory):
        """No caching should occur when disabled."""
        # Store memory
        await provider_without_cache.store(sample_memory, {})

        # Retrieve twice
        await provider_without_cache.retrieve(
            user_id="user-123",
            query="test memory",
            limit=10,
        )
        await provider_without_cache.retrieve(
            user_id="user-123",
            query="test memory",
            limit=10,
        )

        # get_cache_metrics should indicate no cache
        metrics = provider_without_cache.get_cache_metrics()
        assert metrics["enabled"] is False

    @pytest.mark.asyncio
    async def test_cache_different_users_isolated(self, provider_with_cache):
        """Cache should be isolated per user."""
        from src.memory.schemas import Memory, MemoryType

        # Store memories for two users
        memory1 = Memory(
            user_id="user-1",
            content="User 1 memory",
            memory_type=MemoryType.FACT,
            source="test",
        )
        memory2 = Memory(
            user_id="user-2",
            content="User 2 memory",
            memory_type=MemoryType.FACT,
            source="test",
        )

        await provider_with_cache.store(memory1, {})
        await provider_with_cache.store(memory2, {})

        # Retrieve for user-1
        results1 = await provider_with_cache.retrieve(
            user_id="user-1",
            query="memory",
            limit=10,
        )

        # Retrieve for user-2
        results2 = await provider_with_cache.retrieve(
            user_id="user-2",
            query="memory",
            limit=10,
        )

        # Results should be different
        assert results1 != results2

    @pytest.mark.asyncio
    async def test_cache_different_queries_isolated(self, provider_with_cache, sample_memory):
        """Cache should be isolated per query."""
        await provider_with_cache.store(sample_memory, {})

        # Different queries should have separate cache entries
        results1 = await provider_with_cache.retrieve(
            user_id="user-123",
            query="query one",
            limit=10,
        )

        results2 = await provider_with_cache.retrieve(
            user_id="user-123",
            query="query two",
            limit=10,
        )

        # Both should be cache misses
        metrics = provider_with_cache.get_cache_metrics()
        assert metrics["misses"] >= 2


class TestCacheMetrics:
    """Test cache metrics exposure."""

    @pytest.fixture
    def provider(self):
        """Create provider with caching enabled."""
        from src.memory.providers.local import LocalMemoryProvider

        return LocalMemoryProvider(use_cache=True)

    def test_get_cache_metrics_returns_dict(self, provider):
        """get_cache_metrics should return a dictionary."""
        metrics = provider.get_cache_metrics()

        assert isinstance(metrics, dict)

    def test_cache_metrics_include_standard_fields(self, provider):
        """Cache metrics should include standard fields."""
        metrics = provider.get_cache_metrics()

        assert "enabled" in metrics
        assert "size" in metrics
        assert "hits" in metrics
        assert "misses" in metrics
        assert "hit_rate" in metrics

    @pytest.mark.asyncio
    async def test_hit_rate_calculation(self, provider):
        """Hit rate should be calculated correctly."""
        from src.memory.schemas import Memory, MemoryType

        memory = Memory(
            user_id="user-123",
            content="Test content",
            memory_type=MemoryType.FACT,
            source="test",
        )
        await provider.store(memory, {})

        # First call - miss
        await provider.retrieve(user_id="user-123", query="test", limit=10)

        # Second call - hit
        await provider.retrieve(user_id="user-123", query="test", limit=10)

        # Third call - hit
        await provider.retrieve(user_id="user-123", query="test", limit=10)

        metrics = provider.get_cache_metrics()
        # 2 hits out of 3 calls = 66.7%
        assert metrics["hit_rate"] == pytest.approx(2 / 3, rel=0.01)


class TestCacheConfiguration:
    """Test cache configuration options."""

    def test_custom_ttl(self):
        """Cache TTL should be configurable."""
        from src.memory.providers.local import LocalMemoryProvider

        provider = LocalMemoryProvider(use_cache=True, cache_ttl_seconds=120)

        # Should be reflected in metrics or config
        assert provider.cache_ttl_seconds == 120

    def test_custom_max_size(self):
        """Cache max size should be configurable."""
        from src.memory.providers.local import LocalMemoryProvider

        provider = LocalMemoryProvider(use_cache=True, cache_max_size=500)

        assert provider.cache_max_size == 500
