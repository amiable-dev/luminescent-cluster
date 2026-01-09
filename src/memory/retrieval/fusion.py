# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Reciprocal Rank Fusion (RRF) for combining retrieval results.

Implements RRF algorithm for fusing ranked lists from multiple
retrieval methods as part of ADR-003 Phase 3 Stage 2.

RRF Formula: score(d) = Σ 1/(k + rank_i(d))
Where:
- k is a constant (default 60)
- rank_i(d) is the rank of document d in list i (1-indexed)

Benefits:
- Score-agnostic: Works with any retrieval method
- Effective: Empirically strong performance
- Simple: No hyperparameter tuning needed

Reference: Cormack, G. V., Clarke, C. L., & Buettcher, S. (2009).
"Reciprocal Rank Fusion Outperforms Condorcet and Individual Rank
Learning Methods."

ADR Reference: ADR-003 Memory Architecture, Phase 3 (Two-Stage Retrieval)
"""

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class FusedResult(Generic[T]):
    """A result from rank fusion.

    Attributes:
        item: The fused item (document ID or similar).
        score: RRF fusion score.
        source_ranks: Rank in each source list (1-indexed, None if not present).
        source_scores: Original score from each source (None if not present).
    """

    item: T
    score: float
    source_ranks: dict[str, int]
    source_scores: dict[str, float]


class RRFFusion:
    """Reciprocal Rank Fusion for combining retrieval results.

    Fuses multiple ranked lists into a single ranked list using
    the RRF scoring formula.

    Example:
        >>> fusion = RRFFusion(k=60)
        >>> bm25_results = [("doc1", 0.8), ("doc2", 0.6), ("doc3", 0.4)]
        >>> vector_results = [("doc2", 0.9), ("doc1", 0.7), ("doc4", 0.5)]
        >>> fused = fusion.fuse(bm25=bm25_results, vector=vector_results)
        >>> for item, score in fused:
        ...     print(f"{item}: {score:.4f}")

    Attributes:
        k: RRF constant (default 60). Higher values reduce impact of rank.
    """

    # Default k value from the original RRF paper
    DEFAULT_K = 60

    def __init__(self, k: int = DEFAULT_K):
        """Initialize RRF fusion.

        Args:
            k: RRF constant. Higher values reduce the importance of
               top ranks relative to lower ranks.
        """
        if k < 0:
            raise ValueError("k must be non-negative")
        self.k = k

    def fuse(
        self,
        **ranked_lists: list[tuple[str, float]],
    ) -> list[tuple[str, float]]:
        """Fuse multiple ranked lists using RRF.

        Args:
            **ranked_lists: Named ranked lists, each a list of
                           (item_id, score) tuples sorted by score descending.

        Returns:
            Fused list of (item_id, rrf_score) tuples sorted by score descending.
        """
        if not ranked_lists:
            return []

        # Calculate RRF scores
        rrf_scores: dict[str, float] = {}

        for list_name, results in ranked_lists.items():
            for rank, (item_id, _) in enumerate(results, start=1):
                score = 1.0 / (self.k + rank)
                rrf_scores[item_id] = rrf_scores.get(item_id, 0.0) + score

        # Sort by RRF score descending
        sorted_results = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

        return sorted_results

    def fuse_with_details(
        self,
        **ranked_lists: list[tuple[str, float]],
    ) -> list[FusedResult[str]]:
        """Fuse multiple ranked lists with detailed provenance.

        Args:
            **ranked_lists: Named ranked lists, each a list of
                           (item_id, score) tuples sorted by score descending.

        Returns:
            List of FusedResult objects with source ranks and scores.
        """
        if not ranked_lists:
            return []

        # Track ranks and scores for each item
        item_ranks: dict[str, dict[str, int]] = {}
        item_scores: dict[str, dict[str, float]] = {}
        rrf_scores: dict[str, float] = {}

        for list_name, results in ranked_lists.items():
            for rank, (item_id, score) in enumerate(results, start=1):
                # Track source info
                if item_id not in item_ranks:
                    item_ranks[item_id] = {}
                    item_scores[item_id] = {}

                item_ranks[item_id][list_name] = rank
                item_scores[item_id][list_name] = score

                # Calculate RRF contribution
                rrf_contribution = 1.0 / (self.k + rank)
                rrf_scores[item_id] = rrf_scores.get(item_id, 0.0) + rrf_contribution

        # Build results sorted by RRF score
        results = []
        for item_id, rrf_score in sorted(
            rrf_scores.items(), key=lambda x: x[1], reverse=True
        ):
            results.append(
                FusedResult(
                    item=item_id,
                    score=rrf_score,
                    source_ranks=item_ranks[item_id],
                    source_scores=item_scores[item_id],
                )
            )

        return results

    def fuse_lists(
        self,
        *ranked_lists: list[tuple[str, float]],
    ) -> list[tuple[str, float]]:
        """Fuse multiple ranked lists using positional arguments.

        Alternative to fuse() when source names aren't needed.

        Args:
            *ranked_lists: Ranked lists as positional arguments.

        Returns:
            Fused list of (item_id, rrf_score) tuples.
        """
        if not ranked_lists:
            return []

        # Convert to named lists
        named_lists = {f"list_{i}": lst for i, lst in enumerate(ranked_lists)}
        return self.fuse(**named_lists)

    def weighted_fuse(
        self,
        weights: dict[str, float],
        **ranked_lists: list[tuple[str, float]],
    ) -> list[tuple[str, float]]:
        """Fuse with weights for different sources.

        Weighted RRF: score(d) = Σ w_i / (k + rank_i(d))

        Args:
            weights: Dict mapping source names to weights.
                    Sources not in weights default to weight 1.0.
            **ranked_lists: Named ranked lists.

        Returns:
            Fused list of (item_id, weighted_rrf_score) tuples.
        """
        if not ranked_lists:
            return []

        rrf_scores: dict[str, float] = {}

        for list_name, results in ranked_lists.items():
            weight = weights.get(list_name, 1.0)

            for rank, (item_id, _) in enumerate(results, start=1):
                score = weight / (self.k + rank)
                rrf_scores[item_id] = rrf_scores.get(item_id, 0.0) + score

        sorted_results = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

        return sorted_results

    def interleave(
        self,
        **ranked_lists: list[tuple[str, float]],
    ) -> list[tuple[str, float]]:
        """Simple round-robin interleaving of ranked lists.

        Alternative fusion method that alternates between sources.
        Useful for diversity when RRF is not desired.

        Args:
            **ranked_lists: Named ranked lists.

        Returns:
            Interleaved list of (item_id, position_score) tuples.
        """
        if not ranked_lists:
            return []

        seen: set[str] = set()
        interleaved: list[tuple[str, float]] = []
        lists = list(ranked_lists.values())
        max_len = max(len(lst) for lst in lists) if lists else 0

        position = 1
        for i in range(max_len):
            for lst in lists:
                if i < len(lst):
                    item_id, _ = lst[i]
                    if item_id not in seen:
                        seen.add(item_id)
                        # Score decreases with position
                        interleaved.append((item_id, 1.0 / position))
                        position += 1

        return interleaved

    @staticmethod
    def normalize_scores(
        results: list[tuple[str, float]],
    ) -> list[tuple[str, float]]:
        """Normalize scores to [0, 1] range.

        Args:
            results: List of (item_id, score) tuples.

        Returns:
            Normalized results.
        """
        if not results:
            return []

        scores = [score for _, score in results]
        min_score = min(scores)
        max_score = max(scores)

        if max_score == min_score:
            return [(item_id, 1.0) for item_id, _ in results]

        return [
            (item_id, (score - min_score) / (max_score - min_score))
            for item_id, score in results
        ]

    @staticmethod
    def top_k(
        results: list[tuple[str, float]],
        k: int,
    ) -> list[tuple[str, float]]:
        """Get top-k results.

        Args:
            results: List of (item_id, score) tuples.
            k: Number of top results to return.

        Returns:
            Top-k results.
        """
        return results[:k]
