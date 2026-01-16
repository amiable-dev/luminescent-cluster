# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Async entity extraction pipeline with storage integration.

Provides the EntityExtractionPipeline class for extracting entities
from memory content and storing them in memory metadata.

Related GitHub Issues:
- #121: Async EntityExtractionPipeline with storage integration

ADR Reference: ADR-003 Memory Architecture, Phase 3 (Entity Extraction)
"""

import asyncio
from typing import Any, List, Optional, TYPE_CHECKING

from src.memory.extraction.entities.mock_extractor import MockEntityExtractor
from src.memory.extraction.entities.types import Entity, EntityExtractor

if TYPE_CHECKING:
    from src.memory.providers.local import LocalMemoryProvider


class EntityExtractionPipeline:
    """Async pipeline for entity extraction and storage.

    Processes memory content to extract entities and store them
    in the memory's metadata. Designed to run after response is
    sent to user (non-blocking via process_async).

    Attributes:
        extractor: The EntityExtractor implementation to use.
        provider: The memory provider for storage.

    Example:
        >>> pipeline = EntityExtractionPipeline()
        >>> entities = await pipeline.process(
        ...     memory_id="mem-123",
        ...     content="The auth-service uses PostgreSQL",
        ...     user_id="user-123"
        ... )
    """

    def __init__(
        self,
        extractor: Optional[EntityExtractor] = None,
        provider: Optional[Any] = None,
    ):
        """Initialize the entity extraction pipeline.

        Args:
            extractor: Extractor implementation (defaults to MockEntityExtractor).
            provider: Memory provider for storage operations.
        """
        self.extractor = extractor or MockEntityExtractor()
        self._provider = provider

    @property
    def provider(self) -> Any:
        """Get the memory provider, creating if needed."""
        if self._provider is None:
            from src.memory.providers.local import LocalMemoryProvider

            self._provider = LocalMemoryProvider()
        return self._provider

    async def process(
        self,
        memory_id: str,
        content: str,
        user_id: str,
    ) -> List[Entity]:
        """Process content and extract entities.

        Extracts entities from the content and stores them in the
        memory's metadata under the "entities" key.

        Args:
            memory_id: ID of the memory to update with entities.
            content: The text content to extract entities from.
            user_id: User ID for authorization (must match memory owner).

        Returns:
            List of extracted Entity objects.
        """
        # Extract entities
        entities = await self.extractor.extract(content, memory_id=memory_id)

        if not entities:
            return []

        # Store entities in memory metadata (with authorization check)
        await self._store_entities(memory_id, entities, user_id)

        return entities

    async def process_async(
        self,
        memory_id: str,
        content: str,
        user_id: str,
    ) -> asyncio.Task:
        """Process content asynchronously (fire-and-forget).

        Use this method to process entity extraction after sending
        response to user. Does not block the caller.

        Args:
            memory_id: ID of the memory to update with entities.
            content: The text content to extract entities from.
            user_id: User ID for filtering/validation.

        Returns:
            asyncio.Task that can be awaited if needed.
        """
        task = asyncio.create_task(
            self.process(
                memory_id=memory_id,
                content=content,
                user_id=user_id,
            )
        )
        return task

    async def _store_entities(
        self,
        memory_id: str,
        entities: List[Entity],
        user_id: str,
    ) -> None:
        """Store entities in memory metadata.

        Security: Verifies memory ownership before updating.

        Args:
            memory_id: ID of the memory to update.
            entities: List of entities to store.
            user_id: User ID for authorization (must match memory owner).
        """
        # Get current memory
        memory = await self.provider.get_by_id(memory_id)

        # Security: Verify memory exists and belongs to requesting user
        if memory is None or memory.user_id != user_id:
            return  # Unauthorized or not found - fail silently

        # Convert entities to JSON-serializable format
        entity_dicts = [
            {
                "name": entity.name,
                "type": entity.entity_type.value,
                "confidence": entity.confidence,
            }
            for entity in entities
        ]

        # Update metadata with entities
        new_metadata = {**memory.metadata, "entities": entity_dicts}

        # Update the memory
        await self.provider.update(memory_id, {"metadata": new_metadata})
