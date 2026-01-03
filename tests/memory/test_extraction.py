# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
TDD: RED Phase - Tests for Memory Extraction.

These tests define the expected behavior for the async memory extraction
pipeline including the extractor interface, prompts, and pipeline.

Related GitHub Issues:
- #91: Extraction UDF Interface
- #92: extract_memory_facts() UDF
- #93: Async Extraction Pipeline
- #94: Confidence Scoring
- #95: Version Tracking

ADR Reference: ADR-003 Memory Architecture, Phase 1b (Async Extraction)
"""

import pytest
from datetime import datetime, timezone
from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock, patch


class TestExtractionResult:
    """TDD: Tests for ExtractionResult dataclass."""

    def test_extraction_result_class_exists(self):
        """ExtractionResult class should be defined.

        GitHub Issue: #91
        ADR Reference: ADR-003 Phase 1b (Extraction)
        """
        from src.memory.extraction.types import ExtractionResult

        assert ExtractionResult is not None

    def test_extraction_result_has_content(self):
        """ExtractionResult should have content field.

        GitHub Issue: #91
        ADR Reference: ADR-003 Phase 1b (Extraction)
        """
        from src.memory.extraction.types import ExtractionResult

        result = ExtractionResult(
            content="User prefers tabs",
            memory_type="preference",
            confidence=0.9,
        )
        assert result.content == "User prefers tabs"

    def test_extraction_result_has_memory_type(self):
        """ExtractionResult should have memory_type field.

        GitHub Issue: #91
        ADR Reference: ADR-003 Phase 1b (Extraction)
        """
        from src.memory.extraction.types import ExtractionResult

        result = ExtractionResult(
            content="Test",
            memory_type="fact",
            confidence=0.8,
        )
        assert result.memory_type == "fact"

    def test_extraction_result_has_confidence(self):
        """ExtractionResult should have confidence field.

        GitHub Issue: #94
        ADR Reference: ADR-003 Phase 1b (Confidence Scoring)
        """
        from src.memory.extraction.types import ExtractionResult

        result = ExtractionResult(
            content="Test",
            memory_type="decision",
            confidence=0.95,
        )
        assert result.confidence == 0.95

    def test_extraction_result_has_raw_source(self):
        """ExtractionResult should have raw_source field.

        GitHub Issue: #91
        ADR Reference: ADR-003 Phase 1b (Extraction)
        """
        from src.memory.extraction.types import ExtractionResult

        result = ExtractionResult(
            content="Extracted fact",
            memory_type="fact",
            confidence=0.9,
            raw_source="Original conversation text",
        )
        assert result.raw_source == "Original conversation text"


class TestMemoryExtractorProtocol:
    """TDD: Tests for MemoryExtractor protocol."""

    def test_memory_extractor_protocol_exists(self):
        """MemoryExtractor protocol should be defined.

        GitHub Issue: #91
        ADR Reference: ADR-003 Phase 1b (Extraction)
        """
        from src.memory.extraction.types import MemoryExtractor

        assert MemoryExtractor is not None

    def test_memory_extractor_has_extract_method(self):
        """MemoryExtractor should define extract method.

        GitHub Issue: #91
        ADR Reference: ADR-003 Phase 1b (Extraction)
        """
        from src.memory.extraction.types import MemoryExtractor

        assert hasattr(MemoryExtractor, "extract")


class TestExtractionPrompts:
    """TDD: Tests for extraction prompts."""

    def test_extraction_system_prompt_exists(self):
        """EXTRACTION_SYSTEM_PROMPT should be defined.

        GitHub Issue: #92
        ADR Reference: ADR-003 Phase 1b (Extraction)
        """
        from src.memory.extraction.prompts import EXTRACTION_SYSTEM_PROMPT

        assert EXTRACTION_SYSTEM_PROMPT is not None
        assert len(EXTRACTION_SYSTEM_PROMPT) > 100

    def test_extraction_system_prompt_mentions_types(self):
        """EXTRACTION_SYSTEM_PROMPT should mention memory types.

        GitHub Issue: #92
        ADR Reference: ADR-003 Phase 1b (Extraction)
        """
        from src.memory.extraction.prompts import EXTRACTION_SYSTEM_PROMPT

        assert "preference" in EXTRACTION_SYSTEM_PROMPT.lower()
        assert "fact" in EXTRACTION_SYSTEM_PROMPT.lower()
        assert "decision" in EXTRACTION_SYSTEM_PROMPT.lower()

    def test_extraction_user_prompt_template_exists(self):
        """EXTRACTION_USER_PROMPT_TEMPLATE should be defined.

        GitHub Issue: #92
        ADR Reference: ADR-003 Phase 1b (Extraction)
        """
        from src.memory.extraction.prompts import EXTRACTION_USER_PROMPT_TEMPLATE

        assert EXTRACTION_USER_PROMPT_TEMPLATE is not None
        assert "{conversation}" in EXTRACTION_USER_PROMPT_TEMPLATE


class TestHaikuExtractor:
    """TDD: Tests for HaikuExtractor implementation."""

    def test_haiku_extractor_class_exists(self):
        """HaikuExtractor class should be defined.

        GitHub Issue: #92
        ADR Reference: ADR-003 Phase 1b (Extraction)
        """
        from src.memory.extraction.haiku_extractor import HaikuExtractor

        assert HaikuExtractor is not None

    def test_haiku_extractor_implements_protocol(self):
        """HaikuExtractor should implement MemoryExtractor protocol.

        GitHub Issue: #92
        ADR Reference: ADR-003 Phase 1b (Extraction)
        """
        from src.memory.extraction.haiku_extractor import HaikuExtractor
        from src.memory.extraction.types import MemoryExtractor

        extractor = HaikuExtractor()
        assert isinstance(extractor, MemoryExtractor)

    def test_haiku_extractor_uses_temperature_zero(self):
        """HaikuExtractor should use temperature=0 for determinism.

        GitHub Issue: #92
        ADR Reference: ADR-003 Phase 1b (Extraction)
        """
        from src.memory.extraction.haiku_extractor import HaikuExtractor

        extractor = HaikuExtractor()
        assert extractor.temperature == 0.0

    @pytest.mark.asyncio
    async def test_haiku_extractor_returns_list(self):
        """HaikuExtractor.extract should return list of ExtractionResult.

        GitHub Issue: #92
        ADR Reference: ADR-003 Phase 1b (Extraction)
        """
        from src.memory.extraction.haiku_extractor import HaikuExtractor

        extractor = HaikuExtractor()

        # Mock the API call
        with patch.object(extractor, "_call_api") as mock_call:
            mock_call.return_value = []
            result = await extractor.extract("User said: I prefer tabs over spaces")

        assert isinstance(result, list)


class TestMockExtractor:
    """TDD: Tests for MockExtractor (for testing without API)."""

    def test_mock_extractor_class_exists(self):
        """MockExtractor class should be defined.

        GitHub Issue: #91
        ADR Reference: ADR-003 Phase 1b (Extraction)
        """
        from src.memory.extraction.mock_extractor import MockExtractor

        assert MockExtractor is not None

    @pytest.mark.asyncio
    async def test_mock_extractor_extracts_preferences(self):
        """MockExtractor should extract preference patterns.

        GitHub Issue: #91
        ADR Reference: ADR-003 Phase 1b (Extraction)
        """
        from src.memory.extraction.mock_extractor import MockExtractor

        extractor = MockExtractor()
        results = await extractor.extract("I prefer tabs over spaces for indentation")

        assert len(results) >= 1
        assert any(r.memory_type == "preference" for r in results)

    @pytest.mark.asyncio
    async def test_mock_extractor_extracts_facts(self):
        """MockExtractor should extract fact patterns.

        GitHub Issue: #91
        ADR Reference: ADR-003 Phase 1b (Extraction)
        """
        from src.memory.extraction.mock_extractor import MockExtractor

        extractor = MockExtractor()
        results = await extractor.extract("The API uses PostgreSQL as the database")

        assert len(results) >= 1
        assert any(r.memory_type == "fact" for r in results)

    @pytest.mark.asyncio
    async def test_mock_extractor_extracts_decisions(self):
        """MockExtractor should extract decision patterns.

        GitHub Issue: #91
        ADR Reference: ADR-003 Phase 1b (Extraction)
        """
        from src.memory.extraction.mock_extractor import MockExtractor

        extractor = MockExtractor()
        results = await extractor.extract("We decided to use REST instead of GraphQL")

        assert len(results) >= 1
        assert any(r.memory_type == "decision" for r in results)


class TestExtractionPipeline:
    """TDD: Tests for async extraction pipeline."""

    def test_extraction_pipeline_class_exists(self):
        """ExtractionPipeline class should be defined.

        GitHub Issue: #93
        ADR Reference: ADR-003 Phase 1b (Async Extraction)
        """
        from src.memory.extraction.pipeline import ExtractionPipeline

        assert ExtractionPipeline is not None

    def test_extraction_pipeline_has_process_method(self):
        """ExtractionPipeline should have process method.

        GitHub Issue: #93
        ADR Reference: ADR-003 Phase 1b (Async Extraction)
        """
        from src.memory.extraction.pipeline import ExtractionPipeline

        pipeline = ExtractionPipeline()
        assert hasattr(pipeline, "process")
        assert callable(pipeline.process)

    def test_extraction_pipeline_has_process_async_method(self):
        """ExtractionPipeline should have process_async method.

        GitHub Issue: #93
        ADR Reference: ADR-003 Phase 1b (Async Extraction)
        """
        from src.memory.extraction.pipeline import ExtractionPipeline

        pipeline = ExtractionPipeline()
        assert hasattr(pipeline, "process_async")

    @pytest.mark.asyncio
    async def test_pipeline_processes_conversation(self):
        """Pipeline should process a conversation and return memories.

        GitHub Issue: #93
        ADR Reference: ADR-003 Phase 1b (Async Extraction)
        """
        from src.memory.extraction.pipeline import ExtractionPipeline
        from src.memory.extraction.mock_extractor import MockExtractor

        pipeline = ExtractionPipeline(extractor=MockExtractor())

        results = await pipeline.process(
            conversation="I always use pytest for testing Python code",
            user_id="user-123",
        )

        assert isinstance(results, list)


class TestExtractionVersioning:
    """TDD: Tests for extraction version tracking."""

    def test_extraction_version_constant_exists(self):
        """EXTRACTION_VERSION constant should be defined.

        GitHub Issue: #95
        ADR Reference: ADR-003 Phase 1b (Version Tracking)
        """
        from src.memory.extraction import EXTRACTION_VERSION

        assert EXTRACTION_VERSION is not None

    def test_extraction_version_is_integer(self):
        """EXTRACTION_VERSION should be an integer.

        GitHub Issue: #95
        ADR Reference: ADR-003 Phase 1b (Version Tracking)
        """
        from src.memory.extraction import EXTRACTION_VERSION

        assert isinstance(EXTRACTION_VERSION, int)
        assert EXTRACTION_VERSION >= 1


class TestConfidenceScoring:
    """TDD: Tests for confidence scoring."""

    def test_calculate_confidence_function_exists(self):
        """calculate_confidence function should be defined.

        GitHub Issue: #94
        ADR Reference: ADR-003 Phase 1b (Confidence Scoring)
        """
        from src.memory.extraction.confidence import calculate_confidence

        assert callable(calculate_confidence)

    def test_confidence_score_range(self):
        """Confidence score should be between 0.0 and 1.0.

        GitHub Issue: #94
        ADR Reference: ADR-003 Phase 1b (Confidence Scoring)
        """
        from src.memory.extraction.confidence import calculate_confidence

        # Test with various inputs
        score = calculate_confidence(
            extraction_text="User prefers tabs",
            source_text="I always use tabs for indentation",
            memory_type="preference",
        )

        assert 0.0 <= score <= 1.0

    def test_explicit_statements_have_higher_confidence(self):
        """Explicit preference statements should have higher confidence.

        GitHub Issue: #94
        ADR Reference: ADR-003 Phase 1b (Confidence Scoring)
        """
        from src.memory.extraction.confidence import calculate_confidence

        # Explicit statement
        explicit_score = calculate_confidence(
            extraction_text="User prefers tabs",
            source_text="I prefer tabs over spaces",
            memory_type="preference",
        )

        # Implicit statement
        implicit_score = calculate_confidence(
            extraction_text="User might prefer tabs",
            source_text="I sometimes use tabs",
            memory_type="preference",
        )

        assert explicit_score >= implicit_score


class TestExtractionModuleExports:
    """TDD: Tests for extraction module exports."""

    def test_extraction_module_exists(self):
        """src.memory.extraction module should exist.

        GitHub Issue: #91
        ADR Reference: ADR-003 Phase 1b (Extraction)
        """
        import src.memory.extraction

        assert src.memory.extraction is not None

    def test_extraction_exports_types(self):
        """extraction module should export types.

        GitHub Issue: #91
        ADR Reference: ADR-003 Phase 1b (Extraction)
        """
        from src.memory.extraction import ExtractionResult, MemoryExtractor

        assert ExtractionResult is not None
        assert MemoryExtractor is not None

    def test_extraction_exports_pipeline(self):
        """extraction module should export ExtractionPipeline.

        GitHub Issue: #93
        ADR Reference: ADR-003 Phase 1b (Extraction)
        """
        from src.memory.extraction import ExtractionPipeline

        assert ExtractionPipeline is not None

    def test_extraction_exports_extractors(self):
        """extraction module should export extractor implementations.

        GitHub Issue: #91-92
        ADR Reference: ADR-003 Phase 1b (Extraction)
        """
        from src.memory.extraction import HaikuExtractor, MockExtractor

        assert HaikuExtractor is not None
        assert MockExtractor is not None
