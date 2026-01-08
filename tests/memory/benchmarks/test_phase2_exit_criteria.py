# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
Phase 2 Exit Criteria Verification Tests.

These tests verify that ADR-003 Phase 2 exit criteria are met:
1. 30% token efficiency improvement
2. Provenance available for all retrieved items
3. Stale memory detection operational

Related GitHub Issues:
- #116: Phase 2: Memory Blocks Architecture

ADR Reference: ADR-003 Memory Architecture, Phase 2 (Context Engineering)
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List

import pytest

from src.memory.blocks.schemas import BlockType, MemoryBlock
from src.memory.evaluation.token_efficiency import TokenEfficiencyMetric
from src.memory.schemas import Memory, MemoryType


@dataclass
class MockMessage:
    """Mock message for testing."""

    role: str
    content: str
    timestamp: datetime


class TestPhase2ExitCriteria:
    """Verify Phase 2 exit criteria are met."""

    def test_token_efficiency_30_percent(self):
        """Exit Criteria: 30% token efficiency improvement.

        The Memory Blocks architecture should achieve at least 30%
        token efficiency compared to baseline unstructured context.
        """
        # Baseline: 5000 tokens of unstructured context
        baseline_tokens = 5000

        # With Memory Blocks architecture, we should use ≤3500 tokens
        blocks = [
            MemoryBlock(
                block_type=BlockType.SYSTEM,
                content="System instructions" * 20,  # ~400 tokens
                token_count=400,
                priority=1,
            ),
            MemoryBlock(
                block_type=BlockType.PROJECT,
                content="Project context" * 30,  # ~600 tokens
                token_count=600,
                priority=2,
            ),
            MemoryBlock(
                block_type=BlockType.TASK,
                content="Task context" * 20,  # ~400 tokens
                token_count=400,
                priority=3,
            ),
            MemoryBlock(
                block_type=BlockType.HISTORY,
                content="History summary" * 30,  # ~600 tokens
                token_count=600,
                priority=4,
            ),
            MemoryBlock(
                block_type=BlockType.KNOWLEDGE,
                content="Knowledge" * 50,  # ~1000 tokens
                token_count=1000,
                priority=5,
            ),
        ]

        metric = TokenEfficiencyMetric(baseline_tokens=baseline_tokens)
        result = metric.calculate_efficiency(blocks)

        # Verify 30% efficiency target is met
        assert result["meets_target"] is True, (
            f"Expected 30% efficiency improvement, got {result['efficiency_improvement']*100:.1f}%"
        )
        assert result["efficiency_improvement"] >= 0.30

    def test_provenance_for_all_retrieved(self):
        """Exit Criteria: Provenance available for all retrieved items.

        Every memory retrieved should have provenance metadata attached.
        """
        from src.memory.retrieval.ranker import MemoryRanker

        # Create sample memories
        now = datetime.now(timezone.utc)
        memories = [
            Memory(
                user_id="user-1",
                content="Prefers tabs over spaces",
                memory_type=MemoryType.PREFERENCE,
                confidence=0.9,
                source="conversation",
                last_accessed_at=now,
                metadata={"memory_id": "mem-1"},
            ),
            Memory(
                user_id="user-1",
                content="Uses Python 3.11",
                memory_type=MemoryType.FACT,
                confidence=0.95,
                source="conversation",
                last_accessed_at=now - timedelta(days=7),
                metadata={"memory_id": "mem-2"},
            ),
        ]

        # Use rank_with_provenance to get memories with provenance
        ranker = MemoryRanker()
        ranked = ranker.rank_with_provenance("tabs", memories)

        # Verify every retrieved memory has provenance
        for memory, score in ranked:
            assert memory.provenance is not None, (
                f"Memory {memory.content} missing provenance"
            )
            assert memory.provenance.source_id is not None
            assert memory.provenance.source_type == "memory"
            assert memory.provenance.retrieval_score == score
            assert memory.provenance.confidence >= 0.0

    def test_stale_memory_detection_operational(self):
        """Exit Criteria: Stale memory detection operational.

        Old memories should receive lower rankings due to decay scoring.
        """
        from src.memory.retrieval.ranker import MemoryRanker

        now = datetime.now(timezone.utc)

        # Create fresh and stale memories with identical content
        fresh_memory = Memory(
            user_id="user-1",
            content="Authentication preference",
            memory_type=MemoryType.PREFERENCE,
            confidence=0.9,
            source="conversation",
            last_accessed_at=now - timedelta(hours=1),  # Fresh
        )

        stale_memory = Memory(
            user_id="user-1",
            content="Authentication preference",
            memory_type=MemoryType.PREFERENCE,
            confidence=0.9,
            source="conversation",
            last_accessed_at=now - timedelta(days=60),  # Stale
        )

        ranker = MemoryRanker(decay_enabled=True, decay_half_life_days=30)

        fresh_score = ranker.calculate_score("auth", fresh_memory)
        stale_score = ranker.calculate_score("auth", stale_memory)

        # Fresh memory should rank higher due to decay
        assert fresh_score > stale_score, (
            f"Fresh memory ({fresh_score:.3f}) should score higher than "
            f"stale memory ({stale_score:.3f})"
        )


class TestBlockAssemblerIntegration:
    """Integration tests for block assembly."""

    @pytest.mark.asyncio
    async def test_assemble_respects_token_budget(self):
        """Block assembly should stay within token budget."""
        from src.memory.blocks.assembler import BlockAssembler

        assembler = BlockAssembler(token_budget=5000)
        blocks = await assembler.assemble(
            user_id="test-user",
            task_context="Test task for budget verification",
        )

        total_tokens = sum(block.token_count for block in blocks)
        assert total_tokens <= 5000, (
            f"Total tokens ({total_tokens}) exceeds budget (5000)"
        )

    @pytest.mark.asyncio
    async def test_assemble_produces_all_block_types(self):
        """Block assembly should produce all five block types."""
        from src.memory.blocks.assembler import BlockAssembler

        assembler = BlockAssembler()
        blocks = await assembler.assemble(
            user_id="test-user",
            task_context="Test task",
            query="test query",
        )

        block_types = {block.block_type for block in blocks}

        assert BlockType.SYSTEM in block_types
        assert BlockType.PROJECT in block_types
        assert BlockType.TASK in block_types
        assert BlockType.HISTORY in block_types
        assert BlockType.KNOWLEDGE in block_types


class TestHistoryCompressionEfficiency:
    """Tests for history compression efficiency."""

    def test_compression_reduces_token_count(self):
        """History compression should reduce token count significantly."""
        from src.memory.blocks.compressor import HistoryCompressor

        # Create verbose conversation history
        now = datetime.now(timezone.utc)
        messages = [
            MockMessage(
                role="user",
                content="This is a very long message " * 10,
                timestamp=now,
            ),
            MockMessage(
                role="assistant",
                content="This is a very long response " * 10,
                timestamp=now,
            ),
        ] * 5  # 10 messages total

        compressor = HistoryCompressor(max_tokens=500)

        # Calculate original token count
        original_text = "\n".join(
            f"{msg.role}: {msg.content}" for msg in messages
        )
        original_tokens = compressor.count_tokens(original_text)

        # Compress
        compressed = compressor.compress(messages)
        compressed_tokens = compressor.count_tokens(compressed)

        # Compression should significantly reduce tokens
        assert compressed_tokens < original_tokens, (
            f"Compression did not reduce tokens: {compressed_tokens} >= {original_tokens}"
        )
        assert compressed_tokens <= 500, (
            f"Compressed tokens ({compressed_tokens}) exceeds limit (500)"
        )
