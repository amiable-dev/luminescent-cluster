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
Token bucket rate limiter for Luminescent Cluster chatbot.

Implements rate limiting with support for:
- Per-user limits
- Per-channel limits
- Per-workspace limits
- Token-based limits (for LLM usage)

Design (from ADR-006):
- Token bucket algorithm for smooth rate limiting
- Burst capacity for handling traffic spikes
- Thread-safe for concurrent access

Version: 1.0.0
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict
import threading
import time


@dataclass
class RateLimitConfig:
    """
    Configuration for rate limiting.

    Attributes:
        requests_per_minute: Global request limit per minute
        tokens_per_minute: Global token limit per minute
        burst_multiplier: Multiplier for burst capacity (default 1.5)
        user_requests_per_minute: Per-user request limit (optional)
        channel_requests_per_minute: Per-channel request limit (optional)
        workspace_requests_per_minute: Per-workspace request limit (optional)
    """

    requests_per_minute: int = 60
    tokens_per_minute: int = 100000
    burst_multiplier: float = 1.0
    user_requests_per_minute: Optional[int] = None
    channel_requests_per_minute: Optional[int] = None
    workspace_requests_per_minute: Optional[int] = None


@dataclass
class RateLimitResult:
    """
    Result of a rate limit check.

    Attributes:
        allowed: Whether the request is allowed
        remaining_requests: Remaining requests in current window
        remaining_tokens: Remaining tokens in current window
        reset_at: When the limit resets
        reason: Reason for denial (if not allowed)
    """

    allowed: bool
    remaining_requests: int
    remaining_tokens: int
    reset_at: datetime
    reason: Optional[str] = None


@dataclass
class TokenBucket:
    """
    A single token bucket for rate limiting.

    Attributes:
        capacity: Maximum tokens in bucket
        tokens: Current token count
        refill_rate: Tokens added per second
        last_refill: Last refill timestamp
    """

    capacity: float
    tokens: float
    refill_rate: float
    last_refill: float = field(default_factory=time.time)

    def refill(self, current_time: Optional[float] = None) -> None:
        """Refill bucket based on elapsed time."""
        now = current_time or time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    def consume(self, amount: float = 1.0) -> bool:
        """Try to consume tokens. Returns True if successful."""
        if self.tokens >= amount:
            self.tokens -= amount
            return True
        return False

    def peek(self) -> float:
        """Get current token count without consuming."""
        return self.tokens


class TokenBucketRateLimiter:
    """
    Token bucket rate limiter with multi-scope support.

    Supports rate limiting at multiple scopes:
    - Global (all requests)
    - Per-user
    - Per-channel
    - Per-workspace

    Example:
        config = RateLimitConfig(
            requests_per_minute=60,
            user_requests_per_minute=10,
        )
        limiter = TokenBucketRateLimiter(config)

        result = limiter.check("user-123", channel_id="channel-456")
        if not result.allowed:
            print(f"Rate limited: {result.reason}")
    """

    def __init__(self, config: Optional[RateLimitConfig] = None):
        """Initialize rate limiter with configuration."""
        self.config = config or RateLimitConfig()
        self._lock = threading.RLock()

        # Buckets for different scopes
        self._user_request_buckets: Dict[str, TokenBucket] = {}
        self._user_token_buckets: Dict[str, TokenBucket] = {}
        self._channel_buckets: Dict[str, TokenBucket] = {}
        self._workspace_buckets: Dict[str, TokenBucket] = {}

        # Time offset for testing
        self._time_offset: float = 0.0

    def _current_time(self) -> float:
        """Get current time with test offset."""
        return time.time() + self._time_offset

    def _advance_time(self, seconds: float) -> None:
        """Advance time for testing purposes."""
        self._time_offset += seconds

    def _get_or_create_bucket(
        self,
        buckets: Dict[str, TokenBucket],
        key: str,
        capacity: float,
        refill_rate: float,
    ) -> TokenBucket:
        """Get or create a token bucket."""
        if key not in buckets:
            buckets[key] = TokenBucket(
                capacity=capacity * self.config.burst_multiplier,
                tokens=capacity * self.config.burst_multiplier,
                refill_rate=refill_rate,
                last_refill=self._current_time(),
            )
        bucket = buckets[key]
        bucket.refill(self._current_time())
        return bucket

    def check(
        self,
        user_id: str,
        channel_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        tokens: int = 0,
    ) -> RateLimitResult:
        """
        Check if a request should be allowed.

        Args:
            user_id: User making the request
            channel_id: Channel context (optional)
            workspace_id: Workspace context (optional)
            tokens: Token count for this request (optional)

        Returns:
            RateLimitResult indicating if request is allowed
        """
        with self._lock:
            now = self._current_time()
            reset_at = datetime.now() + timedelta(minutes=1)

            # Check user request limit
            user_req_bucket = self._get_or_create_bucket(
                self._user_request_buckets,
                user_id,
                capacity=self.config.user_requests_per_minute or self.config.requests_per_minute,
                refill_rate=(
                    self.config.user_requests_per_minute or self.config.requests_per_minute
                )
                / 60.0,
            )

            if not user_req_bucket.consume(1.0):
                return RateLimitResult(
                    allowed=False,
                    remaining_requests=0,
                    remaining_tokens=int(self._get_user_token_bucket(user_id).peek()),
                    reset_at=reset_at,
                    reason=f"User rate limit exceeded: {self.config.user_requests_per_minute or self.config.requests_per_minute} requests per minute",
                )

            # Check user token limit
            if tokens > 0:
                user_token_bucket = self._get_user_token_bucket(user_id)
                if not user_token_bucket.consume(tokens):
                    # Restore request token
                    user_req_bucket.tokens += 1
                    return RateLimitResult(
                        allowed=False,
                        remaining_requests=int(user_req_bucket.peek()),
                        remaining_tokens=0,
                        reset_at=reset_at,
                        reason=f"Token limit exceeded: {self.config.tokens_per_minute} tokens per minute",
                    )

            # Check channel limit if applicable
            if channel_id and self.config.channel_requests_per_minute:
                channel_bucket = self._get_or_create_bucket(
                    self._channel_buckets,
                    channel_id,
                    capacity=self.config.channel_requests_per_minute,
                    refill_rate=self.config.channel_requests_per_minute / 60.0,
                )
                if not channel_bucket.consume(1.0):
                    # Restore user tokens
                    user_req_bucket.tokens += 1
                    return RateLimitResult(
                        allowed=False,
                        remaining_requests=0,
                        remaining_tokens=int(self._get_user_token_bucket(user_id).peek()),
                        reset_at=reset_at,
                        reason=f"Channel rate limit exceeded: {self.config.channel_requests_per_minute} requests per minute",
                    )

            # Check workspace limit if applicable
            if workspace_id and self.config.workspace_requests_per_minute:
                ws_bucket = self._get_or_create_bucket(
                    self._workspace_buckets,
                    workspace_id,
                    capacity=self.config.workspace_requests_per_minute,
                    refill_rate=self.config.workspace_requests_per_minute / 60.0,
                )
                if not ws_bucket.consume(1.0):
                    # Restore user and channel tokens
                    user_req_bucket.tokens += 1
                    if channel_id and self.config.channel_requests_per_minute:
                        self._channel_buckets[channel_id].tokens += 1
                    return RateLimitResult(
                        allowed=False,
                        remaining_requests=0,
                        remaining_tokens=int(self._get_user_token_bucket(user_id).peek()),
                        reset_at=reset_at,
                        reason=f"Workspace rate limit exceeded: {self.config.workspace_requests_per_minute} requests per minute",
                    )

            return RateLimitResult(
                allowed=True,
                remaining_requests=int(user_req_bucket.peek()),
                remaining_tokens=int(self._get_user_token_bucket(user_id).peek()),
                reset_at=reset_at,
            )

    def _get_user_token_bucket(self, user_id: str) -> TokenBucket:
        """Get or create user token bucket."""
        return self._get_or_create_bucket(
            self._user_token_buckets,
            user_id,
            capacity=self.config.tokens_per_minute,
            refill_rate=self.config.tokens_per_minute / 60.0,
        )

    def record(
        self,
        user_id: str,
        tokens_used: int = 0,
        channel_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> None:
        """
        Record usage after request completion.

        This is called after a request completes to record actual token usage.

        Args:
            user_id: User who made the request
            tokens_used: Actual tokens consumed
            channel_id: Channel context (optional)
            workspace_id: Workspace context (optional)
        """
        with self._lock:
            if tokens_used > 0:
                token_bucket = self._get_user_token_bucket(user_id)
                # Consume the tokens (may already be partially consumed from check)
                token_bucket.tokens = max(0, token_bucket.tokens - tokens_used)
