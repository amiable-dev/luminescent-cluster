# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
TDD: Tests for Memory Type Schemas.

These tests define the expected behavior for memory type schemas
before implementation. They should FAIL until schemas are implemented.

Related GitHub Issues:
- #79: Define Memory Type Schemas (Pydantic)

ADR Reference: ADR-003 Memory Architecture, Phase 0 (Foundations)
"""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError


class TestMemoryTypeEnum:
    """TDD: Tests for MemoryType enum."""

    def test_memory_type_has_preference(self):
        """MemoryType should have PREFERENCE value.

        GitHub Issue: #79
        ADR Reference: ADR-003 Phase 0 (Memory Types)
        """
        from src.memory.schemas.memory_types import MemoryType

        assert MemoryType.PREFERENCE.value == "preference"

    def test_memory_type_has_fact(self):
        """MemoryType should have FACT value.

        GitHub Issue: #79
        ADR Reference: ADR-003 Phase 0 (Memory Types)
        """
        from src.memory.schemas.memory_types import MemoryType

        assert MemoryType.FACT.value == "fact"

    def test_memory_type_has_decision(self):
        """MemoryType should have DECISION value.

        GitHub Issue: #79
        ADR Reference: ADR-003 Phase 0 (Memory Types)
        """
        from src.memory.schemas.memory_types import MemoryType

        assert MemoryType.DECISION.value == "decision"


class TestMemorySchema:
    """TDD: Tests for Memory Pydantic model."""

    def test_memory_creates_with_required_fields(self):
        """Memory should be created with required fields.

        GitHub Issue: #79
        ADR Reference: ADR-003 Phase 0 (Memory Schema)
        """
        from src.memory.schemas.memory_types import Memory, MemoryType

        memory = Memory(
            user_id="user-123",
            content="Prefers tabs over spaces",
            memory_type=MemoryType.PREFERENCE,
            source="conversation",
        )

        assert memory.user_id == "user-123"
        assert memory.content == "Prefers tabs over spaces"
        assert memory.memory_type == MemoryType.PREFERENCE
        assert memory.source == "conversation"

    def test_memory_has_default_confidence(self):
        """Memory should have default confidence of 1.0.

        GitHub Issue: #79
        ADR Reference: ADR-003 Phase 0 (Memory Schema)
        """
        from src.memory.schemas.memory_types import Memory, MemoryType

        memory = Memory(
            user_id="user-123",
            content="A fact",
            memory_type=MemoryType.FACT,
            source="test",
        )

        assert memory.confidence == 1.0

    def test_memory_validates_confidence_range(self):
        """Memory should validate confidence is between 0.0 and 1.0.

        GitHub Issue: #79
        ADR Reference: ADR-003 Phase 0 (Memory Schema)
        """
        from src.memory.schemas.memory_types import Memory, MemoryType

        # Valid confidence
        memory = Memory(
            user_id="user-123",
            content="A fact",
            memory_type=MemoryType.FACT,
            source="test",
            confidence=0.85,
        )
        assert memory.confidence == 0.85

        # Invalid confidence (too high)
        with pytest.raises(ValidationError):
            Memory(
                user_id="user-123",
                content="A fact",
                memory_type=MemoryType.FACT,
                source="test",
                confidence=1.5,
            )

        # Invalid confidence (negative)
        with pytest.raises(ValidationError):
            Memory(
                user_id="user-123",
                content="A fact",
                memory_type=MemoryType.FACT,
                source="test",
                confidence=-0.1,
            )

    def test_memory_has_auto_timestamps(self):
        """Memory should auto-generate created_at and last_accessed_at.

        GitHub Issue: #79
        ADR Reference: ADR-003 Phase 0 (Memory Schema)
        """
        from src.memory.schemas.memory_types import Memory, MemoryType

        before = datetime.now(timezone.utc)
        memory = Memory(
            user_id="user-123",
            content="A fact",
            memory_type=MemoryType.FACT,
            source="test",
        )
        after = datetime.now(timezone.utc)

        assert memory.created_at is not None
        assert before <= memory.created_at <= after
        assert memory.last_accessed_at is not None
        assert before <= memory.last_accessed_at <= after

    def test_memory_has_optional_expires_at(self):
        """Memory should have optional expires_at field.

        GitHub Issue: #79
        ADR Reference: ADR-003 Phase 0 (Memory Schema)
        """
        from src.memory.schemas.memory_types import Memory, MemoryType

        # Without expiration
        memory1 = Memory(
            user_id="user-123",
            content="A fact",
            memory_type=MemoryType.FACT,
            source="test",
        )
        assert memory1.expires_at is None

        # With expiration
        expiry = datetime.now(timezone.utc) + timedelta(days=90)
        memory2 = Memory(
            user_id="user-123",
            content="A fact",
            memory_type=MemoryType.FACT,
            source="test",
            expires_at=expiry,
        )
        assert memory2.expires_at == expiry

    def test_memory_has_extraction_version(self):
        """Memory should have extraction_version field with default 1.

        GitHub Issue: #79
        ADR Reference: ADR-003 Phase 0 (Memory Schema)
        """
        from src.memory.schemas.memory_types import Memory, MemoryType

        memory = Memory(
            user_id="user-123",
            content="A fact",
            memory_type=MemoryType.FACT,
            source="test",
        )

        assert memory.extraction_version == 1

    def test_memory_has_raw_source(self):
        """Memory should have optional raw_source field.

        GitHub Issue: #79
        ADR Reference: ADR-003 Phase 0 (Memory Schema)
        """
        from src.memory.schemas.memory_types import Memory, MemoryType

        memory = Memory(
            user_id="user-123",
            content="Prefers PostgreSQL",
            memory_type=MemoryType.FACT,
            source="conversation",
            raw_source="I really like PostgreSQL for its reliability",
        )

        assert memory.raw_source == "I really like PostgreSQL for its reliability"

    def test_memory_serialization_roundtrip(self):
        """Memory should serialize and deserialize correctly.

        GitHub Issue: #79
        ADR Reference: ADR-003 Phase 0 (Memory Schema)
        """
        from src.memory.schemas.memory_types import Memory, MemoryType

        original = Memory(
            user_id="user-123",
            content="A decision",
            memory_type=MemoryType.DECISION,
            source="adr",
            confidence=0.95,
            raw_source="Original text",
        )

        # Serialize to dict
        data = original.model_dump()

        # Deserialize from dict
        restored = Memory.model_validate(data)

        assert restored.user_id == original.user_id
        assert restored.content == original.content
        assert restored.memory_type == original.memory_type
        assert restored.confidence == original.confidence


class TestMemoryScopeEnum:
    """TDD: Tests for MemoryScope enum."""

    def test_memory_scope_has_user(self):
        """MemoryScope should have USER value.

        GitHub Issue: #79
        ADR Reference: ADR-003 Phase 0 (Scope Hierarchy)
        """
        from src.memory.schemas.memory_types import MemoryScope

        assert MemoryScope.USER.value == "user"

    def test_memory_scope_has_project(self):
        """MemoryScope should have PROJECT value.

        GitHub Issue: #79
        ADR Reference: ADR-003 Phase 0 (Scope Hierarchy)
        """
        from src.memory.schemas.memory_types import MemoryScope

        assert MemoryScope.PROJECT.value == "project"

    def test_memory_scope_has_global(self):
        """MemoryScope should have GLOBAL value.

        GitHub Issue: #79
        ADR Reference: ADR-003 Phase 0 (Scope Hierarchy)
        """
        from src.memory.schemas.memory_types import MemoryScope

        assert MemoryScope.GLOBAL.value == "global"


class TestMemoryMetadata:
    """TDD: Tests for Memory metadata field."""

    def test_memory_has_optional_metadata(self):
        """Memory should have optional metadata field for flexible data.

        GitHub Issue: #79
        ADR Reference: ADR-003 Phase 0 (Memory Schema)
        """
        from src.memory.schemas.memory_types import Memory, MemoryType

        memory = Memory(
            user_id="user-123",
            content="A fact",
            memory_type=MemoryType.FACT,
            source="test",
            metadata={"project_id": "proj-456", "scope": "project"},
        )

        assert memory.metadata["project_id"] == "proj-456"
        assert memory.metadata["scope"] == "project"

    def test_memory_metadata_defaults_to_empty_dict(self):
        """Memory metadata should default to empty dict.

        GitHub Issue: #79
        ADR Reference: ADR-003 Phase 0 (Memory Schema)
        """
        from src.memory.schemas.memory_types import Memory, MemoryType

        memory = Memory(
            user_id="user-123",
            content="A fact",
            memory_type=MemoryType.FACT,
            source="test",
        )

        assert memory.metadata == {}
