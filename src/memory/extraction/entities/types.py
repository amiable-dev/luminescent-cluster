# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Entity types and protocols for entity extraction.

This module defines the core types for extracting structured entities
from memory content. Entities represent services, dependencies, APIs,
patterns, frameworks, and configuration items mentioned in memories.

Related GitHub Issues:
- #118: Define EntityType enum and Entity schema

ADR Reference: ADR-003 Memory Architecture, Phase 3 (Entity Extraction)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List, Optional, Protocol, runtime_checkable


class EntityType(str, Enum):
    """Types of entities that can be extracted from memory content.

    These entity types support knowledge graph construction in Phase 4,
    enabling queries like "what services depend on PostgreSQL?"

    Attributes:
        SERVICE: Service names (e.g., auth-service, payment-api)
        DEPENDENCY: External dependencies (e.g., PostgreSQL, Redis)
        API: API endpoints (e.g., /api/v1/users, REST endpoint)
        PATTERN: Code patterns (e.g., Repository Pattern, Factory)
        FRAMEWORK: Frameworks (e.g., FastAPI, Django, React)
        CONFIG: Configuration items (e.g., REDIS_URL, DATABASE_HOST)
    """

    SERVICE = "service"
    DEPENDENCY = "dependency"
    API = "api"
    PATTERN = "pattern"
    FRAMEWORK = "framework"
    CONFIG = "config"


@dataclass
class Entity:
    """Extracted entity from memory content.

    Represents a structured entity extracted from unstructured memory
    text. Entities are stored in Memory.metadata for later querying
    and knowledge graph construction.

    Attributes:
        name: The canonical name of the entity (e.g., "auth-service")
        entity_type: The type of entity (SERVICE, DEPENDENCY, etc.)
        confidence: Extraction confidence score (0.0-1.0)
        source_memory_id: Optional ID of the memory this was extracted from
        mentions: List of raw text mentions that mapped to this entity
        metadata: Additional metadata (e.g., version, host)

    Example:
        >>> entity = Entity(
        ...     name="PostgreSQL",
        ...     entity_type=EntityType.DEPENDENCY,
        ...     confidence=0.95,
        ...     source_memory_id="mem-123",
        ...     mentions=["PostgreSQL", "postgres", "PG"],
        ...     metadata={"version": "15.0"}
        ... )
    """

    name: str
    entity_type: EntityType
    confidence: float
    source_memory_id: Optional[str] = None
    mentions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class EntityExtractor(Protocol):
    """Protocol for entity extraction implementations.

    Implementations can be pattern-based (MockEntityExtractor) or
    LLM-based (HaikuEntityExtractor). Both must implement the
    async extract method.

    Example:
        >>> class MyExtractor:
        ...     async def extract(self, content: str, memory_id: Optional[str] = None) -> List[Entity]:
        ...         # Extract entities from content
        ...         return [Entity(...)]
        >>>
        >>> assert isinstance(MyExtractor(), EntityExtractor)
    """

    async def extract(
        self, content: str, memory_id: Optional[str] = None
    ) -> List[Entity]:
        """Extract entities from text content.

        Args:
            content: The text content to extract entities from.
            memory_id: Optional ID of the source memory for tracking.

        Returns:
            List of extracted Entity objects.
        """
        ...
