# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Memory decay scoring for ADR-003.

Implements exponential decay scoring based on last access time,
used to prioritize recently accessed memories in retrieval.

Related GitHub Issues:
- #81: Memory Lifecycle Policies

ADR Reference: ADR-003 Memory Architecture, Phase 0 (Foundations)
"""

import math
from datetime import datetime, timezone

# Default half-life in days (score reaches 0.5 after this many days)
DEFAULT_HALF_LIFE_DAYS: int = 30


def calculate_decay_score(
    last_accessed_at: datetime,
    half_life_days: int = DEFAULT_HALF_LIFE_DAYS,
) -> float:
    """Calculate exponential decay score based on last access time.

    Uses the formula: score = 2^(-days_since_access / half_life)

    Args:
        last_accessed_at: When the memory was last accessed.
        half_life_days: Days until score decays to 0.5 (default 30).

    Returns:
        Decay score between 0.0 and 1.0.
        - 1.0 for recently accessed memories
        - 0.5 at half_life_days
        - 0.25 at 2 * half_life_days
        - Approaches 0 for very old memories

    Example:
        >>> from datetime import datetime, timezone, timedelta
        >>> now = datetime.now(timezone.utc)
        >>> calculate_decay_score(now)  # Just accessed
        1.0
        >>> calculate_decay_score(now - timedelta(days=30))  # At half-life
        0.5
    """
    now = datetime.now(timezone.utc)
    delta = now - last_accessed_at
    days_since_access = delta.total_seconds() / (24 * 60 * 60)

    # Handle edge case where last_accessed is in the future
    if days_since_access < 0:
        return 1.0

    # Exponential decay: 2^(-t/half_life)
    score = math.pow(2, -days_since_access / half_life_days)

    # Clamp to [0, 1]
    return max(0.0, min(1.0, score))


def calculate_relevance_score(
    similarity: float,
    last_accessed_at: datetime,
    decay_weight: float = 0.3,
    half_life_days: int = DEFAULT_HALF_LIFE_DAYS,
) -> float:
    """Calculate combined relevance score from similarity and decay.

    Combines semantic similarity with temporal decay to produce
    a final relevance score for ranking memories.

    Formula: relevance = similarity * (1 - decay_weight) + similarity * decay * decay_weight
           = similarity * ((1 - decay_weight) + decay * decay_weight)

    This ensures that:
    - decay_weight=0: relevance = similarity (ignore decay)
    - decay_weight=1: relevance = similarity * decay (full decay impact)
    - 0 < decay_weight < 1: blended score

    Args:
        similarity: Semantic similarity score (0.0 to 1.0).
        last_accessed_at: When the memory was last accessed.
        decay_weight: How much decay affects the score (0.0 to 1.0, default 0.3).
        half_life_days: Days until decay score reaches 0.5 (default 30).

    Returns:
        Combined relevance score between 0.0 and 1.0.

    Example:
        >>> from datetime import datetime, timezone
        >>> now = datetime.now(timezone.utc)
        >>> calculate_relevance_score(0.8, now)  # High similarity, just accessed
        0.8
    """
    decay = calculate_decay_score(last_accessed_at, half_life_days)

    # Blend similarity with decay based on weight
    # When decay_weight=0, result is just similarity
    # When decay_weight=1, result is similarity * decay
    relevance = similarity * ((1 - decay_weight) + decay * decay_weight)

    # Clamp to [0, 1]
    return max(0.0, min(1.0, relevance))
