# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
Memory Block schemas for context engineering (ADR-003 Phase 2).

This module defines the core data structures for the Memory Blocks architecture:
- BlockType: Enum for the 5 block types
- Provenance: Tracks source attribution for memories
- MemoryBlock: Container for assembled context blocks

Related GitHub Issues:
- #116: Phase 2: Memory Blocks Architecture

ADR Reference: ADR-003 Memory Architecture, Phase 2 (Context Engineering)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class BlockType(str, Enum):
    """
    Enumeration of memory block types for context engineering.

    Each block type serves a specific purpose in the context assembly:
    - SYSTEM: Core instructions, persona (highest priority)
    - PROJECT: Current project context, conventions
    - TASK: Active task, goals, constraints
    - HISTORY: Compressed conversation history
    - KNOWLEDGE: Retrieved ADRs, incidents, code (lowest priority)
    """

    SYSTEM = "system"
    PROJECT = "project"
    TASK = "task"
    HISTORY = "history"
    KNOWLEDGE = "knowledge"


@dataclass
class Provenance:
    """
    Tracks source attribution for retrieved content.

    Provenance ensures all retrieved items can be traced back to their
    source, meeting the ADR-003 Phase 2 exit criterion:
    "Provenance available for all retrieved items"

    Attributes:
        source_id: Unique identifier of the source (memory ID, ADR path, etc.)
        source_type: Type of source ("memory", "adr", "conversation", "incident")
        confidence: Confidence score from extraction (0.0-1.0)
        created_at: When the source was created
        retrieval_score: Relevance score from retrieval ranking (optional)
    """

    source_id: str
    source_type: str
    confidence: float
    created_at: datetime
    retrieval_score: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert provenance to dictionary for serialization."""
        return {
            "source_id": self.source_id,
            "source_type": self.source_type,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat(),
            "retrieval_score": self.retrieval_score,
        }


@dataclass
class MemoryBlock:
    """
    Container for an assembled context block.

    Memory blocks structure context into discrete functional units,
    enabling selective retrieval and token budget management.

    Attributes:
        block_type: The type of block (SYSTEM, PROJECT, TASK, HISTORY, KNOWLEDGE)
        content: The assembled content for this block
        token_count: Number of tokens in the content
        priority: Priority for context assembly (1 = highest, 5 = lowest)
        metadata: Additional block-specific metadata
        provenance: Source attribution (optional, typically for KNOWLEDGE blocks)
    """

    block_type: BlockType
    content: str
    token_count: int
    priority: int
    metadata: dict[str, Any] = field(default_factory=dict)
    provenance: Optional[Provenance] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert memory block to dictionary for serialization."""
        result = {
            "block_type": self.block_type.value,
            "content": self.content,
            "token_count": self.token_count,
            "priority": self.priority,
            "metadata": self.metadata,
        }
        if self.provenance:
            result["provenance"] = self.provenance.to_dict()
        return result


# Default priorities for each block type (1 = highest priority)
# Priority determines order of assembly and truncation during budget overflow
DEFAULT_BLOCK_PRIORITIES: dict[BlockType, int] = {
    BlockType.SYSTEM: 1,  # Core instructions - never truncate
    BlockType.PROJECT: 2,  # Project context - rarely truncate
    BlockType.TASK: 3,  # Current task - important
    BlockType.HISTORY: 4,  # Conversation history - can compress
    BlockType.KNOWLEDGE: 5,  # Retrieved content - can limit
}

# Default token budgets for each block type
# Total: 5000 tokens (adjustable per model context window)
DEFAULT_TOKEN_BUDGETS: dict[BlockType, int] = {
    BlockType.SYSTEM: 500,  # Core instructions
    BlockType.PROJECT: 1000,  # Project context
    BlockType.TASK: 500,  # Active task
    BlockType.HISTORY: 1000,  # Compressed history
    BlockType.KNOWLEDGE: 2000,  # Retrieved memories
}
