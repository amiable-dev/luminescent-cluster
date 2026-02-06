# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Memory deduplication.

Removes duplicate memories based on similarity threshold.
Preserves memory with highest confidence.

Related GitHub Issues:
- #103: Deduplication

ADR Reference: ADR-003 Memory Architecture, Phase 1d (Janitor Process)
"""

from typing import Any, List, Set, Tuple

from luminescent_cluster.memory.schemas import Memory


class Deduplicator:
    """Deduplicates memories based on content similarity.

    Uses a configurable similarity threshold (default 0.85) to
    identify duplicates. Preserves the memory with highest confidence.

    Attributes:
        similarity_threshold: Minimum similarity to consider duplicate.

    Example:
        >>> dedup = Deduplicator(similarity_threshold=0.85)
        >>> result = await dedup.run(provider, "user-1")
        >>> print(f"Removed {result['removed']} duplicates")
    """

    def __init__(self, similarity_threshold: float = 0.85):
        """Initialize the deduplicator.

        Args:
            similarity_threshold: Minimum similarity for duplicates (0.0-1.0).
        """
        self.similarity_threshold = similarity_threshold

    def calculate_similarity(self, m1: Memory, m2: Memory) -> float:
        """Calculate similarity between two memories.

        Uses simple word overlap for efficiency.

        Args:
            m1: First memory.
            m2: Second memory.

        Returns:
            Similarity score between 0.0 and 1.0.
        """
        if m1.memory_type != m2.memory_type:
            return 0.0

        words1 = set(m1.content.lower().split())
        words2 = set(m2.content.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union) if union else 0.0

    def find_duplicates(
        self, memories: List[Memory]
    ) -> List[Tuple[Memory, Memory, float]]:
        """Find duplicate memory pairs.

        Args:
            memories: List of memories to check.

        Returns:
            List of (memory1, memory2, similarity) tuples.
        """
        duplicates = []
        n = len(memories)

        for i in range(n):
            for j in range(i + 1, n):
                similarity = self.calculate_similarity(memories[i], memories[j])
                if similarity >= self.similarity_threshold:
                    duplicates.append((memories[i], memories[j], similarity))

        return duplicates

    def resolve_duplicates(
        self, memories: List[Memory]
    ) -> Tuple[List[Memory], List[Memory]]:
        """Resolve duplicates by keeping highest confidence.

        Args:
            memories: List of duplicate memories.

        Returns:
            Tuple of (memories_to_keep, memories_to_remove).
        """
        if not memories:
            return [], []

        # Sort by confidence descending
        sorted_mems = sorted(memories, key=lambda m: m.confidence, reverse=True)

        # Keep the highest confidence, remove the rest
        to_keep = [sorted_mems[0]]
        to_remove = sorted_mems[1:]

        return to_keep, to_remove

    async def run(
        self, provider: Any, user_id: str, dry_run: bool = False
    ) -> dict[str, Any]:
        """Run deduplication on all memories for a user.

        Args:
            provider: Memory provider.
            user_id: User ID to deduplicate.
            dry_run: If True, only report what would be done without making changes.

        Returns:
            Statistics about the deduplication run.

        Note:
            Council Review: Uses soft-delete (invalidate) by default instead of
            hard-delete to prevent data loss. Memories can be recovered.
        """
        # Get all memories for user
        all_memories = await provider.search(user_id, filters={}, limit=10000)
        processed = len(all_memories)
        invalidated = 0

        # Group memories by type for more efficient comparison
        by_type: dict[str, List[Memory]] = {}
        for memory in all_memories:
            mem_type = memory.memory_type.value if hasattr(memory.memory_type, 'value') else str(memory.memory_type)
            if mem_type not in by_type:
                by_type[mem_type] = []
            by_type[mem_type].append(memory)

        # Find duplicates within each type
        memories_to_invalidate: Set[str] = set()
        would_invalidate: List[dict] = []

        for mem_type, memories in by_type.items():
            duplicates = self.find_duplicates(memories)

            for m1, m2, similarity in duplicates:
                # Keep higher confidence, invalidate lower
                if m1.confidence >= m2.confidence:
                    if hasattr(m2, 'id') and m2.id:
                        memories_to_invalidate.add(m2.id)
                        would_invalidate.append({
                            'id': m2.id,
                            'content': m2.content[:50],
                            'reason': f'Duplicate of higher confidence memory (similarity: {similarity:.2f})',
                        })
                else:
                    if hasattr(m1, 'id') and m1.id:
                        memories_to_invalidate.add(m1.id)
                        would_invalidate.append({
                            'id': m1.id,
                            'content': m1.content[:50],
                            'reason': f'Duplicate of higher confidence memory (similarity: {similarity:.2f})',
                        })

        if dry_run:
            return {
                'processed': processed,
                'dry_run': True,
                'would_invalidate': would_invalidate,
                'duplicates_found': len(memories_to_invalidate),
            }

        # Soft-delete (invalidate) duplicates instead of hard-delete
        errors: List[str] = []
        for memory_id in memories_to_invalidate:
            try:
                # Use invalidate if available (preferred)
                if hasattr(provider, 'invalidate'):
                    await provider.invalidate(memory_id, reason="Duplicate detected by janitor")
                    invalidated += 1
                # Fallback: use delete (hard delete) if no invalidate method
                elif hasattr(provider, 'delete'):
                    await provider.delete(memory_id)
                    invalidated += 1
                else:
                    errors.append(f"No invalidate or delete method for {memory_id}")
            except Exception as e:
                errors.append(f"Failed to invalidate {memory_id}: {str(e)}")

        return {
            'processed': processed,
            'invalidated': invalidated,
            'removed': invalidated,  # For backward compatibility
            'duplicates_found': len(memories_to_invalidate),
            'errors': errors if errors else None,
        }
