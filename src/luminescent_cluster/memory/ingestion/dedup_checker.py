# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Duplicate detection for grounded memory ingestion.

Prevents duplicate memories from being stored by checking similarity
against existing memories. Duplicates (>0.92 similarity) are blocked.

From ADR-003 Phase 2:
> Deduplication: cosine similarity >0.92 rejects as redundant
"""

from dataclasses import dataclass
from typing import Any, Optional, Protocol


class DedupCheckError(Exception):
    """Raised when duplicate check fails due to provider error.

    SECURITY: Callers should treat this as "cannot verify uniqueness"
    and flag for review rather than auto-approving.
    """

    pass


class MemoryProviderProtocol(Protocol):
    """Protocol for memory providers used by DedupChecker."""

    async def search(
        self,
        user_id: str,
        filters: dict[str, Any],
        limit: int = 10,
    ) -> list[Any]:
        """Search for memories matching filters."""
        ...


@dataclass
class DuplicateCheckResult:
    """Result of duplicate checking.

    Attributes:
        is_duplicate: True if content is a duplicate.
        existing_memory_id: ID of the matching memory (if duplicate).
        similarity_score: Highest similarity score found.
        checked_count: Number of memories checked.
    """

    is_duplicate: bool
    existing_memory_id: Optional[str]
    similarity_score: float
    checked_count: int


class DedupChecker:
    """Checks for duplicate memory content before ingestion.

    Uses word overlap (Jaccard similarity) as a fast approximation
    of semantic similarity. Memories with >0.92 similarity are
    considered duplicates and blocked per ADR-003.

    Example:
        >>> checker = DedupChecker(provider)
        >>> result = await checker.check_duplicate("Prefers tabs", "user-1")
        >>> if result.is_duplicate:
        ...     print(f"Duplicate of {result.existing_memory_id}")
    """

    # ADR-003 specified threshold
    SIMILARITY_THRESHOLD = 0.92

    # Maximum memories to check (performance limit)
    MAX_MEMORIES_TO_CHECK = 100

    def __init__(
        self,
        provider: MemoryProviderProtocol,
        similarity_threshold: float = SIMILARITY_THRESHOLD,
    ):
        """Initialize the dedup checker.

        Args:
            provider: Memory provider to search existing memories.
            similarity_threshold: Minimum similarity to consider duplicate.
        """
        self.provider = provider
        self.similarity_threshold = similarity_threshold

    async def check_duplicate(
        self,
        content: str,
        user_id: str,
        memory_type: Optional[str] = None,
    ) -> DuplicateCheckResult:
        """Check if content duplicates an existing memory.

        Args:
            content: New memory content to check.
            user_id: User ID to scope the search.
            memory_type: Optional memory type filter.

        Returns:
            DuplicateCheckResult with duplicate status and details.
        """
        # Build filters for search
        filters: dict[str, Any] = {}
        if memory_type:
            filters["memory_type"] = memory_type

        # Search existing memories
        try:
            existing_memories = await self.provider.search(
                user_id=user_id,
                filters=filters,
                limit=self.MAX_MEMORIES_TO_CHECK,
            )
        except Exception as e:
            # SECURITY: Fail-closed - raise error instead of allowing through
            # Callers should catch DedupCheckError and flag for review
            raise DedupCheckError(f"Cannot verify uniqueness due to provider error: {e}") from e

        if not existing_memories:
            return DuplicateCheckResult(
                is_duplicate=False,
                existing_memory_id=None,
                similarity_score=0.0,
                checked_count=0,
            )

        # Check similarity against each memory
        highest_similarity = 0.0
        matching_id: Optional[str] = None

        content_words = self._tokenize(content)

        for memory in existing_memories:
            # Get memory content and ID
            memory_content = self._get_content(memory)
            memory_id = self._get_id(memory)

            if not memory_content:
                continue

            existing_words = self._tokenize(memory_content)
            similarity = self._jaccard_similarity(content_words, existing_words)

            if similarity > highest_similarity:
                highest_similarity = similarity
                if similarity >= self.similarity_threshold:
                    matching_id = memory_id

        return DuplicateCheckResult(
            is_duplicate=highest_similarity >= self.similarity_threshold,
            existing_memory_id=matching_id,
            similarity_score=highest_similarity,
            checked_count=len(existing_memories),
        )

    def calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts.

        Uses Jaccard similarity on word tokens.

        Args:
            text1: First text.
            text2: Second text.

        Returns:
            Similarity score between 0.0 and 1.0.
        """
        words1 = self._tokenize(text1)
        words2 = self._tokenize(text2)
        return self._jaccard_similarity(words1, words2)

    def _tokenize(self, text: str) -> set[str]:
        """Tokenize text into words.

        Args:
            text: Text to tokenize.

        Returns:
            Set of lowercase words.
        """
        # Simple word tokenization
        # Normalize: lowercase, split on whitespace and punctuation
        words = text.lower().split()
        # Remove punctuation from words
        cleaned = set()
        for word in words:
            # Strip common punctuation
            word = word.strip(".,;:!?()[]{}\"'")
            if word:
                cleaned.add(word)
        return cleaned

    def _jaccard_similarity(self, set1: set[str], set2: set[str]) -> float:
        """Calculate Jaccard similarity between two sets.

        Args:
            set1: First set of words.
            set2: Second set of words.

        Returns:
            Jaccard index (intersection / union).
        """
        if not set1 or not set2:
            return 0.0

        intersection = set1 & set2
        union = set1 | set2

        return len(intersection) / len(union) if union else 0.0

    def _get_content(self, memory: Any) -> Optional[str]:
        """Extract content from memory object.

        Handles both dict and object forms.

        Args:
            memory: Memory object or dict.

        Returns:
            Memory content string or None.
        """
        if isinstance(memory, dict):
            return memory.get("content")
        return getattr(memory, "content", None)

    def _get_id(self, memory: Any) -> Optional[str]:
        """Extract ID from memory object.

        Handles both dict and object forms.

        Args:
            memory: Memory object or dict.

        Returns:
            Memory ID string or None.
        """
        if isinstance(memory, dict):
            return memory.get("id") or memory.get("memory_id")

        # Try common attribute names
        for attr in ("id", "memory_id", "_id"):
            if hasattr(memory, attr):
                value = getattr(memory, attr)
                if value:
                    return str(value)
        return None

    async def find_similar(
        self,
        content: str,
        user_id: str,
        threshold: float = 0.7,
        limit: int = 5,
    ) -> list[tuple[Any, float]]:
        """Find similar memories above a threshold.

        Useful for surfacing related memories during review.

        Args:
            content: Content to compare.
            user_id: User ID to scope search.
            threshold: Minimum similarity threshold.
            limit: Maximum memories to return.

        Returns:
            List of (memory, similarity) tuples sorted by similarity.
        """
        try:
            existing_memories = await self.provider.search(
                user_id=user_id,
                filters={},
                limit=self.MAX_MEMORIES_TO_CHECK,
            )
        except Exception:
            return []

        if not existing_memories:
            return []

        content_words = self._tokenize(content)
        similar: list[tuple[Any, float]] = []

        for memory in existing_memories:
            memory_content = self._get_content(memory)
            if not memory_content:
                continue

            existing_words = self._tokenize(memory_content)
            similarity = self._jaccard_similarity(content_words, existing_words)

            if similarity >= threshold:
                similar.append((memory, similarity))

        # Sort by similarity descending
        similar.sort(key=lambda x: x[1], reverse=True)
        return similar[:limit]
