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

ADR Reference: ADR-003 Memory Architecture, Phase 1b (Async Extraction)
"""

from src.memory.extraction.confidence import calculate_confidence
from src.memory.extraction.haiku_extractor import HaikuExtractor
from src.memory.extraction.mock_extractor import MockExtractor
from src.memory.extraction.pipeline import EXTRACTION_VERSION, ExtractionPipeline
from src.memory.extraction.prompts import (
    EXTRACTION_SYSTEM_PROMPT,
    EXTRACTION_USER_PROMPT_TEMPLATE,
)
from src.memory.extraction.types import ExtractionResult, MemoryExtractor

__all__ = [
    # Version
    "EXTRACTION_VERSION",
    # Types
    "ExtractionResult",
    "MemoryExtractor",
    # Extractors
    "MockExtractor",
    "HaikuExtractor",
    # Pipeline
    "ExtractionPipeline",
    # Confidence
    "calculate_confidence",
    # Prompts
    "EXTRACTION_SYSTEM_PROMPT",
    "EXTRACTION_USER_PROMPT_TEMPLATE",
]
