# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""TDD: RED Phase - Tests for EntityExtractionPipeline.

These tests define the expected behavior for the async entity
extraction pipeline with storage integration.

Related GitHub Issues:
- #121: Async EntityExtractionPipeline with storage integration

ADR Reference: ADR-003 Memory Architecture, Phase 3 (Entity Extraction)
"""

import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from luminescent_cluster.memory.extraction.entities import Entity, EntityExtractor, EntityType


class TestEntityExtractionPipelineExists:
    """TDD: Tests for EntityExtractionPipeline existence."""

    def test_entity_extraction_pipeline_exists(self):
        """EntityExtractionPipeline class should be defined.

        GitHub Issue: #121
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import EntityExtractionPipeline

        assert EntityExtractionPipeline is not None

    def test_entity_extraction_pipeline_has_process_method(self):
        """EntityExtractionPipeline should have process method.

        GitHub Issue: #121
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import EntityExtractionPipeline

        pipeline = EntityExtractionPipeline()
        assert hasattr(pipeline, "process")
        assert callable(pipeline.process)

    def test_entity_extraction_pipeline_has_process_async_method(self):
        """EntityExtractionPipeline should have process_async method.

        GitHub Issue: #121
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import EntityExtractionPipeline

        pipeline = EntityExtractionPipeline()
        assert hasattr(pipeline, "process_async")
        assert callable(pipeline.process_async)


class TestEntityExtractionPipelineConstructor:
    """TDD: Tests for EntityExtractionPipeline constructor."""

    def test_accepts_extractor_parameter(self):
        """Should accept extractor parameter.

        GitHub Issue: #121
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import (
            EntityExtractionPipeline,
            MockEntityExtractor,
        )

        extractor = MockEntityExtractor()
        pipeline = EntityExtractionPipeline(extractor=extractor)
        assert pipeline.extractor is extractor

    def test_accepts_provider_parameter(self):
        """Should accept provider parameter.

        GitHub Issue: #121
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import EntityExtractionPipeline
        from luminescent_cluster.memory.providers.local import LocalMemoryProvider

        provider = LocalMemoryProvider()
        pipeline = EntityExtractionPipeline(provider=provider)
        assert pipeline.provider is provider

    def test_uses_mock_extractor_by_default(self):
        """Should use MockEntityExtractor by default.

        GitHub Issue: #121
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import (
            EntityExtractionPipeline,
            MockEntityExtractor,
        )

        pipeline = EntityExtractionPipeline()
        assert isinstance(pipeline.extractor, MockEntityExtractor)


class TestEntityExtractionPipelineProcess:
    """TDD: Tests for process method."""

    @pytest.mark.asyncio
    async def test_process_extracts_entities(self):
        """Process should extract entities from content.

        GitHub Issue: #121
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import (
            EntityExtractionPipeline,
            MockEntityExtractor,
        )
        from luminescent_cluster.memory.providers.local import LocalMemoryProvider
        from luminescent_cluster.memory.schemas import Memory, MemoryType

        # Set up provider with a memory
        provider = LocalMemoryProvider()
        memory = Memory(
            user_id="user-123",
            content="The auth-service uses PostgreSQL",
            memory_type=MemoryType.FACT,
            confidence=0.9,
            source="test",
        )
        memory_id = await provider.store(memory, {})

        # Create pipeline
        pipeline = EntityExtractionPipeline(
            extractor=MockEntityExtractor(),
            provider=provider,
        )

        # Process
        entities = await pipeline.process(
            memory_id=memory_id,
            content="The auth-service uses PostgreSQL",
            user_id="user-123",
        )

        assert len(entities) > 0
        assert any(e.entity_type == EntityType.SERVICE for e in entities)
        assert any(e.entity_type == EntityType.DEPENDENCY for e in entities)

    @pytest.mark.asyncio
    async def test_process_stores_entities_in_metadata(self):
        """Process should store entities in memory metadata.

        GitHub Issue: #121
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import (
            EntityExtractionPipeline,
            MockEntityExtractor,
        )
        from luminescent_cluster.memory.providers.local import LocalMemoryProvider
        from luminescent_cluster.memory.schemas import Memory, MemoryType

        # Set up provider with a memory
        provider = LocalMemoryProvider()
        memory = Memory(
            user_id="user-123",
            content="The auth-service uses PostgreSQL",
            memory_type=MemoryType.FACT,
            confidence=0.9,
            source="test",
        )
        memory_id = await provider.store(memory, {})

        # Create pipeline
        pipeline = EntityExtractionPipeline(
            extractor=MockEntityExtractor(),
            provider=provider,
        )

        # Process
        await pipeline.process(
            memory_id=memory_id,
            content="The auth-service uses PostgreSQL",
            user_id="user-123",
        )

        # Check memory metadata has entities
        updated_memory = await provider.get_by_id(memory_id)
        assert "entities" in updated_memory.metadata
        assert len(updated_memory.metadata["entities"]) > 0

    @pytest.mark.asyncio
    async def test_process_returns_empty_list_for_no_entities(self):
        """Process should return empty list when no entities found.

        GitHub Issue: #121
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import (
            EntityExtractionPipeline,
            MockEntityExtractor,
        )
        from luminescent_cluster.memory.providers.local import LocalMemoryProvider
        from luminescent_cluster.memory.schemas import Memory, MemoryType

        # Set up provider with a memory
        provider = LocalMemoryProvider()
        memory = Memory(
            user_id="user-123",
            content="Hello world",
            memory_type=MemoryType.FACT,
            confidence=0.9,
            source="test",
        )
        memory_id = await provider.store(memory, {})

        # Create pipeline
        pipeline = EntityExtractionPipeline(
            extractor=MockEntityExtractor(),
            provider=provider,
        )

        # Process
        entities = await pipeline.process(
            memory_id=memory_id,
            content="Hello world",
            user_id="user-123",
        )

        assert entities == []


class TestEntityExtractionPipelineProcessAsync:
    """TDD: Tests for process_async method."""

    @pytest.mark.asyncio
    async def test_process_async_returns_task(self):
        """process_async should return an asyncio.Task.

        GitHub Issue: #121
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import (
            EntityExtractionPipeline,
            MockEntityExtractor,
        )
        from luminescent_cluster.memory.providers.local import LocalMemoryProvider
        from luminescent_cluster.memory.schemas import Memory, MemoryType

        # Set up provider
        provider = LocalMemoryProvider()
        memory = Memory(
            user_id="user-123",
            content="The auth-service uses PostgreSQL",
            memory_type=MemoryType.FACT,
            confidence=0.9,
            source="test",
        )
        memory_id = await provider.store(memory, {})

        # Create pipeline
        pipeline = EntityExtractionPipeline(
            extractor=MockEntityExtractor(),
            provider=provider,
        )

        # Call process_async
        task = await pipeline.process_async(
            memory_id=memory_id,
            content="The auth-service uses PostgreSQL",
            user_id="user-123",
        )

        assert isinstance(task, asyncio.Task)
        await task  # Clean up

    @pytest.mark.asyncio
    async def test_process_async_task_completes(self):
        """process_async task should complete and return entities.

        GitHub Issue: #121
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import (
            EntityExtractionPipeline,
            MockEntityExtractor,
        )
        from luminescent_cluster.memory.providers.local import LocalMemoryProvider
        from luminescent_cluster.memory.schemas import Memory, MemoryType

        # Set up provider
        provider = LocalMemoryProvider()
        memory = Memory(
            user_id="user-123",
            content="The auth-service uses PostgreSQL",
            memory_type=MemoryType.FACT,
            confidence=0.9,
            source="test",
        )
        memory_id = await provider.store(memory, {})

        # Create pipeline
        pipeline = EntityExtractionPipeline(
            extractor=MockEntityExtractor(),
            provider=provider,
        )

        # Call process_async and await
        task = await pipeline.process_async(
            memory_id=memory_id,
            content="The auth-service uses PostgreSQL",
            user_id="user-123",
        )

        entities = await task
        assert isinstance(entities, list)


class TestEntityExtractionPipelineEntityStorage:
    """TDD: Tests for entity storage format."""

    @pytest.mark.asyncio
    async def test_entities_stored_with_correct_format(self):
        """Entities should be stored in correct JSON format.

        GitHub Issue: #121
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import (
            EntityExtractionPipeline,
            MockEntityExtractor,
        )
        from luminescent_cluster.memory.providers.local import LocalMemoryProvider
        from luminescent_cluster.memory.schemas import Memory, MemoryType

        # Set up provider
        provider = LocalMemoryProvider()
        memory = Memory(
            user_id="user-123",
            content="The auth-service uses PostgreSQL",
            memory_type=MemoryType.FACT,
            confidence=0.9,
            source="test",
        )
        memory_id = await provider.store(memory, {})

        # Create pipeline
        pipeline = EntityExtractionPipeline(
            extractor=MockEntityExtractor(),
            provider=provider,
        )

        # Process
        await pipeline.process(
            memory_id=memory_id,
            content="The auth-service uses PostgreSQL",
            user_id="user-123",
        )

        # Check entity format
        updated_memory = await provider.get_by_id(memory_id)
        entities = updated_memory.metadata["entities"]

        for entity in entities:
            assert "name" in entity
            assert "type" in entity
            assert "confidence" in entity

    @pytest.mark.asyncio
    async def test_entities_include_memory_id(self):
        """Stored entities should include source memory ID.

        GitHub Issue: #121
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import (
            EntityExtractionPipeline,
            MockEntityExtractor,
        )
        from luminescent_cluster.memory.providers.local import LocalMemoryProvider
        from luminescent_cluster.memory.schemas import Memory, MemoryType

        # Set up provider
        provider = LocalMemoryProvider()
        memory = Memory(
            user_id="user-123",
            content="FastAPI is used for the backend",
            memory_type=MemoryType.FACT,
            confidence=0.9,
            source="test",
        )
        memory_id = await provider.store(memory, {})

        # Create pipeline
        pipeline = EntityExtractionPipeline(
            extractor=MockEntityExtractor(),
            provider=provider,
        )

        # Process
        entities = await pipeline.process(
            memory_id=memory_id,
            content="FastAPI is used for the backend",
            user_id="user-123",
        )

        # Check that entities have memory_id
        for entity in entities:
            assert entity.source_memory_id == memory_id


class TestEntityExtractionPipelineSecurity:
    """Security: Tests for authorization and isolation."""

    @pytest.mark.asyncio
    async def test_process_rejects_wrong_user_id(self):
        """Process should not update memory with wrong user_id.

        Security: Prevents cross-user memory modification.
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import (
            EntityExtractionPipeline,
            MockEntityExtractor,
        )
        from luminescent_cluster.memory.providers.local import LocalMemoryProvider
        from luminescent_cluster.memory.schemas import Memory, MemoryType

        # Set up provider with memory owned by user-123
        provider = LocalMemoryProvider()
        memory = Memory(
            user_id="user-123",
            content="FastAPI is used for the backend",
            memory_type=MemoryType.FACT,
            confidence=0.9,
            source="test",
        )
        memory_id = await provider.store(memory, {})

        # Create pipeline
        pipeline = EntityExtractionPipeline(
            extractor=MockEntityExtractor(),
            provider=provider,
        )

        # Process with WRONG user_id (attacker-456)
        entities = await pipeline.process(
            memory_id=memory_id,
            content="FastAPI is used for the backend",
            user_id="attacker-456",  # Wrong user!
        )

        # Entities are extracted (extraction doesn't require auth)
        assert len(entities) > 0

        # But memory should NOT be updated (authorization failed)
        original_memory = await provider.get_by_id(memory_id)
        assert "entities" not in original_memory.metadata

    @pytest.mark.asyncio
    async def test_process_allows_correct_user_id(self):
        """Process should update memory with correct user_id.

        Security: Verifies authorized updates work correctly.
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import (
            EntityExtractionPipeline,
            MockEntityExtractor,
        )
        from luminescent_cluster.memory.providers.local import LocalMemoryProvider
        from luminescent_cluster.memory.schemas import Memory, MemoryType

        # Set up provider with memory owned by user-123
        provider = LocalMemoryProvider()
        memory = Memory(
            user_id="user-123",
            content="FastAPI is used for the backend",
            memory_type=MemoryType.FACT,
            confidence=0.9,
            source="test",
        )
        memory_id = await provider.store(memory, {})

        # Create pipeline
        pipeline = EntityExtractionPipeline(
            extractor=MockEntityExtractor(),
            provider=provider,
        )

        # Process with CORRECT user_id
        await pipeline.process(
            memory_id=memory_id,
            content="FastAPI is used for the backend",
            user_id="user-123",  # Correct user
        )

        # Memory SHOULD be updated
        updated_memory = await provider.get_by_id(memory_id)
        assert "entities" in updated_memory.metadata


class TestEntityExtractionPipelineModuleExport:
    """TDD: Tests for module exports."""

    def test_module_exports_entity_extraction_pipeline(self):
        """Module should export EntityExtractionPipeline.

        GitHub Issue: #121
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import EntityExtractionPipeline

        assert EntityExtractionPipeline is not None
