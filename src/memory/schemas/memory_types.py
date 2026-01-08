# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
Memory Type Schemas for ADR-003.

Defines Pydantic models for memory types: preference, fact, decision.
Schema follows ADR-003 lines 881-900.

Related GitHub Issues:
- #79: Define Memory Type Schemas (Pydantic)

ADR Reference: ADR-003 Memory Architecture, Phase 0 (Foundations)
"""

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

from pydantic import BaseModel, Field, field_validator

if TYPE_CHECKING:
    from src.memory.blocks.schemas import Provenance


class MemoryType(str, Enum):
    """Types of memories that can be stored.

    - PREFERENCE: User preferences (explicit and implicit)
    - FACT: Facts learned about the codebase
    - DECISION: Decisions made with rationale
    """

    PREFERENCE = "preference"
    FACT = "fact"
    DECISION = "decision"


class MemoryScope(str, Enum):
    """Scope hierarchy for memory retrieval.

    - USER: User-specific memories (highest priority)
    - PROJECT: Project-specific memories
    - GLOBAL: Organization-wide memories (lowest priority)
    """

    USER = "user"
    PROJECT = "project"
    GLOBAL = "global"


class Memory(BaseModel):
    """A memory record for persistent technical context.

    Schema from ADR-003 lines 881-900:
    - user_id: User who owns this memory
    - content: The memory content (indexed for semantic search)
    - memory_type: Type of memory (preference, fact, decision)
    - confidence: Extraction confidence score (0.0-1.0)
    - source: Where this memory came from (conversation, adr, etc.)
    - raw_source: Original text for re-extraction
    - extraction_version: For re-processing on prompt updates
    - created_at: When the memory was created
    - last_accessed_at: For decay scoring
    - expires_at: TTL support (optional)
    - metadata: Flexible metadata (scope, project_id, etc.)
    """

    user_id: str = Field(..., description="User who owns this memory")
    content: str = Field(..., description="The memory content")
    memory_type: MemoryType = Field(..., description="Type of memory")
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Extraction confidence score (0.0-1.0)",
    )
    source: str = Field(..., description="Where this memory came from")
    raw_source: Optional[str] = Field(
        default=None, description="Original text for re-extraction"
    )
    extraction_version: int = Field(
        default=1, description="Version for re-processing on prompt updates"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the memory was created",
    )
    last_accessed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last access time for decay scoring",
    )
    expires_at: Optional[datetime] = Field(
        default=None, description="TTL expiration time"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Flexible metadata (scope, project_id, etc.)",
    )
    provenance: Optional[Any] = Field(
        default=None,
        description="Source attribution and retrieval tracking (ADR-003 Phase 2)",
    )

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """Validate confidence is between 0.0 and 1.0."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "user_id": "user-123",
                    "content": "Prefers tabs over spaces",
                    "memory_type": "preference",
                    "confidence": 0.95,
                    "source": "conversation",
                    "raw_source": "I always use tabs, never spaces",
                }
            ]
        }
    }
