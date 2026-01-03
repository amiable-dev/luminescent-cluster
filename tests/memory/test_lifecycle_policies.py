# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
TDD: RED Phase - Tests for Memory Lifecycle Policies.

These tests define the expected behavior for memory lifecycle management
including TTL policies, expiration logic, and decay scoring.

Related GitHub Issues:
- #81: Memory Lifecycle Policies

ADR Reference: ADR-003 Memory Architecture, Phase 0 (Foundations)
"""

import pytest
from datetime import datetime, timezone, timedelta
from typing import Optional


class TestLifecyclePolicyConstants:
    """TDD: Tests for lifecycle policy constants."""

    def test_default_ttl_days_exists(self):
        """DEFAULT_TTL_DAYS constant should be defined.

        GitHub Issue: #81
        ADR Reference: ADR-003 (Lifecycle Policies)
        """
        from src.memory.lifecycle.policies import DEFAULT_TTL_DAYS

        assert DEFAULT_TTL_DAYS is not None

    def test_default_ttl_is_90_days(self):
        """DEFAULT_TTL_DAYS should be 90 (ADR-003 spec).

        GitHub Issue: #81
        ADR Reference: ADR-003 (Lifecycle Policies)
        """
        from src.memory.lifecycle.policies import DEFAULT_TTL_DAYS

        assert DEFAULT_TTL_DAYS == 90

    def test_min_ttl_days_exists(self):
        """MIN_TTL_DAYS constant should be defined.

        GitHub Issue: #81
        ADR Reference: ADR-003 (Lifecycle Policies)
        """
        from src.memory.lifecycle.policies import MIN_TTL_DAYS

        assert MIN_TTL_DAYS is not None

    def test_min_ttl_is_1_day(self):
        """MIN_TTL_DAYS should be 1 (minimum allowed).

        GitHub Issue: #81
        ADR Reference: ADR-003 (Lifecycle Policies)
        """
        from src.memory.lifecycle.policies import MIN_TTL_DAYS

        assert MIN_TTL_DAYS == 1

    def test_max_ttl_days_exists(self):
        """MAX_TTL_DAYS constant should be defined.

        GitHub Issue: #81
        ADR Reference: ADR-003 (Lifecycle Policies)
        """
        from src.memory.lifecycle.policies import MAX_TTL_DAYS

        assert MAX_TTL_DAYS is not None

    def test_max_ttl_is_365_days(self):
        """MAX_TTL_DAYS should be 365 (1 year maximum).

        GitHub Issue: #81
        ADR Reference: ADR-003 (Lifecycle Policies)
        """
        from src.memory.lifecycle.policies import MAX_TTL_DAYS

        assert MAX_TTL_DAYS == 365


class TestLifecyclePolicy:
    """TDD: Tests for LifecyclePolicy dataclass."""

    def test_lifecycle_policy_class_exists(self):
        """LifecyclePolicy class should be defined.

        GitHub Issue: #81
        ADR Reference: ADR-003 (Lifecycle Policies)
        """
        from src.memory.lifecycle.policies import LifecyclePolicy

        assert LifecyclePolicy is not None

    def test_lifecycle_policy_has_ttl_days(self):
        """LifecyclePolicy should have ttl_days field.

        GitHub Issue: #81
        ADR Reference: ADR-003 (Lifecycle Policies)
        """
        from src.memory.lifecycle.policies import LifecyclePolicy

        policy = LifecyclePolicy()
        assert hasattr(policy, "ttl_days")

    def test_lifecycle_policy_ttl_defaults_to_90(self):
        """LifecyclePolicy.ttl_days should default to 90.

        GitHub Issue: #81
        ADR Reference: ADR-003 (Lifecycle Policies)
        """
        from src.memory.lifecycle.policies import LifecyclePolicy

        policy = LifecyclePolicy()
        assert policy.ttl_days == 90

    def test_lifecycle_policy_has_decay_enabled(self):
        """LifecyclePolicy should have decay_enabled field.

        GitHub Issue: #81
        ADR Reference: ADR-003 (Lifecycle Policies)
        """
        from src.memory.lifecycle.policies import LifecyclePolicy

        policy = LifecyclePolicy()
        assert hasattr(policy, "decay_enabled")

    def test_lifecycle_policy_decay_enabled_by_default(self):
        """LifecyclePolicy.decay_enabled should default to True.

        GitHub Issue: #81
        ADR Reference: ADR-003 (Lifecycle Policies)
        """
        from src.memory.lifecycle.policies import LifecyclePolicy

        policy = LifecyclePolicy()
        assert policy.decay_enabled is True

    def test_lifecycle_policy_has_decay_half_life_days(self):
        """LifecyclePolicy should have decay_half_life_days field.

        GitHub Issue: #81
        ADR Reference: ADR-003 (Lifecycle Policies)
        """
        from src.memory.lifecycle.policies import LifecyclePolicy

        policy = LifecyclePolicy()
        assert hasattr(policy, "decay_half_life_days")

    def test_lifecycle_policy_decay_half_life_defaults_to_30(self):
        """LifecyclePolicy.decay_half_life_days should default to 30.

        GitHub Issue: #81
        ADR Reference: ADR-003 (Lifecycle Policies)
        """
        from src.memory.lifecycle.policies import LifecyclePolicy

        policy = LifecyclePolicy()
        assert policy.decay_half_life_days == 30

    def test_lifecycle_policy_custom_ttl(self):
        """LifecyclePolicy should accept custom ttl_days.

        GitHub Issue: #81
        ADR Reference: ADR-003 (Lifecycle Policies)
        """
        from src.memory.lifecycle.policies import LifecyclePolicy

        policy = LifecyclePolicy(ttl_days=180)
        assert policy.ttl_days == 180


class TestExpirationLogic:
    """TDD: Tests for memory expiration logic."""

    def test_calculate_expiration_function_exists(self):
        """calculate_expiration function should be defined.

        GitHub Issue: #81
        ADR Reference: ADR-003 (Lifecycle Policies)
        """
        from src.memory.lifecycle.policies import calculate_expiration

        assert callable(calculate_expiration)

    def test_calculate_expiration_returns_datetime(self):
        """calculate_expiration should return a datetime.

        GitHub Issue: #81
        ADR Reference: ADR-003 (Lifecycle Policies)
        """
        from src.memory.lifecycle.policies import calculate_expiration

        created_at = datetime.now(timezone.utc)
        result = calculate_expiration(created_at)
        assert isinstance(result, datetime)

    def test_calculate_expiration_default_90_days(self):
        """calculate_expiration should add 90 days by default.

        GitHub Issue: #81
        ADR Reference: ADR-003 (Lifecycle Policies)
        """
        from src.memory.lifecycle.policies import calculate_expiration

        created_at = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        result = calculate_expiration(created_at)
        expected = datetime(2024, 3, 31, 0, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_calculate_expiration_custom_ttl(self):
        """calculate_expiration should respect custom ttl_days.

        GitHub Issue: #81
        ADR Reference: ADR-003 (Lifecycle Policies)
        """
        from src.memory.lifecycle.policies import calculate_expiration

        created_at = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        result = calculate_expiration(created_at, ttl_days=30)
        expected = datetime(2024, 1, 31, 0, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_is_expired_function_exists(self):
        """is_expired function should be defined.

        GitHub Issue: #81
        ADR Reference: ADR-003 (Lifecycle Policies)
        """
        from src.memory.lifecycle.policies import is_expired

        assert callable(is_expired)

    def test_is_expired_returns_false_for_future_expiration(self):
        """is_expired should return False if expiration is in the future.

        GitHub Issue: #81
        ADR Reference: ADR-003 (Lifecycle Policies)
        """
        from src.memory.lifecycle.policies import is_expired

        expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        assert is_expired(expires_at) is False

    def test_is_expired_returns_true_for_past_expiration(self):
        """is_expired should return True if expiration is in the past.

        GitHub Issue: #81
        ADR Reference: ADR-003 (Lifecycle Policies)
        """
        from src.memory.lifecycle.policies import is_expired

        expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        assert is_expired(expires_at) is True

    def test_is_expired_returns_false_for_none(self):
        """is_expired should return False if expires_at is None (no expiration).

        GitHub Issue: #81
        ADR Reference: ADR-003 (Lifecycle Policies)
        """
        from src.memory.lifecycle.policies import is_expired

        assert is_expired(None) is False


class TestDecayScoring:
    """TDD: Tests for memory decay scoring."""

    def test_calculate_decay_score_function_exists(self):
        """calculate_decay_score function should be defined.

        GitHub Issue: #81
        ADR Reference: ADR-003 (Lifecycle Policies)
        """
        from src.memory.lifecycle.decay import calculate_decay_score

        assert callable(calculate_decay_score)

    def test_decay_score_is_1_for_just_accessed(self):
        """Decay score should be ~1.0 for recently accessed memories.

        GitHub Issue: #81
        ADR Reference: ADR-003 (Lifecycle Policies)
        """
        from src.memory.lifecycle.decay import calculate_decay_score

        last_accessed = datetime.now(timezone.utc)
        score = calculate_decay_score(last_accessed)
        assert 0.99 <= score <= 1.0

    def test_decay_score_is_0_5_at_half_life(self):
        """Decay score should be ~0.5 at half-life (30 days).

        GitHub Issue: #81
        ADR Reference: ADR-003 (Lifecycle Policies)
        """
        from src.memory.lifecycle.decay import calculate_decay_score

        last_accessed = datetime.now(timezone.utc) - timedelta(days=30)
        score = calculate_decay_score(last_accessed)
        assert 0.45 <= score <= 0.55

    def test_decay_score_is_0_25_at_two_half_lives(self):
        """Decay score should be ~0.25 at two half-lives (60 days).

        GitHub Issue: #81
        ADR Reference: ADR-003 (Lifecycle Policies)
        """
        from src.memory.lifecycle.decay import calculate_decay_score

        last_accessed = datetime.now(timezone.utc) - timedelta(days=60)
        score = calculate_decay_score(last_accessed)
        assert 0.2 <= score <= 0.3

    def test_decay_score_custom_half_life(self):
        """Decay score should respect custom half_life_days.

        GitHub Issue: #81
        ADR Reference: ADR-003 (Lifecycle Policies)
        """
        from src.memory.lifecycle.decay import calculate_decay_score

        last_accessed = datetime.now(timezone.utc) - timedelta(days=15)
        # With half_life=15, should be ~0.5
        score = calculate_decay_score(last_accessed, half_life_days=15)
        assert 0.45 <= score <= 0.55

    def test_decay_score_never_goes_below_zero(self):
        """Decay score should never go below 0.

        GitHub Issue: #81
        ADR Reference: ADR-003 (Lifecycle Policies)
        """
        from src.memory.lifecycle.decay import calculate_decay_score

        last_accessed = datetime.now(timezone.utc) - timedelta(days=365)
        score = calculate_decay_score(last_accessed)
        assert score >= 0

    def test_decay_score_never_exceeds_one(self):
        """Decay score should never exceed 1.0.

        GitHub Issue: #81
        ADR Reference: ADR-003 (Lifecycle Policies)
        """
        from src.memory.lifecycle.decay import calculate_decay_score

        last_accessed = datetime.now(timezone.utc) + timedelta(days=1)  # future
        score = calculate_decay_score(last_accessed)
        assert score <= 1.0


class TestCombinedRelevanceScore:
    """TDD: Tests for combined relevance scoring."""

    def test_calculate_relevance_score_function_exists(self):
        """calculate_relevance_score function should be defined.

        GitHub Issue: #81
        ADR Reference: ADR-003 (Lifecycle Policies)
        """
        from src.memory.lifecycle.decay import calculate_relevance_score

        assert callable(calculate_relevance_score)

    def test_relevance_score_combines_similarity_and_decay(self):
        """Relevance score should combine similarity and decay.

        GitHub Issue: #81
        ADR Reference: ADR-003 (Lifecycle Policies)
        """
        from src.memory.lifecycle.decay import calculate_relevance_score

        last_accessed = datetime.now(timezone.utc)  # decay ~1.0
        similarity = 0.8
        score = calculate_relevance_score(similarity, last_accessed)
        # With decay ~1.0 and similarity 0.8, should be close to 0.8
        assert 0.75 <= score <= 0.85

    def test_relevance_score_penalizes_old_memories(self):
        """Relevance score should be lower for old memories.

        GitHub Issue: #81
        ADR Reference: ADR-003 (Lifecycle Policies)
        """
        from src.memory.lifecycle.decay import calculate_relevance_score

        old_access = datetime.now(timezone.utc) - timedelta(days=60)  # decay ~0.25
        recent_access = datetime.now(timezone.utc)  # decay ~1.0
        similarity = 0.8

        old_score = calculate_relevance_score(similarity, old_access)
        recent_score = calculate_relevance_score(similarity, recent_access)

        assert old_score < recent_score

    def test_relevance_score_with_decay_weight(self):
        """Relevance score should respect decay_weight parameter.

        GitHub Issue: #81
        ADR Reference: ADR-003 (Lifecycle Policies)
        """
        from src.memory.lifecycle.decay import calculate_relevance_score

        last_accessed = datetime.now(timezone.utc) - timedelta(days=30)  # decay ~0.5
        similarity = 0.8

        # With decay_weight=0 (ignore decay), should be just similarity
        score_no_decay = calculate_relevance_score(
            similarity, last_accessed, decay_weight=0.0
        )
        assert 0.78 <= score_no_decay <= 0.82

        # With decay_weight=1 (full decay), should be lower
        score_full_decay = calculate_relevance_score(
            similarity, last_accessed, decay_weight=1.0
        )
        assert score_full_decay < score_no_decay


class TestLifecycleModuleExports:
    """TDD: Tests for lifecycle module exports."""

    def test_lifecycle_module_exists(self):
        """src.memory.lifecycle module should exist.

        GitHub Issue: #81
        ADR Reference: ADR-003 (Lifecycle Policies)
        """
        import src.memory.lifecycle

        assert src.memory.lifecycle is not None

    def test_policies_module_exports(self):
        """policies module should export expected items.

        GitHub Issue: #81
        ADR Reference: ADR-003 (Lifecycle Policies)
        """
        from src.memory.lifecycle import policies

        assert hasattr(policies, "DEFAULT_TTL_DAYS")
        assert hasattr(policies, "LifecyclePolicy")
        assert hasattr(policies, "calculate_expiration")
        assert hasattr(policies, "is_expired")

    def test_decay_module_exports(self):
        """decay module should export expected items.

        GitHub Issue: #81
        ADR Reference: ADR-003 (Lifecycle Policies)
        """
        from src.memory.lifecycle import decay

        assert hasattr(decay, "calculate_decay_score")
        assert hasattr(decay, "calculate_relevance_score")
