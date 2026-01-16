# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Entity extraction types and implementations.

This module provides entity extraction from memory content,
supporting knowledge graph construction in Phase 4.

Related GitHub Issues:
- #118: Entity Types and Schema Definition
- #119: MockEntityExtractor for testing
- #120: HaikuEntityExtractor for LLM extraction
- #121: EntityExtractionPipeline integration

ADR Reference: ADR-003 Memory Architecture, Phase 3 (Entity Extraction)
"""

from src.memory.extraction.entities import prompts
from src.memory.extraction.entities.haiku_extractor import HaikuEntityExtractor
from src.memory.extraction.entities.mock_extractor import MockEntityExtractor
from src.memory.extraction.entities.pipeline import EntityExtractionPipeline
from src.memory.extraction.entities.types import Entity, EntityExtractor, EntityType

__all__ = [
    # Types
    "Entity",
    "EntityExtractor",
    "EntityType",
    # Extractors
    "MockEntityExtractor",
    "HaikuEntityExtractor",
    # Pipeline
    "EntityExtractionPipeline",
    # Prompts module
    "prompts",
]
