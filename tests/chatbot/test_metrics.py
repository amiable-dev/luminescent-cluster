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
TDD: RED Phase - Tests for ChatMetrics telemetry.

These tests define the expected behavior for the ChatMetrics telemetry class.
They should FAIL until the implementation is complete.

Related GitHub Issues:
- #66: Test ChatMetrics telemetry (this file)
- #67: Implement ChatMetrics class

ADR Reference: ADR-006 Chatbot Platform Integrations
"""

import pytest
from datetime import datetime
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

from luminescent_cluster.chatbot.metrics import ChatMetrics, QueryMetric


class TestChatMetricsClass:
    """Tests for ChatMetrics class existence and basic properties."""

    def test_chat_metrics_exists(self):
        """ChatMetrics class should exist."""
        assert ChatMetrics is not None

    def test_chat_metrics_instantiates(self):
        """ChatMetrics should be instantiable."""
        metrics = ChatMetrics()
        assert metrics is not None

    def test_query_metric_dataclass_exists(self):
        """QueryMetric dataclass should exist for individual metrics."""
        assert QueryMetric is not None


class TestRecordQuery:
    """Tests for record_query method per ADR-006 spec."""

    @pytest.mark.asyncio
    async def test_record_query_exists(self):
        """ChatMetrics should have async record_query method."""
        metrics = ChatMetrics()
        assert hasattr(metrics, "record_query")

    @pytest.mark.asyncio
    async def test_record_query_accepts_required_fields(self):
        """record_query should accept all ADR-006 required fields."""
        metrics = ChatMetrics()

        # ADR-006 spec: record_query signature
        await metrics.record_query(
            platform="discord",
            user_id="user-123",
            query_type="chat",
            latency_ms=150,
            tokens_used=100,
            memory_hits=5,
        )

        # Should not raise

    @pytest.mark.asyncio
    async def test_record_query_stores_metrics(self):
        """record_query should store metrics for retrieval."""
        metrics = ChatMetrics()

        await metrics.record_query(
            platform="slack",
            user_id="user-456",
            query_type="command",
            latency_ms=200,
            tokens_used=50,
            memory_hits=2,
        )

        # Should be able to retrieve metrics
        all_metrics = metrics.get_metrics()
        assert len(all_metrics) == 1
        assert all_metrics[0].platform == "slack"
        assert all_metrics[0].latency_ms == 200


class TestLatencyTracking:
    """Tests for latency tracking by platform."""

    @pytest.mark.asyncio
    async def test_latency_tracked_per_platform(self):
        """Latency should be tracked separately per platform."""
        metrics = ChatMetrics()

        # Record metrics for different platforms
        await metrics.record_query("discord", "u1", "chat", 100, 50, 1)
        await metrics.record_query("discord", "u2", "chat", 200, 50, 1)
        await metrics.record_query("slack", "u3", "chat", 150, 50, 1)

        # Get latency stats
        discord_stats = metrics.get_latency_stats("discord")
        slack_stats = metrics.get_latency_stats("slack")

        assert discord_stats["count"] == 2
        assert discord_stats["avg_ms"] == 150  # (100+200)/2
        assert slack_stats["count"] == 1
        assert slack_stats["avg_ms"] == 150

    @pytest.mark.asyncio
    async def test_latency_percentiles(self):
        """Should calculate p50 and p95 latency."""
        metrics = ChatMetrics()

        # Record several metrics
        for i in range(100):
            await metrics.record_query("discord", "u1", "chat", i * 10, 50, 1)

        stats = metrics.get_latency_stats("discord")

        assert "p50" in stats
        assert "p95" in stats
        assert stats["p50"] <= stats["p95"]


class TestMemoryRelevance:
    """Tests for memory retrieval relevance calculation."""

    @pytest.mark.asyncio
    async def test_memory_relevance_calculated(self):
        """Memory relevance should be memory_hits / tokens_used."""
        metrics = ChatMetrics()

        await metrics.record_query(
            platform="discord",
            user_id="u1",
            query_type="chat",
            latency_ms=100,
            tokens_used=100,
            memory_hits=25,
        )

        all_metrics = metrics.get_metrics()
        assert all_metrics[0].memory_relevance == 0.25  # 25/100

    @pytest.mark.asyncio
    async def test_memory_relevance_handles_zero_tokens(self):
        """Memory relevance should handle zero tokens gracefully."""
        metrics = ChatMetrics()

        await metrics.record_query(
            platform="discord",
            user_id="u1",
            query_type="chat",
            latency_ms=100,
            tokens_used=0,
            memory_hits=5,
        )

        all_metrics = metrics.get_metrics()
        assert all_metrics[0].memory_relevance == 0.0  # Avoid division by zero


class TestTokenUsageTracking:
    """Tests for token usage tracking."""

    @pytest.mark.asyncio
    async def test_token_usage_aggregated(self):
        """Token usage should be aggregated."""
        metrics = ChatMetrics()

        await metrics.record_query("discord", "u1", "chat", 100, 50, 1)
        await metrics.record_query("discord", "u2", "chat", 100, 75, 1)
        await metrics.record_query("slack", "u3", "chat", 100, 100, 1)

        total = metrics.get_total_tokens()
        assert total == 225  # 50 + 75 + 100

    @pytest.mark.asyncio
    async def test_token_usage_by_platform(self):
        """Token usage should be available per platform."""
        metrics = ChatMetrics()

        await metrics.record_query("discord", "u1", "chat", 100, 50, 1)
        await metrics.record_query("discord", "u2", "chat", 100, 75, 1)
        await metrics.record_query("slack", "u3", "chat", 100, 100, 1)

        discord_tokens = metrics.get_tokens_by_platform("discord")
        slack_tokens = metrics.get_tokens_by_platform("slack")

        assert discord_tokens == 125
        assert slack_tokens == 100


class TestErrorTracking:
    """Tests for error rate tracking."""

    @pytest.mark.asyncio
    async def test_record_error(self):
        """ChatMetrics should track errors."""
        metrics = ChatMetrics()

        await metrics.record_error(
            platform="discord",
            error_type="timeout",
            provider="anthropic",
        )

        errors = metrics.get_errors()
        assert len(errors) == 1
        assert errors[0].error_type == "timeout"

    @pytest.mark.asyncio
    async def test_error_rate_by_provider(self):
        """Error rate should be calculable by provider."""
        metrics = ChatMetrics()

        # 3 successful queries, 1 error
        await metrics.record_query("discord", "u1", "chat", 100, 50, 1)
        await metrics.record_query("discord", "u2", "chat", 100, 50, 1)
        await metrics.record_query("discord", "u3", "chat", 100, 50, 1)
        await metrics.record_error("discord", "timeout", "anthropic")

        error_rate = metrics.get_error_rate("anthropic")
        assert error_rate == 0.25  # 1 error / 4 total


class TestMetricsExport:
    """Tests for metrics export."""

    @pytest.mark.asyncio
    async def test_export_to_dict(self):
        """Metrics should be exportable as dictionary."""
        metrics = ChatMetrics()

        await metrics.record_query("discord", "u1", "chat", 100, 50, 5)

        exported = metrics.export()

        assert "total_queries" in exported
        assert "total_tokens" in exported
        assert "platforms" in exported
        assert "latency" in exported

    @pytest.mark.asyncio
    async def test_metrics_reset(self):
        """Metrics should be clearable."""
        metrics = ChatMetrics()

        await metrics.record_query("discord", "u1", "chat", 100, 50, 5)
        assert len(metrics.get_metrics()) == 1

        metrics.reset()
        assert len(metrics.get_metrics()) == 0


class TestDegradedStatus:
    """Tests for degraded status detection."""

    @pytest.mark.asyncio
    async def test_detect_degraded_by_latency(self):
        """Should detect degraded status when latency exceeds threshold."""
        metrics = ChatMetrics(degraded_latency_threshold_ms=500)

        await metrics.record_query("discord", "u1", "chat", 600, 50, 1)

        assert metrics.is_degraded() is True

    @pytest.mark.asyncio
    async def test_not_degraded_under_threshold(self):
        """Should not be degraded when latency is under threshold."""
        metrics = ChatMetrics(degraded_latency_threshold_ms=500)

        await metrics.record_query("discord", "u1", "chat", 100, 50, 1)

        assert metrics.is_degraded() is False

    @pytest.mark.asyncio
    async def test_detect_degraded_by_error_rate(self):
        """Should detect degraded status when error rate exceeds threshold."""
        metrics = ChatMetrics(degraded_error_rate_threshold=0.1)

        # 9 successful, 2 errors = ~18% error rate
        for _ in range(9):
            await metrics.record_query("discord", "u1", "chat", 100, 50, 1)
        await metrics.record_error("discord", "error1", "anthropic")
        await metrics.record_error("discord", "error2", "anthropic")

        assert metrics.is_degraded() is True
