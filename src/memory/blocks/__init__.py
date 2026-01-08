# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
Memory Blocks module for context engineering (ADR-003 Phase 2).

This module implements the Memory Blocks architecture for structured
context management across five functional blocks:
- System Block: Core instructions, persona
- Project Block: Current project context, conventions
- Task Block: Active task, goals, constraints
- History Block: Compressed conversation history
- Knowledge Block: Retrieved ADRs, incidents, code

Related GitHub Issues:
- #116: Phase 2: Memory Blocks Architecture

ADR Reference: ADR-003 Memory Architecture, Phase 2 (Context Engineering)
"""

from .assembler import BlockAssembler
from .compressor import HistoryCompressor
from .schemas import (
    BlockType,
    DEFAULT_BLOCK_PRIORITIES,
    DEFAULT_TOKEN_BUDGETS,
    MemoryBlock,
    Provenance,
)

__all__ = [
    "BlockAssembler",
    "BlockType",
    "HistoryCompressor",
    "MemoryBlock",
    "Provenance",
    "DEFAULT_BLOCK_PRIORITIES",
    "DEFAULT_TOKEN_BUDGETS",
]
