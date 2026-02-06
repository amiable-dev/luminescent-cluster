# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
Token Efficiency Measurement for Phase 2 exit criteria (ADR-003).

This module provides metrics to measure token efficiency and verify
the Phase 2 exit criterion: 30% token efficiency improvement.

Related GitHub Issues:
- #116: Phase 2: Memory Blocks Architecture

ADR Reference: ADR-003 Memory Architecture, Phase 2 (Context Engineering)
"""

from typing import Any

from luminescent_cluster.memory.blocks.schemas import MemoryBlock


class TokenEfficiencyMetric:
    """
    Measure token efficiency for Phase 2 exit criteria.

    Compares actual token usage against a baseline to calculate
    efficiency improvements achieved through the Memory Blocks architecture.

    The Phase 2 target is 30% efficiency improvement.
    """

    # Phase 2 exit criterion: 30% efficiency improvement
    TARGET_EFFICIENCY = 0.30

    def __init__(self, baseline_tokens: int = 5000) -> None:
        """
        Initialize the token efficiency metric.

        Args:
            baseline_tokens: Baseline token count for comparison (default 5000)
        """
        self.baseline = baseline_tokens

    def calculate_efficiency(
        self,
        blocks: list[MemoryBlock],
    ) -> dict[str, Any]:
        """
        Calculate token efficiency metrics for assembled blocks.

        Args:
            blocks: List of MemoryBlocks to measure

        Returns:
            Dictionary containing:
            - total_tokens: Total tokens in all blocks
            - baseline_tokens: Baseline token count
            - efficiency_improvement: Fraction of tokens saved (0.0-1.0)
            - meets_target: Whether 30% target is met
            - breakdown: Token count per block type
        """
        # Calculate total tokens
        total_tokens = sum(block.token_count for block in blocks)

        # Calculate efficiency improvement
        if self.baseline > 0:
            efficiency_improvement = 1 - (total_tokens / self.baseline)
        else:
            efficiency_improvement = 0.0

        # Check if target met
        meets_target = efficiency_improvement >= self.TARGET_EFFICIENCY

        # Calculate breakdown by block type
        breakdown: dict[str, int] = {}
        for block in blocks:
            block_type_value = block.block_type.value
            if block_type_value in breakdown:
                breakdown[block_type_value] += block.token_count
            else:
                breakdown[block_type_value] = block.token_count

        return {
            "total_tokens": total_tokens,
            "baseline_tokens": self.baseline,
            "efficiency_improvement": round(efficiency_improvement, 2),
            "meets_target": meets_target,
            "breakdown": breakdown,
        }
