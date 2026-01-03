# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
TDD: RED Phase - Tests for LocalMemoryProvider.

These tests define the expected behavior for the OSS implementation
of the MemoryProvider protocol.

Related GitHub Issues:
- #85: Implement LocalMemoryProvider

ADR Reference: ADR-003 Memory Architecture, Phase 1a (Storage)
"""

import pytest
from datetime import datetime, timezone
from typing import Optional


class TestLocalMemoryProviderExists:
    """TDD: Tests for LocalMemoryProvider class existence."""

    def test_local_memory_provider_class_exists(self):
        """LocalMemoryProvider class should be defined.

        GitHub Issue: #85
        ADR Reference: ADR-003 Phase 1a (Storage)
        """
        from src.memory.providers.local import LocalMemoryProvider

        assert LocalMemoryProvider is not None

    def test_local_memory_provider_implements_protocol(self):
        """LocalMemoryProvider should implement MemoryProvider protocol.

        GitHub Issue: #85
        ADR Reference: ADR-003 Phase 1a (Storage)
        """
        from src.extensions.protocols import MemoryProvider
        from src.memory.providers.local import LocalMemoryProvider

        provider = LocalMemoryProvider()
        assert isinstance(provider, MemoryProvider)


class TestLocalMemoryProviderStore:
    """TDD: Tests for LocalMemoryProvider.store method."""

    @pytest.fixture
    def provider(self):
        """Create a fresh LocalMemoryProvider for each test."""
        from src.memory.providers.local import LocalMemoryProvider

        return LocalMemoryProvider()

    @pytest.fixture
    def sample_memory(self):
        """Create a sample memory for testing."""
        from src.memory.schemas import Memory, MemoryType

        return Memory(
            user_id="user-123",
            content="Prefers tabs over spaces",
            memory_type=MemoryType.PREFERENCE,
            source="conversation",
        )

    @pytest.mark.asyncio
    async def test_store_returns_memory_id(self, provider, sample_memory):
        """store should return a memory ID string.

        GitHub Issue: #85
        ADR Reference: ADR-003 Phase 1a (Storage)
        """
        memory_id = await provider.store(sample_memory, {})
        assert isinstance(memory_id, str)
        assert len(memory_id) > 0

    @pytest.mark.asyncio
    async def test_store_generates_unique_ids(self, provider, sample_memory):
        """store should generate unique IDs for each memory.

        GitHub Issue: #85
        ADR Reference: ADR-003 Phase 1a (Storage)
        """
        id1 = await provider.store(sample_memory, {})
        id2 = await provider.store(sample_memory, {})
        assert id1 != id2


class TestLocalMemoryProviderRetrieve:
    """TDD: Tests for LocalMemoryProvider.retrieve method."""

    @pytest.fixture
    def provider(self):
        """Create a fresh LocalMemoryProvider for each test."""
        from src.memory.providers.local import LocalMemoryProvider

        return LocalMemoryProvider()

    @pytest.fixture
    def sample_memory(self):
        """Create a sample memory for testing."""
        from src.memory.schemas import Memory, MemoryType

        return Memory(
            user_id="user-123",
            content="Prefers tabs over spaces",
            memory_type=MemoryType.PREFERENCE,
            source="conversation",
        )

    @pytest.mark.asyncio
    async def test_retrieve_returns_list(self, provider):
        """retrieve should return a list of memories.

        GitHub Issue: #85
        ADR Reference: ADR-003 Phase 1a (Storage)
        """
        result = await provider.retrieve("tabs or spaces", "user-123")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_retrieve_finds_stored_memory(self, provider, sample_memory):
        """retrieve should find previously stored memories.

        GitHub Issue: #85
        ADR Reference: ADR-003 Phase 1a (Storage)
        """
        await provider.store(sample_memory, {})
        # Use "tabs" as query - substring search matches exact substrings
        result = await provider.retrieve("tabs", "user-123")
        assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_retrieve_respects_user_id(self, provider, sample_memory):
        """retrieve should only return memories for the specified user.

        GitHub Issue: #85
        ADR Reference: ADR-003 Phase 1a (Storage)
        """
        await provider.store(sample_memory, {})
        result = await provider.retrieve("tabs", "other-user")
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_retrieve_respects_limit(self, provider, sample_memory):
        """retrieve should respect the limit parameter.

        GitHub Issue: #85
        ADR Reference: ADR-003 Phase 1a (Storage)
        """
        # Store multiple memories
        for i in range(10):
            memory = sample_memory.model_copy(update={"content": f"Memory {i}"})
            await provider.store(memory, {})

        result = await provider.retrieve("memory", "user-123", limit=3)
        assert len(result) <= 3


class TestLocalMemoryProviderGetById:
    """TDD: Tests for LocalMemoryProvider.get_by_id method."""

    @pytest.fixture
    def provider(self):
        """Create a fresh LocalMemoryProvider for each test."""
        from src.memory.providers.local import LocalMemoryProvider

        return LocalMemoryProvider()

    @pytest.fixture
    def sample_memory(self):
        """Create a sample memory for testing."""
        from src.memory.schemas import Memory, MemoryType

        return Memory(
            user_id="user-123",
            content="Prefers tabs over spaces",
            memory_type=MemoryType.PREFERENCE,
            source="conversation",
        )

    @pytest.mark.asyncio
    async def test_get_by_id_returns_stored_memory(self, provider, sample_memory):
        """get_by_id should return the stored memory.

        GitHub Issue: #85
        ADR Reference: ADR-003 Phase 1a (Storage)
        """
        memory_id = await provider.store(sample_memory, {})
        result = await provider.get_by_id(memory_id)
        assert result is not None
        assert result.content == sample_memory.content

    @pytest.mark.asyncio
    async def test_get_by_id_returns_none_for_unknown(self, provider):
        """get_by_id should return None for unknown IDs.

        GitHub Issue: #85
        ADR Reference: ADR-003 Phase 1a (Storage)
        """
        result = await provider.get_by_id("nonexistent-id")
        assert result is None


class TestLocalMemoryProviderDelete:
    """TDD: Tests for LocalMemoryProvider.delete method."""

    @pytest.fixture
    def provider(self):
        """Create a fresh LocalMemoryProvider for each test."""
        from src.memory.providers.local import LocalMemoryProvider

        return LocalMemoryProvider()

    @pytest.fixture
    def sample_memory(self):
        """Create a sample memory for testing."""
        from src.memory.schemas import Memory, MemoryType

        return Memory(
            user_id="user-123",
            content="Prefers tabs over spaces",
            memory_type=MemoryType.PREFERENCE,
            source="conversation",
        )

    @pytest.mark.asyncio
    async def test_delete_returns_true_for_existing(self, provider, sample_memory):
        """delete should return True for existing memories.

        GitHub Issue: #85
        ADR Reference: ADR-003 Phase 1a (Storage)
        """
        memory_id = await provider.store(sample_memory, {})
        result = await provider.delete(memory_id)
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_returns_false_for_unknown(self, provider):
        """delete should return False for unknown IDs.

        GitHub Issue: #85
        ADR Reference: ADR-003 Phase 1a (Storage)
        """
        result = await provider.delete("nonexistent-id")
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_removes_memory(self, provider, sample_memory):
        """delete should remove the memory from storage.

        GitHub Issue: #85
        ADR Reference: ADR-003 Phase 1a (Storage)
        """
        memory_id = await provider.store(sample_memory, {})
        await provider.delete(memory_id)
        result = await provider.get_by_id(memory_id)
        assert result is None


class TestLocalMemoryProviderSearch:
    """TDD: Tests for LocalMemoryProvider.search method."""

    @pytest.fixture
    def provider(self):
        """Create a fresh LocalMemoryProvider for each test."""
        from src.memory.providers.local import LocalMemoryProvider

        return LocalMemoryProvider()

    @pytest.fixture
    def sample_memory(self):
        """Create a sample memory for testing."""
        from src.memory.schemas import Memory, MemoryType

        return Memory(
            user_id="user-123",
            content="Prefers tabs over spaces",
            memory_type=MemoryType.PREFERENCE,
            source="conversation",
        )

    @pytest.mark.asyncio
    async def test_search_returns_list(self, provider):
        """search should return a list of memories.

        GitHub Issue: #85
        ADR Reference: ADR-003 Phase 1a (Storage)
        """
        result = await provider.search("user-123", {})
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_search_filters_by_memory_type(self, provider):
        """search should filter by memory_type.

        GitHub Issue: #85
        ADR Reference: ADR-003 Phase 1a (Storage)
        """
        from src.memory.schemas import Memory, MemoryType

        # Store different memory types
        pref = Memory(
            user_id="user-123",
            content="Preference",
            memory_type=MemoryType.PREFERENCE,
            source="test",
        )
        fact = Memory(
            user_id="user-123",
            content="Fact",
            memory_type=MemoryType.FACT,
            source="test",
        )
        await provider.store(pref, {})
        await provider.store(fact, {})

        result = await provider.search(
            "user-123", {"memory_type": MemoryType.PREFERENCE}
        )
        assert len(result) == 1
        assert result[0].memory_type == MemoryType.PREFERENCE


class TestProvidersModuleExports:
    """TDD: Tests for providers module exports."""

    def test_providers_module_exists(self):
        """src.memory.providers module should exist.

        GitHub Issue: #85
        ADR Reference: ADR-003 Phase 1a (Storage)
        """
        import src.memory.providers

        assert src.memory.providers is not None

    def test_providers_exports_local_memory_provider(self):
        """providers module should export LocalMemoryProvider.

        GitHub Issue: #85
        ADR Reference: ADR-003 Phase 1a (Storage)
        """
        from src.memory.providers import LocalMemoryProvider

        assert LocalMemoryProvider is not None
