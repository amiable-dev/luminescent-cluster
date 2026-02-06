# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Cross-encoder reranking for Two-Stage Retrieval Architecture.

Implements cross-encoder based reranking using sentence-transformers
as part of ADR-003 Phase 3 Stage 2.

Cross-encoders provide more accurate relevance scores than bi-encoders
by jointly encoding query-document pairs. Used after initial candidate
retrieval to improve final ranking quality.

Model: cross-encoder/ms-marco-MiniLM-L-6-v2 (fast, good quality)

ADR Reference: ADR-003 Memory Architecture, Phase 3 (Two-Stage Retrieval)
"""

import logging
from dataclasses import dataclass
from typing import Optional, Protocol

import numpy as np
from numpy.typing import NDArray

from luminescent_cluster.memory.schemas import Memory

logger = logging.getLogger(__name__)


class CrossEncoderModel(Protocol):
    """Protocol for cross-encoder models."""

    def predict(
        self,
        sentences: list[tuple[str, str]] | list[list[str]],
        batch_size: int = 32,
        show_progress_bar: bool = False,
    ) -> NDArray[np.float32]: ...


@dataclass
class RerankResult:
    """A reranking result.

    Attributes:
        memory_id: ID of the memory.
        memory: The Memory object.
        score: Cross-encoder relevance score.
        original_rank: Original rank before reranking.
        original_score: Original score before reranking.
    """

    memory_id: str
    memory: Memory
    score: float
    original_rank: int
    original_score: float


class CrossEncoderReranker:
    """Cross-encoder reranking for memory retrieval.

    Provides reranking using cross-encoder models that jointly
    encode query-document pairs for more accurate relevance scoring.

    Example:
        >>> reranker = CrossEncoderReranker()
        >>> candidates = [(mem_id, memory, initial_score), ...]
        >>> reranked = reranker.rerank("database config", candidates, top_k=10)
        >>> for result in reranked:
        ...     print(f"{result.memory_id}: {result.score:.4f}")

    Attributes:
        model_name: Name of the cross-encoder model.
    """

    # Default model - fast and good quality for MS MARCO
    DEFAULT_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        lazy_load: bool = True,
    ):
        """Initialize the reranker.

        Args:
            model_name: Cross-encoder model name.
            lazy_load: If True, load model on first use.
        """
        self.model_name = model_name
        self._model: Optional[CrossEncoderModel] = None
        self._lazy_load = lazy_load

        if not lazy_load:
            self._load_model()

    def _load_model(self) -> CrossEncoderModel:
        """Load the cross-encoder model.

        Returns:
            Loaded cross-encoder model.
        """
        if self._model is not None:
            return self._model

        try:
            from sentence_transformers import CrossEncoder

            logger.info(f"Loading cross-encoder model: {self.model_name}")
            self._model = CrossEncoder(self.model_name)
            logger.info("Cross-encoder model loaded successfully")
            return self._model
        except ImportError as e:
            raise ImportError(
                "sentence-transformers is required for CrossEncoderReranker. "
                "Install with: pip install sentence-transformers"
            ) from e

    @property
    def model(self) -> CrossEncoderModel:
        """Get the model, loading if necessary."""
        if self._model is None:
            return self._load_model()
        return self._model

    def rerank(
        self,
        query: str,
        candidates: list[tuple[str, Memory, float]],
        top_k: int = 10,
        batch_size: int = 32,
    ) -> list[RerankResult]:
        """Rerank candidates using cross-encoder.

        Args:
            query: Search query.
            candidates: List of (memory_id, Memory, original_score) tuples.
            top_k: Number of top results to return.
            batch_size: Batch size for inference.

        Returns:
            List of RerankResult sorted by cross-encoder score descending.
        """
        if not candidates:
            return []

        # Prepare query-document pairs
        pairs: list[tuple[str, str]] = []
        for _, memory, _ in candidates:
            pairs.append((query, memory.content))

        # Get cross-encoder scores
        scores = self.model.predict(pairs, batch_size=batch_size, show_progress_bar=False)

        # Build results with scores
        results: list[RerankResult] = []
        for i, (mem_id, memory, original_score) in enumerate(candidates):
            results.append(
                RerankResult(
                    memory_id=mem_id,
                    memory=memory,
                    score=float(scores[i]),
                    original_rank=i + 1,
                    original_score=original_score,
                )
            )

        # Sort by cross-encoder score descending
        results.sort(key=lambda x: x.score, reverse=True)

        return results[:top_k]

    def rerank_simple(
        self,
        query: str,
        candidates: list[tuple[str, Memory, float]],
        top_k: int = 10,
    ) -> list[tuple[str, float]]:
        """Rerank and return simple (memory_id, score) tuples.

        Args:
            query: Search query.
            candidates: List of (memory_id, Memory, original_score) tuples.
            top_k: Number of top results to return.

        Returns:
            List of (memory_id, score) tuples sorted by score descending.
        """
        results = self.rerank(query, candidates, top_k)
        return [(r.memory_id, r.score) for r in results]

    def rerank_with_memories(
        self,
        query: str,
        candidates: list[tuple[str, Memory, float]],
        top_k: int = 10,
    ) -> list[tuple[Memory, float]]:
        """Rerank and return (Memory, score) tuples.

        Args:
            query: Search query.
            candidates: List of (memory_id, Memory, original_score) tuples.
            top_k: Number of top results to return.

        Returns:
            List of (Memory, score) tuples sorted by score descending.
        """
        results = self.rerank(query, candidates, top_k)
        return [(r.memory, r.score) for r in results]

    def score_pair(self, query: str, document: str) -> float:
        """Score a single query-document pair.

        Args:
            query: Search query.
            document: Document content.

        Returns:
            Cross-encoder relevance score.
        """
        scores = self.model.predict([(query, document)], show_progress_bar=False)
        return float(scores[0])

    def score_pairs(
        self,
        pairs: list[tuple[str, str]],
        batch_size: int = 32,
    ) -> list[float]:
        """Score multiple query-document pairs.

        Args:
            pairs: List of (query, document) tuples.
            batch_size: Batch size for inference.

        Returns:
            List of relevance scores.
        """
        if not pairs:
            return []

        scores = self.model.predict(pairs, batch_size=batch_size, show_progress_bar=False)
        return [float(s) for s in scores]

    def is_loaded(self) -> bool:
        """Check if the model is loaded.

        Returns:
            True if model is loaded.
        """
        return self._model is not None


class FallbackReranker:
    """Fallback reranker that passes through original scores.

    Used when cross-encoder is not available or not needed.
    """

    def rerank(
        self,
        query: str,
        candidates: list[tuple[str, Memory, float]],
        top_k: int = 10,
        batch_size: int = 32,
    ) -> list[RerankResult]:
        """Pass through candidates sorted by original score.

        Args:
            query: Search query (ignored).
            candidates: List of (memory_id, Memory, original_score) tuples.
            top_k: Number of top results to return.
            batch_size: Batch size (ignored).

        Returns:
            List of RerankResult sorted by original score descending.
        """
        if not candidates:
            return []

        # Sort by original score
        sorted_candidates = sorted(candidates, key=lambda x: x[2], reverse=True)

        results: list[RerankResult] = []
        for i, (mem_id, memory, original_score) in enumerate(sorted_candidates[:top_k]):
            results.append(
                RerankResult(
                    memory_id=mem_id,
                    memory=memory,
                    score=original_score,
                    original_rank=i + 1,
                    original_score=original_score,
                )
            )

        return results

    def rerank_simple(
        self,
        query: str,
        candidates: list[tuple[str, Memory, float]],
        top_k: int = 10,
    ) -> list[tuple[str, float]]:
        """Pass through candidates sorted by original score.

        Args:
            query: Search query (ignored).
            candidates: List of (memory_id, Memory, original_score) tuples.
            top_k: Number of top results to return.

        Returns:
            List of (memory_id, score) tuples.
        """
        results = self.rerank(query, candidates, top_k)
        return [(r.memory_id, r.score) for r in results]

    def rerank_with_memories(
        self,
        query: str,
        candidates: list[tuple[str, Memory, float]],
        top_k: int = 10,
    ) -> list[tuple[Memory, float]]:
        """Pass through candidates sorted by original score.

        Args:
            query: Search query (ignored).
            candidates: List of (memory_id, Memory, original_score) tuples.
            top_k: Number of top results to return.

        Returns:
            List of (Memory, score) tuples.
        """
        results = self.rerank(query, candidates, top_k)
        return [(r.memory, r.score) for r in results]

    def is_loaded(self) -> bool:
        """Fallback is always 'loaded'.

        Returns:
            True.
        """
        return True


def get_reranker(
    use_cross_encoder: bool = True,
    model_name: str = CrossEncoderReranker.DEFAULT_MODEL,
) -> CrossEncoderReranker | FallbackReranker:
    """Get a reranker instance.

    Args:
        use_cross_encoder: If True, use cross-encoder. If False, use fallback.
        model_name: Cross-encoder model name.

    Returns:
        Reranker instance.
    """
    if use_cross_encoder:
        return CrossEncoderReranker(model_name=model_name)
    return FallbackReranker()
