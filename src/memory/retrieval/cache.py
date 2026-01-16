"""Retrieval cache for provider-side caching (ADR-003 Option G).

LRU cache with TTL for reducing retrieval costs:
- Key: (user_id, query_hash)
- Automatic TTL expiration
- LRU eviction when max size reached
- Invalidation on memory store/delete
- Thread-safe operations

Target: 75-90% cost reduction for repeated queries.
"""

import hashlib
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class CacheEntry:
    """A cached retrieval result with metadata."""

    results: list[Any]
    created_at: float
    last_accessed_at: float
    user_id: str

    def is_expired(self, ttl_seconds: float) -> bool:
        """Check if this entry has expired."""
        return time.time() - self.created_at > ttl_seconds


class RetrievalCache:
    """LRU cache with TTL for retrieval results.

    Features:
    - Configurable max size and TTL
    - Automatic LRU eviction
    - TTL expiration
    - Per-user invalidation
    - Thread-safe operations
    - Hit/miss metrics
    """

    DEFAULT_MAX_SIZE = 1000
    DEFAULT_TTL_SECONDS = 3600  # 1 hour

    def __init__(
        self,
        max_size: int = DEFAULT_MAX_SIZE,
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
        refresh_on_access: bool = False,
    ) -> None:
        """Initialize the cache.

        Args:
            max_size: Maximum number of entries
            ttl_seconds: Time-to-live in seconds
            refresh_on_access: If True, TTL refreshes on access
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.refresh_on_access = refresh_on_access

        # OrderedDict maintains insertion order for LRU
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()

        # Metrics
        self._hits = 0
        self._misses = 0

        # Index for fast user-based invalidation
        self._user_keys: dict[str, set[str]] = {}

    def generate_key(
        self,
        user_id: str,
        query: str,
        limit: Optional[int] = None,
        **kwargs: Any,
    ) -> str:
        """Generate a cache key from query parameters.

        Args:
            user_id: User ID
            query: Query string
            limit: Optional result limit
            **kwargs: Additional parameters to include in key

        Returns:
            Hash-based cache key
        """
        # Build key components
        components = [user_id, query]
        if limit is not None:
            components.append(str(limit))
        for k, v in sorted(kwargs.items()):
            components.append(f"{k}={v}")

        # Create hash
        key_string = "|".join(components)
        return hashlib.sha256(key_string.encode()).hexdigest()[:32]

    def get(
        self,
        user_id: str,
        query: str,
        limit: Optional[int] = None,
        **kwargs: Any,
    ) -> Optional[list[Any]]:
        """Get cached results.

        Args:
            user_id: User ID
            query: Query string
            limit: Optional result limit

        Returns:
            Cached results or None if miss/expired
        """
        key = self.generate_key(user_id, query, limit, **kwargs)

        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._misses += 1
                return None

            if entry.is_expired(self.ttl_seconds):
                # Remove expired entry
                self._remove_entry(key, entry)
                self._misses += 1
                return None

            # Move to end for LRU
            self._cache.move_to_end(key)

            # Optionally refresh TTL
            if self.refresh_on_access:
                entry.created_at = time.time()

            entry.last_accessed_at = time.time()
            self._hits += 1

            return entry.results

    def set(
        self,
        user_id: str,
        query: str,
        results: list[Any],
        limit: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        """Cache retrieval results.

        Args:
            user_id: User ID
            query: Query string
            results: Results to cache
            limit: Optional result limit
        """
        key = self.generate_key(user_id, query, limit, **kwargs)
        now = time.time()

        with self._lock:
            # Check if we need to evict
            if len(self._cache) >= self.max_size and key not in self._cache:
                self._evict_oldest()

            # Create entry
            entry = CacheEntry(
                results=results,
                created_at=now,
                last_accessed_at=now,
                user_id=user_id,
            )

            # Store entry
            self._cache[key] = entry
            self._cache.move_to_end(key)

            # Update user index
            if user_id not in self._user_keys:
                self._user_keys[user_id] = set()
            self._user_keys[user_id].add(key)

    def invalidate_user(self, user_id: str) -> int:
        """Invalidate all entries for a user.

        Args:
            user_id: User ID to invalidate

        Returns:
            Number of entries invalidated
        """
        with self._lock:
            keys = self._user_keys.get(user_id, set()).copy()
            count = 0

            for key in keys:
                if key in self._cache:
                    entry = self._cache[key]
                    self._remove_entry(key, entry)
                    count += 1

            return count

    def invalidate_all(self) -> None:
        """Clear entire cache."""
        with self._lock:
            self._cache.clear()
            self._user_keys.clear()

    def size(self) -> int:
        """Get current cache size."""
        with self._lock:
            return len(self._cache)

    def hit_rate(self) -> float:
        """Get cache hit rate."""
        with self._lock:
            total = self._hits + self._misses
            if total == 0:
                return 0.0
            return self._hits / total

    def get_metrics(self) -> dict[str, Any]:
        """Get cache metrics.

        Returns:
            Dictionary with cache statistics
        """
        with self._lock:
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": self.hit_rate(),
                "ttl_seconds": self.ttl_seconds,
            }

    def _evict_oldest(self) -> None:
        """Evict the oldest entry (LRU)."""
        if self._cache:
            # Get oldest (first) item
            oldest_key = next(iter(self._cache))
            entry = self._cache[oldest_key]
            self._remove_entry(oldest_key, entry)

    def _remove_entry(self, key: str, entry: CacheEntry) -> None:
        """Remove an entry and update indexes."""
        if key in self._cache:
            del self._cache[key]

        # Update user index
        user_id = entry.user_id
        if user_id in self._user_keys and key in self._user_keys[user_id]:
            self._user_keys[user_id].discard(key)
            if not self._user_keys[user_id]:
                del self._user_keys[user_id]

    def to_dict(self) -> dict[str, Any]:
        """Serialize cache to dictionary.

        Returns:
            Dictionary representation
        """
        with self._lock:
            entries = {}
            for key, entry in self._cache.items():
                entries[key] = {
                    "results": entry.results,
                    "created_at": entry.created_at,
                    "last_accessed_at": entry.last_accessed_at,
                    "user_id": entry.user_id,
                }

            return {
                "config": {
                    "max_size": self.max_size,
                    "ttl_seconds": self.ttl_seconds,
                    "refresh_on_access": self.refresh_on_access,
                },
                "entries": entries,
                "metrics": {
                    "hits": self._hits,
                    "misses": self._misses,
                },
            }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RetrievalCache":
        """Deserialize cache from dictionary.

        Args:
            data: Dictionary representation

        Returns:
            RetrievalCache instance
        """
        config = data.get("config", {})
        cache = cls(
            max_size=config.get("max_size", cls.DEFAULT_MAX_SIZE),
            ttl_seconds=config.get("ttl_seconds", cls.DEFAULT_TTL_SECONDS),
            refresh_on_access=config.get("refresh_on_access", False),
        )

        # Restore entries
        for key, entry_data in data.get("entries", {}).items():
            entry = CacheEntry(
                results=entry_data["results"],
                created_at=entry_data["created_at"],
                last_accessed_at=entry_data["last_accessed_at"],
                user_id=entry_data["user_id"],
            )

            # Only restore non-expired entries
            if not entry.is_expired(cache.ttl_seconds):
                cache._cache[key] = entry

                # Update user index
                user_id = entry.user_id
                if user_id not in cache._user_keys:
                    cache._user_keys[user_id] = set()
                cache._user_keys[user_id].add(key)

        # Restore metrics
        metrics = data.get("metrics", {})
        cache._hits = metrics.get("hits", 0)
        cache._misses = metrics.get("misses", 0)

        return cache
