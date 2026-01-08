# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
TDD: Tests for Block Assembler.

These tests define the expected behavior for memory block assembly,
meeting the ADR-003 Phase 2 requirement for structured context management.

Related GitHub Issues:
- #116: Phase 2: Memory Blocks Architecture

ADR Reference: ADR-003 Memory Architecture, Phase 2 (Context Engineering)
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import pytest


@dataclass
class MockMessage:
    """Mock message for testing."""

    role: str
    content: str
    timestamp: datetime


class TestBlockAssemblerExists:
    """TDD: Tests for BlockAssembler class existence."""

    def test_block_assembler_exists(self):
        """BlockAssembler class should be defined."""
        from src.memory.blocks.assembler import BlockAssembler

        assert BlockAssembler is not None

    def test_block_assembler_instantiable(self):
        """BlockAssembler should be instantiable with token_budget."""
        from src.memory.blocks.assembler import BlockAssembler

        assembler = BlockAssembler(token_budget=5000)
        assert assembler.token_budget == 5000

    def test_default_token_budget(self):
        """BlockAssembler should default to 5000 token budget."""
        from src.memory.blocks.assembler import BlockAssembler

        assembler = BlockAssembler()
        assert assembler.token_budget == 5000


class TestBlockBudgets:
    """TDD: Tests for block budget configuration."""

    def test_has_block_budgets(self):
        """BlockAssembler should have block_budgets dict."""
        from src.memory.blocks.assembler import BlockAssembler

        assembler = BlockAssembler()
        assert hasattr(assembler, "block_budgets")
        assert isinstance(assembler.block_budgets, dict)

    def test_default_block_budgets(self):
        """BlockAssembler should have default budgets for all block types."""
        from src.memory.blocks.assembler import BlockAssembler
        from src.memory.blocks.schemas import BlockType

        assembler = BlockAssembler()

        # Should have budget for each block type
        assert BlockType.SYSTEM in assembler.block_budgets
        assert BlockType.PROJECT in assembler.block_budgets
        assert BlockType.TASK in assembler.block_budgets
        assert BlockType.HISTORY in assembler.block_budgets
        assert BlockType.KNOWLEDGE in assembler.block_budgets

    def test_custom_block_budgets(self):
        """BlockAssembler should accept custom block budgets."""
        from src.memory.blocks.assembler import BlockAssembler
        from src.memory.blocks.schemas import BlockType

        custom_budgets = {
            BlockType.SYSTEM: 200,
            BlockType.PROJECT: 500,
            BlockType.TASK: 300,
            BlockType.HISTORY: 500,
            BlockType.KNOWLEDGE: 1000,
        }

        assembler = BlockAssembler(block_budgets=custom_budgets)

        assert assembler.block_budgets[BlockType.SYSTEM] == 200
        assert assembler.block_budgets[BlockType.KNOWLEDGE] == 1000


class TestBuildSystemBlock:
    """TDD: Tests for system block building."""

    @pytest.fixture
    def assembler(self):
        """Create a BlockAssembler for tests."""
        from src.memory.blocks.assembler import BlockAssembler

        return BlockAssembler()

    @pytest.mark.asyncio
    async def test_build_system_block_returns_memory_block(self, assembler):
        """build_system_block should return a MemoryBlock."""
        from src.memory.blocks.schemas import BlockType, MemoryBlock

        result = await assembler.build_system_block()

        assert isinstance(result, MemoryBlock)
        assert result.block_type == BlockType.SYSTEM

    @pytest.mark.asyncio
    async def test_build_system_block_has_content(self, assembler):
        """build_system_block should have content."""
        result = await assembler.build_system_block()

        assert result.content is not None
        assert len(result.content) > 0

    @pytest.mark.asyncio
    async def test_build_system_block_respects_budget(self, assembler):
        """build_system_block should respect token budget."""
        from src.memory.blocks.schemas import BlockType

        budget = assembler.block_budgets[BlockType.SYSTEM]
        result = await assembler.build_system_block()

        assert result.token_count <= budget


class TestBuildProjectBlock:
    """TDD: Tests for project block building."""

    @pytest.fixture
    def assembler(self):
        """Create a BlockAssembler for tests."""
        from src.memory.blocks.assembler import BlockAssembler

        return BlockAssembler()

    @pytest.mark.asyncio
    async def test_build_project_block_returns_memory_block(self, assembler):
        """build_project_block should return a MemoryBlock."""
        from src.memory.blocks.schemas import BlockType, MemoryBlock

        result = await assembler.build_project_block(user_id="test-user")

        assert isinstance(result, MemoryBlock)
        assert result.block_type == BlockType.PROJECT

    @pytest.mark.asyncio
    async def test_build_project_block_includes_user_id(self, assembler):
        """build_project_block should include user_id in metadata."""
        result = await assembler.build_project_block(user_id="test-user-123")

        assert result.metadata.get("user_id") == "test-user-123"


class TestBuildTaskBlock:
    """TDD: Tests for task block building."""

    @pytest.fixture
    def assembler(self):
        """Create a BlockAssembler for tests."""
        from src.memory.blocks.assembler import BlockAssembler

        return BlockAssembler()

    @pytest.mark.asyncio
    async def test_build_task_block_returns_memory_block(self, assembler):
        """build_task_block should return a MemoryBlock."""
        from src.memory.blocks.schemas import BlockType, MemoryBlock

        result = await assembler.build_task_block(task_context="Implement feature X")

        assert isinstance(result, MemoryBlock)
        assert result.block_type == BlockType.TASK

    @pytest.mark.asyncio
    async def test_build_task_block_contains_context(self, assembler):
        """build_task_block should contain the task context."""
        result = await assembler.build_task_block(task_context="Implement feature X")

        assert "Implement feature X" in result.content

    @pytest.mark.asyncio
    async def test_build_task_block_empty_context(self, assembler):
        """build_task_block should handle empty context."""
        result = await assembler.build_task_block(task_context="")

        assert result.content == ""
        assert result.token_count == 0


class TestBuildHistoryBlock:
    """TDD: Tests for history block building."""

    @pytest.fixture
    def assembler(self):
        """Create a BlockAssembler for tests."""
        from src.memory.blocks.assembler import BlockAssembler

        return BlockAssembler()

    @pytest.fixture
    def sample_messages(self):
        """Create sample conversation messages."""
        now = datetime.now(timezone.utc)
        return [
            MockMessage(role="user", content="Hello", timestamp=now),
            MockMessage(role="assistant", content="Hi there!", timestamp=now),
            MockMessage(role="user", content="How are you?", timestamp=now),
        ]

    @pytest.mark.asyncio
    async def test_build_history_block_returns_memory_block(
        self, assembler, sample_messages
    ):
        """build_history_block should return a MemoryBlock."""
        from src.memory.blocks.schemas import BlockType, MemoryBlock

        result = await assembler.build_history_block(
            conversation_history=sample_messages
        )

        assert isinstance(result, MemoryBlock)
        assert result.block_type == BlockType.HISTORY

    @pytest.mark.asyncio
    async def test_build_history_block_empty_history(self, assembler):
        """build_history_block should handle empty history."""
        result = await assembler.build_history_block(conversation_history=[])

        assert result.content == ""
        assert result.token_count == 0

    @pytest.mark.asyncio
    async def test_build_history_block_uses_compressor(
        self, assembler, sample_messages
    ):
        """build_history_block should use HistoryCompressor."""
        result = await assembler.build_history_block(
            conversation_history=sample_messages
        )

        # Should contain at least some content from messages
        assert len(result.content) > 0


class TestBuildKnowledgeBlock:
    """TDD: Tests for knowledge block building."""

    @pytest.fixture
    def assembler(self):
        """Create a BlockAssembler for tests."""
        from src.memory.blocks.assembler import BlockAssembler

        return BlockAssembler()

    @pytest.mark.asyncio
    async def test_build_knowledge_block_returns_memory_block(self, assembler):
        """build_knowledge_block should return a MemoryBlock."""
        from src.memory.blocks.schemas import BlockType, MemoryBlock

        result = await assembler.build_knowledge_block(
            user_id="test-user",
            query="coding preferences",
        )

        assert isinstance(result, MemoryBlock)
        assert result.block_type == BlockType.KNOWLEDGE

    @pytest.mark.asyncio
    async def test_build_knowledge_block_has_provenance(self, assembler):
        """build_knowledge_block should include provenance."""
        result = await assembler.build_knowledge_block(
            user_id="test-user",
            query="coding preferences",
        )

        # Should have query in metadata
        assert result.metadata.get("query") == "coding preferences"

        # ADR-003 Phase 2: Should have provenance attached
        assert result.provenance is not None
        assert result.provenance.source_type == "knowledge_retrieval"
        assert result.provenance.retrieval_score is not None

    @pytest.mark.asyncio
    async def test_build_knowledge_block_empty_query(self, assembler):
        """build_knowledge_block should handle empty query."""
        result = await assembler.build_knowledge_block(
            user_id="test-user",
            query="",
        )

        assert result.content == ""
        assert result.token_count == 0


class TestAssemble:
    """TDD: Tests for full block assembly."""

    @pytest.fixture
    def assembler(self):
        """Create a BlockAssembler for tests."""
        from src.memory.blocks.assembler import BlockAssembler

        return BlockAssembler()

    @pytest.fixture
    def sample_messages(self):
        """Create sample conversation messages."""
        now = datetime.now(timezone.utc)
        return [
            MockMessage(role="user", content="Hello", timestamp=now),
            MockMessage(role="assistant", content="Hi!", timestamp=now),
        ]

    @pytest.mark.asyncio
    async def test_assemble_returns_list(self, assembler):
        """assemble should return a list of MemoryBlocks."""
        result = await assembler.assemble(user_id="test-user")

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_assemble_returns_all_block_types(self, assembler, sample_messages):
        """assemble should return blocks for all types."""
        from src.memory.blocks.schemas import BlockType

        result = await assembler.assemble(
            user_id="test-user",
            task_context="Test task",
            conversation_history=sample_messages,
            query="test query",
        )

        block_types = {block.block_type for block in result}

        assert BlockType.SYSTEM in block_types
        assert BlockType.PROJECT in block_types
        assert BlockType.TASK in block_types
        assert BlockType.HISTORY in block_types
        assert BlockType.KNOWLEDGE in block_types

    @pytest.mark.asyncio
    async def test_assemble_respects_total_budget(self, assembler, sample_messages):
        """assemble should respect total token budget."""
        result = await assembler.assemble(
            user_id="test-user",
            task_context="Test task",
            conversation_history=sample_messages,
            query="test query",
        )

        total_tokens = sum(block.token_count for block in result)

        # Should be within or close to budget
        assert total_tokens <= assembler.token_budget + 100  # Small tolerance

    @pytest.mark.asyncio
    async def test_assemble_minimal_params(self, assembler):
        """assemble should work with minimal parameters."""
        result = await assembler.assemble(user_id="test-user")

        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_assemble_blocks_sorted_by_priority(self, assembler, sample_messages):
        """assemble should return blocks sorted by priority."""
        result = await assembler.assemble(
            user_id="test-user",
            task_context="Test task",
            conversation_history=sample_messages,
            query="test query",
        )

        # First block should be highest priority (lowest number)
        priorities = [block.priority for block in result]
        assert priorities == sorted(priorities)


class TestToPrompt:
    """TDD: Tests for converting blocks to prompt string."""

    @pytest.fixture
    def assembler(self):
        """Create a BlockAssembler for tests."""
        from src.memory.blocks.assembler import BlockAssembler

        return BlockAssembler()

    @pytest.mark.asyncio
    async def test_to_prompt_returns_string(self, assembler):
        """to_prompt should return a string."""
        blocks = await assembler.assemble(user_id="test-user")
        result = assembler.to_prompt(blocks)

        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_to_prompt_includes_all_blocks(self, assembler):
        """to_prompt should include content from all blocks."""
        blocks = await assembler.assemble(
            user_id="test-user",
            task_context="My test task",
        )
        result = assembler.to_prompt(blocks)

        assert "My test task" in result

    @pytest.mark.asyncio
    async def test_to_prompt_empty_blocks(self, assembler):
        """to_prompt should handle empty blocks list."""
        result = assembler.to_prompt([])

        assert result == ""
