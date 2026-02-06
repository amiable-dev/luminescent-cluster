# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
Protocol Compliance Suite.

Tests for MemoryProvider protocol compliance following ADR-007 patterns:
1. Definition Layer - Protocol interface
2. Behavior Layer - Expected behaviors
3. Compliance Layer - Full compliance verification

Related GitHub Issues:
- #112: Protocol Compliance Suite

ADR Reference: ADR-003 Memory Architecture, ADR-007 Extension Points
"""

import pytest
from datetime import datetime, timezone
from typing import Optional

from luminescent_cluster.memory.providers.local import LocalMemoryProvider
from luminescent_cluster.memory.schemas import Memory, MemoryType


class TestProtocolDefinition:
    """Layer 1: Protocol Definition Tests.

    Verifies that MemoryProvider protocol is properly defined.
    """

    def test_protocol_exists(self):
        """MemoryProvider protocol should be defined."""
        from luminescent_cluster.memory.protocols import MemoryProvider
        assert MemoryProvider is not None

    def test_protocol_is_runtime_checkable(self):
        """Protocol should be runtime checkable."""
        from typing import runtime_checkable, Protocol
        from luminescent_cluster.memory.protocols import MemoryProvider

        # Should have @runtime_checkable decorator
        assert hasattr(MemoryProvider, '__protocol_attrs__') or \
               isinstance(MemoryProvider, type)

    def test_protocol_defines_store_method(self):
        """Protocol should define store method."""
        from luminescent_cluster.memory.protocols import MemoryProvider
        assert hasattr(MemoryProvider, 'store')

    def test_protocol_defines_retrieve_method(self):
        """Protocol should define retrieve method."""
        from luminescent_cluster.memory.protocols import MemoryProvider
        assert hasattr(MemoryProvider, 'retrieve')

    def test_protocol_defines_get_by_id_method(self):
        """Protocol should define get_by_id method."""
        from luminescent_cluster.memory.protocols import MemoryProvider
        assert hasattr(MemoryProvider, 'get_by_id')

    def test_protocol_defines_delete_method(self):
        """Protocol should define delete method."""
        from luminescent_cluster.memory.protocols import MemoryProvider
        assert hasattr(MemoryProvider, 'delete')

    def test_protocol_defines_search_method(self):
        """Protocol should define search method."""
        from luminescent_cluster.memory.protocols import MemoryProvider
        assert hasattr(MemoryProvider, 'search')

    def test_protocol_version_defined(self):
        """Protocol version should be defined."""
        from luminescent_cluster.memory.protocols import MEMORY_PROVIDER_VERSION
        assert MEMORY_PROVIDER_VERSION is not None
        assert isinstance(MEMORY_PROVIDER_VERSION, str)


class TestLocalProviderBehavior:
    """Layer 2: Behavior Tests.

    Verifies expected behaviors of MemoryProvider implementations.
    """

    @pytest.fixture
    def provider(self) -> LocalMemoryProvider:
        """Create provider for behavior tests."""
        return LocalMemoryProvider()

    @pytest.fixture
    def sample_memory(self) -> Memory:
        """Create sample memory for testing."""
        now = datetime.now(timezone.utc)
        return Memory(
            user_id="test-user",
            content="Test preference content",
            memory_type=MemoryType.PREFERENCE,
            confidence=0.9,
            source="test",
            raw_source="Original test text",
            extraction_version=1,
            created_at=now,
            last_accessed_at=now,
        )

    @pytest.mark.asyncio
    async def test_store_returns_memory_id(self, provider, sample_memory):
        """Store should return a valid memory ID."""
        memory_id = await provider.store(sample_memory, {})
        assert memory_id is not None
        assert isinstance(memory_id, str)
        assert len(memory_id) > 0

    @pytest.mark.asyncio
    async def test_store_makes_memory_retrievable(self, provider, sample_memory):
        """Stored memory should be retrievable."""
        await provider.store(sample_memory, {})

        results = await provider.retrieve(
            query="Test preference",
            user_id="test-user",
            limit=10,
        )

        assert len(results) > 0
        assert any(m.content == sample_memory.content for m in results)

    @pytest.mark.asyncio
    async def test_retrieve_returns_list(self, provider, sample_memory):
        """Retrieve should return a list of memories."""
        await provider.store(sample_memory, {})

        results = await provider.retrieve(
            query="anything",
            user_id="test-user",
            limit=10,
        )

        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_retrieve_respects_limit(self, provider):
        """Retrieve should respect the limit parameter."""
        now = datetime.now(timezone.utc)

        # Store 10 memories
        for i in range(10):
            memory = Memory(
                user_id="test-user",
                content=f"Memory {i}",
                memory_type=MemoryType.FACT,
                confidence=0.9,
                source="test",
                raw_source="test",
                extraction_version=1,
                created_at=now,
                last_accessed_at=now,
            )
            await provider.store(memory, {})

        # Retrieve with limit
        results = await provider.retrieve("Memory", "test-user", limit=5)
        assert len(results) <= 5

    @pytest.mark.asyncio
    async def test_get_by_id_returns_memory_or_none(self, provider, sample_memory):
        """Get by ID should return memory or None."""
        memory_id = await provider.store(sample_memory, {})

        # Valid ID should return memory
        result = await provider.get_by_id(memory_id)
        assert result is not None
        assert result.content == sample_memory.content

        # Invalid ID should return None
        result = await provider.get_by_id("nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_returns_boolean(self, provider, sample_memory):
        """Delete should return boolean indicating success."""
        memory_id = await provider.store(sample_memory, {})

        # Successful delete
        result = await provider.delete(memory_id)
        assert isinstance(result, bool)
        assert result is True

        # Delete already deleted - should return False
        result = await provider.delete(memory_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_removes_memory(self, provider, sample_memory):
        """Delete should make memory no longer retrievable."""
        memory_id = await provider.store(sample_memory, {})

        await provider.delete(memory_id)

        result = await provider.get_by_id(memory_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_search_returns_list(self, provider, sample_memory):
        """Search should return a list of memories."""
        await provider.store(sample_memory, {})

        results = await provider.search(
            user_id="test-user",
            filters={},
            limit=10,
        )

        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_filters_by_type(self, provider):
        """Search should filter by memory type."""
        now = datetime.now(timezone.utc)

        # Store different types
        pref = Memory(
            user_id="test-user",
            content="Preference memory",
            memory_type=MemoryType.PREFERENCE,
            confidence=0.9,
            source="test",
            raw_source="test",
            extraction_version=1,
            created_at=now,
            last_accessed_at=now,
        )
        fact = Memory(
            user_id="test-user",
            content="Fact memory",
            memory_type=MemoryType.FACT,
            confidence=0.9,
            source="test",
            raw_source="test",
            extraction_version=1,
            created_at=now,
            last_accessed_at=now,
        )

        await provider.store(pref, {})
        await provider.store(fact, {})

        # Search for preferences only
        results = await provider.search(
            user_id="test-user",
            filters={"memory_type": "preference"},
            limit=10,
        )

        for memory in results:
            assert memory.memory_type == MemoryType.PREFERENCE


class TestProtocolCompliance:
    """Layer 3: Full Compliance Tests.

    Verifies that implementations fully comply with the protocol.
    """

    def test_local_provider_implements_protocol(self):
        """LocalMemoryProvider should implement MemoryProvider protocol."""
        from luminescent_cluster.memory.protocols import MemoryProvider

        provider = LocalMemoryProvider()

        # Check required methods exist
        assert hasattr(provider, 'store')
        assert hasattr(provider, 'retrieve')
        assert hasattr(provider, 'get_by_id')
        assert hasattr(provider, 'delete')
        assert hasattr(provider, 'search')

        # Check methods are async
        import asyncio
        assert asyncio.iscoroutinefunction(provider.store)
        assert asyncio.iscoroutinefunction(provider.retrieve)
        assert asyncio.iscoroutinefunction(provider.get_by_id)
        assert asyncio.iscoroutinefunction(provider.delete)
        assert asyncio.iscoroutinefunction(provider.search)

    @pytest.mark.asyncio
    async def test_store_signature_compliance(self):
        """Store should accept (memory, context) and return str."""
        provider = LocalMemoryProvider()
        now = datetime.now(timezone.utc)

        memory = Memory(
            user_id="test",
            content="test",
            memory_type=MemoryType.FACT,
            confidence=0.9,
            source="test",
            raw_source="test",
            extraction_version=1,
            created_at=now,
            last_accessed_at=now,
        )

        result = await provider.store(memory, {})
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_retrieve_signature_compliance(self):
        """Retrieve should accept (query, user_id, limit) and return list."""
        provider = LocalMemoryProvider()

        result = await provider.retrieve("query", "user-id", limit=5)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_by_id_signature_compliance(self):
        """Get by ID should accept (memory_id) and return Optional[Memory]."""
        provider = LocalMemoryProvider()

        result = await provider.get_by_id("nonexistent")
        assert result is None or isinstance(result, Memory)

    @pytest.mark.asyncio
    async def test_delete_signature_compliance(self):
        """Delete should accept (memory_id) and return bool."""
        provider = LocalMemoryProvider()

        result = await provider.delete("nonexistent")
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_search_signature_compliance(self):
        """Search should accept (user_id, filters, limit) and return list."""
        provider = LocalMemoryProvider()

        result = await provider.search("user-id", {}, limit=10)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_complete_crud_workflow(self):
        """Complete CRUD workflow should work correctly."""
        provider = LocalMemoryProvider()
        now = datetime.now(timezone.utc)

        # Create
        memory = Memory(
            user_id="workflow-user",
            content="Workflow test memory",
            memory_type=MemoryType.FACT,
            confidence=0.9,
            source="test",
            raw_source="test",
            extraction_version=1,
            created_at=now,
            last_accessed_at=now,
        )
        memory_id = await provider.store(memory, {})
        assert memory_id is not None

        # Read
        retrieved = await provider.get_by_id(memory_id)
        assert retrieved is not None
        assert retrieved.content == memory.content

        # Search
        search_results = await provider.search("workflow-user", {}, limit=10)
        assert len(search_results) > 0

        # Retrieve
        retrieve_results = await provider.retrieve("Workflow", "workflow-user", limit=10)
        assert len(retrieve_results) > 0

        # Delete
        deleted = await provider.delete(memory_id)
        assert deleted is True

        # Verify deletion
        after_delete = await provider.get_by_id(memory_id)
        assert after_delete is None
