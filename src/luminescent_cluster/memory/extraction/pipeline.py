# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Async extraction pipeline for memory processing.

Provides the ExtractionPipeline class for processing conversations
and storing extracted memories asynchronously.

Related GitHub Issues:
- #93: Async Extraction Pipeline

ADR Reference: ADR-003 Memory Architecture, Phase 1b (Async Extraction)
"""

import asyncio
from typing import Any, List, Optional

from luminescent_cluster.memory.extraction.mock_extractor import MockExtractor
from luminescent_cluster.memory.extraction.types import ExtractionResult, MemoryExtractor
from luminescent_cluster.memory.providers.local import LocalMemoryProvider
from luminescent_cluster.memory.schemas import Memory, MemoryType

# Current extraction version for re-processing tracking
EXTRACTION_VERSION = 1


class ExtractionPipeline:
    """Async pipeline for memory extraction and storage.

    Processes conversations to extract memories and store them
    in the memory provider. Designed to run after response is
    sent to user (non-blocking).

    Attributes:
        extractor: The MemoryExtractor implementation to use.
        provider: The memory provider for storage.
        extraction_version: Version for re-processing tracking.

    Example:
        >>> pipeline = ExtractionPipeline()
        >>> results = await pipeline.process(
        ...     conversation="I prefer tabs over spaces",
        ...     user_id="user-123"
        ... )
    """

    def __init__(
        self,
        extractor: Optional[MemoryExtractor] = None,
        provider: Optional[Any] = None,
    ):
        """Initialize the extraction pipeline.

        Args:
            extractor: Extractor implementation (defaults to MockExtractor).
            provider: Memory provider (defaults to LocalMemoryProvider).
        """
        self.extractor = extractor or MockExtractor()
        self._provider = provider
        self.extraction_version = EXTRACTION_VERSION

    @property
    def provider(self) -> Any:
        """Get the memory provider, creating if needed."""
        if self._provider is None:
            self._provider = LocalMemoryProvider()
        return self._provider

    async def process(
        self,
        conversation: str,
        user_id: str,
        source: str = "conversation",
        metadata: Optional[dict[str, Any]] = None,
    ) -> List[ExtractionResult]:
        """Process a conversation and extract memories.

        Args:
            conversation: The conversation text to process.
            user_id: User ID for the memories.
            source: Source of the conversation.
            metadata: Additional metadata for memories.

        Returns:
            List of ExtractionResult objects.
        """
        # Extract memories
        extractions = await self.extractor.extract(conversation)

        # Store each extraction
        for extraction in extractions:
            await self._store_extraction(
                extraction=extraction,
                user_id=user_id,
                source=source,
                metadata=metadata,
            )

        return extractions

    async def process_async(
        self,
        conversation: str,
        user_id: str,
        source: str = "conversation",
        metadata: Optional[dict[str, Any]] = None,
    ) -> asyncio.Task:
        """Process a conversation asynchronously (fire-and-forget).

        Use this method to process extraction after sending
        response to user. Does not block.

        Args:
            conversation: The conversation text to process.
            user_id: User ID for the memories.
            source: Source of the conversation.
            metadata: Additional metadata for memories.

        Returns:
            asyncio.Task that can be awaited if needed.
        """
        task = asyncio.create_task(
            self.process(
                conversation=conversation,
                user_id=user_id,
                source=source,
                metadata=metadata,
            )
        )
        return task

    async def _store_extraction(
        self,
        extraction: ExtractionResult,
        user_id: str,
        source: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[str]:
        """Store an extraction result as a memory.

        Args:
            extraction: The extraction result.
            user_id: User ID for the memory.
            source: Source of the memory.
            metadata: Additional metadata.

        Returns:
            Memory ID if stored successfully, None otherwise.
        """
        try:
            # Convert memory_type string to enum
            mem_type = MemoryType(extraction.memory_type)
        except ValueError:
            # Invalid memory type, skip
            return None

        # Create memory object
        memory = Memory(
            user_id=user_id,
            content=extraction.content,
            memory_type=mem_type,
            confidence=extraction.confidence,
            source=source,
            raw_source=extraction.raw_source,
            extraction_version=self.extraction_version,
            metadata=metadata or {},
        )

        # Store using provider
        try:
            memory_id = await self.provider.store(memory, {})
            return memory_id
        except Exception as e:
            print(f"Failed to store extraction: {e}")
            return None
