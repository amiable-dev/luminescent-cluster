# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""TDD: RED Phase - Tests for MockEntityExtractor.

These tests define the expected behavior for the pattern-based
entity extractor used in development and testing.

Related GitHub Issues:
- #119: Implement MockEntityExtractor for testing

ADR Reference: ADR-003 Memory Architecture, Phase 3 (Entity Extraction)
"""

import pytest

from luminescent_cluster.memory.extraction.entities import Entity, EntityExtractor, EntityType


class TestMockEntityExtractorExists:
    """TDD: Tests for MockEntityExtractor existence and protocol."""

    def test_mock_entity_extractor_exists(self):
        """MockEntityExtractor class should be defined.

        GitHub Issue: #119
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import MockEntityExtractor

        assert MockEntityExtractor is not None

    def test_mock_entity_extractor_implements_protocol(self):
        """MockEntityExtractor should implement EntityExtractor protocol.

        GitHub Issue: #119
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import MockEntityExtractor

        extractor = MockEntityExtractor()
        assert isinstance(extractor, EntityExtractor)

    def test_mock_entity_extractor_has_extract_method(self):
        """MockEntityExtractor should have async extract method.

        GitHub Issue: #119
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import MockEntityExtractor

        extractor = MockEntityExtractor()
        assert hasattr(extractor, "extract")
        assert callable(extractor.extract)


class TestMockEntityExtractorServiceExtraction:
    """TDD: Tests for SERVICE entity extraction."""

    @pytest.mark.asyncio
    async def test_extracts_service_names_with_hyphen(self):
        """Should extract service names like auth-service, payment-api.

        GitHub Issue: #119
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import MockEntityExtractor

        extractor = MockEntityExtractor()
        entities = await extractor.extract("The auth-service handles authentication")

        service_entities = [e for e in entities if e.entity_type == EntityType.SERVICE]
        assert len(service_entities) >= 1
        assert any(e.name == "auth-service" for e in service_entities)

    @pytest.mark.asyncio
    async def test_extracts_multiple_services(self):
        """Should extract multiple service references.

        GitHub Issue: #119
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import MockEntityExtractor

        extractor = MockEntityExtractor()
        text = "The auth-service calls payment-api and user-service"
        entities = await extractor.extract(text)

        service_entities = [e for e in entities if e.entity_type == EntityType.SERVICE]
        service_names = [e.name for e in service_entities]
        assert "auth-service" in service_names
        assert "payment-api" in service_names

    @pytest.mark.asyncio
    async def test_extracts_service_with_api_suffix(self):
        """Should extract services ending with -api.

        GitHub Issue: #119
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import MockEntityExtractor

        extractor = MockEntityExtractor()
        entities = await extractor.extract("The payment-api processes transactions")

        service_entities = [e for e in entities if e.entity_type == EntityType.SERVICE]
        assert any(e.name == "payment-api" for e in service_entities)


class TestMockEntityExtractorDependencyExtraction:
    """TDD: Tests for DEPENDENCY entity extraction."""

    @pytest.mark.asyncio
    async def test_extracts_database_dependencies(self):
        """Should extract database dependencies like PostgreSQL, Redis.

        GitHub Issue: #119
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import MockEntityExtractor

        extractor = MockEntityExtractor()
        entities = await extractor.extract("We use PostgreSQL for the database")

        dep_entities = [e for e in entities if e.entity_type == EntityType.DEPENDENCY]
        assert any(e.name == "PostgreSQL" for e in dep_entities)

    @pytest.mark.asyncio
    async def test_extracts_redis_dependency(self):
        """Should extract Redis as a dependency.

        GitHub Issue: #119
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import MockEntityExtractor

        extractor = MockEntityExtractor()
        entities = await extractor.extract("Redis is used for caching")

        dep_entities = [e for e in entities if e.entity_type == EntityType.DEPENDENCY]
        assert any(e.name == "Redis" for e in dep_entities)

    @pytest.mark.asyncio
    async def test_extracts_message_queue_dependencies(self):
        """Should extract message queue dependencies like RabbitMQ, Kafka.

        GitHub Issue: #119
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import MockEntityExtractor

        extractor = MockEntityExtractor()
        entities = await extractor.extract("We use Kafka for event streaming")

        dep_entities = [e for e in entities if e.entity_type == EntityType.DEPENDENCY]
        assert any(e.name == "Kafka" for e in dep_entities)


class TestMockEntityExtractorAPIExtraction:
    """TDD: Tests for API entity extraction."""

    @pytest.mark.asyncio
    async def test_extracts_api_endpoints(self):
        """Should extract API endpoints like /api/v1/users.

        GitHub Issue: #119
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import MockEntityExtractor

        extractor = MockEntityExtractor()
        entities = await extractor.extract("The /api/v1/users endpoint handles user data")

        api_entities = [e for e in entities if e.entity_type == EntityType.API]
        assert any("/api/v1/users" in e.name for e in api_entities)

    @pytest.mark.asyncio
    async def test_extracts_rest_endpoints(self):
        """Should extract REST API endpoints.

        GitHub Issue: #119
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import MockEntityExtractor

        extractor = MockEntityExtractor()
        entities = await extractor.extract("POST /users creates a new user")

        api_entities = [e for e in entities if e.entity_type == EntityType.API]
        assert any("/users" in e.name for e in api_entities)


class TestMockEntityExtractorPatternExtraction:
    """TDD: Tests for PATTERN entity extraction."""

    @pytest.mark.asyncio
    async def test_extracts_repository_pattern(self):
        """Should extract Repository Pattern.

        GitHub Issue: #119
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import MockEntityExtractor

        extractor = MockEntityExtractor()
        entities = await extractor.extract("We use the Repository Pattern for data access")

        pattern_entities = [e for e in entities if e.entity_type == EntityType.PATTERN]
        assert any("Repository" in e.name for e in pattern_entities)

    @pytest.mark.asyncio
    async def test_extracts_factory_pattern(self):
        """Should extract Factory Pattern.

        GitHub Issue: #119
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import MockEntityExtractor

        extractor = MockEntityExtractor()
        entities = await extractor.extract("The Factory Pattern creates instances")

        pattern_entities = [e for e in entities if e.entity_type == EntityType.PATTERN]
        assert any("Factory" in e.name for e in pattern_entities)


class TestMockEntityExtractorFrameworkExtraction:
    """TDD: Tests for FRAMEWORK entity extraction."""

    @pytest.mark.asyncio
    async def test_extracts_fastapi_framework(self):
        """Should extract FastAPI framework.

        GitHub Issue: #119
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import MockEntityExtractor

        extractor = MockEntityExtractor()
        entities = await extractor.extract("Built with FastAPI for the backend")

        framework_entities = [e for e in entities if e.entity_type == EntityType.FRAMEWORK]
        assert any(e.name == "FastAPI" for e in framework_entities)

    @pytest.mark.asyncio
    async def test_extracts_django_framework(self):
        """Should extract Django framework.

        GitHub Issue: #119
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import MockEntityExtractor

        extractor = MockEntityExtractor()
        entities = await extractor.extract("The Django project handles the admin")

        framework_entities = [e for e in entities if e.entity_type == EntityType.FRAMEWORK]
        assert any(e.name == "Django" for e in framework_entities)

    @pytest.mark.asyncio
    async def test_extracts_react_framework(self):
        """Should extract React framework.

        GitHub Issue: #119
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import MockEntityExtractor

        extractor = MockEntityExtractor()
        entities = await extractor.extract("The frontend uses React")

        framework_entities = [e for e in entities if e.entity_type == EntityType.FRAMEWORK]
        assert any(e.name == "React" for e in framework_entities)


class TestMockEntityExtractorConfigExtraction:
    """TDD: Tests for CONFIG entity extraction."""

    @pytest.mark.asyncio
    async def test_extracts_env_variables(self):
        """Should extract environment variables like REDIS_URL.

        GitHub Issue: #119
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import MockEntityExtractor

        extractor = MockEntityExtractor()
        entities = await extractor.extract("Set REDIS_URL to configure Redis")

        config_entities = [e for e in entities if e.entity_type == EntityType.CONFIG]
        assert any(e.name == "REDIS_URL" for e in config_entities)

    @pytest.mark.asyncio
    async def test_extracts_database_host_config(self):
        """Should extract DATABASE_HOST configuration.

        GitHub Issue: #119
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import MockEntityExtractor

        extractor = MockEntityExtractor()
        entities = await extractor.extract("DATABASE_HOST should be set in .env")

        config_entities = [e for e in entities if e.entity_type == EntityType.CONFIG]
        assert any(e.name == "DATABASE_HOST" for e in config_entities)


class TestMockEntityExtractorEntityProperties:
    """TDD: Tests for extracted Entity properties."""

    @pytest.mark.asyncio
    async def test_entity_has_confidence_score(self):
        """Extracted entities should have confidence scores.

        GitHub Issue: #119
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import MockEntityExtractor

        extractor = MockEntityExtractor()
        entities = await extractor.extract("The auth-service uses PostgreSQL")

        for entity in entities:
            assert 0.0 <= entity.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_entity_stores_memory_id(self):
        """Entity should store source memory ID if provided.

        GitHub Issue: #119
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import MockEntityExtractor

        extractor = MockEntityExtractor()
        entities = await extractor.extract(
            "The auth-service uses PostgreSQL",
            memory_id="mem-123",
        )

        for entity in entities:
            assert entity.source_memory_id == "mem-123"

    @pytest.mark.asyncio
    async def test_returns_empty_list_for_no_entities(self):
        """Should return empty list when no entities found.

        GitHub Issue: #119
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import MockEntityExtractor

        extractor = MockEntityExtractor()
        entities = await extractor.extract("Hello world")

        assert entities == []


class TestMockEntityExtractorModuleExport:
    """TDD: Tests for module exports."""

    def test_module_exports_mock_entity_extractor(self):
        """Module should export MockEntityExtractor.

        GitHub Issue: #119
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from luminescent_cluster.memory.extraction.entities import MockEntityExtractor

        assert MockEntityExtractor is not None
