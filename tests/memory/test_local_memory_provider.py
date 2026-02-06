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
        from luminescent_cluster.memory.providers.local import LocalMemoryProvider

        assert LocalMemoryProvider is not None

    def test_local_memory_provider_implements_protocol(self):
        """LocalMemoryProvider should implement MemoryProvider protocol.

        GitHub Issue: #85
        ADR Reference: ADR-003 Phase 1a (Storage)
        """
        from luminescent_cluster.extensions.protocols import MemoryProvider
        from luminescent_cluster.memory.providers.local import LocalMemoryProvider

        provider = LocalMemoryProvider()
        assert isinstance(provider, MemoryProvider)


class TestLocalMemoryProviderStore:
    """TDD: Tests for LocalMemoryProvider.store method."""

    @pytest.fixture
    def provider(self):
        """Create a fresh LocalMemoryProvider for each test."""
        from luminescent_cluster.memory.providers.local import LocalMemoryProvider

        return LocalMemoryProvider()

    @pytest.fixture
    def sample_memory(self):
        """Create a sample memory for testing."""
        from luminescent_cluster.memory.schemas import Memory, MemoryType

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
        from luminescent_cluster.memory.providers.local import LocalMemoryProvider

        return LocalMemoryProvider()

    @pytest.fixture
    def sample_memory(self):
        """Create a sample memory for testing."""
        from luminescent_cluster.memory.schemas import Memory, MemoryType

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
        from luminescent_cluster.memory.providers.local import LocalMemoryProvider

        return LocalMemoryProvider()

    @pytest.fixture
    def sample_memory(self):
        """Create a sample memory for testing."""
        from luminescent_cluster.memory.schemas import Memory, MemoryType

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
        from luminescent_cluster.memory.providers.local import LocalMemoryProvider

        return LocalMemoryProvider()

    @pytest.fixture
    def sample_memory(self):
        """Create a sample memory for testing."""
        from luminescent_cluster.memory.schemas import Memory, MemoryType

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
        from luminescent_cluster.memory.providers.local import LocalMemoryProvider

        return LocalMemoryProvider()

    @pytest.fixture
    def sample_memory(self):
        """Create a sample memory for testing."""
        from luminescent_cluster.memory.schemas import Memory, MemoryType

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
        from luminescent_cluster.memory.schemas import Memory, MemoryType

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
        """luminescent_cluster.memory.providers module should exist.

        GitHub Issue: #85
        ADR Reference: ADR-003 Phase 1a (Storage)
        """
        import luminescent_cluster.memory.providers

        assert luminescent_cluster.memory.providers is not None

    def test_providers_exports_local_memory_provider(self):
        """providers module should export LocalMemoryProvider.

        GitHub Issue: #85
        ADR Reference: ADR-003 Phase 1a (Storage)
        """
        from luminescent_cluster.memory.providers import LocalMemoryProvider

        assert LocalMemoryProvider is not None


class TestLocalMemoryProviderHybridRetrieval:
    """Tests for LocalMemoryProvider with hybrid retrieval enabled.

    ADR Reference: ADR-003 Phase 3 (Two-Stage Retrieval)
    """

    @pytest.fixture
    def hybrid_provider(self):
        """Create a LocalMemoryProvider with hybrid retrieval enabled."""
        from luminescent_cluster.memory.providers.local import LocalMemoryProvider

        # Use fallback reranker (no cross-encoder) for faster tests
        return LocalMemoryProvider(
            use_hybrid_retrieval=True,
            use_cross_encoder=False,
            use_query_rewriter=False,
        )

    @pytest.fixture
    def sample_memories(self):
        """Create sample memories for testing."""
        from luminescent_cluster.memory.schemas import Memory, MemoryType

        return [
            Memory(
                user_id="user-123",
                content="Prefers tabs over spaces for indentation",
                memory_type=MemoryType.PREFERENCE,
                source="conversation",
            ),
            Memory(
                user_id="user-123",
                content="Uses Python for backend development",
                memory_type=MemoryType.FACT,
                source="conversation",
            ),
            Memory(
                user_id="user-123",
                content="Decided to use PostgreSQL for the database",
                memory_type=MemoryType.DECISION,
                source="meeting",
            ),
            Memory(
                user_id="user-123",
                content="Prefers dark mode in all applications",
                memory_type=MemoryType.PREFERENCE,
                source="conversation",
            ),
        ]

    def test_hybrid_provider_is_hybrid_enabled(self, hybrid_provider):
        """Hybrid provider should report hybrid is enabled."""
        assert hybrid_provider.is_hybrid_enabled is True

    def test_simple_provider_is_not_hybrid_enabled(self):
        """Simple provider should report hybrid is disabled."""
        from luminescent_cluster.memory.providers.local import LocalMemoryProvider

        provider = LocalMemoryProvider()
        assert provider.is_hybrid_enabled is False

    @pytest.mark.asyncio
    async def test_hybrid_store_and_retrieve(self, hybrid_provider, sample_memories):
        """Hybrid provider should store and retrieve memories."""
        # Store all memories
        for memory in sample_memories:
            await hybrid_provider.store(memory, {})

        # Retrieve using semantic query
        results = await hybrid_provider.retrieve("indentation", "user-123")
        assert len(results) >= 1
        # Should find the tabs preference
        contents = [r.content for r in results]
        assert any("tabs" in c.lower() for c in contents)

    @pytest.mark.asyncio
    async def test_hybrid_retrieve_respects_user_id(self, hybrid_provider, sample_memories):
        """Hybrid retrieval should only return memories for the specified user."""
        # Store memories
        for memory in sample_memories:
            await hybrid_provider.store(memory, {})

        # Query with different user ID
        results = await hybrid_provider.retrieve("tabs", "other-user")
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_hybrid_retrieve_respects_limit(self, hybrid_provider, sample_memories):
        """Hybrid retrieval should respect the limit parameter."""
        # Store memories
        for memory in sample_memories:
            await hybrid_provider.store(memory, {})

        results = await hybrid_provider.retrieve("prefers", "user-123", limit=1)
        assert len(results) <= 1

    @pytest.mark.asyncio
    async def test_hybrid_delete_removes_from_index(self, hybrid_provider, sample_memories):
        """Deleting a memory should remove it from hybrid indexes."""
        # Store memories
        memory_ids = []
        for memory in sample_memories:
            mid = await hybrid_provider.store(memory, {})
            memory_ids.append(mid)

        # Verify memory can be retrieved
        results_before = await hybrid_provider.retrieve("tabs", "user-123")
        assert len(results_before) >= 1

        # Delete the tabs preference memory
        tabs_id = memory_ids[0]  # First memory is tabs preference
        await hybrid_provider.delete(tabs_id)

        # After deletion, should not find by get_by_id
        result = await hybrid_provider.get_by_id(tabs_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_hybrid_clear_removes_all(self, hybrid_provider, sample_memories):
        """Clear should remove all memories from hybrid indexes."""
        # Store memories
        for memory in sample_memories:
            await hybrid_provider.store(memory, {})

        # Verify memories exist
        assert hybrid_provider.count() == len(sample_memories)

        # Clear all
        hybrid_provider.clear()

        # Should be empty
        assert hybrid_provider.count() == 0

    @pytest.mark.asyncio
    async def test_hybrid_retrieve_with_scores(self, hybrid_provider, sample_memories):
        """retrieve_with_scores should return memories with scores."""
        # Store memories
        for memory in sample_memories:
            await hybrid_provider.store(memory, {})

        results = await hybrid_provider.retrieve_with_scores("Python", "user-123")
        assert len(results) >= 1

        # Each result should be (Memory, score) tuple
        for memory, score in results:
            assert hasattr(memory, "content")
            assert isinstance(score, float)
            assert score >= 0.0

    @pytest.mark.asyncio
    async def test_hybrid_retrieve_with_metrics(self, hybrid_provider, sample_memories):
        """retrieve_with_metrics should return memories with metrics."""
        from luminescent_cluster.memory.retrieval.hybrid import RetrievalMetrics

        # Store memories
        for memory in sample_memories:
            await hybrid_provider.store(memory, {})

        memories, metrics = await hybrid_provider.retrieve_with_metrics(
            "database", "user-123"
        )

        assert isinstance(memories, list)
        assert isinstance(metrics, RetrievalMetrics)
        assert metrics.total_time_ms >= 0

    @pytest.mark.asyncio
    async def test_retrieve_with_scores_requires_hybrid(self):
        """retrieve_with_scores should raise if hybrid not enabled."""
        from luminescent_cluster.memory.providers.local import LocalMemoryProvider

        provider = LocalMemoryProvider()  # Simple mode

        with pytest.raises(RuntimeError, match="requires hybrid retrieval"):
            await provider.retrieve_with_scores("query", "user-123")

    @pytest.mark.asyncio
    async def test_retrieve_with_metrics_requires_hybrid(self):
        """retrieve_with_metrics should raise if hybrid not enabled."""
        from luminescent_cluster.memory.providers.local import LocalMemoryProvider

        provider = LocalMemoryProvider()  # Simple mode

        with pytest.raises(RuntimeError, match="requires hybrid retrieval"):
            await provider.retrieve_with_metrics("query", "user-123")

    @pytest.mark.asyncio
    async def test_hybrid_filters_invalid_memories(self, hybrid_provider):
        """Hybrid retrieval should filter out invalidated memories."""
        from luminescent_cluster.memory.schemas import Memory, MemoryType

        # Store a valid memory
        valid = Memory(
            user_id="user-123",
            content="Valid preference for testing",
            memory_type=MemoryType.PREFERENCE,
            source="test",
        )
        valid_id = await hybrid_provider.store(valid, {})

        # Store an invalidated memory
        invalid = Memory(
            user_id="user-123",
            content="Invalid preference for testing",
            memory_type=MemoryType.PREFERENCE,
            source="test",
            metadata={"is_valid": False},
        )
        await hybrid_provider.store(invalid, {})

        # Retrieve should only return valid memory
        results = await hybrid_provider.retrieve("preference", "user-123")
        assert len(results) == 1
        assert results[0].content == valid.content


class TestLocalMemoryProviderHybridIntegration:
    """Integration tests for hybrid retrieval with real components.

    These tests verify the full two-stage pipeline works correctly.
    """

    @pytest.fixture
    def full_hybrid_provider(self):
        """Create provider with all hybrid features enabled."""
        from luminescent_cluster.memory.providers.local import LocalMemoryProvider

        return LocalMemoryProvider(
            use_hybrid_retrieval=True,
            use_cross_encoder=False,  # Use fallback for speed
            use_query_rewriter=True,
        )

    @pytest.fixture
    def diverse_memories(self):
        """Create diverse memories for semantic testing."""
        from luminescent_cluster.memory.schemas import Memory, MemoryType

        return [
            Memory(
                user_id="user-1",
                content="The authentication system uses JWT tokens with RSA256 signing",
                memory_type=MemoryType.FACT,
                source="codebase",
            ),
            Memory(
                user_id="user-1",
                content="User prefers React over Vue for frontend development",
                memory_type=MemoryType.PREFERENCE,
                source="conversation",
            ),
            Memory(
                user_id="user-1",
                content="Decided to implement caching using Redis for session storage",
                memory_type=MemoryType.DECISION,
                source="meeting",
            ),
            Memory(
                user_id="user-1",
                content="The API rate limiting is set to 100 requests per minute",
                memory_type=MemoryType.FACT,
                source="documentation",
            ),
            Memory(
                user_id="user-1",
                content="Prefers PostgreSQL over MySQL for relational databases",
                memory_type=MemoryType.PREFERENCE,
                source="conversation",
            ),
        ]

    @pytest.mark.asyncio
    async def test_semantic_similarity_retrieval(
        self, full_hybrid_provider, diverse_memories
    ):
        """Hybrid retrieval should find semantically similar content."""
        # Store all memories
        for memory in diverse_memories:
            await full_hybrid_provider.store(memory, {})

        # Query for auth-related content (should find JWT memory)
        results = await full_hybrid_provider.retrieve("login security", "user-1")
        # Vector search should find auth-related content
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_keyword_retrieval(self, full_hybrid_provider, diverse_memories):
        """Hybrid retrieval should find keyword matches via BM25."""
        # Store all memories
        for memory in diverse_memories:
            await full_hybrid_provider.store(memory, {})

        # Query with exact keyword
        results = await full_hybrid_provider.retrieve("PostgreSQL", "user-1")
        assert len(results) >= 1
        # Should find the PostgreSQL preference
        contents = [r.content for r in results]
        assert any("PostgreSQL" in c for c in contents)

    @pytest.mark.asyncio
    async def test_multi_user_isolation(self, full_hybrid_provider):
        """Hybrid retrieval should maintain user isolation."""
        from luminescent_cluster.memory.schemas import Memory, MemoryType

        # Store memories for two users
        user1_memory = Memory(
            user_id="user-1",
            content="User 1's secret configuration",
            memory_type=MemoryType.FACT,
            source="test",
        )
        user2_memory = Memory(
            user_id="user-2",
            content="User 2's secret configuration",
            memory_type=MemoryType.FACT,
            source="test",
        )
        await full_hybrid_provider.store(user1_memory, {})
        await full_hybrid_provider.store(user2_memory, {})

        # User 1 should only see their memory
        results1 = await full_hybrid_provider.retrieve("secret", "user-1")
        assert len(results1) == 1
        assert "User 1" in results1[0].content

        # User 2 should only see their memory
        results2 = await full_hybrid_provider.retrieve("secret", "user-2")
        assert len(results2) == 1
        assert "User 2" in results2[0].content

    @pytest.mark.asyncio
    async def test_empty_results_for_no_index(self, full_hybrid_provider):
        """Hybrid retrieval should return empty for users with no memories."""
        results = await full_hybrid_provider.retrieve("anything", "nonexistent-user")
        assert results == []


class TestLocalMemoryProviderGraphSupport:
    """Tests for Knowledge Graph integration in LocalMemoryProvider.

    ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
    GitHub Issue: #126
    """

    @pytest.fixture
    def graph_provider(self):
        """Create provider with graph enabled."""
        from luminescent_cluster.memory.providers.local import LocalMemoryProvider

        return LocalMemoryProvider(
            use_hybrid_retrieval=True,
            use_cross_encoder=False,  # Fast tests
            use_query_rewriter=False,
            use_graph=True,
        )

    @pytest.fixture
    def sample_memories_with_entities(self):
        """Create memories with extractable entities."""
        from luminescent_cluster.memory.schemas import Memory, MemoryType

        return [
            Memory(
                user_id="user-123",
                content="The auth-service uses PostgreSQL for user data",
                memory_type=MemoryType.FACT,
                source="codebase",
            ),
            Memory(
                user_id="user-123",
                content="Payment service also connects to PostgreSQL",
                memory_type=MemoryType.FACT,
                source="codebase",
            ),
            Memory(
                user_id="user-123",
                content="Auth service had an incident yesterday",
                memory_type=MemoryType.FACT,
                source="incident-report",
            ),
        ]

    def test_provider_accepts_use_graph_parameter(self):
        """Provider should accept use_graph parameter.

        GitHub Issue: #126
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.providers.local import LocalMemoryProvider

        provider = LocalMemoryProvider(
            use_hybrid_retrieval=True,
            use_graph=True,
        )
        assert provider.is_graph_enabled is True

    def test_graph_defaults_to_disabled(self):
        """Graph should be disabled by default.

        GitHub Issue: #126
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.providers.local import LocalMemoryProvider

        provider = LocalMemoryProvider(use_hybrid_retrieval=True)
        assert provider.is_graph_enabled is False

    def test_graph_requires_hybrid(self):
        """Graph requires hybrid retrieval to be enabled.

        GitHub Issue: #126
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        from luminescent_cluster.memory.providers.local import LocalMemoryProvider

        # Graph with hybrid disabled should not enable graph
        provider = LocalMemoryProvider(
            use_hybrid_retrieval=False,
            use_graph=True,
        )
        assert provider.is_graph_enabled is False

    @pytest.mark.asyncio
    async def test_store_updates_graph(self, graph_provider, sample_memories_with_entities):
        """Storing memory should update the graph.

        GitHub Issue: #126
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        # Store memories with entities
        for memory in sample_memories_with_entities:
            await graph_provider.store(memory, {})

        # Graph should be updated (check via retrieval metrics)
        _, metrics = await graph_provider.retrieve_with_metrics(
            "postgresql", "user-123"
        )

        # Graph candidates should be tracked
        assert hasattr(metrics, "graph_candidates")

    @pytest.mark.asyncio
    async def test_clear_clears_graph(self, graph_provider, sample_memories_with_entities):
        """Clear should clear the graph.

        GitHub Issue: #126
        ADR Reference: ADR-003 Phase 4 (Knowledge Graph)
        """
        # Store memories
        for memory in sample_memories_with_entities:
            await graph_provider.store(memory, {})

        # Clear
        graph_provider.clear()

        # Should be empty
        assert graph_provider.count() == 0
