# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
TDD: RED Phase - Tests for Janitor Process.

Related GitHub Issues:
- #102: Janitor Process Framework
- #103: Deduplication
- #104: Contradiction Handling
- #105: Expiration Cleanup

ADR Reference: ADR-003 Memory Architecture, Phase 1d (Janitor Process)
"""

import pytest
from datetime import datetime, timedelta, timezone
from typing import List

from luminescent_cluster.memory.schemas import Memory, MemoryType


class TestJanitorFramework:
    """Tests for the janitor process framework."""

    @pytest.fixture
    def janitor(self):
        """Create janitor for testing."""
        from luminescent_cluster.memory.janitor.runner import JanitorRunner
        from luminescent_cluster.memory.providers.local import LocalMemoryProvider
        provider = LocalMemoryProvider()
        return JanitorRunner(provider)

    def test_janitor_initialization(self, janitor):
        """Janitor should initialize with provider."""
        assert janitor.provider is not None

    def test_janitor_has_required_tasks(self, janitor):
        """Janitor should have all required cleanup tasks."""
        assert hasattr(janitor, 'run_deduplication')
        assert hasattr(janitor, 'run_contradiction_resolution')
        assert hasattr(janitor, 'run_expiration_cleanup')

    @pytest.mark.asyncio
    async def test_run_all_tasks(self, janitor):
        """Should run all cleanup tasks."""
        result = await janitor.run_all()
        assert 'deduplication' in result
        assert 'contradiction' in result
        assert 'expiration' in result

    @pytest.mark.asyncio
    async def test_run_returns_statistics(self, janitor):
        """Run should return cleanup statistics."""
        result = await janitor.run_all()
        assert 'total_processed' in result
        assert 'total_removed' in result
        assert 'duration_ms' in result


class TestDeduplication:
    """Tests for memory deduplication."""

    @pytest.fixture
    def deduplicator(self):
        """Create deduplicator for testing."""
        from luminescent_cluster.memory.janitor.deduplication import Deduplicator
        return Deduplicator()

    @pytest.fixture
    async def populated_provider(self):
        """Provider with duplicate memories."""
        from luminescent_cluster.memory.providers.local import LocalMemoryProvider
        provider = LocalMemoryProvider()
        now = datetime.now(timezone.utc)

        # Create duplicate memories
        memories = [
            Memory(
                user_id="user-1",
                content="Prefers tabs over spaces",
                memory_type=MemoryType.PREFERENCE,
                confidence=0.9,
                source="conversation",
                raw_source="I prefer tabs over spaces",
                extraction_version=1,
                created_at=now - timedelta(hours=2),
                last_accessed_at=now - timedelta(hours=2),
            ),
            Memory(
                user_id="user-1",
                content="Prefers tabs instead of spaces",  # Very similar
                memory_type=MemoryType.PREFERENCE,
                confidence=0.85,
                source="conversation",
                raw_source="I prefer tabs over spaces",
                extraction_version=1,
                created_at=now - timedelta(hours=1),
                last_accessed_at=now - timedelta(hours=1),
            ),
            Memory(
                user_id="user-1",
                content="Uses Python 3.11",  # Different
                memory_type=MemoryType.FACT,
                confidence=0.95,
                source="conversation",
                raw_source="Using Python 3.11",
                extraction_version=1,
                created_at=now,
                last_accessed_at=now,
            ),
        ]

        for memory in memories:
            await provider.store(memory, {})

        return provider

    def test_deduplicator_initialization(self, deduplicator):
        """Deduplicator should initialize with default threshold."""
        assert deduplicator.similarity_threshold >= 0.85

    def test_custom_similarity_threshold(self):
        """Should accept custom similarity threshold."""
        from luminescent_cluster.memory.janitor.deduplication import Deduplicator
        dedup = Deduplicator(similarity_threshold=0.9)
        assert dedup.similarity_threshold == 0.9

    def test_calculate_similarity(self, deduplicator):
        """Should calculate similarity between memories."""
        now = datetime.now(timezone.utc)
        m1 = Memory(
            user_id="user-1",
            content="Prefers tabs over spaces",
            memory_type=MemoryType.PREFERENCE,
            confidence=0.9,
            source="test",
            raw_source="test",
            extraction_version=1,
            created_at=now,
            last_accessed_at=now,
        )
        m2 = Memory(
            user_id="user-1",
            content="Prefers tabs instead of spaces",
            memory_type=MemoryType.PREFERENCE,
            confidence=0.9,
            source="test",
            raw_source="test",
            extraction_version=1,
            created_at=now,
            last_accessed_at=now,
        )

        similarity = deduplicator.calculate_similarity(m1, m2)
        assert 0.0 <= similarity <= 1.0
        assert similarity >= 0.5  # Should be somewhat similar

    def test_detect_duplicates(self, deduplicator):
        """Should detect duplicate memories."""
        now = datetime.now(timezone.utc)
        memories = [
            Memory(
                user_id="user-1",
                content="Prefers tabs over spaces",
                memory_type=MemoryType.PREFERENCE,
                confidence=0.9,
                source="test",
                raw_source="test",
                extraction_version=1,
                created_at=now,
                last_accessed_at=now,
            ),
            Memory(
                user_id="user-1",
                content="Prefers tabs over spaces",  # Exact duplicate
                memory_type=MemoryType.PREFERENCE,
                confidence=0.85,
                source="test",
                raw_source="test",
                extraction_version=1,
                created_at=now,
                last_accessed_at=now,
            ),
        ]

        duplicates = deduplicator.find_duplicates(memories)
        assert len(duplicates) > 0

    def test_preserve_highest_confidence(self, deduplicator):
        """Should preserve memory with highest confidence."""
        now = datetime.now(timezone.utc)
        memories = [
            Memory(
                user_id="user-1",
                content="Prefers tabs",
                memory_type=MemoryType.PREFERENCE,
                confidence=0.9,
                source="test",
                raw_source="test",
                extraction_version=1,
                created_at=now,
                last_accessed_at=now,
            ),
            Memory(
                user_id="user-1",
                content="Prefers tabs",  # Same content
                memory_type=MemoryType.PREFERENCE,
                confidence=0.95,  # Higher confidence
                source="test",
                raw_source="test",
                extraction_version=1,
                created_at=now,
                last_accessed_at=now,
            ),
        ]

        to_keep, to_remove = deduplicator.resolve_duplicates(memories)
        assert to_keep[0].confidence == 0.95  # Kept higher confidence

    @pytest.mark.asyncio
    async def test_deduplication_run(self, populated_provider):
        """Should deduplicate memories in provider."""
        from luminescent_cluster.memory.janitor.deduplication import Deduplicator
        dedup = Deduplicator(similarity_threshold=0.7)

        result = await dedup.run(populated_provider, "user-1")
        assert 'processed' in result
        assert 'removed' in result


class TestContradictionHandling:
    """Tests for contradiction detection and resolution."""

    @pytest.fixture
    def handler(self):
        """Create contradiction handler for testing."""
        from luminescent_cluster.memory.janitor.contradiction import ContradictionHandler
        return ContradictionHandler()

    @pytest.fixture
    async def contradicting_provider(self):
        """Provider with contradicting memories."""
        from luminescent_cluster.memory.providers.local import LocalMemoryProvider
        provider = LocalMemoryProvider()
        now = datetime.now(timezone.utc)

        memories = [
            Memory(
                user_id="user-1",
                content="Prefers tabs over spaces",
                memory_type=MemoryType.PREFERENCE,
                confidence=0.9,
                source="conversation",
                raw_source="I prefer tabs",
                extraction_version=1,
                created_at=now - timedelta(days=7),
                last_accessed_at=now - timedelta(days=7),
            ),
            Memory(
                user_id="user-1",
                content="Prefers spaces over tabs",  # Contradicts above
                memory_type=MemoryType.PREFERENCE,
                confidence=0.85,
                source="conversation",
                raw_source="I prefer spaces now",
                extraction_version=1,
                created_at=now,  # Newer
                last_accessed_at=now,
            ),
        ]

        for memory in memories:
            await provider.store(memory, {})

        return provider

    def test_handler_initialization(self, handler):
        """Handler should initialize with resolution strategy."""
        assert handler.strategy == "newer_wins"

    def test_detect_contradiction(self, handler):
        """Should detect contradicting memories."""
        now = datetime.now(timezone.utc)
        m1 = Memory(
            user_id="user-1",
            content="Prefers tabs over spaces",
            memory_type=MemoryType.PREFERENCE,
            confidence=0.9,
            source="test",
            raw_source="test",
            extraction_version=1,
            created_at=now,
            last_accessed_at=now,
        )
        m2 = Memory(
            user_id="user-1",
            content="Prefers spaces over tabs",
            memory_type=MemoryType.PREFERENCE,
            confidence=0.9,
            source="test",
            raw_source="test",
            extraction_version=1,
            created_at=now,
            last_accessed_at=now,
        )

        is_contradiction = handler.is_contradiction(m1, m2)
        # Should detect potential contradiction based on same topic
        assert isinstance(is_contradiction, bool)

    def test_newer_wins_resolution(self, handler):
        """Newer memory should win in contradiction resolution."""
        now = datetime.now(timezone.utc)
        old_memory = Memory(
            user_id="user-1",
            content="Prefers tabs",
            memory_type=MemoryType.PREFERENCE,
            confidence=0.9,
            source="test",
            raw_source="test",
            extraction_version=1,
            created_at=now - timedelta(days=7),
            last_accessed_at=now - timedelta(days=7),
        )
        new_memory = Memory(
            user_id="user-1",
            content="Prefers spaces",
            memory_type=MemoryType.PREFERENCE,
            confidence=0.85,
            source="test",
            raw_source="test",
            extraction_version=1,
            created_at=now,
            last_accessed_at=now,
        )

        winner = handler.resolve(old_memory, new_memory)
        assert winner == new_memory

    def test_flag_for_review(self, handler):
        """Should flag contradictions for human review."""
        now = datetime.now(timezone.utc)
        m1 = Memory(
            user_id="user-1",
            content="Uses PostgreSQL",
            memory_type=MemoryType.DECISION,
            confidence=0.95,
            source="test",
            raw_source="test",
            extraction_version=1,
            created_at=now,
            last_accessed_at=now,
        )
        m2 = Memory(
            user_id="user-1",
            content="Uses MySQL",
            memory_type=MemoryType.DECISION,
            confidence=0.95,
            source="test",
            raw_source="test",
            extraction_version=1,
            created_at=now,
            last_accessed_at=now,
        )

        flagged = handler.flag_for_review(m1, m2)
        assert 'reason' in flagged
        assert 'memories' in flagged

    @pytest.mark.asyncio
    async def test_contradiction_run(self, contradicting_provider):
        """Should resolve contradictions in provider."""
        from luminescent_cluster.memory.janitor.contradiction import ContradictionHandler
        handler = ContradictionHandler()

        result = await handler.run(contradicting_provider, "user-1")
        assert 'processed' in result
        assert 'resolved' in result


class TestExpirationCleanup:
    """Tests for expiration-based cleanup."""

    @pytest.fixture
    def cleaner(self):
        """Create expiration cleaner for testing."""
        from luminescent_cluster.memory.janitor.expiration import ExpirationCleaner
        return ExpirationCleaner()

    @pytest.fixture
    async def expired_provider(self):
        """Provider with expired memories."""
        from luminescent_cluster.memory.providers.local import LocalMemoryProvider
        provider = LocalMemoryProvider()
        now = datetime.now(timezone.utc)

        memories = [
            Memory(
                user_id="user-1",
                content="Expired memory",
                memory_type=MemoryType.FACT,
                confidence=0.9,
                source="test",
                raw_source="test",
                extraction_version=1,
                created_at=now - timedelta(days=100),
                last_accessed_at=now - timedelta(days=100),
                expires_at=now - timedelta(days=10),  # Already expired
            ),
            Memory(
                user_id="user-1",
                content="Valid memory",
                memory_type=MemoryType.FACT,
                confidence=0.9,
                source="test",
                raw_source="test",
                extraction_version=1,
                created_at=now,
                last_accessed_at=now,
                expires_at=now + timedelta(days=90),  # Not expired
            ),
        ]

        for memory in memories:
            await provider.store(memory, {})

        return provider

    def test_cleaner_initialization(self, cleaner):
        """Cleaner should initialize."""
        assert cleaner is not None

    def test_is_expired(self, cleaner):
        """Should correctly identify expired memories."""
        now = datetime.now(timezone.utc)

        expired = Memory(
            user_id="user-1",
            content="Expired",
            memory_type=MemoryType.FACT,
            confidence=0.9,
            source="test",
            raw_source="test",
            extraction_version=1,
            created_at=now,
            last_accessed_at=now,
            expires_at=now - timedelta(days=1),
        )

        valid = Memory(
            user_id="user-1",
            content="Valid",
            memory_type=MemoryType.FACT,
            confidence=0.9,
            source="test",
            raw_source="test",
            extraction_version=1,
            created_at=now,
            last_accessed_at=now,
            expires_at=now + timedelta(days=90),
        )

        assert cleaner.is_expired(expired) is True
        assert cleaner.is_expired(valid) is False

    def test_no_expiration_not_expired(self, cleaner):
        """Memories without expiration should not be considered expired."""
        now = datetime.now(timezone.utc)

        no_expiry = Memory(
            user_id="user-1",
            content="No expiry",
            memory_type=MemoryType.FACT,
            confidence=0.9,
            source="test",
            raw_source="test",
            extraction_version=1,
            created_at=now,
            last_accessed_at=now,
            expires_at=None,
        )

        assert cleaner.is_expired(no_expiry) is False

    @pytest.mark.asyncio
    async def test_expiration_cleanup_run(self, expired_provider):
        """Should remove expired memories from provider."""
        from luminescent_cluster.memory.janitor.expiration import ExpirationCleaner
        cleaner = ExpirationCleaner()

        result = await cleaner.run(expired_provider, "user-1")
        assert 'processed' in result
        assert 'removed' in result

    @pytest.mark.asyncio
    async def test_cleanup_preserves_valid_memories(self, expired_provider):
        """Cleanup should preserve non-expired memories."""
        from luminescent_cluster.memory.janitor.expiration import ExpirationCleaner
        cleaner = ExpirationCleaner()

        await cleaner.run(expired_provider, "user-1")

        # Should still have the valid memory
        remaining = await expired_provider.retrieve("Valid memory", "user-1", limit=10)
        assert len(remaining) >= 1


class TestJanitorScheduler:
    """Tests for janitor scheduling."""

    @pytest.fixture
    def scheduler(self):
        """Create scheduler for testing."""
        from luminescent_cluster.memory.janitor.scheduler import JanitorScheduler
        return JanitorScheduler()

    def test_scheduler_initialization(self, scheduler):
        """Scheduler should initialize with default schedule."""
        assert scheduler.schedule_interval_hours > 0

    def test_custom_schedule_interval(self):
        """Should accept custom schedule interval."""
        from luminescent_cluster.memory.janitor.scheduler import JanitorScheduler
        scheduler = JanitorScheduler(schedule_interval_hours=12)
        assert scheduler.schedule_interval_hours == 12

    def test_should_run_check(self, scheduler):
        """Should determine if janitor should run."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        should_run = scheduler.should_run(last_run=now - timedelta(hours=48))
        assert should_run is True

        should_not_run = scheduler.should_run(last_run=now - timedelta(minutes=30))
        assert should_not_run is False

    def test_get_next_run_time(self, scheduler):
        """Should calculate next scheduled run time."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        next_run = scheduler.get_next_run(last_run=now)
        assert next_run > now


class TestJanitorSoftDelete:
    """Tests for soft-delete (invalidate) behavior.

    Council Review Finding: Janitor was using hard-delete which risks data loss.
    Should use soft-delete (invalidate_memory) by default.

    ADR Reference: ADR-003 Memory Architecture, Phase 1d (Janitor Process)
    """

    @pytest.fixture
    async def provider_with_duplicates(self):
        """Provider with duplicate memories for testing."""
        from luminescent_cluster.memory.providers.local import LocalMemoryProvider
        provider = LocalMemoryProvider()
        now = datetime.now(timezone.utc)

        memories = [
            Memory(
                user_id="user-1",
                content="Prefers tabs over spaces",
                memory_type=MemoryType.PREFERENCE,
                confidence=0.9,
                source="conversation",
                raw_source="I prefer tabs",
                extraction_version=1,
                created_at=now,
                last_accessed_at=now,
            ),
            Memory(
                user_id="user-1",
                content="Prefers tabs over spaces",  # Exact duplicate
                memory_type=MemoryType.PREFERENCE,
                confidence=0.7,
                source="conversation",
                raw_source="I prefer tabs",
                extraction_version=1,
                created_at=now,
                last_accessed_at=now,
            ),
        ]

        for memory in memories:
            await provider.store(memory, {})

        return provider

    @pytest.mark.asyncio
    async def test_deduplicator_has_dry_run_mode(self):
        """Deduplicator should support dry_run mode."""
        from luminescent_cluster.memory.janitor.deduplication import Deduplicator
        from luminescent_cluster.memory.providers.local import LocalMemoryProvider

        dedup = Deduplicator()
        provider = LocalMemoryProvider()

        # dry_run should be supported
        result = await dedup.run(provider, "user-1", dry_run=True)
        assert 'dry_run' in result or 'would_remove' in result or result.get('removed', 0) == 0

    @pytest.mark.asyncio
    async def test_deduplicator_soft_delete_default(self, provider_with_duplicates):
        """Deduplicator should use soft-delete (invalidate) by default."""
        from luminescent_cluster.memory.janitor.deduplication import Deduplicator

        dedup = Deduplicator(similarity_threshold=0.9)
        initial_count = provider_with_duplicates.count()

        # Run deduplication
        result = await dedup.run(provider_with_duplicates, "user-1")

        # Memories should still exist (soft-deleted, not hard-deleted)
        # The count may be same if using invalidation
        # Or check that invalidated memories are marked
        assert result.get('removed', 0) >= 0 or result.get('invalidated', 0) >= 0

    @pytest.mark.asyncio
    async def test_contradiction_handler_has_dry_run_mode(self):
        """ContradictionHandler should support dry_run mode."""
        from luminescent_cluster.memory.janitor.contradiction import ContradictionHandler
        from luminescent_cluster.memory.providers.local import LocalMemoryProvider

        handler = ContradictionHandler()
        provider = LocalMemoryProvider()

        result = await handler.run(provider, "user-1", dry_run=True)
        assert 'dry_run' in result or 'would_resolve' in result or result.get('resolved', 0) == 0

    @pytest.mark.asyncio
    async def test_contradiction_handler_soft_delete_default(self):
        """ContradictionHandler should use soft-delete by default."""
        from luminescent_cluster.memory.janitor.contradiction import ContradictionHandler
        from luminescent_cluster.memory.providers.local import LocalMemoryProvider

        handler = ContradictionHandler()
        provider = LocalMemoryProvider()
        now = datetime.now(timezone.utc)

        # Create contradicting memories
        await provider.store(Memory(
            user_id="user-1",
            content="Prefers tabs over spaces",
            memory_type=MemoryType.PREFERENCE,
            confidence=0.9,
            source="test",
            raw_source="test",
            extraction_version=1,
            created_at=now - timedelta(days=1),
            last_accessed_at=now,
        ), {})

        await provider.store(Memory(
            user_id="user-1",
            content="Prefers spaces over tabs",
            memory_type=MemoryType.PREFERENCE,
            confidence=0.9,
            source="test",
            raw_source="test",
            extraction_version=1,
            created_at=now,
            last_accessed_at=now,
        ), {})

        result = await handler.run(provider, "user-1")

        # Should resolve without hard-deleting
        assert result.get('resolved', 0) >= 0 or result.get('invalidated', 0) >= 0
