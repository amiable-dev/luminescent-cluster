"""Tests for retrieval cache (ADR-003 Option G).

TDD RED phase: These tests define the expected API for LRU cache with TTL.

Cache Strategy:
- LRU cache with configurable TTL
- Key: (user_id, query_hash)
- Invalidation on memory store/delete
- Metrics: hit rate, memory usage

Target: 75-90% cost reduction for repeated queries.
"""

import pytest
import time
from datetime import timedelta
from unittest.mock import Mock


class TestRetrievalCacheCreation:
    """Test RetrievalCache instantiation."""

    def test_cache_creation_with_defaults(self):
        """Cache should be instantiated with default settings."""
        from luminescent_cluster.memory.retrieval.cache import RetrievalCache

        cache = RetrievalCache()

        assert cache.max_size > 0
        assert cache.ttl_seconds > 0

    def test_cache_creation_with_custom_settings(self):
        """Cache should accept custom max_size and TTL."""
        from luminescent_cluster.memory.retrieval.cache import RetrievalCache

        cache = RetrievalCache(max_size=100, ttl_seconds=300)

        assert cache.max_size == 100
        assert cache.ttl_seconds == 300

    def test_cache_initially_empty(self):
        """New cache should be empty."""
        from luminescent_cluster.memory.retrieval.cache import RetrievalCache

        cache = RetrievalCache()

        assert cache.size() == 0
        assert cache.hit_rate() == 0.0


class TestCacheKeyGeneration:
    """Test cache key generation."""

    def test_generate_key_from_user_and_query(self):
        """Key should be generated from user_id and query."""
        from luminescent_cluster.memory.retrieval.cache import RetrievalCache

        cache = RetrievalCache()

        key1 = cache.generate_key(user_id="user-123", query="auth decisions")
        key2 = cache.generate_key(user_id="user-123", query="auth decisions")
        key3 = cache.generate_key(user_id="user-456", query="auth decisions")

        assert key1 == key2  # Same user, same query
        assert key1 != key3  # Different user

    def test_key_includes_optional_params(self):
        """Key should incorporate optional parameters."""
        from luminescent_cluster.memory.retrieval.cache import RetrievalCache

        cache = RetrievalCache()

        key1 = cache.generate_key(user_id="user-123", query="test", limit=10)
        key2 = cache.generate_key(user_id="user-123", query="test", limit=20)

        assert key1 != key2  # Different limits

    def test_key_is_deterministic(self):
        """Same inputs should always produce same key."""
        from luminescent_cluster.memory.retrieval.cache import RetrievalCache

        cache = RetrievalCache()

        keys = [
            cache.generate_key(user_id="user-123", query="test query")
            for _ in range(10)
        ]

        assert len(set(keys)) == 1  # All keys should be identical


class TestCacheOperations:
    """Test basic cache get/set operations."""

    def test_set_and_get(self):
        """Should store and retrieve cached results."""
        from luminescent_cluster.memory.retrieval.cache import RetrievalCache

        cache = RetrievalCache()
        results = [{"id": "mem-1", "content": "test"}]

        cache.set(
            user_id="user-123",
            query="auth decisions",
            results=results,
        )

        cached = cache.get(user_id="user-123", query="auth decisions")

        assert cached is not None
        assert cached == results

    def test_get_miss_returns_none(self):
        """Cache miss should return None."""
        from luminescent_cluster.memory.retrieval.cache import RetrievalCache

        cache = RetrievalCache()

        result = cache.get(user_id="user-123", query="nonexistent")

        assert result is None

    def test_size_increases_on_set(self):
        """Cache size should increase when items are added."""
        from luminescent_cluster.memory.retrieval.cache import RetrievalCache

        cache = RetrievalCache()

        cache.set(user_id="user-1", query="q1", results=[])
        assert cache.size() == 1

        cache.set(user_id="user-2", query="q2", results=[])
        assert cache.size() == 2


class TestCacheTTL:
    """Test TTL expiration."""

    def test_entry_expires_after_ttl(self):
        """Cached entry should expire after TTL."""
        from luminescent_cluster.memory.retrieval.cache import RetrievalCache

        cache = RetrievalCache(ttl_seconds=1)  # 1 second TTL

        cache.set(user_id="user-123", query="test", results=["data"])
        assert cache.get(user_id="user-123", query="test") is not None

        time.sleep(1.1)  # Wait for expiration

        assert cache.get(user_id="user-123", query="test") is None

    def test_fresh_entry_not_expired(self):
        """Recently cached entry should not be expired."""
        from luminescent_cluster.memory.retrieval.cache import RetrievalCache

        cache = RetrievalCache(ttl_seconds=60)

        cache.set(user_id="user-123", query="test", results=["data"])

        # Should still be valid
        assert cache.get(user_id="user-123", query="test") is not None

    def test_ttl_refresh_on_access(self):
        """TTL should optionally refresh on access."""
        from luminescent_cluster.memory.retrieval.cache import RetrievalCache

        cache = RetrievalCache(ttl_seconds=2, refresh_on_access=True)

        cache.set(user_id="user-123", query="test", results=["data"])
        time.sleep(1)  # 1 second elapsed

        # Access refreshes TTL
        assert cache.get(user_id="user-123", query="test") is not None

        time.sleep(1)  # Another 1 second (total 2 seconds, but TTL was refreshed)
        assert cache.get(user_id="user-123", query="test") is not None


class TestCacheLRU:
    """Test LRU eviction."""

    def test_lru_eviction_on_max_size(self):
        """Oldest entry should be evicted when max size reached."""
        from luminescent_cluster.memory.retrieval.cache import RetrievalCache

        cache = RetrievalCache(max_size=3)

        cache.set(user_id="user-1", query="q1", results=["first"])
        cache.set(user_id="user-2", query="q2", results=["second"])
        cache.set(user_id="user-3", query="q3", results=["third"])

        # Cache full, add fourth item
        cache.set(user_id="user-4", query="q4", results=["fourth"])

        # First entry should be evicted
        assert cache.get(user_id="user-1", query="q1") is None
        assert cache.get(user_id="user-4", query="q4") is not None

    def test_recently_accessed_not_evicted(self):
        """Recently accessed entries should not be evicted."""
        from luminescent_cluster.memory.retrieval.cache import RetrievalCache

        cache = RetrievalCache(max_size=3)

        cache.set(user_id="user-1", query="q1", results=["first"])
        cache.set(user_id="user-2", query="q2", results=["second"])
        cache.set(user_id="user-3", query="q3", results=["third"])

        # Access first entry to make it recent
        cache.get(user_id="user-1", query="q1")

        # Add fourth - should evict second (oldest non-accessed)
        cache.set(user_id="user-4", query="q4", results=["fourth"])

        # First should still be present (recently accessed)
        assert cache.get(user_id="user-1", query="q1") is not None
        # Second should be evicted
        assert cache.get(user_id="user-2", query="q2") is None


class TestCacheInvalidation:
    """Test cache invalidation."""

    def test_invalidate_by_user(self):
        """Should invalidate all entries for a user."""
        from luminescent_cluster.memory.retrieval.cache import RetrievalCache

        cache = RetrievalCache()

        cache.set(user_id="user-123", query="q1", results=["data1"])
        cache.set(user_id="user-123", query="q2", results=["data2"])
        cache.set(user_id="user-456", query="q3", results=["data3"])

        cache.invalidate_user("user-123")

        assert cache.get(user_id="user-123", query="q1") is None
        assert cache.get(user_id="user-123", query="q2") is None
        assert cache.get(user_id="user-456", query="q3") is not None

    def test_invalidate_all(self):
        """Should clear entire cache."""
        from luminescent_cluster.memory.retrieval.cache import RetrievalCache

        cache = RetrievalCache()

        cache.set(user_id="user-1", query="q1", results=["data1"])
        cache.set(user_id="user-2", query="q2", results=["data2"])

        cache.invalidate_all()

        assert cache.size() == 0

    def test_invalidate_returns_count(self):
        """Invalidation should return count of evicted entries."""
        from luminescent_cluster.memory.retrieval.cache import RetrievalCache

        cache = RetrievalCache()

        cache.set(user_id="user-123", query="q1", results=["data1"])
        cache.set(user_id="user-123", query="q2", results=["data2"])

        count = cache.invalidate_user("user-123")

        assert count == 2


class TestCacheMetrics:
    """Test cache metrics."""

    def test_hit_rate_calculation(self):
        """Hit rate should be calculated correctly."""
        from luminescent_cluster.memory.retrieval.cache import RetrievalCache

        cache = RetrievalCache()

        cache.set(user_id="user-123", query="test", results=["data"])

        # 3 hits
        for _ in range(3):
            cache.get(user_id="user-123", query="test")

        # 2 misses
        for _ in range(2):
            cache.get(user_id="user-123", query="nonexistent")

        # Hit rate = 3 / 5 = 0.6
        assert cache.hit_rate() == pytest.approx(0.6, rel=0.01)

    def test_metrics_include_size(self):
        """Metrics should include current cache size."""
        from luminescent_cluster.memory.retrieval.cache import RetrievalCache

        cache = RetrievalCache(max_size=100)

        cache.set(user_id="user-1", query="q1", results=["data1"])
        cache.set(user_id="user-2", query="q2", results=["data2"])

        metrics = cache.get_metrics()

        assert metrics["size"] == 2
        assert metrics["max_size"] == 100

    def test_metrics_include_hits_and_misses(self):
        """Metrics should include hit and miss counts."""
        from luminescent_cluster.memory.retrieval.cache import RetrievalCache

        cache = RetrievalCache()

        cache.set(user_id="user-123", query="test", results=["data"])
        cache.get(user_id="user-123", query="test")  # hit
        cache.get(user_id="user-123", query="miss")  # miss

        metrics = cache.get_metrics()

        assert metrics["hits"] == 1
        assert metrics["misses"] == 1


class TestCacheThreadSafety:
    """Test thread safety."""

    def test_concurrent_access(self):
        """Cache should handle concurrent access."""
        from luminescent_cluster.memory.retrieval.cache import RetrievalCache
        import threading

        cache = RetrievalCache(max_size=1000)
        errors = []

        def writer(thread_id: int):
            try:
                for i in range(100):
                    cache.set(
                        user_id=f"user-{thread_id}",
                        query=f"q-{i}",
                        results=[f"data-{thread_id}-{i}"],
                    )
            except Exception as e:
                errors.append(e)

        def reader(thread_id: int):
            try:
                for i in range(100):
                    cache.get(user_id=f"user-{thread_id}", query=f"q-{i}")
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(5):
            threads.append(threading.Thread(target=writer, args=(i,)))
            threads.append(threading.Thread(target=reader, args=(i,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


class TestCacheSerialization:
    """Test cache serialization for persistence."""

    def test_cache_to_dict(self):
        """Cache should serialize to dictionary."""
        from luminescent_cluster.memory.retrieval.cache import RetrievalCache

        cache = RetrievalCache(max_size=100, ttl_seconds=300)

        cache.set(user_id="user-123", query="test", results=["data"])

        data = cache.to_dict()

        assert "entries" in data
        assert "config" in data
        assert data["config"]["max_size"] == 100

    def test_cache_from_dict(self):
        """Cache should deserialize from dictionary."""
        from luminescent_cluster.memory.retrieval.cache import RetrievalCache

        original = RetrievalCache(max_size=50, ttl_seconds=120)
        original.set(user_id="user-123", query="test", results=["data"])

        data = original.to_dict()
        restored = RetrievalCache.from_dict(data)

        assert restored.max_size == 50
        assert restored.get(user_id="user-123", query="test") is not None
