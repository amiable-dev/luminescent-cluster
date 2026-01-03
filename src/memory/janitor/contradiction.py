# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Contradiction detection and resolution.

Handles contradicting memories using "newer wins" strategy.

Related GitHub Issues:
- #104: Contradiction Handling

ADR Reference: ADR-003 Memory Architecture, Phase 1d (Janitor Process)
"""

from typing import Any, Dict, List, Set

from src.memory.schemas import Memory


# Keywords that indicate potential contradictions
CONTRADICTION_INDICATORS = {
    'prefer': ['prefer', 'like', 'want', 'use'],
    'database': ['postgresql', 'mysql', 'mongodb', 'sqlite', 'redis'],
    'framework': ['django', 'fastapi', 'flask', 'express', 'react', 'vue'],
    'language': ['python', 'javascript', 'typescript', 'rust', 'go'],
    'formatting': ['tabs', 'spaces', 'indent'],
}


class ContradictionHandler:
    """Handles contradicting memories.

    Uses "newer wins" strategy by default. Can flag
    contradictions for human review.

    Attributes:
        strategy: Resolution strategy ("newer_wins").

    Example:
        >>> handler = ContradictionHandler()
        >>> winner = handler.resolve(old_memory, new_memory)
        >>> # winner is new_memory (newer wins)
    """

    def __init__(self, strategy: str = "newer_wins"):
        """Initialize the handler.

        Args:
            strategy: Resolution strategy.
        """
        self.strategy = strategy

    def is_contradiction(self, m1: Memory, m2: Memory) -> bool:
        """Check if two memories contradict each other.

        Args:
            m1: First memory.
            m2: Second memory.

        Returns:
            True if memories may contradict.
        """
        # Must be same type to contradict
        if m1.memory_type != m2.memory_type:
            return False

        # Check for opposing keywords in same category
        content1_lower = m1.content.lower()
        content2_lower = m2.content.lower()

        for category, keywords in CONTRADICTION_INDICATORS.items():
            keywords_in_m1 = [k for k in keywords if k in content1_lower]
            keywords_in_m2 = [k for k in keywords if k in content2_lower]

            # If both have keywords from same category but different ones
            if keywords_in_m1 and keywords_in_m2:
                if set(keywords_in_m1) != set(keywords_in_m2):
                    # Same category, different values = potential contradiction
                    return True

        return False

    def resolve(self, m1: Memory, m2: Memory) -> Memory:
        """Resolve contradiction between two memories.

        Args:
            m1: First memory.
            m2: Second memory.

        Returns:
            The memory to keep (newer one wins).
        """
        if self.strategy == "newer_wins":
            if m1.created_at > m2.created_at:
                return m1
            return m2

        # Default to newer wins
        return m2 if m2.created_at > m1.created_at else m1

    def flag_for_review(self, m1: Memory, m2: Memory) -> Dict[str, Any]:
        """Flag contradicting memories for human review.

        Args:
            m1: First memory.
            m2: Second memory.

        Returns:
            Dictionary with contradiction details for review.
        """
        return {
            'reason': 'Potential contradiction detected',
            'memories': [
                {
                    'content': m1.content,
                    'created_at': m1.created_at.isoformat(),
                    'confidence': m1.confidence,
                },
                {
                    'content': m2.content,
                    'created_at': m2.created_at.isoformat(),
                    'confidence': m2.confidence,
                },
            ],
            'suggested_resolution': 'newer_wins',
        }

    async def run(self, provider: Any, user_id: str) -> Dict[str, Any]:
        """Run contradiction resolution on all memories for a user.

        Args:
            provider: Memory provider.
            user_id: User ID to process.

        Returns:
            Statistics about the resolution run.
        """
        # Get all memories for user
        all_memories = await provider.search(user_id, filters={}, limit=10000)
        processed = len(all_memories)
        resolved = 0
        flagged: List[Dict[str, Any]] = []

        # Group by type for comparison
        by_type: Dict[str, List[Memory]] = {}
        for memory in all_memories:
            mem_type = memory.memory_type.value if hasattr(memory.memory_type, 'value') else str(memory.memory_type)
            if mem_type not in by_type:
                by_type[mem_type] = []
            by_type[mem_type].append(memory)

        # Find contradictions within each type
        memories_to_remove: Set[str] = set()

        for mem_type, memories in by_type.items():
            n = len(memories)
            for i in range(n):
                for j in range(i + 1, n):
                    if self.is_contradiction(memories[i], memories[j]):
                        # Resolve using strategy
                        winner = self.resolve(memories[i], memories[j])
                        loser = memories[j] if winner == memories[i] else memories[i]

                        if hasattr(loser, 'id') and loser.id:
                            memories_to_remove.add(loser.id)

                        # Flag for review if high confidence contradiction
                        if memories[i].confidence > 0.8 and memories[j].confidence > 0.8:
                            flagged.append(self.flag_for_review(memories[i], memories[j]))

        # Remove contradicting memories
        for memory_id in memories_to_remove:
            try:
                await provider.delete(memory_id)
                resolved += 1
            except Exception:
                pass

        return {
            'processed': processed,
            'resolved': resolved,
            'flagged_for_review': flagged,
        }
