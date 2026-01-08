# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Memory ranking logic.

Combines semantic similarity, recency, and confidence for ranking.

Related GitHub Issues:
- #97: Memory Ranking Logic
- #100: Memory Decay Scoring

ADR Reference: ADR-003 Memory Architecture, Phase 1c (Retrieval & Ranking)
"""

import math
from datetime import datetime, timezone
from typing import List, Tuple

from src.memory.blocks.schemas import Provenance
from src.memory.schemas import Memory


class MemoryRanker:
    """Ranks memories based on combined scoring factors.

    Combines:
    - Semantic similarity between query and memory content
    - Recency based on last_accessed_at (with decay)
    - Confidence score from extraction

    Attributes:
        similarity_weight: Weight for similarity score (default 0.5).
        recency_weight: Weight for recency score (default 0.3).
        confidence_weight: Weight for confidence score (default 0.2).
        decay_enabled: Whether to apply decay to recency (default True).
        decay_half_life_days: Half-life for decay calculation (default 30).

    Example:
        >>> ranker = MemoryRanker()
        >>> ranked = ranker.rank("tabs", memories)
        >>> for memory, score in ranked:
        ...     print(f"{memory.content}: {score:.2f}")
    """

    def __init__(
        self,
        similarity_weight: float = 0.5,
        recency_weight: float = 0.3,
        confidence_weight: float = 0.2,
        decay_enabled: bool = True,
        decay_half_life_days: int = 30,
    ):
        """Initialize the ranker with weights.

        Args:
            similarity_weight: Weight for similarity score.
            recency_weight: Weight for recency score.
            confidence_weight: Weight for confidence score.
            decay_enabled: Enable decay-based recency scoring.
            decay_half_life_days: Half-life for exponential decay.
        """
        self.similarity_weight = similarity_weight
        self.recency_weight = recency_weight
        self.confidence_weight = confidence_weight
        self.decay_enabled = decay_enabled
        self.decay_half_life_days = decay_half_life_days

    def calculate_similarity(self, query: str, content: str) -> float:
        """Calculate similarity between query and content.

        Uses simple word overlap for now. Can be enhanced with
        embedding-based similarity later.

        Args:
            query: Search query.
            content: Memory content to compare.

        Returns:
            Similarity score between 0.0 and 1.0.
        """
        if not query or not content:
            return 0.0

        # Simple word overlap similarity
        query_words = set(query.lower().split())
        content_words = set(content.lower().split())

        if not query_words or not content_words:
            return 0.0

        # Jaccard similarity
        intersection = query_words & content_words
        union = query_words | content_words

        if not union:
            return 0.0

        jaccard = len(intersection) / len(union)

        # Boost for exact substring match
        if query.lower() in content.lower():
            jaccard = min(1.0, jaccard + 0.3)

        return min(1.0, jaccard)

    def calculate_recency(self, last_accessed_at: datetime) -> float:
        """Calculate recency score with exponential decay.

        Args:
            last_accessed_at: When the memory was last accessed.

        Returns:
            Recency score between 0.0 and 1.0.
        """
        now = datetime.now(timezone.utc)

        # Ensure timezone aware comparison
        if last_accessed_at.tzinfo is None:
            last_accessed_at = last_accessed_at.replace(tzinfo=timezone.utc)

        # Calculate age in days
        age_delta = now - last_accessed_at
        age_days = age_delta.total_seconds() / (24 * 60 * 60)

        if age_days < 0:
            age_days = 0

        if not self.decay_enabled:
            # Simple linear decay over 90 days
            return max(0.0, 1.0 - (age_days / 90))

        # Guard against zero half-life (would cause ZeroDivisionError)
        if self.decay_half_life_days <= 0:
            return 0.0

        # Exponential decay: score = 0.5 ^ (age / half_life)
        decay_score = math.pow(0.5, age_days / self.decay_half_life_days)

        return decay_score

    def calculate_score(self, query: str, memory: Memory) -> float:
        """Calculate combined ranking score for a memory.

        Args:
            query: Search query.
            memory: Memory to score.

        Returns:
            Combined score between 0.0 and 1.0.
        """
        similarity = self.calculate_similarity(query, memory.content)
        recency = self.calculate_recency(memory.last_accessed_at)
        confidence = memory.confidence

        score = (
            self.similarity_weight * similarity
            + self.recency_weight * recency
            + self.confidence_weight * confidence
        )

        return score

    def rank(
        self,
        query: str,
        memories: List[Memory],
        limit: int | None = None,
    ) -> List[Tuple[Memory, float]]:
        """Rank memories by relevance to query.

        Args:
            query: Search query.
            memories: List of memories to rank.
            limit: Maximum number of results to return.

        Returns:
            List of (memory, score) tuples sorted by score descending.
        """
        if not memories:
            return []

        # Score each memory
        scored = [(memory, self.calculate_score(query, memory)) for memory in memories]

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)

        # Apply limit
        if limit is not None:
            scored = scored[:limit]

        return scored

    def rank_with_provenance(
        self,
        query: str,
        memories: List[Memory],
        limit: int | None = None,
        attach_provenance: bool = True,
    ) -> List[Tuple[Memory, float]]:
        """Rank memories by relevance to query with provenance tracking.

        ADR-003 Phase 2: Attaches provenance with retrieval scores to each memory.

        Args:
            query: Search query.
            memories: List of memories to rank.
            limit: Maximum number of results to return.
            attach_provenance: Whether to attach provenance to memories.

        Returns:
            List of (memory, score) tuples sorted by score descending.
            Memories have provenance attached if attach_provenance=True.
        """
        if not memories:
            return []

        # Score and attach provenance to each memory
        scored = []
        for memory in memories:
            score = self.calculate_score(query, memory)

            if attach_provenance:
                # Preserve existing provenance if present, just add retrieval_score
                if memory.provenance is not None:
                    # Update existing provenance with retrieval score
                    from dataclasses import replace

                    updated_provenance = replace(
                        memory.provenance, retrieval_score=score
                    )
                    memory_with_provenance = memory.model_copy(
                        update={"provenance": updated_provenance}
                    )
                else:
                    # Create new provenance record with retrieval metadata
                    provenance = Provenance(
                        source_id=memory.metadata.get("memory_id", "unknown"),
                        source_type="memory",
                        confidence=memory.confidence,
                        created_at=memory.created_at,
                        retrieval_score=score,
                    )
                    memory_with_provenance = memory.model_copy(
                        update={"provenance": provenance}
                    )
                scored.append((memory_with_provenance, score))
            else:
                scored.append((memory, score))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)

        # Apply limit
        if limit is not None:
            scored = scored[:limit]

        return scored
