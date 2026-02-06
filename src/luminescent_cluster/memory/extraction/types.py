# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Types for memory extraction.

Defines the ExtractionResult dataclass and MemoryExtractor protocol.

Related GitHub Issues:
- #91: Extraction UDF Interface

ADR Reference: ADR-003 Memory Architecture, Phase 1b (Async Extraction)
"""

from dataclasses import dataclass, field
from typing import Any, List, Optional, Protocol, runtime_checkable


@dataclass
class ExtractionResult:
    """Result of extracting a memory from conversation.

    Attributes:
        content: The extracted memory content.
        memory_type: Type of memory (preference, fact, decision).
        confidence: Extraction confidence score (0.0-1.0).
        raw_source: Original text the memory was extracted from.
        metadata: Additional metadata about the extraction.
    """

    content: str
    memory_type: str  # preference, fact, decision
    confidence: float
    raw_source: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class MemoryExtractor(Protocol):
    """Protocol for memory extraction implementations.

    Extractors analyze conversation text and extract memories
    (preferences, facts, decisions) with confidence scores.
    """

    async def extract(self, text: str) -> List[ExtractionResult]:
        """Extract memories from text.

        Args:
            text: Conversation text to analyze.

        Returns:
            List of ExtractionResult objects.
        """
        ...
