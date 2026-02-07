# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Tests for cross-encoder reranking.

Uses mocked cross-encoder for fast unit tests.
Integration tests with real models are in benchmarks.

ADR Reference: ADR-003 Memory Architecture, Phase 3 (Two-Stage Retrieval)
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from luminescent_cluster.memory.retrieval.reranker import (
    CrossEncoderReranker,
    FallbackReranker,
    RerankResult,
    get_reranker,
)
from luminescent_cluster.memory.schemas import Memory, MemoryType


class MockCrossEncoder:
    """Mock cross-encoder for testing."""

    def __init__(self, model_name: str = "test-model"):
        self.model_name = model_name

    def predict(
        self,
        sentences: list[tuple[str, str]] | list[list[str]],
        batch_size: int = 32,
        show_progress_bar: bool = False,
    ) -> np.ndarray:
        """Generate deterministic mock scores based on content overlap."""
        scores = []
        for query, doc in sentences:
            # Simple overlap-based scoring
            query_words = set(query.lower().split())
            doc_words = set(doc.lower().split())
            overlap = len(query_words & doc_words)
            total = len(query_words | doc_words)
            score = overlap / total if total > 0 else 0.0
            # Scale to typical cross-encoder range [-5, 5]
            scores.append(score * 10 - 5)
        return np.array(scores, dtype=np.float32)


@pytest.fixture
def mock_cross_encoder() -> MockCrossEncoder:
    """Create a mock cross-encoder."""
    return MockCrossEncoder()


@pytest.fixture
def reranker(mock_cross_encoder: MockCrossEncoder) -> CrossEncoderReranker:
    """Create a CrossEncoderReranker with mocked model."""
    with patch(
        "luminescent_cluster.memory.retrieval.reranker.CrossEncoderReranker._load_model"
    ) as mock_load:
        mock_load.return_value = mock_cross_encoder
        r = CrossEncoderReranker(lazy_load=True)
        r._model = mock_cross_encoder
        return r


@pytest.fixture
def sample_candidates() -> list[tuple[str, Memory, float]]:
    """Create sample candidates for reranking."""
    now = datetime.now(timezone.utc)
    return [
        (
            "mem-1",
            Memory(
                user_id="user-1",
                content="The database uses PostgreSQL for persistent storage",
                memory_type=MemoryType.FACT,
                source="test",
                created_at=now,
                last_accessed_at=now,
            ),
            0.8,
        ),
        (
            "mem-2",
            Memory(
                user_id="user-1",
                content="Redis is used for caching frequently accessed data",
                memory_type=MemoryType.FACT,
                source="test",
                created_at=now,
                last_accessed_at=now,
            ),
            0.7,
        ),
        (
            "mem-3",
            Memory(
                user_id="user-1",
                content="The API uses JWT tokens for authentication",
                memory_type=MemoryType.FACT,
                source="test",
                created_at=now,
                last_accessed_at=now,
            ),
            0.6,
        ),
        (
            "mem-4",
            Memory(
                user_id="user-1",
                content="User prefers dark mode for the editor",
                memory_type=MemoryType.PREFERENCE,
                source="test",
                created_at=now,
                last_accessed_at=now,
            ),
            0.5,
        ),
    ]


class TestCrossEncoderReranker:
    """Tests for CrossEncoderReranker."""

    def test_rerank_basic(
        self,
        reranker: CrossEncoderReranker,
        sample_candidates: list[tuple[str, Memory, float]],
    ) -> None:
        """Test basic reranking."""
        results = reranker.rerank("database storage", sample_candidates, top_k=4)

        assert len(results) == 4
        # Results should be RerankResult objects
        for result in results:
            assert isinstance(result, RerankResult)
            assert isinstance(result.memory_id, str)
            assert isinstance(result.memory, Memory)
            assert isinstance(result.score, float)

    def test_rerank_top_k_limit(
        self,
        reranker: CrossEncoderReranker,
        sample_candidates: list[tuple[str, Memory, float]],
    ) -> None:
        """Test top_k limit is respected."""
        results = reranker.rerank("database", sample_candidates, top_k=2)
        assert len(results) == 2

    def test_rerank_sorted_by_score(
        self,
        reranker: CrossEncoderReranker,
        sample_candidates: list[tuple[str, Memory, float]],
    ) -> None:
        """Test results are sorted by cross-encoder score descending."""
        results = reranker.rerank("storage", sample_candidates, top_k=4)

        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_rerank_preserves_original_info(
        self,
        reranker: CrossEncoderReranker,
        sample_candidates: list[tuple[str, Memory, float]],
    ) -> None:
        """Test original rank and score are preserved."""
        results = reranker.rerank("database", sample_candidates, top_k=4)

        for result in results:
            # Original rank should be 1-indexed
            assert result.original_rank >= 1
            assert result.original_rank <= len(sample_candidates)
            # Original score should match input
            original = sample_candidates[result.original_rank - 1]
            assert result.original_score == original[2]

    def test_rerank_empty_candidates(self, reranker: CrossEncoderReranker) -> None:
        """Test reranking empty candidates."""
        results = reranker.rerank("query", [], top_k=10)
        assert results == []

    def test_rerank_simple(
        self,
        reranker: CrossEncoderReranker,
        sample_candidates: list[tuple[str, Memory, float]],
    ) -> None:
        """Test rerank_simple returns (memory_id, score) tuples."""
        results = reranker.rerank_simple("database", sample_candidates, top_k=4)

        assert len(results) == 4
        for mem_id, score in results:
            assert isinstance(mem_id, str)
            assert isinstance(score, float)

    def test_rerank_with_memories(
        self,
        reranker: CrossEncoderReranker,
        sample_candidates: list[tuple[str, Memory, float]],
    ) -> None:
        """Test rerank_with_memories returns (Memory, score) tuples."""
        results = reranker.rerank_with_memories("database", sample_candidates, top_k=4)

        assert len(results) == 4
        for memory, score in results:
            assert isinstance(memory, Memory)
            assert isinstance(score, float)


class TestCrossEncoderScoring:
    """Tests for scoring methods."""

    def test_score_pair(self, reranker: CrossEncoderReranker) -> None:
        """Test scoring a single pair."""
        score = reranker.score_pair("database storage", "The database stores data")
        assert isinstance(score, float)

    def test_score_pairs(self, reranker: CrossEncoderReranker) -> None:
        """Test scoring multiple pairs."""
        pairs = [
            ("database", "PostgreSQL database"),
            ("cache", "Redis caching layer"),
            ("auth", "JWT authentication"),
        ]
        scores = reranker.score_pairs(pairs)

        assert len(scores) == 3
        for score in scores:
            assert isinstance(score, float)

    def test_score_pairs_empty(self, reranker: CrossEncoderReranker) -> None:
        """Test scoring empty pairs list."""
        scores = reranker.score_pairs([])
        assert scores == []


class TestCrossEncoderLoadState:
    """Tests for model loading state."""

    def test_is_loaded_before_use(self) -> None:
        """Test is_loaded before model is used."""
        with patch(
            "luminescent_cluster.memory.retrieval.reranker.CrossEncoderReranker._load_model"
        ) as mock_load:
            mock_load.return_value = MockCrossEncoder()
            reranker = CrossEncoderReranker(lazy_load=True)
            assert not reranker.is_loaded()

    def test_is_loaded_after_use(self, reranker: CrossEncoderReranker) -> None:
        """Test is_loaded after model is used."""
        # Model is already loaded in fixture
        assert reranker.is_loaded()


class TestFallbackReranker:
    """Tests for FallbackReranker."""

    @pytest.fixture
    def fallback_reranker(self) -> FallbackReranker:
        """Create a FallbackReranker."""
        return FallbackReranker()

    def test_rerank_sorts_by_original_score(
        self,
        fallback_reranker: FallbackReranker,
        sample_candidates: list[tuple[str, Memory, float]],
    ) -> None:
        """Test fallback sorts by original score."""
        # Shuffle candidates
        shuffled = sample_candidates.copy()
        shuffled.reverse()

        results = fallback_reranker.rerank("query", shuffled, top_k=4)

        # Should be sorted by original score descending
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_rerank_top_k_limit(
        self,
        fallback_reranker: FallbackReranker,
        sample_candidates: list[tuple[str, Memory, float]],
    ) -> None:
        """Test top_k limit is respected."""
        results = fallback_reranker.rerank("query", sample_candidates, top_k=2)
        assert len(results) == 2

    def test_rerank_uses_original_score_as_score(
        self,
        fallback_reranker: FallbackReranker,
        sample_candidates: list[tuple[str, Memory, float]],
    ) -> None:
        """Test that score equals original_score in fallback."""
        results = fallback_reranker.rerank("query", sample_candidates, top_k=4)

        for result in results:
            assert result.score == result.original_score

    def test_rerank_empty_candidates(self, fallback_reranker: FallbackReranker) -> None:
        """Test reranking empty candidates."""
        results = fallback_reranker.rerank("query", [], top_k=10)
        assert results == []

    def test_rerank_simple(
        self,
        fallback_reranker: FallbackReranker,
        sample_candidates: list[tuple[str, Memory, float]],
    ) -> None:
        """Test rerank_simple returns (memory_id, score) tuples."""
        results = fallback_reranker.rerank_simple("query", sample_candidates, top_k=4)

        assert len(results) == 4
        for mem_id, score in results:
            assert isinstance(mem_id, str)
            assert isinstance(score, float)

    def test_rerank_with_memories(
        self,
        fallback_reranker: FallbackReranker,
        sample_candidates: list[tuple[str, Memory, float]],
    ) -> None:
        """Test rerank_with_memories returns (Memory, score) tuples."""
        results = fallback_reranker.rerank_with_memories("query", sample_candidates, top_k=4)

        assert len(results) == 4
        for memory, score in results:
            assert isinstance(memory, Memory)
            assert isinstance(score, float)

    def test_is_loaded_always_true(self, fallback_reranker: FallbackReranker) -> None:
        """Test fallback is always 'loaded'."""
        assert fallback_reranker.is_loaded()


class TestGetReranker:
    """Tests for get_reranker factory function."""

    def test_get_cross_encoder_reranker(self) -> None:
        """Test getting CrossEncoderReranker."""
        reranker = get_reranker(use_cross_encoder=True)
        assert isinstance(reranker, CrossEncoderReranker)

    def test_get_fallback_reranker(self) -> None:
        """Test getting FallbackReranker."""
        reranker = get_reranker(use_cross_encoder=False)
        assert isinstance(reranker, FallbackReranker)

    def test_get_reranker_custom_model(self) -> None:
        """Test getting CrossEncoderReranker with custom model."""
        reranker = get_reranker(use_cross_encoder=True, model_name="custom-model")
        assert isinstance(reranker, CrossEncoderReranker)
        assert reranker.model_name == "custom-model"


class TestRerankResult:
    """Tests for RerankResult dataclass."""

    def test_rerank_result_creation(self) -> None:
        """Test creating a RerankResult."""
        now = datetime.now(timezone.utc)
        memory = Memory(
            user_id="user-1",
            content="Test content",
            memory_type=MemoryType.FACT,
            source="test",
            created_at=now,
            last_accessed_at=now,
        )

        result = RerankResult(
            memory_id="mem-1",
            memory=memory,
            score=0.95,
            original_rank=1,
            original_score=0.8,
        )

        assert result.memory_id == "mem-1"
        assert result.memory == memory
        assert result.score == 0.95
        assert result.original_rank == 1
        assert result.original_score == 0.8

    def test_rerank_result_fields_accessible(self) -> None:
        """Test all fields are accessible."""
        now = datetime.now(timezone.utc)
        memory = Memory(
            user_id="user-1",
            content="Test",
            memory_type=MemoryType.FACT,
            source="test",
            created_at=now,
            last_accessed_at=now,
        )

        result = RerankResult(
            memory_id="id",
            memory=memory,
            score=1.0,
            original_rank=5,
            original_score=0.5,
        )

        # All fields should be accessible
        _ = result.memory_id
        _ = result.memory
        _ = result.score
        _ = result.original_rank
        _ = result.original_score
