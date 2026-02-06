# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Tests for MaaS Provider & Services - ADR-003 Phase 4.2 (Issues #150-155).

TDD RED phase: Write tests first, then implement.
"""

import pytest

from luminescent_cluster.memory.maas.registry import AgentRegistry
from luminescent_cluster.memory.maas.types import AgentCapability, AgentType


class TestMaaSProvider:
    """Test MaaSMemoryProvider wrapper."""

    def setup_method(self):
        """Reset registries before each test."""
        from luminescent_cluster.memory.maas.handoff import HandoffManager
        from luminescent_cluster.memory.maas.pool import PoolRegistry
        from luminescent_cluster.memory.maas.registry import AgentRegistry

        AgentRegistry.reset()
        PoolRegistry.reset()
        HandoffManager.reset()

    def teardown_method(self):
        """Reset registries after each test."""
        from luminescent_cluster.memory.maas.handoff import HandoffManager
        from luminescent_cluster.memory.maas.pool import PoolRegistry
        from luminescent_cluster.memory.maas.registry import AgentRegistry

        AgentRegistry.reset()
        PoolRegistry.reset()
        HandoffManager.reset()

    @pytest.mark.asyncio
    async def test_provider_store(self):
        """Verify provider can store memory with agent context."""
        from luminescent_cluster.memory.maas.provider import MaaSMemoryProvider
        from luminescent_cluster.memory.schemas.memory_types import Memory, MemoryType

        provider = MaaSMemoryProvider()

        memory = Memory(
            user_id="user-123",
            content="Test memory content",
            memory_type=MemoryType.FACT,
            source="test",
        )

        memory_id = await provider.store(
            memory=memory,
            context={"agent_id": "agent-001"},
        )

        assert memory_id is not None
        assert isinstance(memory_id, str)

    @pytest.mark.asyncio
    async def test_provider_retrieve(self):
        """Verify provider can retrieve memories."""
        from luminescent_cluster.memory.maas.provider import MaaSMemoryProvider
        from luminescent_cluster.memory.schemas.memory_types import Memory, MemoryType

        provider = MaaSMemoryProvider()

        # Store a memory first
        memory = Memory(
            user_id="user-123",
            content="Test retrieval content",
            memory_type=MemoryType.FACT,
            source="test",
        )
        await provider.store(memory=memory, context={})

        # Retrieve
        results = await provider.retrieve(
            query="retrieval",
            user_id="user-123",
            limit=5,
        )

        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_provider_get_by_id(self):
        """Verify provider can get memory by ID."""
        from luminescent_cluster.memory.maas.provider import MaaSMemoryProvider
        from luminescent_cluster.memory.schemas.memory_types import Memory, MemoryType

        provider = MaaSMemoryProvider()

        memory = Memory(
            user_id="user-123",
            content="Test get by ID",
            memory_type=MemoryType.PREFERENCE,
            source="test",
        )
        memory_id = await provider.store(memory=memory, context={})

        result = await provider.get_by_id(memory_id)

        assert result is not None
        assert result.content == "Test get by ID"

    @pytest.mark.asyncio
    async def test_provider_delete(self):
        """Verify provider can delete memory."""
        from luminescent_cluster.memory.maas.provider import MaaSMemoryProvider
        from luminescent_cluster.memory.schemas.memory_types import Memory, MemoryType

        provider = MaaSMemoryProvider()

        memory = Memory(
            user_id="user-123",
            content="Test delete",
            memory_type=MemoryType.FACT,
            source="test",
        )
        memory_id = await provider.store(memory=memory, context={})

        result = await provider.delete(memory_id)
        assert result is True

        # Should be gone
        retrieved = await provider.get_by_id(memory_id)
        assert retrieved is None


class TestCodeKBService:
    """Test Code Knowledge Base service."""

    def test_search_code_kb(self):
        """Verify code KB search works."""
        from luminescent_cluster.memory.maas.services import CodeKBService

        service = CodeKBService()

        # Mock search - should return empty for now
        results = service.search(query="authentication", limit=5)

        assert isinstance(results, list)

    def test_search_with_service_filter(self):
        """Verify code KB search can filter by service."""
        from luminescent_cluster.memory.maas.services import CodeKBService

        service = CodeKBService()

        results = service.search(
            query="authentication",
            service_filter="auth-service",
            limit=5,
        )

        assert isinstance(results, list)


class TestDecisionService:
    """Test Decision service for ADRs."""

    def test_search_decisions(self):
        """Verify decision search works."""
        from luminescent_cluster.memory.maas.services import DecisionService

        service = DecisionService()

        results = service.search(query="database choice", limit=5)

        assert isinstance(results, list)

    def test_get_decision_by_id(self):
        """Verify decision can be retrieved by ID."""
        from luminescent_cluster.memory.maas.services import DecisionService

        service = DecisionService()

        # Should return None for nonexistent
        result = service.get_by_id("ADR-999")

        assert result is None


class TestIncidentService:
    """Test Incident service."""

    def test_search_incidents(self):
        """Verify incident search works."""
        from luminescent_cluster.memory.maas.services import IncidentService

        service = IncidentService()

        results = service.search(query="outage", limit=5)

        assert isinstance(results, list)

    def test_search_incidents_by_service(self):
        """Verify incidents can be filtered by service."""
        from luminescent_cluster.memory.maas.services import IncidentService

        service = IncidentService()

        results = service.search(
            query="outage",
            service_filter="payment-service",
            limit=5,
        )

        assert isinstance(results, list)
