# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""TDD: RED Phase - Tests for HaikuEntityExtractor.

These tests define the expected behavior for the LLM-based
entity extractor using Claude Haiku.

Related GitHub Issues:
- #120: Implement HaikuEntityExtractor for LLM extraction

ADR Reference: ADR-003 Memory Architecture, Phase 3 (Entity Extraction)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from luminescent_cluster.memory.extraction.entities import Entity, EntityExtractor, EntityType


class TestHaikuEntityExtractorExists:
    """TDD: Tests for HaikuEntityExtractor existence and protocol."""

    def test_haiku_entity_extractor_exists(self):
        """HaikuEntityExtractor class should be defined.

        GitHub Issue: #120
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import HaikuEntityExtractor

        assert HaikuEntityExtractor is not None

    def test_haiku_entity_extractor_implements_protocol(self):
        """HaikuEntityExtractor should implement EntityExtractor protocol.

        GitHub Issue: #120
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import HaikuEntityExtractor

        extractor = HaikuEntityExtractor()
        assert isinstance(extractor, EntityExtractor)

    def test_haiku_entity_extractor_has_extract_method(self):
        """HaikuEntityExtractor should have async extract method.

        GitHub Issue: #120
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import HaikuEntityExtractor

        extractor = HaikuEntityExtractor()
        assert hasattr(extractor, "extract")
        assert callable(extractor.extract)


class TestHaikuEntityExtractorConstructor:
    """TDD: Tests for HaikuEntityExtractor constructor."""

    def test_accepts_model_parameter(self):
        """Should accept model parameter.

        GitHub Issue: #120
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import HaikuEntityExtractor

        extractor = HaikuEntityExtractor(model="claude-3-haiku-20240307")
        assert extractor.model == "claude-3-haiku-20240307"

    def test_accepts_temperature_parameter(self):
        """Should accept temperature parameter.

        GitHub Issue: #120
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import HaikuEntityExtractor

        extractor = HaikuEntityExtractor(temperature=0.0)
        assert extractor.temperature == 0.0

    def test_accepts_max_tokens_parameter(self):
        """Should accept max_tokens parameter.

        GitHub Issue: #120
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import HaikuEntityExtractor

        extractor = HaikuEntityExtractor(max_tokens=1024)
        assert extractor.max_tokens == 1024

    def test_accepts_api_key_parameter(self):
        """Should accept api_key parameter.

        GitHub Issue: #120
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import HaikuEntityExtractor

        extractor = HaikuEntityExtractor(api_key="test-key")
        # Should not raise


class TestHaikuEntityExtractorPrompts:
    """TDD: Tests for entity extraction prompts."""

    def test_entity_extraction_system_prompt_exists(self):
        """Entity extraction system prompt should be defined.

        GitHub Issue: #120
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities.prompts import ENTITY_EXTRACTION_SYSTEM_PROMPT

        assert ENTITY_EXTRACTION_SYSTEM_PROMPT is not None
        assert len(ENTITY_EXTRACTION_SYSTEM_PROMPT) > 0

    def test_entity_extraction_user_prompt_exists(self):
        """Entity extraction user prompt template should be defined.

        GitHub Issue: #120
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities.prompts import ENTITY_EXTRACTION_USER_TEMPLATE

        assert ENTITY_EXTRACTION_USER_TEMPLATE is not None
        assert "{content}" in ENTITY_EXTRACTION_USER_TEMPLATE

    def test_system_prompt_mentions_entity_types(self):
        """System prompt should mention all entity types.

        GitHub Issue: #120
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities.prompts import ENTITY_EXTRACTION_SYSTEM_PROMPT

        assert "SERVICE" in ENTITY_EXTRACTION_SYSTEM_PROMPT
        assert "DEPENDENCY" in ENTITY_EXTRACTION_SYSTEM_PROMPT
        assert "API" in ENTITY_EXTRACTION_SYSTEM_PROMPT
        assert "PATTERN" in ENTITY_EXTRACTION_SYSTEM_PROMPT
        assert "FRAMEWORK" in ENTITY_EXTRACTION_SYSTEM_PROMPT
        assert "CONFIG" in ENTITY_EXTRACTION_SYSTEM_PROMPT


class TestHaikuEntityExtractorExtraction:
    """TDD: Tests for entity extraction with mocked API."""

    @pytest.mark.asyncio
    async def test_extracts_entities_from_response(self):
        """Should parse entities from API response.

        GitHub Issue: #120
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import HaikuEntityExtractor

        # Mock the API response
        mock_response = [
            {
                "name": "auth-service",
                "entity_type": "service",
                "confidence": 0.95,
            },
            {
                "name": "PostgreSQL",
                "entity_type": "dependency",
                "confidence": 0.9,
            },
        ]

        extractor = HaikuEntityExtractor()

        with patch.object(extractor, "_call_api", new_callable=AsyncMock) as mock_api:
            mock_api.return_value = mock_response
            entities = await extractor.extract("The auth-service uses PostgreSQL")

        assert len(entities) == 2
        assert entities[0].name == "auth-service"
        assert entities[0].entity_type == EntityType.SERVICE
        assert entities[1].name == "PostgreSQL"
        assert entities[1].entity_type == EntityType.DEPENDENCY

    @pytest.mark.asyncio
    async def test_stores_memory_id_in_entities(self):
        """Should store memory_id in extracted entities.

        GitHub Issue: #120
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import HaikuEntityExtractor

        mock_response = [
            {
                "name": "FastAPI",
                "entity_type": "framework",
                "confidence": 0.9,
            },
        ]

        extractor = HaikuEntityExtractor()

        with patch.object(extractor, "_call_api", new_callable=AsyncMock) as mock_api:
            mock_api.return_value = mock_response
            entities = await extractor.extract(
                "Built with FastAPI",
                memory_id="mem-123",
            )

        assert entities[0].source_memory_id == "mem-123"

    @pytest.mark.asyncio
    async def test_returns_empty_list_on_api_error(self):
        """Should return empty list on API error.

        GitHub Issue: #120
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import HaikuEntityExtractor

        extractor = HaikuEntityExtractor()

        with patch.object(extractor, "_call_api", new_callable=AsyncMock) as mock_api:
            mock_api.side_effect = Exception("API error")
            entities = await extractor.extract("Test content")

        assert entities == []

    @pytest.mark.asyncio
    async def test_returns_empty_list_for_no_entities(self):
        """Should return empty list when no entities extracted.

        GitHub Issue: #120
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import HaikuEntityExtractor

        extractor = HaikuEntityExtractor()

        with patch.object(extractor, "_call_api", new_callable=AsyncMock) as mock_api:
            mock_api.return_value = []
            entities = await extractor.extract("Hello world")

        assert entities == []

    @pytest.mark.asyncio
    async def test_skips_malformed_entities(self):
        """Should skip malformed entities in response.

        GitHub Issue: #120
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import HaikuEntityExtractor

        mock_response = [
            {
                "name": "valid-service",
                "entity_type": "service",
                "confidence": 0.9,
            },
            {
                "invalid": "missing required fields",
            },
        ]

        extractor = HaikuEntityExtractor()

        with patch.object(extractor, "_call_api", new_callable=AsyncMock) as mock_api:
            mock_api.return_value = mock_response
            entities = await extractor.extract("Content with entities")

        # Should only have the valid entity
        assert len(entities) == 1
        assert entities[0].name == "valid-service"


class TestHaikuEntityExtractorModuleExport:
    """TDD: Tests for module exports."""

    def test_module_exports_haiku_entity_extractor(self):
        """Module should export HaikuEntityExtractor.

        GitHub Issue: #120
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import HaikuEntityExtractor

        assert HaikuEntityExtractor is not None

    def test_prompts_module_exists(self):
        """Entity prompts module should exist.

        GitHub Issue: #120
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import prompts

        assert prompts is not None
