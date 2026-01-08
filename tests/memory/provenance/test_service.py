# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
TDD: Tests for Provenance Service.

These tests define the expected behavior for provenance tracking,
meeting the ADR-003 Phase 2 exit criterion:
"Provenance available for all retrieved items"

Related GitHub Issues:
- #116: Phase 2: Memory Blocks Architecture

ADR Reference: ADR-003 Memory Architecture, Phase 2 (Context Engineering)
"""

from datetime import datetime, timezone
from typing import Optional

import pytest


class TestProvenanceServiceExists:
    """TDD: Tests for ProvenanceService class existence."""

    def test_provenance_service_exists(self):
        """ProvenanceService class should be defined."""
        from src.memory.provenance.service import ProvenanceService

        assert ProvenanceService is not None

    def test_provenance_service_instantiable(self):
        """ProvenanceService should be instantiable."""
        from src.memory.provenance.service import ProvenanceService

        service = ProvenanceService()
        assert service is not None


class TestCreateProvenance:
    """TDD: Tests for provenance creation."""

    @pytest.mark.asyncio
    async def test_create_provenance_returns_provenance(self):
        """create_provenance should return a Provenance object."""
        from src.memory.blocks.schemas import Provenance
        from src.memory.provenance.service import ProvenanceService

        service = ProvenanceService()
        result = await service.create_provenance(
            source_id="mem-123",
            source_type="memory",
            confidence=0.95,
        )

        assert isinstance(result, Provenance)
        assert result.source_id == "mem-123"
        assert result.source_type == "memory"
        assert result.confidence == 0.95

    @pytest.mark.asyncio
    async def test_create_provenance_sets_created_at(self):
        """create_provenance should set created_at timestamp."""
        from src.memory.provenance.service import ProvenanceService

        service = ProvenanceService()
        before = datetime.now(timezone.utc)
        result = await service.create_provenance(
            source_id="mem-123",
            source_type="memory",
            confidence=0.95,
        )
        after = datetime.now(timezone.utc)

        assert result.created_at >= before
        assert result.created_at <= after

    @pytest.mark.asyncio
    async def test_create_provenance_with_metadata(self):
        """create_provenance should store optional metadata."""
        from src.memory.provenance.service import ProvenanceService

        service = ProvenanceService()
        result = await service.create_provenance(
            source_id="mem-123",
            source_type="adr",
            confidence=0.99,
            metadata={"adr_id": "003", "version": "4.4"},
        )

        assert result.source_type == "adr"
        assert result.metadata is not None
        assert result.metadata["adr_id"] == "003"
        assert result.metadata["version"] == "4.4"


class TestAttachProvenance:
    """TDD: Tests for attaching provenance to memories."""

    @pytest.fixture
    def service(self):
        """Create a fresh ProvenanceService for each test."""
        from src.memory.provenance.service import ProvenanceService

        return ProvenanceService()

    @pytest.mark.asyncio
    async def test_attach_to_memory(self, service):
        """attach_to_memory should store provenance for memory ID."""
        from src.memory.blocks.schemas import Provenance

        prov = await service.create_provenance(
            source_id="mem-123",
            source_type="memory",
            confidence=0.95,
        )

        await service.attach_to_memory("mem-456", prov)

        # Should be retrievable
        retrieved = await service.get_provenance("mem-456")
        assert retrieved is not None
        assert retrieved.source_id == "mem-123"

    @pytest.mark.asyncio
    async def test_attach_overwrites_existing(self, service):
        """attach_to_memory should overwrite existing provenance."""
        prov1 = await service.create_provenance(
            source_id="old-source",
            source_type="memory",
            confidence=0.5,
        )
        prov2 = await service.create_provenance(
            source_id="new-source",
            source_type="adr",
            confidence=0.99,
        )

        await service.attach_to_memory("mem-123", prov1)
        await service.attach_to_memory("mem-123", prov2)

        retrieved = await service.get_provenance("mem-123")
        assert retrieved.source_id == "new-source"


class TestGetProvenance:
    """TDD: Tests for retrieving provenance."""

    @pytest.fixture
    def service(self):
        """Create a fresh ProvenanceService for each test."""
        from src.memory.provenance.service import ProvenanceService

        return ProvenanceService()

    @pytest.mark.asyncio
    async def test_get_provenance_returns_none_if_not_found(self, service):
        """get_provenance should return None for unknown memory IDs."""
        result = await service.get_provenance("unknown-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_provenance_returns_attached(self, service):
        """get_provenance should return attached provenance."""
        prov = await service.create_provenance(
            source_id="mem-123",
            source_type="memory",
            confidence=0.95,
        )
        await service.attach_to_memory("target-mem", prov)

        result = await service.get_provenance("target-mem")

        assert result is not None
        assert result.source_id == "mem-123"
        assert result.confidence == 0.95


class TestTrackRetrieval:
    """TDD: Tests for tracking retrieval events."""

    @pytest.fixture
    def service(self):
        """Create a fresh ProvenanceService for each test."""
        from src.memory.provenance.service import ProvenanceService

        return ProvenanceService()

    @pytest.mark.asyncio
    async def test_track_retrieval_updates_score(self, service):
        """track_retrieval should update retrieval_score in provenance."""
        prov = await service.create_provenance(
            source_id="mem-123",
            source_type="memory",
            confidence=0.95,
        )
        await service.attach_to_memory("target-mem", prov)

        await service.track_retrieval(
            memory_id="target-mem",
            retrieval_score=0.87,
            retrieved_by="user-456",
        )

        result = await service.get_provenance("target-mem")
        assert result.retrieval_score == 0.87

    @pytest.mark.asyncio
    async def test_track_retrieval_without_existing_provenance(self, service):
        """track_retrieval should silently no-op for unknown memory IDs.

        Council Round 11: Prevents orphan entries in _retrieval_history
        that would cause unbounded memory growth.
        """
        # Should not raise, just no-op
        await service.track_retrieval(
            memory_id="unknown-mem",
            retrieval_score=0.87,
            retrieved_by="user-456",
        )

        # Provenance should still not exist
        result = await service.get_provenance("unknown-mem")
        assert result is None

        # Retrieval history should NOT have an orphan entry
        history = await service.get_retrieval_history("unknown-mem")
        assert history == [], "Should not create orphan retrieval history entries"


class TestProvenanceHistory:
    """TDD: Tests for provenance history tracking."""

    @pytest.fixture
    def service(self):
        """Create a fresh ProvenanceService for each test."""
        from src.memory.provenance.service import ProvenanceService

        return ProvenanceService()

    @pytest.mark.asyncio
    async def test_get_retrieval_history(self, service):
        """get_retrieval_history should return list of retrieval events."""
        prov = await service.create_provenance(
            source_id="mem-123",
            source_type="memory",
            confidence=0.95,
        )
        await service.attach_to_memory("target-mem", prov)

        await service.track_retrieval("target-mem", 0.87, "user-1")
        await service.track_retrieval("target-mem", 0.92, "user-2")

        history = await service.get_retrieval_history("target-mem")

        assert len(history) == 2
        assert history[0]["retrieved_by"] == "user-1"
        assert history[1]["retrieved_by"] == "user-2"

    @pytest.mark.asyncio
    async def test_get_retrieval_history_empty_for_unknown(self, service):
        """get_retrieval_history should return empty list for unknown memory."""
        history = await service.get_retrieval_history("unknown-mem")
        assert history == []


class TestMemoryBoundedStorage:
    """TDD: Tests for bounded storage to prevent memory leaks.

    Council Round 9: Identified unbounded memory growth in retrieval history.
    """

    @pytest.fixture
    def service(self):
        """Create a fresh ProvenanceService for each test."""
        from src.memory.provenance.service import ProvenanceService

        return ProvenanceService()

    @pytest.mark.asyncio
    async def test_retrieval_history_is_bounded(self, service):
        """Retrieval history should have a maximum size to prevent memory leaks."""
        prov = await service.create_provenance(
            source_id="mem-123",
            source_type="memory",
            confidence=0.95,
        )
        await service.attach_to_memory("target-mem", prov)

        # Track many retrieval events
        for i in range(200):
            await service.track_retrieval("target-mem", 0.5 + (i / 1000), f"user-{i}")

        history = await service.get_retrieval_history("target-mem")

        # Should be bounded (default 100)
        assert len(history) <= 100, "Retrieval history should be bounded to prevent memory leaks"

    @pytest.mark.asyncio
    async def test_retrieval_history_keeps_recent(self, service):
        """Bounded retrieval history should keep most recent events."""
        prov = await service.create_provenance(
            source_id="mem-123",
            source_type="memory",
            confidence=0.95,
        )
        await service.attach_to_memory("target-mem", prov)

        # Track many retrieval events
        for i in range(150):
            await service.track_retrieval("target-mem", 0.5, f"user-{i}")

        history = await service.get_retrieval_history("target-mem")

        # Should keep the most recent events (user-50 to user-149)
        if len(history) == 100:
            # Latest should be most recent
            assert history[-1]["retrieved_by"] == "user-149"

    @pytest.mark.asyncio
    async def test_provenance_store_is_bounded(self, service):
        """Provenance store should enforce MAX_PROVENANCE_ENTRIES limit with LRU eviction."""
        from src.memory.provenance.service import ProvenanceService

        # Create service with smaller limit for testing
        service.MAX_PROVENANCE_ENTRIES = 100

        # Attach more entries than the limit
        for i in range(150):
            prov = await service.create_provenance(
                source_id=f"src-{i}",
                source_type="memory",
                confidence=0.95,
            )
            await service.attach_to_memory(f"mem-{i}", prov)

        # Should be bounded to MAX_PROVENANCE_ENTRIES
        assert len(service._provenance_store) == 100, "Provenance store should enforce bound"

        # Oldest entries (mem-0 through mem-49) should be evicted
        oldest_evicted = await service.get_provenance("mem-0")
        assert oldest_evicted is None, "Oldest entries should be evicted"

        # Newest entries should still be present
        newest = await service.get_provenance("mem-149")
        assert newest is not None, "Newest entries should be present"

    @pytest.mark.asyncio
    async def test_provenance_store_lru_updates_on_access(self, service):
        """Accessing provenance should update LRU order to prevent eviction."""
        from src.memory.provenance.service import ProvenanceService

        # Create service with smaller limit for testing
        service.MAX_PROVENANCE_ENTRIES = 5

        # Attach 5 entries
        for i in range(5):
            prov = await service.create_provenance(
                source_id=f"src-{i}",
                source_type="memory",
                confidence=0.95,
            )
            await service.attach_to_memory(f"mem-{i}", prov)

        # Access mem-0 to make it recently used
        await service.get_provenance("mem-0")

        # Add 3 more entries (should evict mem-1, mem-2, mem-3)
        for i in range(5, 8):
            prov = await service.create_provenance(
                source_id=f"src-{i}",
                source_type="memory",
                confidence=0.95,
            )
            await service.attach_to_memory(f"mem-{i}", prov)

        # mem-0 should still be present (was accessed)
        mem_0 = await service.get_provenance("mem-0")
        assert mem_0 is not None, "Recently accessed entry should not be evicted"

        # mem-1 should be evicted (oldest non-accessed)
        mem_1 = await service.get_provenance("mem-1")
        assert mem_1 is None, "Oldest non-accessed entry should be evicted"
