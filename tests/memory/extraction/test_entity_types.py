# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
TDD: RED Phase - Tests for Entity Extraction Types.

These tests define the expected behavior for entity extraction
types, dataclasses, and protocols.

Related GitHub Issues:
- #118: Define EntityType enum and Entity schema

ADR Reference: ADR-003 Memory Architecture, Phase 3 (Entity Extraction)
"""

import pytest
from dataclasses import fields
from typing import get_type_hints


class TestEntityTypeEnum:
    """TDD: Tests for EntityType enum."""

    def test_entity_type_enum_exists(self):
        """EntityType enum should be defined.

        GitHub Issue: #118
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from src.memory.extraction.entities import EntityType

        assert EntityType is not None

    def test_entity_type_has_service(self):
        """EntityType should have SERVICE value.

        GitHub Issue: #118
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from src.memory.extraction.entities import EntityType

        assert EntityType.SERVICE == "service"

    def test_entity_type_has_dependency(self):
        """EntityType should have DEPENDENCY value.

        GitHub Issue: #118
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from src.memory.extraction.entities import EntityType

        assert EntityType.DEPENDENCY == "dependency"

    def test_entity_type_has_api(self):
        """EntityType should have API value.

        GitHub Issue: #118
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from src.memory.extraction.entities import EntityType

        assert EntityType.API == "api"

    def test_entity_type_has_pattern(self):
        """EntityType should have PATTERN value.

        GitHub Issue: #118
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from src.memory.extraction.entities import EntityType

        assert EntityType.PATTERN == "pattern"

    def test_entity_type_has_framework(self):
        """EntityType should have FRAMEWORK value.

        GitHub Issue: #118
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from src.memory.extraction.entities import EntityType

        assert EntityType.FRAMEWORK == "framework"

    def test_entity_type_has_config(self):
        """EntityType should have CONFIG value.

        GitHub Issue: #118
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from src.memory.extraction.entities import EntityType

        assert EntityType.CONFIG == "config"

    def test_entity_type_is_string_enum(self):
        """EntityType should be a string enum for JSON serialization.

        GitHub Issue: #118
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from src.memory.extraction.entities import EntityType

        assert isinstance(EntityType.SERVICE, str)
        assert EntityType.SERVICE.value == "service"


class TestEntityDataclass:
    """TDD: Tests for Entity dataclass."""

    def test_entity_class_exists(self):
        """Entity class should be defined.

        GitHub Issue: #118
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from src.memory.extraction.entities import Entity

        assert Entity is not None

    def test_entity_has_name_field(self):
        """Entity should have name field (str).

        GitHub Issue: #118
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from src.memory.extraction.entities import Entity, EntityType

        entity = Entity(
            name="auth-service",
            entity_type=EntityType.SERVICE,
            confidence=0.95,
        )
        assert entity.name == "auth-service"

    def test_entity_has_entity_type_field(self):
        """Entity should have entity_type field (EntityType).

        GitHub Issue: #118
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from src.memory.extraction.entities import Entity, EntityType

        entity = Entity(
            name="PostgreSQL",
            entity_type=EntityType.DEPENDENCY,
            confidence=0.9,
        )
        assert entity.entity_type == EntityType.DEPENDENCY

    def test_entity_has_confidence_field(self):
        """Entity should have confidence field (float, 0.0-1.0).

        GitHub Issue: #118
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from src.memory.extraction.entities import Entity, EntityType

        entity = Entity(
            name="FastAPI",
            entity_type=EntityType.FRAMEWORK,
            confidence=0.85,
        )
        assert entity.confidence == 0.85
        assert 0.0 <= entity.confidence <= 1.0

    def test_entity_has_source_memory_id_field(self):
        """Entity should have source_memory_id field (optional str).

        GitHub Issue: #118
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from src.memory.extraction.entities import Entity, EntityType

        # Without source_memory_id
        entity1 = Entity(
            name="Redis",
            entity_type=EntityType.DEPENDENCY,
            confidence=0.9,
        )
        assert entity1.source_memory_id is None

        # With source_memory_id
        entity2 = Entity(
            name="Redis",
            entity_type=EntityType.DEPENDENCY,
            confidence=0.9,
            source_memory_id="mem-123",
        )
        assert entity2.source_memory_id == "mem-123"

    def test_entity_has_mentions_field(self):
        """Entity should have mentions field (list of raw text mentions).

        GitHub Issue: #118
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from src.memory.extraction.entities import Entity, EntityType

        entity = Entity(
            name="auth-service",
            entity_type=EntityType.SERVICE,
            confidence=0.95,
            mentions=["auth-service", "authentication service"],
        )
        assert entity.mentions == ["auth-service", "authentication service"]

    def test_entity_mentions_defaults_to_empty_list(self):
        """Entity mentions should default to empty list.

        GitHub Issue: #118
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from src.memory.extraction.entities import Entity, EntityType

        entity = Entity(
            name="FastAPI",
            entity_type=EntityType.FRAMEWORK,
            confidence=0.9,
        )
        assert entity.mentions == []

    def test_entity_has_metadata_field(self):
        """Entity should have metadata field (dict).

        GitHub Issue: #118
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from src.memory.extraction.entities import Entity, EntityType

        entity = Entity(
            name="PostgreSQL",
            entity_type=EntityType.DEPENDENCY,
            confidence=0.9,
            metadata={"version": "15.0", "host": "localhost"},
        )
        assert entity.metadata == {"version": "15.0", "host": "localhost"}

    def test_entity_metadata_defaults_to_empty_dict(self):
        """Entity metadata should default to empty dict.

        GitHub Issue: #118
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from src.memory.extraction.entities import Entity, EntityType

        entity = Entity(
            name="Redis",
            entity_type=EntityType.DEPENDENCY,
            confidence=0.85,
        )
        assert entity.metadata == {}

    def test_entity_is_dataclass(self):
        """Entity should be a dataclass.

        GitHub Issue: #118
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from dataclasses import is_dataclass
        from src.memory.extraction.entities import Entity

        assert is_dataclass(Entity)


class TestEntityExtractorProtocol:
    """TDD: Tests for EntityExtractor protocol."""

    def test_entity_extractor_protocol_exists(self):
        """EntityExtractor protocol should be defined.

        GitHub Issue: #118
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from src.memory.extraction.entities import EntityExtractor

        assert EntityExtractor is not None

    def test_entity_extractor_is_protocol(self):
        """EntityExtractor should be a Protocol.

        GitHub Issue: #118
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from typing import Protocol
        from src.memory.extraction.entities import EntityExtractor

        assert issubclass(EntityExtractor, Protocol)

    def test_entity_extractor_has_extract_method(self):
        """EntityExtractor should define extract method.

        GitHub Issue: #118
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from src.memory.extraction.entities import EntityExtractor

        # Check that extract is defined (will have __func__ for protocol methods)
        assert hasattr(EntityExtractor, "extract")

    def test_entity_extractor_is_runtime_checkable(self):
        """EntityExtractor should be runtime_checkable.

        GitHub Issue: #118
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from typing import runtime_checkable
        from src.memory.extraction.entities import EntityExtractor

        # runtime_checkable protocols have __protocol_attrs__
        assert hasattr(EntityExtractor, "__protocol_attrs__") or hasattr(
            EntityExtractor, "_is_runtime_protocol"
        )


class TestModuleExports:
    """TDD: Tests for module exports."""

    def test_module_exists(self):
        """src.memory.extraction.entities module should exist.

        GitHub Issue: #118
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        import src.memory.extraction.entities

        assert src.memory.extraction.entities is not None

    def test_module_exports_entity_type(self):
        """Module should export EntityType.

        GitHub Issue: #118
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from src.memory.extraction.entities import EntityType

        assert EntityType is not None

    def test_module_exports_entity(self):
        """Module should export Entity.

        GitHub Issue: #118
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from src.memory.extraction.entities import Entity

        assert Entity is not None

    def test_module_exports_entity_extractor(self):
        """Module should export EntityExtractor.

        GitHub Issue: #118
        ADR Reference: ADR-003 Phase 3 (Entity Extraction)
        """
        from src.memory.extraction.entities import EntityExtractor

        assert EntityExtractor is not None
