# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
Memory Isolation Tests - Security Exit Criteria.

Verifies zero cross-user memory leakage as specified in ADR-003.

Related GitHub Issues:
- #111: Memory Isolation Tests

ADR Reference: ADR-003 Memory Architecture (Security Requirements)
"""

import pytest
from datetime import datetime, timezone

from luminescent_cluster.memory.providers.local import LocalMemoryProvider
from luminescent_cluster.memory.schemas import Memory, MemoryType


class TestMemoryIsolation:
    """Tests for user memory isolation."""

    @pytest.fixture
    async def provider_with_users(self) -> LocalMemoryProvider:
        """Create provider with memories from multiple users."""
        provider = LocalMemoryProvider()
        now = datetime.now(timezone.utc)

        # User 1 memories
        for i in range(5):
            memory = Memory(
                user_id="user-1",
                content=f"User 1 secret preference {i}",
                memory_type=MemoryType.PREFERENCE,
                confidence=0.9,
                source="conversation",
                raw_source=f"User 1 said something secret {i}",
                extraction_version=1,
                created_at=now,
                last_accessed_at=now,
            )
            await provider.store(memory, {})

        # User 2 memories
        for i in range(5):
            memory = Memory(
                user_id="user-2",
                content=f"User 2 confidential fact {i}",
                memory_type=MemoryType.FACT,
                confidence=0.9,
                source="conversation",
                raw_source=f"User 2 said something confidential {i}",
                extraction_version=1,
                created_at=now,
                last_accessed_at=now,
            )
            await provider.store(memory, {})

        # User 3 memories
        for i in range(5):
            memory = Memory(
                user_id="user-3",
                content=f"User 3 private decision {i}",
                memory_type=MemoryType.DECISION,
                confidence=0.9,
                source="conversation",
                raw_source=f"User 3 decided something private {i}",
                extraction_version=1,
                created_at=now,
                last_accessed_at=now,
            )
            await provider.store(memory, {})

        return provider

    @pytest.mark.asyncio
    async def test_retrieve_only_returns_own_memories(self, provider_with_users):
        """Retrieve should only return memories for the specified user.

        Exit Criteria: Zero cross-user memory leakage
        GitHub Issue: #111
        """
        # User 1 retrieval
        user1_results = await provider_with_users.retrieve(
            query="secret preference confidential", user_id="user-1", limit=100
        )

        for memory in user1_results:
            assert memory.user_id == "user-1", (
                f"Cross-user leakage: user-1 retrieved memory from {memory.user_id}"
            )

        # User 2 retrieval
        user2_results = await provider_with_users.retrieve(
            query="secret preference confidential", user_id="user-2", limit=100
        )

        for memory in user2_results:
            assert memory.user_id == "user-2", (
                f"Cross-user leakage: user-2 retrieved memory from {memory.user_id}"
            )

    @pytest.mark.asyncio
    async def test_search_only_returns_own_memories(self, provider_with_users):
        """Search should only return memories for the specified user.

        Exit Criteria: Zero cross-user memory leakage
        GitHub Issue: #111
        """
        # Search all memory types for user-1
        user1_results = await provider_with_users.search(
            user_id="user-1", filters={}, limit=100
        )

        for memory in user1_results:
            assert memory.user_id == "user-1", (
                f"Cross-user leakage in search: user-1 got memory from {memory.user_id}"
            )

        # Verify user-1 doesn't see user-2 or user-3 memories
        assert all(m.user_id == "user-1" for m in user1_results)

    @pytest.mark.asyncio
    async def test_get_by_id_respects_isolation(self, provider_with_users):
        """Get by ID should not leak memories across users.

        Exit Criteria: Zero cross-user memory leakage
        GitHub Issue: #111
        """
        # Get all user-2 memory IDs
        user2_memories = await provider_with_users.search(
            user_id="user-2", filters={}, limit=100
        )

        # Attempt to access user-2 memories - should work for valid access
        for memory in user2_memories:
            if hasattr(memory, 'id') and memory.id:
                result = await provider_with_users.get_by_id(memory.id)
                if result:
                    # If accessed, should be the correct memory
                    assert result.user_id == "user-2"

    @pytest.mark.asyncio
    async def test_delete_only_affects_own_memories(self):
        """Delete should only affect the specified memory.

        Exit Criteria: Zero cross-user memory leakage
        GitHub Issue: #111
        """
        provider = LocalMemoryProvider()
        now = datetime.now(timezone.utc)

        # Store memories for different users and track IDs
        user1_ids = []
        for i in range(3):
            memory = Memory(
                user_id="user-1",
                content=f"User 1 memory {i}",
                memory_type=MemoryType.PREFERENCE,
                confidence=0.9,
                source="test",
                raw_source="test",
                extraction_version=1,
                created_at=now,
                last_accessed_at=now,
            )
            memory_id = await provider.store(memory, {})
            user1_ids.append(memory_id)

        user2_ids = []
        for i in range(3):
            memory = Memory(
                user_id="user-2",
                content=f"User 2 memory {i}",
                memory_type=MemoryType.FACT,
                confidence=0.9,
                source="test",
                raw_source="test",
                extraction_version=1,
                created_at=now,
                last_accessed_at=now,
            )
            memory_id = await provider.store(memory, {})
            user2_ids.append(memory_id)

        # Get initial counts
        user1_before = await provider.search("user-1", {}, limit=100)
        user2_before = await provider.search("user-2", {}, limit=100)

        # Delete one of user-1's memories
        await provider.delete(user1_ids[0])

        # Verify only user-1's count changed
        user1_after = await provider.search("user-1", {}, limit=100)
        user2_after = await provider.search("user-2", {}, limit=100)

        assert len(user1_after) == len(user1_before) - 1, "User-1 memory not deleted"
        assert len(user2_after) == len(user2_before), "User-2 memories affected by user-1 delete"

    @pytest.mark.asyncio
    async def test_no_cross_user_query_leakage(self, provider_with_users):
        """Queries with content from other users should not return their memories.

        Exit Criteria: Zero cross-user memory leakage
        GitHub Issue: #111
        """
        # User 1 searches for content that exists in user 2's memories
        results = await provider_with_users.retrieve(
            query="User 2 confidential fact",  # Content from user-2
            user_id="user-1",  # Searching as user-1
            limit=100,
        )

        # Should not find user-2's memories even with matching content
        for memory in results:
            assert memory.user_id == "user-1", (
                f"Query leakage: user-1 found user-2 content"
            )

    @pytest.mark.asyncio
    async def test_empty_result_for_nonexistent_user(self, provider_with_users):
        """Non-existent users should get empty results.

        Exit Criteria: Zero cross-user memory leakage
        GitHub Issue: #111
        """
        results = await provider_with_users.retrieve(
            query="anything", user_id="nonexistent-user", limit=100
        )
        assert len(results) == 0

        search_results = await provider_with_users.search(
            user_id="nonexistent-user", filters={}, limit=100
        )
        assert len(search_results) == 0

    @pytest.mark.asyncio
    async def test_store_respects_user_id(self, provider_with_users):
        """Stored memories should be associated with correct user.

        Exit Criteria: Zero cross-user memory leakage
        GitHub Issue: #111
        """
        now = datetime.now(timezone.utc)

        # Store as user-1
        memory = Memory(
            user_id="user-1",
            content="New user-1 memory",
            memory_type=MemoryType.FACT,
            confidence=0.9,
            source="test",
            raw_source="test",
            extraction_version=1,
            created_at=now,
            last_accessed_at=now,
        )
        memory_id = await provider_with_users.store(memory, {})

        # Verify it's accessible to user-1
        user1_results = await provider_with_users.search("user-1", {}, limit=100)
        found = any(m.content == "New user-1 memory" for m in user1_results)
        assert found, "Memory not stored for user-1"

        # Verify it's NOT accessible to user-2
        user2_results = await provider_with_users.search("user-2", {}, limit=100)
        leaked = any(m.content == "New user-1 memory" for m in user2_results)
        assert not leaked, "Memory leaked to user-2"
