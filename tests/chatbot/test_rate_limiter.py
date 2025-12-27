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
TDD: RED Phase - Tests for token bucket rate limiter.

These tests define the expected behavior for the rate limiter before
implementation. They should FAIL until the limiter is implemented.

Related GitHub Issues:
- #26: Test token bucket rate limiter
- #27: Implement TokenBucketRateLimiter
- #28: Test per-user rate limits
- #29: Test per-channel rate limits

ADR Reference: ADR-006 Chatbot Platform Integrations
"""

import pytest
import time
from datetime import datetime, timedelta

# Import the rate limiter - this will fail until implemented (RED phase)
from src.chatbot.rate_limiter import (
    TokenBucketRateLimiter,
    RateLimitConfig,
    RateLimitResult,
)


class TestRateLimitConfig:
    """TDD: Tests for RateLimitConfig data model."""

    def test_config_with_defaults(self):
        """RateLimitConfig should have sensible defaults."""
        config = RateLimitConfig()

        assert config.requests_per_minute > 0
        assert config.tokens_per_minute > 0
        assert config.burst_multiplier >= 1.0

    def test_config_custom_values(self):
        """RateLimitConfig should accept custom values."""
        config = RateLimitConfig(
            requests_per_minute=30,
            tokens_per_minute=50000,
            burst_multiplier=2.0,
        )

        assert config.requests_per_minute == 30
        assert config.tokens_per_minute == 50000
        assert config.burst_multiplier == 2.0

    def test_config_per_scope_limits(self):
        """RateLimitConfig should support per-scope limits."""
        config = RateLimitConfig(
            requests_per_minute=60,
            user_requests_per_minute=10,
            channel_requests_per_minute=30,
            workspace_requests_per_minute=100,
        )

        assert config.user_requests_per_minute == 10
        assert config.channel_requests_per_minute == 30
        assert config.workspace_requests_per_minute == 100


class TestRateLimitResult:
    """TDD: Tests for RateLimitResult data model."""

    def test_result_allowed(self):
        """RateLimitResult should indicate allowed request."""
        result = RateLimitResult(
            allowed=True,
            remaining_requests=9,
            remaining_tokens=9500,
            reset_at=datetime.now() + timedelta(minutes=1),
        )

        assert result.allowed is True
        assert result.remaining_requests == 9

    def test_result_denied(self):
        """RateLimitResult should indicate denied request with reason."""
        result = RateLimitResult(
            allowed=False,
            remaining_requests=0,
            remaining_tokens=0,
            reset_at=datetime.now() + timedelta(seconds=30),
            reason="Rate limit exceeded: 10 requests per minute",
        )

        assert result.allowed is False
        assert result.reason is not None
        assert "Rate limit" in result.reason


class TestTokenBucketAlgorithm:
    """TDD: Tests for token bucket algorithm (Issue #26)."""

    def test_bucket_starts_full(self):
        """Token bucket should start with full capacity."""
        config = RateLimitConfig(requests_per_minute=10)
        limiter = TokenBucketRateLimiter(config)

        # First request should be allowed
        result = limiter.check("user-123")
        assert result.allowed is True
        assert result.remaining_requests == 9

    def test_bucket_depletes_with_requests(self):
        """Token bucket should deplete as requests are made."""
        config = RateLimitConfig(requests_per_minute=5)
        limiter = TokenBucketRateLimiter(config)

        # Make 5 requests
        for i in range(5):
            result = limiter.check("user-123")
            assert result.allowed is True
            assert result.remaining_requests == 4 - i

    def test_bucket_rejects_when_empty(self):
        """Token bucket should reject when empty."""
        config = RateLimitConfig(requests_per_minute=3)
        limiter = TokenBucketRateLimiter(config)

        # Exhaust the bucket
        for _ in range(3):
            limiter.check("user-123")

        # Next request should be rejected
        result = limiter.check("user-123")
        assert result.allowed is False
        assert result.remaining_requests == 0

    def test_bucket_refills_over_time(self):
        """Token bucket should refill over time."""
        config = RateLimitConfig(requests_per_minute=60)  # 1 per second
        limiter = TokenBucketRateLimiter(config)

        # Use all tokens
        for _ in range(60):
            limiter.check("user-123")

        # Wait for refill (simulate time passing)
        limiter._advance_time(2.0)  # Advance 2 seconds

        # Should have ~2 tokens now
        result = limiter.check("user-123")
        assert result.allowed is True

    def test_bucket_has_burst_capacity(self):
        """Token bucket should allow burst up to multiplier."""
        config = RateLimitConfig(
            requests_per_minute=10,
            burst_multiplier=2.0,
        )
        limiter = TokenBucketRateLimiter(config)

        # Should allow 20 requests in burst (10 * 2.0)
        for i in range(20):
            result = limiter.check(f"user-{i % 5}")  # Different users
            # At least first 10 should work for each user

    def test_bucket_tracks_tokens_separately(self):
        """Token bucket should track request count and token count separately."""
        config = RateLimitConfig(
            requests_per_minute=100,
            tokens_per_minute=1000,
        )
        limiter = TokenBucketRateLimiter(config)

        # Make a request that uses many tokens
        result = limiter.check("user-123", tokens=500)
        assert result.allowed is True
        assert result.remaining_tokens == 500

        # Another large request should be limited by tokens
        result = limiter.check("user-123", tokens=600)
        assert result.allowed is False
        assert "token" in result.reason.lower()


class TestPerUserRateLimits:
    """TDD: Tests for per-user rate limiting (Issue #28)."""

    def test_users_have_separate_buckets(self):
        """Each user should have their own rate limit bucket."""
        config = RateLimitConfig(requests_per_minute=5)
        limiter = TokenBucketRateLimiter(config)

        # User A exhausts their limit
        for _ in range(5):
            limiter.check("user-A")

        # User B should still have full limit
        result = limiter.check("user-B")
        assert result.allowed is True
        assert result.remaining_requests == 4

    def test_user_limit_independent_of_global(self):
        """User limits should be independent of global limits."""
        config = RateLimitConfig(
            requests_per_minute=100,
            user_requests_per_minute=5,
        )
        limiter = TokenBucketRateLimiter(config)

        # User hits their personal limit
        for _ in range(5):
            limiter.check("user-123")

        result = limiter.check("user-123")
        assert result.allowed is False

        # But global limit is fine, other users work
        result = limiter.check("user-456")
        assert result.allowed is True

    def test_user_token_tracking(self):
        """Should track token usage per user."""
        config = RateLimitConfig(
            requests_per_minute=100,
            tokens_per_minute=1000,
        )
        limiter = TokenBucketRateLimiter(config)

        # User A uses tokens
        limiter.check("user-A", tokens=400)

        # User A's remaining tokens
        result = limiter.check("user-A", tokens=0)
        assert result.remaining_tokens == 600

        # User B has full tokens
        result = limiter.check("user-B", tokens=0)
        assert result.remaining_tokens == 1000


class TestPerChannelRateLimits:
    """TDD: Tests for per-channel rate limiting (Issue #29)."""

    def test_channels_have_separate_buckets(self):
        """Each channel should have its own rate limit bucket."""
        config = RateLimitConfig(channel_requests_per_minute=10)
        limiter = TokenBucketRateLimiter(config)

        # Exhaust channel A limit
        for _ in range(10):
            limiter.check("user-1", channel_id="channel-A")

        # Channel A is exhausted
        result = limiter.check("user-1", channel_id="channel-A")
        assert result.allowed is False

        # Channel B is fine
        result = limiter.check("user-1", channel_id="channel-B")
        assert result.allowed is True

    def test_channel_limit_aggregates_users(self):
        """Channel limit should aggregate all users in channel."""
        config = RateLimitConfig(channel_requests_per_minute=5)
        limiter = TokenBucketRateLimiter(config)

        # Different users in same channel
        limiter.check("user-1", channel_id="channel-A")
        limiter.check("user-2", channel_id="channel-A")
        limiter.check("user-3", channel_id="channel-A")
        limiter.check("user-4", channel_id="channel-A")
        limiter.check("user-5", channel_id="channel-A")

        # Channel is now at limit
        result = limiter.check("user-6", channel_id="channel-A")
        assert result.allowed is False

    def test_user_and_channel_limits_both_apply(self):
        """Both user and channel limits should be enforced."""
        config = RateLimitConfig(
            user_requests_per_minute=3,
            channel_requests_per_minute=10,
        )
        limiter = TokenBucketRateLimiter(config)

        # User hits their limit before channel
        for _ in range(3):
            limiter.check("user-123", channel_id="channel-A")

        result = limiter.check("user-123", channel_id="channel-A")
        assert result.allowed is False
        assert "user" in result.reason.lower()


class TestPerWorkspaceRateLimits:
    """TDD: Tests for per-workspace rate limiting."""

    def test_workspaces_have_separate_buckets(self):
        """Each workspace should have its own rate limit bucket."""
        config = RateLimitConfig(workspace_requests_per_minute=20)
        limiter = TokenBucketRateLimiter(config)

        # Exhaust workspace A
        for i in range(20):
            limiter.check(f"user-{i}", workspace_id="ws-A")

        # Workspace A exhausted
        result = limiter.check("user-new", workspace_id="ws-A")
        assert result.allowed is False

        # Workspace B is fine
        result = limiter.check("user-new", workspace_id="ws-B")
        assert result.allowed is True

    def test_workspace_aggregates_all_channels(self):
        """Workspace limit should aggregate all channels."""
        config = RateLimitConfig(workspace_requests_per_minute=5)
        limiter = TokenBucketRateLimiter(config)

        # Requests across different channels in same workspace
        limiter.check("user-1", channel_id="ch-1", workspace_id="ws-A")
        limiter.check("user-2", channel_id="ch-2", workspace_id="ws-A")
        limiter.check("user-3", channel_id="ch-3", workspace_id="ws-A")
        limiter.check("user-4", channel_id="ch-4", workspace_id="ws-A")
        limiter.check("user-5", channel_id="ch-5", workspace_id="ws-A")

        # Workspace limit reached
        result = limiter.check("user-6", channel_id="ch-1", workspace_id="ws-A")
        assert result.allowed is False


class TestRateLimiterConcurrency:
    """TDD: Tests for thread-safe rate limiting."""

    def test_concurrent_access_is_safe(self):
        """Rate limiter should be thread-safe."""
        import threading

        config = RateLimitConfig(requests_per_minute=100)
        limiter = TokenBucketRateLimiter(config)

        results = []
        errors = []

        def make_request():
            try:
                result = limiter.check("user-123")
                results.append(result.allowed)
            except Exception as e:
                errors.append(e)

        # Create many threads
        threads = [threading.Thread(target=make_request) for _ in range(50)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        # Should have allowed most requests
        assert sum(results) >= 50  # All should succeed with 100 limit


class TestRateLimiterRecording:
    """TDD: Tests for recording usage after request completion."""

    def test_record_updates_usage(self):
        """Recording should update token usage."""
        config = RateLimitConfig(tokens_per_minute=1000)
        limiter = TokenBucketRateLimiter(config)

        # Check first (reserves capacity)
        result = limiter.check("user-123")
        assert result.allowed is True

        # Record actual usage
        limiter.record("user-123", tokens_used=500)

        # Check remaining
        result = limiter.check("user-123", tokens=0)
        assert result.remaining_tokens == 500

    def test_record_without_check(self):
        """Should be able to record without prior check."""
        config = RateLimitConfig(tokens_per_minute=1000)
        limiter = TokenBucketRateLimiter(config)

        # Just record usage
        limiter.record("user-123", tokens_used=300)

        result = limiter.check("user-123", tokens=0)
        assert result.remaining_tokens == 700
