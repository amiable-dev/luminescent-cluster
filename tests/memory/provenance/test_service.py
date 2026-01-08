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
        """create_provenance should accept optional metadata."""
        from src.memory.provenance.service import ProvenanceService

        service = ProvenanceService()
        result = await service.create_provenance(
            source_id="mem-123",
            source_type="adr",
            confidence=0.99,
            metadata={"adr_id": "003", "version": "4.4"},
        )

        assert result.source_type == "adr"


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
        """track_retrieval should handle missing provenance gracefully."""
        # Should not raise, just no-op
        await service.track_retrieval(
            memory_id="unknown-mem",
            retrieval_score=0.87,
            retrieved_by="user-456",
        )

        result = await service.get_provenance("unknown-mem")
        assert result is None


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
