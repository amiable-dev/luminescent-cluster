# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
TDD: Tests for Memory Block Schema.

These tests define the expected behavior for the Memory Blocks architecture
following ADR-003 Phase 2 (Context Engineering).

Related GitHub Issues:
- #116: Phase 2: Memory Blocks Architecture

ADR Reference: ADR-003 Memory Architecture, Phase 2 (Context Engineering)
"""

from datetime import datetime, timezone
from typing import Any

import pytest


class TestBlockType:
    """TDD: Tests for BlockType enum."""

    def test_block_type_enum_exists(self):
        """BlockType enum should be defined."""
        from src.memory.blocks.schemas import BlockType

        assert BlockType is not None

    def test_block_type_has_system(self):
        """BlockType should have SYSTEM value."""
        from src.memory.blocks.schemas import BlockType

        assert BlockType.SYSTEM == "system"

    def test_block_type_has_project(self):
        """BlockType should have PROJECT value."""
        from src.memory.blocks.schemas import BlockType

        assert BlockType.PROJECT == "project"

    def test_block_type_has_task(self):
        """BlockType should have TASK value."""
        from src.memory.blocks.schemas import BlockType

        assert BlockType.TASK == "task"

    def test_block_type_has_history(self):
        """BlockType should have HISTORY value."""
        from src.memory.blocks.schemas import BlockType

        assert BlockType.HISTORY == "history"

    def test_block_type_has_knowledge(self):
        """BlockType should have KNOWLEDGE value."""
        from src.memory.blocks.schemas import BlockType

        assert BlockType.KNOWLEDGE == "knowledge"

    def test_block_type_is_string_enum(self):
        """BlockType should be a string enum for serialization."""
        from src.memory.blocks.schemas import BlockType

        assert isinstance(BlockType.SYSTEM.value, str)


class TestProvenance:
    """TDD: Tests for Provenance dataclass."""

    def test_provenance_exists(self):
        """Provenance dataclass should be defined."""
        from src.memory.blocks.schemas import Provenance

        assert Provenance is not None

    def test_provenance_has_required_fields(self):
        """Provenance should have required fields."""
        from src.memory.blocks.schemas import Provenance

        now = datetime.now(timezone.utc)
        prov = Provenance(
            source_id="mem-123",
            source_type="memory",
            confidence=0.95,
            created_at=now,
        )

        assert prov.source_id == "mem-123"
        assert prov.source_type == "memory"
        assert prov.confidence == 0.95
        assert prov.created_at == now

    def test_provenance_retrieval_score_optional(self):
        """Provenance retrieval_score should be optional."""
        from src.memory.blocks.schemas import Provenance

        now = datetime.now(timezone.utc)
        prov = Provenance(
            source_id="mem-123",
            source_type="memory",
            confidence=0.95,
            created_at=now,
        )

        assert prov.retrieval_score is None

    def test_provenance_with_retrieval_score(self):
        """Provenance should accept retrieval_score."""
        from src.memory.blocks.schemas import Provenance

        now = datetime.now(timezone.utc)
        prov = Provenance(
            source_id="mem-123",
            source_type="memory",
            confidence=0.95,
            created_at=now,
            retrieval_score=0.87,
        )

        assert prov.retrieval_score == 0.87

    def test_provenance_to_dict(self):
        """Provenance should be convertible to dict."""
        from src.memory.blocks.schemas import Provenance

        now = datetime.now(timezone.utc)
        prov = Provenance(
            source_id="mem-123",
            source_type="memory",
            confidence=0.95,
            created_at=now,
            retrieval_score=0.87,
        )

        result = prov.to_dict()

        assert isinstance(result, dict)
        assert result["source_id"] == "mem-123"
        assert result["source_type"] == "memory"
        assert result["confidence"] == 0.95
        assert result["retrieval_score"] == 0.87


class TestMemoryBlock:
    """TDD: Tests for MemoryBlock dataclass."""

    def test_memory_block_exists(self):
        """MemoryBlock dataclass should be defined."""
        from src.memory.blocks.schemas import MemoryBlock

        assert MemoryBlock is not None

    def test_memory_block_has_required_fields(self):
        """MemoryBlock should have required fields."""
        from src.memory.blocks.schemas import BlockType, MemoryBlock

        block = MemoryBlock(
            block_type=BlockType.SYSTEM,
            content="System instructions here",
            token_count=50,
            priority=1,
            metadata={"version": "1.0"},
        )

        assert block.block_type == BlockType.SYSTEM
        assert block.content == "System instructions here"
        assert block.token_count == 50
        assert block.priority == 1
        assert block.metadata == {"version": "1.0"}

    def test_memory_block_provenance_optional(self):
        """MemoryBlock provenance should be optional."""
        from src.memory.blocks.schemas import BlockType, MemoryBlock

        block = MemoryBlock(
            block_type=BlockType.KNOWLEDGE,
            content="Retrieved knowledge",
            token_count=100,
            priority=5,
            metadata={},
        )

        assert block.provenance is None

    def test_memory_block_with_provenance(self):
        """MemoryBlock should accept provenance."""
        from src.memory.blocks.schemas import BlockType, MemoryBlock, Provenance

        now = datetime.now(timezone.utc)
        prov = Provenance(
            source_id="mem-456",
            source_type="adr",
            confidence=0.99,
            created_at=now,
        )

        block = MemoryBlock(
            block_type=BlockType.KNOWLEDGE,
            content="ADR content",
            token_count=200,
            priority=3,
            metadata={"adr_id": "003"},
            provenance=prov,
        )

        assert block.provenance is not None
        assert block.provenance.source_id == "mem-456"

    def test_memory_block_to_dict(self):
        """MemoryBlock should be convertible to dict."""
        from src.memory.blocks.schemas import BlockType, MemoryBlock

        block = MemoryBlock(
            block_type=BlockType.TASK,
            content="Current task",
            token_count=30,
            priority=2,
            metadata={"task_id": "t-123"},
        )

        result = block.to_dict()

        assert isinstance(result, dict)
        assert result["block_type"] == "task"
        assert result["content"] == "Current task"
        assert result["token_count"] == 30
        assert result["priority"] == 2

    def test_memory_block_priority_order(self):
        """Lower priority number should mean higher importance."""
        from src.memory.blocks.schemas import BlockType, MemoryBlock

        system_block = MemoryBlock(
            block_type=BlockType.SYSTEM,
            content="System",
            token_count=100,
            priority=1,  # Highest priority
            metadata={},
        )
        knowledge_block = MemoryBlock(
            block_type=BlockType.KNOWLEDGE,
            content="Knowledge",
            token_count=100,
            priority=5,  # Lowest priority
            metadata={},
        )

        assert system_block.priority < knowledge_block.priority


class TestBlockTypeDefaults:
    """TDD: Tests for default block type priorities and budgets."""

    def test_default_priorities_defined(self):
        """DEFAULT_BLOCK_PRIORITIES should be defined."""
        from src.memory.blocks.schemas import DEFAULT_BLOCK_PRIORITIES

        assert DEFAULT_BLOCK_PRIORITIES is not None
        assert isinstance(DEFAULT_BLOCK_PRIORITIES, dict)

    def test_default_priorities_for_all_block_types(self):
        """DEFAULT_BLOCK_PRIORITIES should cover all block types."""
        from src.memory.blocks.schemas import BlockType, DEFAULT_BLOCK_PRIORITIES

        for block_type in BlockType:
            assert block_type in DEFAULT_BLOCK_PRIORITIES

    def test_system_has_highest_priority(self):
        """System block should have priority 1 (highest)."""
        from src.memory.blocks.schemas import BlockType, DEFAULT_BLOCK_PRIORITIES

        assert DEFAULT_BLOCK_PRIORITIES[BlockType.SYSTEM] == 1

    def test_default_token_budgets_defined(self):
        """DEFAULT_TOKEN_BUDGETS should be defined."""
        from src.memory.blocks.schemas import DEFAULT_TOKEN_BUDGETS

        assert DEFAULT_TOKEN_BUDGETS is not None
        assert isinstance(DEFAULT_TOKEN_BUDGETS, dict)

    def test_default_token_budgets_for_all_block_types(self):
        """DEFAULT_TOKEN_BUDGETS should cover all block types."""
        from src.memory.blocks.schemas import BlockType, DEFAULT_TOKEN_BUDGETS

        for block_type in BlockType:
            assert block_type in DEFAULT_TOKEN_BUDGETS

    def test_total_default_budget_fits_5000_with_overhead(self):
        """Content budgets + XML overhead should fit within 5000 total budget."""
        from src.memory.blocks.assembler import BlockAssembler
        from src.memory.blocks.schemas import DEFAULT_TOKEN_BUDGETS

        # Content budgets sum to 4925
        content_total = sum(DEFAULT_TOKEN_BUDGETS.values())
        assert content_total == 4925

        # With XML overhead (15 tokens per block * 5 blocks = 75), total is ~5000
        xml_overhead = BlockAssembler.XML_OVERHEAD_PER_BLOCK * len(DEFAULT_TOKEN_BUDGETS)
        total_with_overhead = content_total + xml_overhead
        assert total_with_overhead == 5000
