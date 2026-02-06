# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Memory extraction for ADR-003.

This module provides async memory extraction from conversations,
including pattern-based and LLM-based extractors.

Related GitHub Issues:
- #91: Extraction UDF Interface
- #92: extract_memory_facts() UDF
- #93: Async Extraction Pipeline
- #94: Confidence Scoring
- #95: Version Tracking
- #118: Entity Types and Schema Definition
- #119: MockEntityExtractor for testing
- #120: HaikuEntityExtractor for LLM extraction
- #121: EntityExtractionPipeline integration

ADR Reference: ADR-003 Memory Architecture
- Phase 1b (Async Extraction)
- Phase 3 (Entity Extraction)
"""

from luminescent_cluster.memory.extraction.confidence import calculate_confidence
from luminescent_cluster.memory.extraction.haiku_extractor import HaikuExtractor
from luminescent_cluster.memory.extraction.mock_extractor import MockExtractor
from luminescent_cluster.memory.extraction.pipeline import EXTRACTION_VERSION, ExtractionPipeline
from luminescent_cluster.memory.extraction.prompts import (
    EXTRACTION_SYSTEM_PROMPT,
    EXTRACTION_USER_PROMPT_TEMPLATE,
)
from luminescent_cluster.memory.extraction.types import ExtractionResult, MemoryExtractor

# Entity extraction (Phase 3)
from luminescent_cluster.memory.extraction.entities import (
    Entity,
    EntityExtractor,
    EntityExtractionPipeline,
    EntityType,
    HaikuEntityExtractor,
    MockEntityExtractor,
)

__all__ = [
    # Version
    "EXTRACTION_VERSION",
    # Memory Types
    "ExtractionResult",
    "MemoryExtractor",
    # Memory Extractors
    "MockExtractor",
    "HaikuExtractor",
    # Memory Pipeline
    "ExtractionPipeline",
    # Confidence
    "calculate_confidence",
    # Prompts
    "EXTRACTION_SYSTEM_PROMPT",
    "EXTRACTION_USER_PROMPT_TEMPLATE",
    # Entity Types (Phase 3)
    "Entity",
    "EntityExtractor",
    "EntityType",
    # Entity Extractors (Phase 3)
    "MockEntityExtractor",
    "HaikuEntityExtractor",
    # Entity Pipeline (Phase 3)
    "EntityExtractionPipeline",
]
