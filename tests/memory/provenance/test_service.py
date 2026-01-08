# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
TDD: Tests for Provenance Service.

These tests define the expected behavior for provenance tracking,
meeting the ADR-003 Phase 2 exit criterion:
"Provenance available for all retrieved items"

Related GitHub Issues:
- #116: Phase 2: Memory Blocks Architecture

ADR Reference: ADR-003 Memory Architecture, Phase 2 (Context Engineering)
"""

from datetime import datetime, timezone
from typing import Optional

import pytest


class TestProvenanceServiceExists:
    """TDD: Tests for ProvenanceService class existence."""

    def test_provenance_service_exists(self):
        """ProvenanceService class should be defined."""
        from src.memory.provenance.service import ProvenanceService

        assert ProvenanceService is not None

    def test_provenance_service_instantiable(self):
        """ProvenanceService should be instantiable."""
        from src.memory.provenance.service import ProvenanceService

        service = ProvenanceService()
        assert service is not None


class TestCreateProvenance:
    """TDD: Tests for provenance creation."""

    @pytest.mark.asyncio
    async def test_create_provenance_returns_provenance(self):
        """create_provenance should return a Provenance object."""
        from src.memory.blocks.schemas import Provenance
        from src.memory.provenance.service import ProvenanceService

        service = ProvenanceService()
        result = await service.create_provenance(
            source_id="mem-123",
            source_type="memory",
            confidence=0.95,
        )

        assert isinstance(result, Provenance)
        assert result.source_id == "mem-123"
        assert result.source_type == "memory"
        assert result.confidence == 0.95

    @pytest.mark.asyncio
    async def test_create_provenance_sets_created_at(self):
        """create_provenance should set created_at timestamp."""
        from src.memory.provenance.service import ProvenanceService

        service = ProvenanceService()
        before = datetime.now(timezone.utc)
        result = await service.create_provenance(
            source_id="mem-123",
            source_type="memory",
            confidence=0.95,
        )
        after = datetime.now(timezone.utc)

        assert result.created_at >= before
        assert result.created_at <= after

    @pytest.mark.asyncio
    async def test_create_provenance_with_metadata(self):
        """create_provenance should store optional metadata."""
        from src.memory.provenance.service import ProvenanceService

        service = ProvenanceService()
        result = await service.create_provenance(
            source_id="mem-123",
            source_type="adr",
            confidence=0.99,
            metadata={"adr_id": "003", "version": "4.4"},
        )

        assert result.source_type == "adr"
        assert result.metadata is not None
        assert result.metadata["adr_id"] == "003"
        assert result.metadata["version"] == "4.4"

    @pytest.mark.asyncio
    async def test_create_provenance_rejects_oversized_metadata(self):
        """create_provenance should reject metadata exceeding size limit.

        Council Round 12/13: Prevents DoS via oversized metadata payloads.
        Now validates bounds BEFORE serialization to prevent json.dumps DoS.
        """
        from src.memory.provenance.service import ProvenanceService

        service = ProvenanceService()
        # Create metadata that exceeds the limit
        oversized_metadata = {"data": "x" * 20000}

        # Council Round 13: Now catches value length before json.dumps
        with pytest.raises(ValueError, match=".* exceeds limit"):
            await service.create_provenance(
                source_id="mem-123",
                source_type="memory",
                confidence=0.95,
                metadata=oversized_metadata,
            )


class TestAttachProvenance:
    """TDD: Tests for attaching provenance to memories."""

    @pytest.fixture
    def service(self):
        """Create a fresh ProvenanceService for each test."""
        from src.memory.provenance.service import ProvenanceService

        return ProvenanceService()

    @pytest.mark.asyncio
    async def test_attach_to_memory(self, service):
        """attach_to_memory should store provenance for memory ID."""
        from src.memory.blocks.schemas import Provenance

        prov = await service.create_provenance(
            source_id="mem-123",
            source_type="memory",
            confidence=0.95,
        )

        await service.attach_to_memory("mem-456", prov)

        # Should be retrievable
        retrieved = await service.get_provenance("mem-456")
        assert retrieved is not None
        assert retrieved.source_id == "mem-123"

    @pytest.mark.asyncio
    async def test_attach_overwrites_existing(self, service):
        """attach_to_memory should overwrite existing provenance."""
        prov1 = await service.create_provenance(
            source_id="old-source",
            source_type="memory",
            confidence=0.5,
        )
        prov2 = await service.create_provenance(
            source_id="new-source",
            source_type="adr",
            confidence=0.99,
        )

        await service.attach_to_memory("mem-123", prov1)
        await service.attach_to_memory("mem-123", prov2)

        retrieved = await service.get_provenance("mem-123")
        assert retrieved.source_id == "new-source"


class TestGetProvenance:
    """TDD: Tests for retrieving provenance."""

    @pytest.fixture
    def service(self):
        """Create a fresh ProvenanceService for each test."""
        from src.memory.provenance.service import ProvenanceService

        return ProvenanceService()

    @pytest.mark.asyncio
    async def test_get_provenance_returns_none_if_not_found(self, service):
        """get_provenance should return None for unknown memory IDs."""
        result = await service.get_provenance("unknown-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_provenance_returns_attached(self, service):
        """get_provenance should return attached provenance."""
        prov = await service.create_provenance(
            source_id="mem-123",
            source_type="memory",
            confidence=0.95,
        )
        await service.attach_to_memory("target-mem", prov)

        result = await service.get_provenance("target-mem")

        assert result is not None
        assert result.source_id == "mem-123"
        assert result.confidence == 0.95


class TestTrackRetrieval:
    """TDD: Tests for tracking retrieval events."""

    @pytest.fixture
    def service(self):
        """Create a fresh ProvenanceService for each test."""
        from src.memory.provenance.service import ProvenanceService

        return ProvenanceService()

    @pytest.mark.asyncio
    async def test_track_retrieval_updates_score(self, service):
        """track_retrieval should update retrieval_score in provenance."""
        prov = await service.create_provenance(
            source_id="mem-123",
            source_type="memory",
            confidence=0.95,
        )
        await service.attach_to_memory("target-mem", prov)

        await service.track_retrieval(
            memory_id="target-mem",
            retrieval_score=0.87,
            retrieved_by="user-456",
        )

        result = await service.get_provenance("target-mem")
        assert result.retrieval_score == 0.87

    @pytest.mark.asyncio
    async def test_track_retrieval_without_existing_provenance(self, service):
        """track_retrieval should silently no-op for unknown memory IDs.

        Council Round 11: Prevents orphan entries in _retrieval_history
        that would cause unbounded memory growth.
        """
        # Should not raise, just no-op
        await service.track_retrieval(
            memory_id="unknown-mem",
            retrieval_score=0.87,
            retrieved_by="user-456",
        )

        # Provenance should still not exist
        result = await service.get_provenance("unknown-mem")
        assert result is None

        # Retrieval history should NOT have an orphan entry
        history = await service.get_retrieval_history("unknown-mem")
        assert history == [], "Should not create orphan retrieval history entries"


class TestProvenanceHistory:
    """TDD: Tests for provenance history tracking."""

    @pytest.fixture
    def service(self):
        """Create a fresh ProvenanceService for each test."""
        from src.memory.provenance.service import ProvenanceService

        return ProvenanceService()

    @pytest.mark.asyncio
    async def test_get_retrieval_history(self, service):
        """get_retrieval_history should return list of retrieval events."""
        prov = await service.create_provenance(
            source_id="mem-123",
            source_type="memory",
            confidence=0.95,
        )
        await service.attach_to_memory("target-mem", prov)

        await service.track_retrieval("target-mem", 0.87, "user-1")
        await service.track_retrieval("target-mem", 0.92, "user-2")

        history = await service.get_retrieval_history("target-mem")

        assert len(history) == 2
        assert history[0]["retrieved_by"] == "user-1"
        assert history[1]["retrieved_by"] == "user-2"

    @pytest.mark.asyncio
    async def test_get_retrieval_history_empty_for_unknown(self, service):
        """get_retrieval_history should return empty list for unknown memory."""
        history = await service.get_retrieval_history("unknown-mem")
        assert history == []


class TestMemoryBoundedStorage:
    """TDD: Tests for bounded storage to prevent memory leaks.

    Council Round 9: Identified unbounded memory growth in retrieval history.
    """

    @pytest.fixture
    def service(self):
        """Create a fresh ProvenanceService for each test."""
        from src.memory.provenance.service import ProvenanceService

        return ProvenanceService()

    @pytest.mark.asyncio
    async def test_retrieval_history_is_bounded(self, service):
        """Retrieval history should have a maximum size to prevent memory leaks."""
        prov = await service.create_provenance(
            source_id="mem-123",
            source_type="memory",
            confidence=0.95,
        )
        await service.attach_to_memory("target-mem", prov)

        # Track many retrieval events
        for i in range(200):
            await service.track_retrieval("target-mem", 0.5 + (i / 1000), f"user-{i}")

        history = await service.get_retrieval_history("target-mem")

        # Should be bounded (default 100)
        assert len(history) <= 100, "Retrieval history should be bounded to prevent memory leaks"

    @pytest.mark.asyncio
    async def test_retrieval_history_keeps_recent(self, service):
        """Bounded retrieval history should keep most recent events."""
        prov = await service.create_provenance(
            source_id="mem-123",
            source_type="memory",
            confidence=0.95,
        )
        await service.attach_to_memory("target-mem", prov)

        # Track many retrieval events
        for i in range(150):
            await service.track_retrieval("target-mem", 0.5, f"user-{i}")

        history = await service.get_retrieval_history("target-mem")

        # Should keep the most recent events (user-50 to user-149)
        if len(history) == 100:
            # Latest should be most recent
            assert history[-1]["retrieved_by"] == "user-149"

    @pytest.mark.asyncio
    async def test_provenance_store_is_bounded(self, service):
        """Provenance store should enforce MAX_PROVENANCE_ENTRIES limit with LRU eviction."""
        from src.memory.provenance.service import ProvenanceService

        # Create service with smaller limit for testing
        service.MAX_PROVENANCE_ENTRIES = 100

        # Attach more entries than the limit
        for i in range(150):
            prov = await service.create_provenance(
                source_id=f"src-{i}",
                source_type="memory",
                confidence=0.95,
            )
            await service.attach_to_memory(f"mem-{i}", prov)

        # Should be bounded to MAX_PROVENANCE_ENTRIES
        assert len(service._provenance_store) == 100, "Provenance store should enforce bound"

        # Oldest entries (mem-0 through mem-49) should be evicted
        oldest_evicted = await service.get_provenance("mem-0")
        assert oldest_evicted is None, "Oldest entries should be evicted"

        # Newest entries should still be present
        newest = await service.get_provenance("mem-149")
        assert newest is not None, "Newest entries should be present"

    @pytest.mark.asyncio
    async def test_provenance_store_lru_updates_on_access(self, service):
        """Accessing provenance should update LRU order to prevent eviction."""
        from src.memory.provenance.service import ProvenanceService

        # Create service with smaller limit for testing
        service.MAX_PROVENANCE_ENTRIES = 5

        # Attach 5 entries
        for i in range(5):
            prov = await service.create_provenance(
                source_id=f"src-{i}",
                source_type="memory",
                confidence=0.95,
            )
            await service.attach_to_memory(f"mem-{i}", prov)

        # Access mem-0 to make it recently used
        await service.get_provenance("mem-0")

        # Add 3 more entries (should evict mem-1, mem-2, mem-3)
        for i in range(5, 8):
            prov = await service.create_provenance(
                source_id=f"src-{i}",
                source_type="memory",
                confidence=0.95,
            )
            await service.attach_to_memory(f"mem-{i}", prov)

        # mem-0 should still be present (was accessed)
        mem_0 = await service.get_provenance("mem-0")
        assert mem_0 is not None, "Recently accessed entry should not be evicted"

        # mem-1 should be evicted (oldest non-accessed)
        mem_1 = await service.get_provenance("mem-1")
        assert mem_1 is None, "Oldest non-accessed entry should be evicted"


class TestStringIdValidation:
    """TDD: Tests for string identifier length validation.

    Council Round 13: Identified missing length validations for string
    identifiers which pose a memory exhaustion risk.
    """

    @pytest.fixture
    def service(self):
        """Create a fresh ProvenanceService for each test."""
        from src.memory.provenance.service import ProvenanceService

        return ProvenanceService()

    @pytest.mark.asyncio
    async def test_create_provenance_rejects_oversized_source_id(self, service):
        """create_provenance should reject source_id exceeding limit."""
        oversized_id = "x" * 500  # Exceeds MAX_STRING_ID_LENGTH (256)

        with pytest.raises(ValueError, match="source_id length .* exceeds limit"):
            await service.create_provenance(
                source_id=oversized_id,
                source_type="memory",
                confidence=0.95,
            )

    @pytest.mark.asyncio
    async def test_create_provenance_rejects_oversized_source_type(self, service):
        """create_provenance should reject source_type exceeding limit."""
        oversized_type = "y" * 500

        with pytest.raises(ValueError, match="source_type length .* exceeds limit"):
            await service.create_provenance(
                source_id="mem-123",
                source_type=oversized_type,
                confidence=0.95,
            )

    @pytest.mark.asyncio
    async def test_attach_to_memory_rejects_oversized_memory_id(self, service):
        """attach_to_memory should reject memory_id exceeding limit."""
        prov = await service.create_provenance(
            source_id="src-123",
            source_type="memory",
            confidence=0.95,
        )
        oversized_id = "z" * 500

        with pytest.raises(ValueError, match="memory_id length .* exceeds limit"):
            await service.attach_to_memory(oversized_id, prov)

    @pytest.mark.asyncio
    async def test_track_retrieval_rejects_oversized_memory_id(self, service):
        """track_retrieval should reject memory_id exceeding limit."""
        oversized_id = "a" * 500

        with pytest.raises(ValueError, match="memory_id length .* exceeds limit"):
            await service.track_retrieval(
                memory_id=oversized_id,
                retrieval_score=0.9,
                retrieved_by="user-1",
            )

    @pytest.mark.asyncio
    async def test_track_retrieval_rejects_oversized_retrieved_by(self, service):
        """track_retrieval should reject retrieved_by exceeding limit."""
        oversized_user = "b" * 500

        with pytest.raises(ValueError, match="retrieved_by length .* exceeds limit"):
            await service.track_retrieval(
                memory_id="mem-123",
                retrieval_score=0.9,
                retrieved_by=oversized_user,
            )

    @pytest.mark.asyncio
    async def test_get_provenance_rejects_oversized_memory_id(self, service):
        """get_provenance should reject memory_id exceeding limit."""
        oversized_id = "c" * 500

        with pytest.raises(ValueError, match="memory_id length .* exceeds limit"):
            await service.get_provenance(oversized_id)

    @pytest.mark.asyncio
    async def test_get_retrieval_history_rejects_oversized_memory_id(self, service):
        """get_retrieval_history should reject memory_id exceeding limit."""
        oversized_id = "d" * 500

        with pytest.raises(ValueError, match="memory_id length .* exceeds limit"):
            await service.get_retrieval_history(oversized_id)


class TestMetadataBoundsValidation:
    """TDD: Tests for metadata bounds validation before serialization.

    Council Round 13: Identified that json.dumps DoS vector allows massive
    objects to be serialized into memory before rejection.
    """

    @pytest.fixture
    def service(self):
        """Create a fresh ProvenanceService for each test."""
        from src.memory.provenance.service import ProvenanceService

        return ProvenanceService()

    @pytest.mark.asyncio
    async def test_metadata_key_count_validation(self, service):
        """Metadata with too many keys should be rejected before serialization."""
        # Create metadata with more than MAX_METADATA_KEYS (100)
        oversized_metadata = {f"key_{i}": f"value_{i}" for i in range(150)}

        with pytest.raises(ValueError, match="Metadata key count .* exceeds limit"):
            await service.create_provenance(
                source_id="mem-123",
                source_type="memory",
                confidence=0.95,
                metadata=oversized_metadata,
            )

    @pytest.mark.asyncio
    async def test_metadata_key_length_validation(self, service):
        """Metadata keys exceeding length limit should be rejected."""
        oversized_key = "k" * 500
        metadata = {oversized_key: "value"}

        with pytest.raises(ValueError, match="Metadata key length .* exceeds limit"):
            await service.create_provenance(
                source_id="mem-123",
                source_type="memory",
                confidence=0.95,
                metadata=metadata,
            )

    @pytest.mark.asyncio
    async def test_metadata_type_validation(self, service):
        """Metadata must be a dictionary."""
        # This shouldn't happen with type hints, but validate anyway
        with pytest.raises(ValueError, match="Metadata must be a dictionary"):
            await service.create_provenance(
                source_id="mem-123",
                source_type="memory",
                confidence=0.95,
                metadata="not a dict",  # type: ignore
            )

    @pytest.mark.asyncio
    async def test_valid_metadata_within_bounds(self, service):
        """Valid metadata within bounds should be accepted."""
        # Create metadata within all limits
        valid_metadata = {f"key_{i}": f"value_{i}" for i in range(50)}

        result = await service.create_provenance(
            source_id="mem-123",
            source_type="memory",
            confidence=0.95,
            metadata=valid_metadata,
        )

        assert result is not None
        assert result.metadata is not None
        assert len(result.metadata) == 50


class TestNestedMetadataValidation:
    """TDD: Tests for nested metadata structure validation.

    Council Round 14: Identified that shallow validation allows nested
    structures (lists, dicts) to bypass bounds checks, enabling DoS via
    deeply nested or wide structures.
    """

    @pytest.fixture
    def service(self):
        """Create a fresh ProvenanceService for each test."""
        from src.memory.provenance.service import ProvenanceService

        return ProvenanceService()

    @pytest.mark.asyncio
    async def test_deeply_nested_dict_rejected(self, service):
        """Deeply nested dicts should be rejected to prevent DoS."""
        # Create deeply nested structure exceeding MAX_METADATA_DEPTH (5)
        nested = {"level": "bottom"}
        for i in range(10):  # Creates 10 levels of nesting
            nested = {"level": nested}

        with pytest.raises(ValueError, match="Metadata nesting depth .* exceeds limit"):
            await service.create_provenance(
                source_id="mem-123",
                source_type="memory",
                confidence=0.95,
                metadata=nested,
            )

    @pytest.mark.asyncio
    async def test_deeply_nested_list_rejected(self, service):
        """Deeply nested lists should be rejected to prevent DoS."""
        # Create deeply nested list structure
        nested = ["bottom"]
        for i in range(10):
            nested = [nested]

        metadata = {"data": nested}

        with pytest.raises(ValueError, match="Metadata nesting depth .* exceeds limit"):
            await service.create_provenance(
                source_id="mem-123",
                source_type="memory",
                confidence=0.95,
                metadata=metadata,
            )

    @pytest.mark.asyncio
    async def test_wide_nested_structure_rejected(self, service):
        """Wide nested structures exceeding element limit should be rejected."""
        # Create a structure with many elements (exceeding MAX_METADATA_ELEMENTS = 500)
        # Use nested lists to bypass simple key count check
        wide_list = list(range(600))  # 600 elements
        metadata = {"data": wide_list}

        with pytest.raises(ValueError, match="Metadata total element count .* exceeds limit"):
            await service.create_provenance(
                source_id="mem-123",
                source_type="memory",
                confidence=0.95,
                metadata=metadata,
            )

    @pytest.mark.asyncio
    async def test_bytes_in_metadata_rejected(self, service):
        """Bytes values in metadata should be rejected (not JSON serializable)."""
        metadata = {"data": b"binary data"}

        with pytest.raises(ValueError, match="Metadata cannot contain bytes"):
            await service.create_provenance(
                source_id="mem-123",
                source_type="memory",
                confidence=0.95,
                metadata=metadata,
            )

    @pytest.mark.asyncio
    async def test_nested_bytes_rejected(self, service):
        """Bytes nested in structures should also be rejected."""
        metadata = {"outer": {"inner": [b"nested bytes"]}}

        with pytest.raises(ValueError, match="Metadata cannot contain bytes"):
            await service.create_provenance(
                source_id="mem-123",
                source_type="memory",
                confidence=0.95,
                metadata=metadata,
            )

    @pytest.mark.asyncio
    async def test_oversized_string_in_nested_structure_rejected(self, service):
        """Oversized strings in nested structures should be rejected."""
        # MAX_METADATA_SIZE_BYTES is 10000
        oversized_string = "x" * 20000
        metadata = {"outer": {"inner": oversized_string}}

        with pytest.raises(ValueError, match="Metadata string value length .* exceeds limit"):
            await service.create_provenance(
                source_id="mem-123",
                source_type="memory",
                confidence=0.95,
                metadata=metadata,
            )

    @pytest.mark.asyncio
    async def test_valid_nested_structure_accepted(self, service):
        """Valid nested structures within bounds should be accepted."""
        # Create a valid nested structure within all limits
        metadata = {
            "level1": {
                "level2": {
                    "level3": {
                        "values": [1, 2, 3, "test"]
                    }
                }
            },
            "simple": "value",
            "list": [{"nested": "dict"}, "string", 42]
        }

        result = await service.create_provenance(
            source_id="mem-123",
            source_type="memory",
            confidence=0.95,
            metadata=metadata,
        )

        assert result is not None
        assert result.metadata is not None
        assert result.metadata["level1"]["level2"]["level3"]["values"] == [1, 2, 3, "test"]

    @pytest.mark.asyncio
    async def test_tuple_handled_like_list(self, service):
        """Tuples should be validated like lists."""
        # Deeply nested tuples
        nested = ("bottom",)
        for i in range(10):
            nested = (nested,)

        metadata = {"data": nested}

        with pytest.raises(ValueError, match="Metadata nesting depth .* exceeds limit"):
            await service.create_provenance(
                source_id="mem-123",
                source_type="memory",
                confidence=0.95,
                metadata=metadata,
            )

    @pytest.mark.asyncio
    async def test_nested_key_length_validation(self, service):
        """Keys in nested dicts should also be length-validated."""
        oversized_key = "k" * 500
        metadata = {"outer": {oversized_key: "value"}}

        with pytest.raises(ValueError, match="Metadata key length .* exceeds limit"):
            await service.create_provenance(
                source_id="mem-123",
                source_type="memory",
                confidence=0.95,
                metadata=metadata,
            )


class TestProvenanceBypassPrevention:
    """TDD: Tests for preventing validation bypass via direct object construction.

    Council Round 15: Identified that attach_to_memory accepts Provenance objects
    without validation, allowing bypass of DoS protections.
    """

    @pytest.fixture
    def service(self):
        """Create a fresh ProvenanceService for each test."""
        from src.memory.provenance.service import ProvenanceService

        return ProvenanceService()

    @pytest.mark.asyncio
    async def test_attach_validates_provenance_source_id(self, service):
        """attach_to_memory should validate provenance.source_id length."""
        from datetime import datetime, timezone
        from src.memory.blocks.schemas import Provenance

        # Directly construct Provenance with oversized source_id
        malicious_prov = Provenance(
            source_id="x" * 500,
            source_type="memory",
            confidence=0.95,
            created_at=datetime.now(timezone.utc),
            retrieval_score=None,
            metadata=None,
        )

        with pytest.raises(ValueError, match="provenance.source_id length .* exceeds limit"):
            await service.attach_to_memory("mem-123", malicious_prov)

    @pytest.mark.asyncio
    async def test_attach_validates_provenance_source_type(self, service):
        """attach_to_memory should validate provenance.source_type length."""
        from datetime import datetime, timezone
        from src.memory.blocks.schemas import Provenance

        malicious_prov = Provenance(
            source_id="src-123",
            source_type="y" * 500,
            confidence=0.95,
            created_at=datetime.now(timezone.utc),
            retrieval_score=None,
            metadata=None,
        )

        with pytest.raises(ValueError, match="provenance.source_type length .* exceeds limit"):
            await service.attach_to_memory("mem-123", malicious_prov)

    @pytest.mark.asyncio
    async def test_attach_validates_provenance_metadata_keys(self, service):
        """attach_to_memory should validate provenance.metadata key count."""
        from datetime import datetime, timezone
        from src.memory.blocks.schemas import Provenance

        # Bypass create_provenance by directly constructing Provenance
        malicious_metadata = {f"key_{i}": f"value_{i}" for i in range(150)}
        malicious_prov = Provenance(
            source_id="src-123",
            source_type="memory",
            confidence=0.95,
            created_at=datetime.now(timezone.utc),
            retrieval_score=None,
            metadata=malicious_metadata,
        )

        with pytest.raises(ValueError, match="Metadata key count .* exceeds limit"):
            await service.attach_to_memory("mem-123", malicious_prov)

    @pytest.mark.asyncio
    async def test_attach_validates_provenance_metadata_depth(self, service):
        """attach_to_memory should validate provenance.metadata nesting depth."""
        from datetime import datetime, timezone
        from src.memory.blocks.schemas import Provenance

        # Create deeply nested structure
        nested = {"level": "bottom"}
        for i in range(10):
            nested = {"level": nested}

        malicious_prov = Provenance(
            source_id="src-123",
            source_type="memory",
            confidence=0.95,
            created_at=datetime.now(timezone.utc),
            retrieval_score=None,
            metadata=nested,
        )

        with pytest.raises(ValueError, match="Metadata nesting depth .* exceeds limit"):
            await service.attach_to_memory("mem-123", malicious_prov)

    @pytest.mark.asyncio
    async def test_attach_accepts_valid_provenance(self, service):
        """attach_to_memory should accept valid Provenance objects."""
        from datetime import datetime, timezone
        from src.memory.blocks.schemas import Provenance

        valid_prov = Provenance(
            source_id="src-123",
            source_type="memory",
            confidence=0.95,
            created_at=datetime.now(timezone.utc),
            retrieval_score=None,
            metadata={"valid": "metadata"},
        )

        await service.attach_to_memory("mem-123", valid_prov)

        retrieved = await service.get_provenance("mem-123")
        assert retrieved is not None
        assert retrieved.source_id == "src-123"

    @pytest.mark.asyncio
    async def test_attach_validates_provenance_metadata_total_size(self, service):
        """attach_to_memory should validate total metadata size (Council Round 16)."""
        from datetime import datetime, timezone
        from src.memory.blocks.schemas import Provenance

        # Create fewer keys with larger values that together exceed size limit
        # MAX_METADATA_SIZE_BYTES is 10000, MAX_METADATA_KEYS is 100
        # Use 50 keys with 300 chars each = ~15KB total (after JSON encoding)
        large_metadata = {f"key_{i}": "v" * 300 for i in range(50)}

        malicious_prov = Provenance(
            source_id="src-123",
            source_type="memory",
            confidence=0.95,
            created_at=datetime.now(timezone.utc),
            retrieval_score=None,
            metadata=large_metadata,
        )

        with pytest.raises(ValueError, match="metadata size .* exceeds limit"):
            await service.attach_to_memory("mem-123", malicious_prov)


class TestStrictTypeSafety:
    """TDD: Tests for strict type safety in metadata validation.

    Council Round 16: Identified lack of strict type safety for JSON serialization.
    """

    @pytest.fixture
    def service(self):
        """Create a fresh ProvenanceService for each test."""
        from src.memory.provenance.service import ProvenanceService

        return ProvenanceService()

    @pytest.mark.asyncio
    async def test_non_string_dict_keys_rejected(self, service):
        """Metadata dict keys must be strings."""
        # Use integer keys (Python allows, JSON doesn't)
        metadata = {123: "value"}  # type: ignore

        with pytest.raises(ValueError, match="Metadata dict keys must be strings"):
            await service.create_provenance(
                source_id="mem-123",
                source_type="memory",
                confidence=0.95,
                metadata=metadata,
            )

    @pytest.mark.asyncio
    async def test_nested_non_string_keys_rejected(self, service):
        """Nested dict keys must also be strings."""
        metadata = {"outer": {456: "value"}}  # type: ignore

        with pytest.raises(ValueError, match="Metadata dict keys must be strings"):
            await service.create_provenance(
                source_id="mem-123",
                source_type="memory",
                confidence=0.95,
                metadata=metadata,
            )

    @pytest.mark.asyncio
    async def test_unsupported_types_rejected(self, service):
        """Unsupported types in metadata should be rejected."""
        # datetime is not JSON serializable
        from datetime import datetime
        metadata = {"timestamp": datetime.now()}

        with pytest.raises(ValueError, match="Metadata contains unsupported type"):
            await service.create_provenance(
                source_id="mem-123",
                source_type="memory",
                confidence=0.95,
                metadata=metadata,
            )

    @pytest.mark.asyncio
    async def test_custom_objects_rejected(self, service):
        """Custom objects in metadata should be rejected."""
        class CustomClass:
            def __str__(self):
                # Expensive __str__ - this is the DoS vector
                return "x" * 1000000

        metadata = {"custom": CustomClass()}

        with pytest.raises(ValueError, match="Metadata contains unsupported type"):
            await service.create_provenance(
                source_id="mem-123",
                source_type="memory",
                confidence=0.95,
                metadata=metadata,
            )

    @pytest.mark.asyncio
    async def test_nested_unsupported_types_rejected(self, service):
        """Unsupported types nested in structures should be rejected."""
        from datetime import datetime
        metadata = {"outer": {"inner": [datetime.now()]}}

        with pytest.raises(ValueError, match="Metadata contains unsupported type"):
            await service.create_provenance(
                source_id="mem-123",
                source_type="memory",
                confidence=0.95,
                metadata=metadata,
            )

    @pytest.mark.asyncio
    async def test_all_json_primitives_accepted(self, service):
        """All valid JSON primitives should be accepted."""
        metadata = {
            "string": "text",
            "integer": 42,
            "float": 3.14,
            "boolean": True,
            "null": None,
            "list": [1, "two", 3.0, True, None],
            "nested_dict": {"key": "value"},
            "mixed": [{"a": 1}, [2, 3], "str"],
        }

        result = await service.create_provenance(
            source_id="mem-123",
            source_type="memory",
            confidence=0.95,
            metadata=metadata,
        )

        assert result is not None
        assert result.metadata == metadata
