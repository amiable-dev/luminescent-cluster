# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
TDD: Tests for Token Efficiency Measurement.

These tests verify the token efficiency metrics for Phase 2 exit criteria:
- 30% token efficiency improvement target

Related GitHub Issues:
- #116: Phase 2: Memory Blocks Architecture

ADR Reference: ADR-003 Memory Architecture, Phase 2 (Context Engineering)
"""

import pytest

from src.memory.blocks.schemas import BlockType, MemoryBlock


class TestTokenEfficiencyMetricExists:
    """TDD: Tests for TokenEfficiencyMetric class existence."""

    def test_token_efficiency_metric_exists(self):
        """TokenEfficiencyMetric class should be defined."""
        from src.memory.evaluation.token_efficiency import TokenEfficiencyMetric

        assert TokenEfficiencyMetric is not None

    def test_token_efficiency_metric_instantiable(self):
        """TokenEfficiencyMetric should be instantiable with baseline_tokens."""
        from src.memory.evaluation.token_efficiency import TokenEfficiencyMetric

        metric = TokenEfficiencyMetric(baseline_tokens=5000)
        assert metric.baseline == 5000

    def test_default_baseline(self):
        """TokenEfficiencyMetric should default to 5000 baseline tokens."""
        from src.memory.evaluation.token_efficiency import TokenEfficiencyMetric

        metric = TokenEfficiencyMetric()
        assert metric.baseline == 5000


class TestCalculateEfficiency:
    """TDD: Tests for efficiency calculation."""

    @pytest.fixture
    def metric(self):
        """Create a TokenEfficiencyMetric for tests."""
        from src.memory.evaluation.token_efficiency import TokenEfficiencyMetric

        return TokenEfficiencyMetric(baseline_tokens=5000)

    @pytest.fixture
    def sample_blocks(self):
        """Create sample memory blocks for testing."""
        return [
            MemoryBlock(
                block_type=BlockType.SYSTEM,
                content="System instructions",
                token_count=400,
                priority=1,
            ),
            MemoryBlock(
                block_type=BlockType.PROJECT,
                content="Project context",
                token_count=800,
                priority=2,
            ),
            MemoryBlock(
                block_type=BlockType.TASK,
                content="Task context",
                token_count=400,
                priority=3,
            ),
            MemoryBlock(
                block_type=BlockType.HISTORY,
                content="History",
                token_count=800,
                priority=4,
            ),
            MemoryBlock(
                block_type=BlockType.KNOWLEDGE,
                content="Knowledge",
                token_count=1100,
                priority=5,
            ),
        ]

    def test_calculate_efficiency_returns_dict(self, metric, sample_blocks):
        """calculate_efficiency should return a dict."""
        result = metric.calculate_efficiency(sample_blocks)

        assert isinstance(result, dict)

    def test_calculate_efficiency_has_total_tokens(self, metric, sample_blocks):
        """calculate_efficiency result should include total_tokens."""
        result = metric.calculate_efficiency(sample_blocks)

        assert "total_tokens" in result
        assert result["total_tokens"] == 3500  # Sum of all blocks

    def test_calculate_efficiency_has_baseline(self, metric, sample_blocks):
        """calculate_efficiency result should include baseline_tokens."""
        result = metric.calculate_efficiency(sample_blocks)

        assert "baseline_tokens" in result
        assert result["baseline_tokens"] == 5000

    def test_calculate_efficiency_improvement(self, metric, sample_blocks):
        """calculate_efficiency should calculate efficiency improvement."""
        result = metric.calculate_efficiency(sample_blocks)

        # 5000 - 3500 = 1500 saved, 1500/5000 = 0.30 = 30%
        assert "efficiency_improvement" in result
        assert result["efficiency_improvement"] == 0.30

    def test_calculate_efficiency_meets_target(self, metric, sample_blocks):
        """calculate_efficiency should indicate if target is met."""
        result = metric.calculate_efficiency(sample_blocks)

        assert "meets_target" in result
        assert result["meets_target"] is True  # 30% meets 30% target

    def test_calculate_efficiency_below_target(self, metric):
        """calculate_efficiency should detect when target not met."""
        # Blocks totaling 4000 tokens = only 20% efficiency
        blocks = [
            MemoryBlock(
                block_type=BlockType.SYSTEM,
                content="System",
                token_count=4000,
                priority=1,
            )
        ]

        result = metric.calculate_efficiency(blocks)

        assert result["meets_target"] is False

    def test_calculate_efficiency_empty_blocks(self, metric):
        """calculate_efficiency should handle empty blocks."""
        result = metric.calculate_efficiency([])

        assert result["total_tokens"] == 0
        assert result["efficiency_improvement"] == 1.0  # 100% savings
        assert result["meets_target"] is True


class TestEfficiencyBreakdown:
    """TDD: Tests for per-block efficiency breakdown."""

    @pytest.fixture
    def metric(self):
        """Create a TokenEfficiencyMetric for tests."""
        from src.memory.evaluation.token_efficiency import TokenEfficiencyMetric

        return TokenEfficiencyMetric(baseline_tokens=5000)

    @pytest.fixture
    def sample_blocks(self):
        """Create sample memory blocks for testing."""
        return [
            MemoryBlock(
                block_type=BlockType.SYSTEM,
                content="System",
                token_count=500,
                priority=1,
            ),
            MemoryBlock(
                block_type=BlockType.KNOWLEDGE,
                content="Knowledge",
                token_count=1500,
                priority=5,
            ),
        ]

    def test_breakdown_by_block_type(self, metric, sample_blocks):
        """Should provide breakdown by block type."""
        result = metric.calculate_efficiency(sample_blocks)

        assert "breakdown" in result
        assert BlockType.SYSTEM.value in result["breakdown"]
        assert result["breakdown"][BlockType.SYSTEM.value] == 500

    def test_breakdown_includes_all_blocks(self, metric, sample_blocks):
        """breakdown should include all block types in input."""
        result = metric.calculate_efficiency(sample_blocks)

        assert result["breakdown"][BlockType.SYSTEM.value] == 500
        assert result["breakdown"][BlockType.KNOWLEDGE.value] == 1500
