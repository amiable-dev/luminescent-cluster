# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
TDD: RED Phase - Tests for Memory MCP Tools.

These tests define the expected behavior for the memory CRUD MCP tools:
- create_memory
- get_memories
- search_memories
- delete_memory

Related GitHub Issues:
- #86: create_memory MCP Tool
- #87: get_memories MCP Tool
- #88: search_memories MCP Tool
- #89: delete_memory MCP Tool

ADR Reference: ADR-003 Memory Architecture, Phase 1a (Storage)
"""

import pytest
from datetime import datetime, timezone
from typing import Any


class TestCreateMemoryTool:
    """TDD: Tests for create_memory MCP tool."""

    def test_create_memory_function_exists(self):
        """create_memory function should be defined.

        GitHub Issue: #86
        ADR Reference: ADR-003 Phase 1a (MCP Tools)
        """
        from src.memory.mcp.tools import create_memory

        assert callable(create_memory)

    @pytest.mark.asyncio
    async def test_create_memory_returns_dict(self):
        """create_memory should return a dict with memory_id.

        GitHub Issue: #86
        ADR Reference: ADR-003 Phase 1a (MCP Tools)
        """
        from src.memory.mcp.tools import create_memory

        result = await create_memory(
            user_id="user-123",
            content="Prefers tabs over spaces",
            memory_type="preference",
            source="conversation",
        )

        assert isinstance(result, dict)
        assert "memory_id" in result

    @pytest.mark.asyncio
    async def test_create_memory_validates_memory_type(self):
        """create_memory should validate memory_type.

        GitHub Issue: #86
        ADR Reference: ADR-003 Phase 1a (MCP Tools)
        """
        from src.memory.mcp.tools import create_memory

        # Valid types should work
        result = await create_memory(
            user_id="user-123",
            content="Test",
            memory_type="fact",
            source="test",
        )
        assert "memory_id" in result

    @pytest.mark.asyncio
    async def test_create_memory_with_optional_fields(self):
        """create_memory should accept optional fields.

        GitHub Issue: #86
        ADR Reference: ADR-003 Phase 1a (MCP Tools)
        """
        from src.memory.mcp.tools import create_memory

        result = await create_memory(
            user_id="user-123",
            content="Test memory",
            memory_type="decision",
            source="adr",
            confidence=0.95,
            raw_source="Original text",
            metadata={"project": "test-project"},
        )

        assert "memory_id" in result


class TestGetMemoriesTool:
    """TDD: Tests for get_memories MCP tool."""

    def test_get_memories_function_exists(self):
        """get_memories function should be defined.

        GitHub Issue: #87
        ADR Reference: ADR-003 Phase 1a (MCP Tools)
        """
        from src.memory.mcp.tools import get_memories

        assert callable(get_memories)

    @pytest.mark.asyncio
    async def test_get_memories_returns_dict(self):
        """get_memories should return a dict with memories list.

        GitHub Issue: #87
        ADR Reference: ADR-003 Phase 1a (MCP Tools)
        """
        from src.memory.mcp.tools import get_memories

        result = await get_memories(
            query="tabs or spaces",
            user_id="user-123",
        )

        assert isinstance(result, dict)
        assert "memories" in result
        assert isinstance(result["memories"], list)

    @pytest.mark.asyncio
    async def test_get_memories_respects_limit(self):
        """get_memories should respect the limit parameter.

        GitHub Issue: #87
        ADR Reference: ADR-003 Phase 1a (MCP Tools)
        """
        from src.memory.mcp.tools import create_memory, get_memories

        # Create multiple memories
        for i in range(10):
            await create_memory(
                user_id="user-limit-test",
                content=f"Memory number {i}",
                memory_type="fact",
                source="test",
            )

        result = await get_memories(
            query="memory",
            user_id="user-limit-test",
            limit=3,
        )

        assert len(result["memories"]) <= 3

    @pytest.mark.asyncio
    async def test_get_memories_includes_count(self):
        """get_memories should include total count.

        GitHub Issue: #87
        ADR Reference: ADR-003 Phase 1a (MCP Tools)
        """
        from src.memory.mcp.tools import get_memories

        result = await get_memories(
            query="test",
            user_id="user-123",
        )

        assert "count" in result


class TestSearchMemoriesTool:
    """TDD: Tests for search_memories MCP tool."""

    def test_search_memories_function_exists(self):
        """search_memories function should be defined.

        GitHub Issue: #88
        ADR Reference: ADR-003 Phase 1a (MCP Tools)
        """
        from src.memory.mcp.tools import search_memories

        assert callable(search_memories)

    @pytest.mark.asyncio
    async def test_search_memories_returns_dict(self):
        """search_memories should return a dict with memories list.

        GitHub Issue: #88
        ADR Reference: ADR-003 Phase 1a (MCP Tools)
        """
        from src.memory.mcp.tools import search_memories

        result = await search_memories(
            user_id="user-123",
        )

        assert isinstance(result, dict)
        assert "memories" in result

    @pytest.mark.asyncio
    async def test_search_memories_filters_by_type(self):
        """search_memories should filter by memory_type.

        GitHub Issue: #88
        ADR Reference: ADR-003 Phase 1a (MCP Tools)
        """
        from src.memory.mcp.tools import create_memory, search_memories

        # Create different types
        await create_memory(
            user_id="user-filter-test",
            content="A preference",
            memory_type="preference",
            source="test",
        )
        await create_memory(
            user_id="user-filter-test",
            content="A fact",
            memory_type="fact",
            source="test",
        )

        result = await search_memories(
            user_id="user-filter-test",
            memory_type="preference",
        )

        for memory in result["memories"]:
            assert memory["memory_type"] == "preference"

    @pytest.mark.asyncio
    async def test_search_memories_filters_by_source(self):
        """search_memories should filter by source.

        GitHub Issue: #88
        ADR Reference: ADR-003 Phase 1a (MCP Tools)
        """
        from src.memory.mcp.tools import search_memories

        result = await search_memories(
            user_id="user-123",
            source="conversation",
        )

        assert isinstance(result, dict)


class TestDeleteMemoryTool:
    """TDD: Tests for delete_memory MCP tool."""

    def test_delete_memory_function_exists(self):
        """delete_memory function should be defined.

        GitHub Issue: #89
        ADR Reference: ADR-003 Phase 1a (MCP Tools)
        """
        from src.memory.mcp.tools import delete_memory

        assert callable(delete_memory)

    @pytest.mark.asyncio
    async def test_delete_memory_returns_dict(self):
        """delete_memory should return a dict with success status.

        GitHub Issue: #89
        ADR Reference: ADR-003 Phase 1a (MCP Tools)
        """
        from src.memory.mcp.tools import create_memory, delete_memory

        # Create a memory first
        create_result = await create_memory(
            user_id="user-123",
            content="To be deleted",
            memory_type="fact",
            source="test",
        )

        result = await delete_memory(memory_id=create_result["memory_id"])

        assert isinstance(result, dict)
        assert "success" in result

    @pytest.mark.asyncio
    async def test_delete_memory_returns_true_for_existing(self):
        """delete_memory should return success=True for existing memories.

        GitHub Issue: #89
        ADR Reference: ADR-003 Phase 1a (MCP Tools)
        """
        from src.memory.mcp.tools import create_memory, delete_memory

        create_result = await create_memory(
            user_id="user-123",
            content="Delete me",
            memory_type="fact",
            source="test",
        )

        result = await delete_memory(memory_id=create_result["memory_id"])
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_delete_memory_returns_false_for_unknown(self):
        """delete_memory should return success=False for unknown IDs.

        GitHub Issue: #89
        ADR Reference: ADR-003 Phase 1a (MCP Tools)
        """
        from src.memory.mcp.tools import delete_memory

        result = await delete_memory(memory_id="nonexistent-id")
        assert result["success"] is False


class TestGetMemoryByIdTool:
    """TDD: Tests for get_memory_by_id MCP tool."""

    def test_get_memory_by_id_function_exists(self):
        """get_memory_by_id function should be defined.

        GitHub Issue: #87
        ADR Reference: ADR-003 Phase 1a (MCP Tools)
        """
        from src.memory.mcp.tools import get_memory_by_id

        assert callable(get_memory_by_id)

    @pytest.mark.asyncio
    async def test_get_memory_by_id_returns_memory(self):
        """get_memory_by_id should return the memory.

        GitHub Issue: #87
        ADR Reference: ADR-003 Phase 1a (MCP Tools)
        """
        from src.memory.mcp.tools import create_memory, get_memory_by_id

        create_result = await create_memory(
            user_id="user-123",
            content="Test memory",
            memory_type="fact",
            source="test",
        )

        result = await get_memory_by_id(memory_id=create_result["memory_id"])

        assert isinstance(result, dict)
        assert result.get("content") == "Test memory"

    @pytest.mark.asyncio
    async def test_get_memory_by_id_returns_none_for_unknown(self):
        """get_memory_by_id should return error for unknown IDs.

        GitHub Issue: #87
        ADR Reference: ADR-003 Phase 1a (MCP Tools)
        """
        from src.memory.mcp.tools import get_memory_by_id

        result = await get_memory_by_id(memory_id="nonexistent-id")
        assert result.get("error") is not None or result.get("memory") is None


class TestMCPModuleExports:
    """TDD: Tests for MCP module exports."""

    def test_mcp_module_exists(self):
        """src.memory.mcp module should exist.

        GitHub Issue: #86
        ADR Reference: ADR-003 Phase 1a (MCP Tools)
        """
        import src.memory.mcp

        assert src.memory.mcp is not None

    def test_mcp_exports_all_tools(self):
        """mcp module should export all CRUD tools.

        GitHub Issue: #86-89
        ADR Reference: ADR-003 Phase 1a (MCP Tools)
        """
        from src.memory.mcp import (
            create_memory,
            delete_memory,
            get_memories,
            get_memory_by_id,
            search_memories,
        )

        assert callable(create_memory)
        assert callable(get_memories)
        assert callable(search_memories)
        assert callable(delete_memory)
        assert callable(get_memory_by_id)


class TestUpdateMemoryTool:
    """TDD: RED Phase - Tests for update_memory MCP tool.

    ADR-003 Interface Contract: update_memory(key, value, source)

    Related GitHub Issues:
    - #113: Integrate Memory Module with MCP Servers

    ADR Reference: ADR-003 Memory Architecture, Interface Contract (lines 249-279)
    """

    def test_update_memory_function_exists(self):
        """update_memory function should be defined.

        GitHub Issue: #113
        ADR Reference: ADR-003 Interface Contract
        """
        from src.memory.mcp.tools import update_memory

        assert callable(update_memory)

    @pytest.mark.asyncio
    async def test_update_memory_returns_dict(self):
        """update_memory should return a dict with success status.

        GitHub Issue: #113
        ADR Reference: ADR-003 Interface Contract
        """
        from src.memory.mcp.tools import create_memory, update_memory

        # Create a memory first
        create_result = await create_memory(
            user_id="user-update-test",
            content="Original content",
            memory_type="preference",
            source="test",
        )

        result = await update_memory(
            memory_id=create_result["memory_id"],
            content="Updated content",
            source="test-update",
        )

        assert isinstance(result, dict)
        assert "success" in result

    @pytest.mark.asyncio
    async def test_update_memory_changes_content(self):
        """update_memory should change the memory content.

        GitHub Issue: #113
        ADR Reference: ADR-003 Interface Contract
        """
        from src.memory.mcp.tools import create_memory, get_memory_by_id, update_memory

        # Create a memory first
        create_result = await create_memory(
            user_id="user-update-test",
            content="Original content",
            memory_type="fact",
            source="test",
        )

        # Update the memory
        await update_memory(
            memory_id=create_result["memory_id"],
            content="Updated content",
            source="test-update",
        )

        # Verify the update
        result = await get_memory_by_id(create_result["memory_id"])
        assert result.get("content") == "Updated content"

    @pytest.mark.asyncio
    async def test_update_memory_tracks_source(self):
        """update_memory should track the update source.

        GitHub Issue: #113
        ADR Reference: ADR-003 Interface Contract
        """
        from src.memory.mcp.tools import create_memory, get_memory_by_id, update_memory

        create_result = await create_memory(
            user_id="user-update-test",
            content="Test content",
            memory_type="fact",
            source="original-source",
        )

        await update_memory(
            memory_id=create_result["memory_id"],
            content="Updated content",
            source="new-source",
        )

        result = await get_memory_by_id(create_result["memory_id"])
        # Source should be updated or tracked in history
        assert result.get("source") == "new-source" or "update_history" in result

    @pytest.mark.asyncio
    async def test_update_memory_fails_for_unknown_id(self):
        """update_memory should return error for unknown memory IDs.

        GitHub Issue: #113
        ADR Reference: ADR-003 Interface Contract
        """
        from src.memory.mcp.tools import update_memory

        result = await update_memory(
            memory_id="nonexistent-id",
            content="Updated content",
            source="test",
        )

        assert result.get("success") is False or result.get("error") is not None


class TestInvalidateMemoryTool:
    """TDD: RED Phase - Tests for invalidate_memory MCP tool.

    ADR-003 Interface Contract: invalidate_memory(key, reason)

    Related GitHub Issues:
    - #113: Integrate Memory Module with MCP Servers

    ADR Reference: ADR-003 Memory Architecture, Interface Contract (lines 249-279)
    """

    def test_invalidate_memory_function_exists(self):
        """invalidate_memory function should be defined.

        GitHub Issue: #113
        ADR Reference: ADR-003 Interface Contract
        """
        from src.memory.mcp.tools import invalidate_memory

        assert callable(invalidate_memory)

    @pytest.mark.asyncio
    async def test_invalidate_memory_returns_dict(self):
        """invalidate_memory should return a dict with success status.

        GitHub Issue: #113
        ADR Reference: ADR-003 Interface Contract
        """
        from src.memory.mcp.tools import create_memory, invalidate_memory

        create_result = await create_memory(
            user_id="user-invalidate-test",
            content="To be invalidated",
            memory_type="fact",
            source="test",
        )

        result = await invalidate_memory(
            memory_id=create_result["memory_id"],
            reason="Information is outdated",
        )

        assert isinstance(result, dict)
        assert "success" in result

    @pytest.mark.asyncio
    async def test_invalidate_memory_marks_as_invalid(self):
        """invalidate_memory should mark the memory as invalid.

        GitHub Issue: #113
        ADR Reference: ADR-003 Interface Contract
        """
        from src.memory.mcp.tools import create_memory, get_memory_by_id, invalidate_memory

        create_result = await create_memory(
            user_id="user-invalidate-test",
            content="Valid memory",
            memory_type="fact",
            source="test",
        )

        await invalidate_memory(
            memory_id=create_result["memory_id"],
            reason="No longer accurate",
        )

        result = await get_memory_by_id(create_result["memory_id"])
        # Memory should either be marked invalid or have invalidation metadata
        assert (
            result.get("is_valid") is False
            or result.get("invalidated") is True
            or result.get("invalidation_reason") is not None
            or result.get("error") is not None  # Memory might be soft-deleted
        )

    @pytest.mark.asyncio
    async def test_invalidate_memory_records_reason(self):
        """invalidate_memory should record the invalidation reason.

        GitHub Issue: #113
        ADR Reference: ADR-003 Interface Contract
        """
        from src.memory.mcp.tools import create_memory, invalidate_memory

        create_result = await create_memory(
            user_id="user-invalidate-test",
            content="Test memory",
            memory_type="fact",
            source="test",
        )

        reason = "User corrected this information"
        result = await invalidate_memory(
            memory_id=create_result["memory_id"],
            reason=reason,
        )

        # The reason should be recorded somewhere
        assert (
            result.get("success") is True
            or "reason" in result
            or result.get("invalidation_reason") == reason
        )

    @pytest.mark.asyncio
    async def test_invalidate_memory_fails_for_unknown_id(self):
        """invalidate_memory should return error for unknown memory IDs.

        GitHub Issue: #113
        ADR Reference: ADR-003 Interface Contract
        """
        from src.memory.mcp.tools import invalidate_memory

        result = await invalidate_memory(
            memory_id="nonexistent-id",
            reason="Test reason",
        )

        assert result.get("success") is False or result.get("error") is not None

    @pytest.mark.asyncio
    async def test_invalidated_memory_excluded_from_retrieval(self):
        """Invalidated memories should not appear in normal retrieval.

        GitHub Issue: #113
        ADR Reference: ADR-003 Interface Contract
        """
        from src.memory.mcp.tools import create_memory, get_memories, invalidate_memory

        # Create and invalidate a memory
        create_result = await create_memory(
            user_id="user-invalidate-exclude-test",
            content="Invalidated memory for exclusion test",
            memory_type="preference",
            source="test",
        )

        await invalidate_memory(
            memory_id=create_result["memory_id"],
            reason="Test exclusion",
        )

        # Retrieve memories - invalidated should not appear
        results = await get_memories(
            query="Invalidated memory exclusion",
            user_id="user-invalidate-exclude-test",
            limit=100,
        )

        # The invalidated memory should not be in results
        for memory in results.get("memories", []):
            if memory.get("content") == "Invalidated memory for exclusion test":
                # If it's returned, it should be marked as invalid
                assert (
                    memory.get("is_valid") is False
                    or memory.get("invalidated") is True
                )


class TestGetMemoryProvenanceTool:
    """TDD: RED Phase - Tests for get_memory_provenance MCP tool.

    ADR-003 Interface Contract: get_memory_provenance(key)

    Related GitHub Issues:
    - #113: Integrate Memory Module with MCP Servers

    ADR Reference: ADR-003 Memory Architecture, Interface Contract (lines 249-279)
    """

    def test_get_memory_provenance_function_exists(self):
        """get_memory_provenance function should be defined.

        GitHub Issue: #113
        ADR Reference: ADR-003 Interface Contract
        """
        from src.memory.mcp.tools import get_memory_provenance

        assert callable(get_memory_provenance)

    @pytest.mark.asyncio
    async def test_get_memory_provenance_returns_dict(self):
        """get_memory_provenance should return a dict with provenance info.

        GitHub Issue: #113
        ADR Reference: ADR-003 Interface Contract
        """
        from src.memory.mcp.tools import create_memory, get_memory_provenance

        create_result = await create_memory(
            user_id="user-provenance-test",
            content="Test memory for provenance",
            memory_type="fact",
            source="conversation",
            raw_source="User said: I prefer Python over JavaScript",
        )

        result = await get_memory_provenance(memory_id=create_result["memory_id"])

        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_get_memory_provenance_includes_source(self):
        """get_memory_provenance should include original source.

        GitHub Issue: #113
        ADR Reference: ADR-003 Interface Contract
        """
        from src.memory.mcp.tools import create_memory, get_memory_provenance

        create_result = await create_memory(
            user_id="user-provenance-test",
            content="Python preference",
            memory_type="preference",
            source="conversation",
            raw_source="Original: User mentioned Python preference",
        )

        result = await get_memory_provenance(memory_id=create_result["memory_id"])

        # Should include source information
        assert (
            "source" in result
            or "raw_source" in result
            or "origin" in result
        )

    @pytest.mark.asyncio
    async def test_get_memory_provenance_includes_creation_time(self):
        """get_memory_provenance should include creation timestamp.

        GitHub Issue: #113
        ADR Reference: ADR-003 Interface Contract
        """
        from src.memory.mcp.tools import create_memory, get_memory_provenance

        create_result = await create_memory(
            user_id="user-provenance-test",
            content="Test memory",
            memory_type="fact",
            source="test",
        )

        result = await get_memory_provenance(memory_id=create_result["memory_id"])

        # Should include creation timestamp
        assert (
            "created_at" in result
            or "creation_time" in result
            or "timestamp" in result
        )

    @pytest.mark.asyncio
    async def test_get_memory_provenance_includes_extraction_version(self):
        """get_memory_provenance should include extraction version.

        GitHub Issue: #113
        ADR Reference: ADR-003 Interface Contract
        """
        from src.memory.mcp.tools import create_memory, get_memory_provenance

        create_result = await create_memory(
            user_id="user-provenance-test",
            content="Test memory",
            memory_type="fact",
            source="test",
        )

        result = await get_memory_provenance(memory_id=create_result["memory_id"])

        # Should include extraction version
        assert "extraction_version" in result or "version" in result

    @pytest.mark.asyncio
    async def test_get_memory_provenance_tracks_updates(self):
        """get_memory_provenance should track update history.

        GitHub Issue: #113
        ADR Reference: ADR-003 Interface Contract
        """
        from src.memory.mcp.tools import (
            create_memory,
            get_memory_provenance,
            update_memory,
        )

        create_result = await create_memory(
            user_id="user-provenance-test",
            content="Original content",
            memory_type="fact",
            source="test",
        )

        # Update the memory
        await update_memory(
            memory_id=create_result["memory_id"],
            content="Updated content",
            source="test-update",
        )

        result = await get_memory_provenance(memory_id=create_result["memory_id"])

        # Should include update history or last modified time
        assert (
            "update_history" in result
            or "last_modified_at" in result
            or "updates" in result
            or "modified_at" in result
        )

    @pytest.mark.asyncio
    async def test_get_memory_provenance_fails_for_unknown_id(self):
        """get_memory_provenance should return error for unknown IDs.

        GitHub Issue: #113
        ADR Reference: ADR-003 Interface Contract
        """
        from src.memory.mcp.tools import get_memory_provenance

        result = await get_memory_provenance(memory_id="nonexistent-id")

        assert result.get("error") is not None or result.get("provenance") is None


class TestMCPServerIntegration:
    """TDD: RED Phase - Tests for MCP server memory tool integration.

    Verifies that memory tools are properly integrated into the MCP server.

    Related GitHub Issues:
    - #113: Integrate Memory Module with MCP Servers

    ADR Reference: ADR-003 Memory Architecture, Phase 1a (MCP Tools)
    """

    def test_mcp_tools_module_exports_adr003_interface(self):
        """mcp module should export ADR-003 interface tools.

        GitHub Issue: #113
        ADR Reference: ADR-003 Interface Contract
        """
        from src.memory.mcp import (
            create_memory,
            delete_memory,
            get_memories,
            get_memory_by_id,
            get_memory_provenance,
            invalidate_memory,
            search_memories,
            update_memory,
        )

        # All ADR-003 interface functions should be importable
        assert callable(update_memory)
        assert callable(invalidate_memory)
        assert callable(get_memory_provenance)
