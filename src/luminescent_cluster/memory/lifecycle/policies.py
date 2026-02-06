# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Memory lifecycle policies for ADR-003.

Defines TTL policies, expiration logic, and policy configuration
for memory lifecycle management.

Related GitHub Issues:
- #81: Memory Lifecycle Policies

ADR Reference: ADR-003 Memory Architecture, Phase 0 (Foundations)
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

# TTL Constants (from ADR-003)
DEFAULT_TTL_DAYS: int = 90  # Default memory TTL
MIN_TTL_DAYS: int = 1  # Minimum allowed TTL
MAX_TTL_DAYS: int = 365  # Maximum allowed TTL (1 year)


@dataclass
class LifecyclePolicy:
    """Configuration for memory lifecycle management.

    Attributes:
        ttl_days: Time-to-live in days (default 90).
        decay_enabled: Whether to apply decay scoring (default True).
        decay_half_life_days: Days until decay score reaches 0.5 (default 30).

    Example:
        >>> policy = LifecyclePolicy(ttl_days=180, decay_enabled=True)
        >>> policy.ttl_days
        180
    """

    ttl_days: int = DEFAULT_TTL_DAYS
    decay_enabled: bool = True
    decay_half_life_days: int = 30


def calculate_expiration(
    created_at: datetime,
    ttl_days: int = DEFAULT_TTL_DAYS,
) -> datetime:
    """Calculate expiration datetime from creation time.

    Args:
        created_at: When the memory was created.
        ttl_days: Time-to-live in days (default 90).

    Returns:
        The datetime when the memory should expire.

    Example:
        >>> from datetime import datetime, timezone
        >>> created = datetime(2024, 1, 1, tzinfo=timezone.utc)
        >>> calculate_expiration(created, ttl_days=30)
        datetime.datetime(2024, 1, 31, 0, 0, tzinfo=datetime.timezone.utc)
    """
    return created_at + timedelta(days=ttl_days)


def is_expired(expires_at: Optional[datetime]) -> bool:
    """Check if a memory has expired.

    Args:
        expires_at: The expiration datetime, or None for no expiration.

    Returns:
        True if the memory has expired, False otherwise.
        Returns False if expires_at is None (no expiration set).

    Example:
        >>> from datetime import datetime, timezone, timedelta
        >>> past = datetime.now(timezone.utc) - timedelta(days=1)
        >>> is_expired(past)
        True
        >>> future = datetime.now(timezone.utc) + timedelta(days=1)
        >>> is_expired(future)
        False
        >>> is_expired(None)
        False
    """
    if expires_at is None:
        return False

    now = datetime.now(timezone.utc)
    return expires_at <= now
