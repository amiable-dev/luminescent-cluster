# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Memory lifecycle management for ADR-003.

This module provides TTL policies, expiration logic, and decay scoring
for memory lifecycle management.

Related GitHub Issues:
- #81: Memory Lifecycle Policies

ADR Reference: ADR-003 Memory Architecture, Phase 0 (Foundations)
"""

from luminescent_cluster.memory.lifecycle.decay import (
    calculate_decay_score,
    calculate_relevance_score,
)
from luminescent_cluster.memory.lifecycle.policies import (
    DEFAULT_TTL_DAYS,
    MAX_TTL_DAYS,
    MIN_TTL_DAYS,
    LifecyclePolicy,
    calculate_expiration,
    is_expired,
)

__all__ = [
    # Constants
    "DEFAULT_TTL_DAYS",
    "MIN_TTL_DAYS",
    "MAX_TTL_DAYS",
    # Classes
    "LifecyclePolicy",
    # Functions
    "calculate_expiration",
    "is_expired",
    "calculate_decay_score",
    "calculate_relevance_score",
]
