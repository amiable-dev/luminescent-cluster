# Copyright 2024-2025 Amiable Development
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
ChatMetrics - Telemetry for Luminescent Cluster chatbot.

Provides observability metrics for chatbot operations including:
- Query latency by platform (p50, p95)
- Memory retrieval relevance
- Token usage
- Error rates by provider
- Degraded status detection

Design (from ADR-006):
- Track query latency for performance monitoring
- Calculate memory_relevance as memory_hits / tokens_used
- Detect degraded status based on latency and error thresholds

Version: 1.0.0
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List, Any
import threading
import statistics
import logging

logger = logging.getLogger(__name__)


@dataclass
class QueryMetric:
    """
    Individual query metric record.

    Attributes:
        platform: Platform name (discord, slack, etc.)
        user_id: User who made the query
        query_type: Type of query (chat, command, etc.)
        latency_ms: Query latency in milliseconds
        tokens_used: Number of tokens used
        memory_hits: Number of memory retrieval hits
        memory_relevance: Calculated memory_hits / tokens_used
        timestamp: When the query was recorded
    """

    platform: str
    user_id: str
    query_type: str
    latency_ms: int
    tokens_used: int
    memory_hits: int
    memory_relevance: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Calculate memory relevance after initialization."""
        if self.tokens_used > 0:
            self.memory_relevance = self.memory_hits / self.tokens_used
        else:
            self.memory_relevance = 0.0


@dataclass
class ErrorMetric:
    """
    Error metric record.

    Attributes:
        platform: Platform where error occurred
        error_type: Type of error (timeout, rate_limit, etc.)
        provider: LLM provider that caused the error
        timestamp: When the error was recorded
    """

    platform: str
    error_type: str
    provider: str
    timestamp: datetime = field(default_factory=datetime.now)


class ChatMetrics:
    """
    Telemetry metrics for chatbot operations.

    Tracks query latency, memory relevance, token usage, and error rates.
    Thread-safe for concurrent access.

    Example:
        metrics = ChatMetrics()

        await metrics.record_query(
            platform="discord",
            user_id="user-123",
            query_type="chat",
            latency_ms=150,
            tokens_used=100,
            memory_hits=5,
        )

        stats = metrics.get_latency_stats("discord")
        print(f"Discord p50: {stats['p50']}ms")
    """

    def __init__(
        self,
        degraded_latency_threshold_ms: int = 5000,
        degraded_error_rate_threshold: float = 0.1,
    ):
        """
        Initialize ChatMetrics.

        Args:
            degraded_latency_threshold_ms: Latency threshold for degraded status
            degraded_error_rate_threshold: Error rate threshold for degraded status
        """
        self._lock = threading.RLock()
        self._metrics: List[QueryMetric] = []
        self._errors: List[ErrorMetric] = []

        self.degraded_latency_threshold_ms = degraded_latency_threshold_ms
        self.degraded_error_rate_threshold = degraded_error_rate_threshold

    async def record_query(
        self,
        platform: str,
        user_id: str,
        query_type: str,
        latency_ms: int,
        tokens_used: int,
        memory_hits: int,
    ) -> None:
        """
        Record a query metric (ADR-006 spec).

        Args:
            platform: Platform name (discord, slack, telegram, whatsapp)
            user_id: User who made the query
            query_type: Type of query (chat, command, etc.)
            latency_ms: Query latency in milliseconds
            tokens_used: Number of tokens used
            memory_hits: Number of memory retrieval hits
        """
        metric = QueryMetric(
            platform=platform,
            user_id=user_id,
            query_type=query_type,
            latency_ms=latency_ms,
            tokens_used=tokens_used,
            memory_hits=memory_hits,
        )

        with self._lock:
            self._metrics.append(metric)

        logger.debug(
            f"Recorded query: platform={platform}, latency={latency_ms}ms, "
            f"tokens={tokens_used}, memory_relevance={metric.memory_relevance:.2f}"
        )

    async def record_error(
        self,
        platform: str,
        error_type: str,
        provider: str,
    ) -> None:
        """
        Record an error metric.

        Args:
            platform: Platform where error occurred
            error_type: Type of error
            provider: LLM provider that caused the error
        """
        error = ErrorMetric(
            platform=platform,
            error_type=error_type,
            provider=provider,
        )

        with self._lock:
            self._errors.append(error)

        logger.warning(f"Recorded error: platform={platform}, type={error_type}")

    def get_metrics(self) -> List[QueryMetric]:
        """Get all recorded query metrics."""
        with self._lock:
            return list(self._metrics)

    def get_errors(self) -> List[ErrorMetric]:
        """Get all recorded error metrics."""
        with self._lock:
            return list(self._errors)

    def get_latency_stats(self, platform: str) -> Dict[str, Any]:
        """
        Get latency statistics for a platform.

        Args:
            platform: Platform name

        Returns:
            Dict with count, avg_ms, p50, p95 statistics
        """
        with self._lock:
            latencies = [m.latency_ms for m in self._metrics if m.platform == platform]

        if not latencies:
            return {"count": 0, "avg_ms": 0, "p50": 0, "p95": 0}

        latencies_sorted = sorted(latencies)
        count = len(latencies)

        return {
            "count": count,
            "avg_ms": sum(latencies) // count,
            "p50": self._percentile(latencies_sorted, 50),
            "p95": self._percentile(latencies_sorted, 95),
        }

    def _percentile(self, sorted_data: List[int], percentile: int) -> int:
        """Calculate percentile from sorted data."""
        if not sorted_data:
            return 0
        k = (len(sorted_data) - 1) * (percentile / 100)
        f = int(k)
        c = f + 1 if f < len(sorted_data) - 1 else f
        return int(sorted_data[f] + (sorted_data[c] - sorted_data[f]) * (k - f))

    def get_total_tokens(self) -> int:
        """Get total tokens used across all queries."""
        with self._lock:
            return sum(m.tokens_used for m in self._metrics)

    def get_tokens_by_platform(self, platform: str) -> int:
        """Get tokens used for a specific platform."""
        with self._lock:
            return sum(m.tokens_used for m in self._metrics if m.platform == platform)

    def get_error_rate(self, provider: Optional[str] = None) -> float:
        """
        Get error rate, optionally filtered by provider.

        Args:
            provider: Optional provider to filter by

        Returns:
            Error rate as float (0.0 to 1.0)
        """
        with self._lock:
            total_queries = len(self._metrics)
            if provider:
                error_count = sum(1 for e in self._errors if e.provider == provider)
            else:
                error_count = len(self._errors)

        total = total_queries + error_count
        if total == 0:
            return 0.0

        return error_count / total

    def is_degraded(self) -> bool:
        """
        Check if system is in degraded state.

        Degraded status is triggered when:
        - Recent latency exceeds threshold
        - Error rate exceeds threshold

        Returns:
            True if system is degraded
        """
        with self._lock:
            # Check latency threshold
            if self._metrics:
                recent_latency = self._metrics[-1].latency_ms
                if recent_latency > self.degraded_latency_threshold_ms:
                    return True

            # Check error rate threshold
            error_rate = self.get_error_rate()
            if error_rate > self.degraded_error_rate_threshold:
                return True

        return False

    def export(self) -> Dict[str, Any]:
        """
        Export metrics as dictionary.

        Returns:
            Dict containing all metrics data
        """
        with self._lock:
            platforms = set(m.platform for m in self._metrics)

            platform_stats = {}
            for platform in platforms:
                platform_stats[platform] = {
                    "queries": sum(1 for m in self._metrics if m.platform == platform),
                    "tokens": self.get_tokens_by_platform(platform),
                    "latency": self.get_latency_stats(platform),
                }

            return {
                "total_queries": len(self._metrics),
                "total_errors": len(self._errors),
                "total_tokens": self.get_total_tokens(),
                "platforms": platform_stats,
                "latency": {p: self.get_latency_stats(p) for p in platforms},
                "error_rate": self.get_error_rate(),
                "is_degraded": self.is_degraded(),
            }

    def reset(self) -> None:
        """Clear all recorded metrics."""
        with self._lock:
            self._metrics.clear()
            self._errors.clear()
        logger.info("Metrics reset")
