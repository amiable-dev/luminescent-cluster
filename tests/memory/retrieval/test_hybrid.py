# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Tests for Two-Stage Hybrid Retrieval.

Uses mocked models for fast unit tests.
Integration tests with real models are in benchmarks.

ADR Reference: ADR-003 Memory Architecture, Phase 3 (Two-Stage Retrieval)
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.memory.retrieval.bm25 import BM25Search
from src.memory.retrieval.fusion import RRFFusion
from src.memory.retrieval.hybrid import (
    HybridResult,
    HybridRetriever,
    RetrievalMetrics,
    create_hybrid_retriever,
)
from src.memory.retrieval.reranker import FallbackReranker
from src.memory.retrieval.vector_search import VectorSearch
from src.memory.schemas import Memory, MemoryType


class MockSentenceTransformer:
    """Mock sentence transformer for vector search."""

    def encode(
        self,
        sentences: list[str] | str,
        batch_size: int = 32,
        show_progress_bar: bool = False,
        normalize_embeddings: bool = True,
    ) -> np.ndarray:
        if isinstance(sentences, str):
            sentences = [sentences]

        embeddings = []
        for text in sentences:
            np.random.seed(hash(text) % (2**32))
            embedding = np.random.randn(384).astype(np.float32)
            if normalize_embeddings:
                embedding = embedding / np.linalg.norm(embedding)
            embeddings.append(embedding)

        return np.array(embeddings, dtype=np.float32)


@pytest.fixture
def mock_vector_search() -> VectorSearch:
    """Create a VectorSearch with mocked model."""
    with patch(
        "src.memory.retrieval.vector_search.VectorSearch._load_model"
    ) as mock_load:
        mock_load.return_value = MockSentenceTransformer()
        vs = VectorSearch(lazy_load=True)
        vs._model = MockSentenceTransformer()
        return vs


@pytest.fixture
def sample_memories() -> list[Memory]:
    """Create sample memories for testing."""
    now = datetime.now(timezone.utc)
    return [
        Memory(
            user_id="user-1",
            content="The database uses PostgreSQL for persistent storage",
            memory_type=MemoryType.FACT,
            source="test",
            created_at=now,
            last_accessed_at=now,
            metadata={"memory_id": "mem-1"},
        ),
        Memory(
            user_id="user-1",
            content="Redis is used for caching frequently accessed data",
            memory_type=MemoryType.FACT,
            source="test",
            created_at=now,
            last_accessed_at=now,
            metadata={"memory_id": "mem-2"},
        ),
        Memory(
            user_id="user-1",
            content="The API uses JWT tokens for authentication",
            memory_type=MemoryType.FACT,
            source="test",
            created_at=now,
            last_accessed_at=now,
            metadata={"memory_id": "mem-3"},
        ),
        Memory(
            user_id="user-1",
            content="User prefers dark mode for the editor",
            memory_type=MemoryType.PREFERENCE,
            source="test",
            created_at=now,
            last_accessed_at=now,
            metadata={"memory_id": "mem-4"},
        ),
        Memory(
            user_id="user-1",
            content="Database migrations should be run before deployment",
            memory_type=MemoryType.DECISION,
            source="test",
            created_at=now,
            last_accessed_at=now,
            metadata={"memory_id": "mem-5"},
        ),
    ]


@pytest.fixture
def hybrid_retriever(mock_vector_search: VectorSearch) -> HybridRetriever:
    """Create a HybridRetriever with mocked components."""
    return HybridRetriever(
        bm25=BM25Search(),
        vector=mock_vector_search,
        fusion=RRFFusion(k=60),
        reranker=FallbackReranker(),  # Use fallback for fast tests
    )


class TestHybridRetrieverIndexing:
    """Tests for indexing operations."""

    def test_index_memories(
        self,
        hybrid_retriever: HybridRetriever,
        sample_memories: list[Memory],
    ) -> None:
        """Test indexing memories builds both indexes."""
        hybrid_retriever.index_memories("user-1", sample_memories)

        assert hybrid_retriever.has_index("user-1")
        stats = hybrid_retriever.index_stats("user-1")
        assert stats["bm25_docs"] == 5
        assert stats["vector_docs"] == 5

    def test_index_memories_with_ids(
        self,
        hybrid_retriever: HybridRetriever,
        sample_memories: list[Memory],
    ) -> None:
        """Test indexing with explicit IDs."""
        memory_ids = ["id-a", "id-b", "id-c", "id-d", "id-e"]
        hybrid_retriever.index_memories("user-1", sample_memories, memory_ids)

        assert hybrid_retriever.has_index("user-1")

    def test_add_memory(
        self,
        hybrid_retriever: HybridRetriever,
        sample_memories: list[Memory],
    ) -> None:
        """Test adding a single memory."""
        hybrid_retriever.index_memories("user-1", sample_memories[:2])
        initial_stats = hybrid_retriever.index_stats("user-1")

        hybrid_retriever.add_memory("user-1", sample_memories[2], "new-mem")

        new_stats = hybrid_retriever.index_stats("user-1")
        assert new_stats["bm25_docs"] == initial_stats["bm25_docs"] + 1
        assert new_stats["vector_docs"] == initial_stats["vector_docs"] + 1

    def test_remove_memory(
        self,
        hybrid_retriever: HybridRetriever,
        sample_memories: list[Memory],
    ) -> None:
        """Test removing a memory."""
        hybrid_retriever.index_memories("user-1", sample_memories)
        initial_stats = hybrid_retriever.index_stats("user-1")

        removed = hybrid_retriever.remove_memory("user-1", "mem-1")

        assert removed is True
        new_stats = hybrid_retriever.index_stats("user-1")
        assert new_stats["bm25_docs"] == initial_stats["bm25_docs"] - 1

    def test_clear_index(
        self,
        hybrid_retriever: HybridRetriever,
        sample_memories: list[Memory],
    ) -> None:
        """Test clearing indexes."""
        hybrid_retriever.index_memories("user-1", sample_memories)
        assert hybrid_retriever.has_index("user-1")

        hybrid_retriever.clear_index("user-1")
        assert not hybrid_retriever.has_index("user-1")


class TestHybridRetrieverRetrieve:
    """Tests for retrieval operations."""

    @pytest.mark.asyncio
    async def test_retrieve_basic(
        self,
        hybrid_retriever: HybridRetriever,
        sample_memories: list[Memory],
    ) -> None:
        """Test basic retrieval."""
        hybrid_retriever.index_memories("user-1", sample_memories)

        results, metrics = await hybrid_retriever.retrieve(
            "database storage", "user-1", top_k=5
        )

        assert len(results) > 0
        assert isinstance(metrics, RetrievalMetrics)
        for result in results:
            assert isinstance(result, HybridResult)
            assert isinstance(result.memory, Memory)
            assert isinstance(result.score, float)

    @pytest.mark.asyncio
    async def test_retrieve_top_k_limit(
        self,
        hybrid_retriever: HybridRetriever,
        sample_memories: list[Memory],
    ) -> None:
        """Test top_k limit is respected."""
        hybrid_retriever.index_memories("user-1", sample_memories)

        results, _ = await hybrid_retriever.retrieve(
            "database", "user-1", top_k=2
        )

        assert len(results) <= 2

    @pytest.mark.asyncio
    async def test_retrieve_sorted_by_score(
        self,
        hybrid_retriever: HybridRetriever,
        sample_memories: list[Memory],
    ) -> None:
        """Test results are sorted by score descending."""
        hybrid_retriever.index_memories("user-1", sample_memories)

        results, _ = await hybrid_retriever.retrieve(
            "database", "user-1", top_k=5
        )

        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_retrieve_empty_index(
        self, hybrid_retriever: HybridRetriever
    ) -> None:
        """Test retrieval from empty index."""
        results, metrics = await hybrid_retriever.retrieve(
            "database", "user-1", top_k=5
        )

        assert len(results) == 0
        assert metrics.final_results == 0

    @pytest.mark.asyncio
    async def test_retrieve_nonexistent_user(
        self,
        hybrid_retriever: HybridRetriever,
        sample_memories: list[Memory],
    ) -> None:
        """Test retrieval for nonexistent user."""
        hybrid_retriever.index_memories("user-1", sample_memories)

        results, _ = await hybrid_retriever.retrieve(
            "database", "nonexistent", top_k=5
        )

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_retrieve_simple(
        self,
        hybrid_retriever: HybridRetriever,
        sample_memories: list[Memory],
    ) -> None:
        """Test simplified retrieval."""
        hybrid_retriever.index_memories("user-1", sample_memories)

        results = await hybrid_retriever.retrieve_simple(
            "database", "user-1", top_k=5
        )

        assert len(results) > 0
        for memory, score in results:
            assert isinstance(memory, Memory)
            assert isinstance(score, float)


class TestHybridRetrieverMetrics:
    """Tests for retrieval metrics."""

    @pytest.mark.asyncio
    async def test_metrics_structure(
        self,
        hybrid_retriever: HybridRetriever,
        sample_memories: list[Memory],
    ) -> None:
        """Test metrics structure."""
        hybrid_retriever.index_memories("user-1", sample_memories)

        _, metrics = await hybrid_retriever.retrieve(
            "database", "user-1", top_k=5
        )

        assert metrics.total_time_ms > 0
        assert metrics.stage1_time_ms >= 0
        assert metrics.stage2_time_ms >= 0
        assert metrics.bm25_candidates >= 0
        assert metrics.vector_candidates >= 0

    @pytest.mark.asyncio
    async def test_metrics_latency_under_1s(
        self,
        hybrid_retriever: HybridRetriever,
        sample_memories: list[Memory],
    ) -> None:
        """Test retrieval latency is under 1 second."""
        hybrid_retriever.index_memories("user-1", sample_memories)

        _, metrics = await hybrid_retriever.retrieve(
            "database", "user-1", top_k=10
        )

        # Exit criteria: latency < 1s
        assert metrics.total_time_ms < 1000

    @pytest.mark.asyncio
    async def test_metrics_candidate_counts(
        self,
        hybrid_retriever: HybridRetriever,
        sample_memories: list[Memory],
    ) -> None:
        """Test candidate count metrics."""
        hybrid_retriever.index_memories("user-1", sample_memories)

        _, metrics = await hybrid_retriever.retrieve(
            "database", "user-1", top_k=5
        )

        # Should have candidates from both BM25 and vector
        assert metrics.bm25_candidates >= 0
        assert metrics.vector_candidates >= 0
        assert metrics.fused_candidates >= 0


class TestHybridRetrieverSourceTracking:
    """Tests for source score tracking."""

    @pytest.mark.asyncio
    async def test_source_scores_tracked(
        self,
        hybrid_retriever: HybridRetriever,
        sample_memories: list[Memory],
    ) -> None:
        """Test source scores are tracked in results."""
        hybrid_retriever.index_memories("user-1", sample_memories)

        results, _ = await hybrid_retriever.retrieve(
            "database", "user-1", top_k=5
        )

        for result in results:
            assert "reranker" in result.source_scores
            # May or may not have bm25/vector depending on fusion

    @pytest.mark.asyncio
    async def test_source_ranks_tracked(
        self,
        hybrid_retriever: HybridRetriever,
        sample_memories: list[Memory],
    ) -> None:
        """Test source ranks are tracked in results."""
        hybrid_retriever.index_memories("user-1", sample_memories)

        results, _ = await hybrid_retriever.retrieve(
            "database", "user-1", top_k=5
        )

        for result in results:
            assert isinstance(result.source_ranks, dict)


class TestHybridRetrieverConfiguration:
    """Tests for configuration options."""

    def test_custom_weights(self, mock_vector_search: VectorSearch) -> None:
        """Test custom BM25/vector weights."""
        retriever = HybridRetriever(
            vector=mock_vector_search,
            reranker=FallbackReranker(),
            bm25_weight=2.0,
            vector_weight=1.0,
        )

        assert retriever.bm25_weight == 2.0
        assert retriever.vector_weight == 1.0

    def test_without_query_rewriter(
        self, mock_vector_search: VectorSearch
    ) -> None:
        """Test without query rewriter."""
        retriever = HybridRetriever(
            vector=mock_vector_search,
            reranker=FallbackReranker(),
            query_rewriter=None,
        )

        assert retriever.query_rewriter is None

    @pytest.mark.asyncio
    async def test_disable_reranker(
        self,
        hybrid_retriever: HybridRetriever,
        sample_memories: list[Memory],
    ) -> None:
        """Test disabling reranker."""
        hybrid_retriever.index_memories("user-1", sample_memories)

        _, metrics = await hybrid_retriever.retrieve(
            "database", "user-1", top_k=5, use_reranker=False
        )

        # Fallback reranker should be used
        assert not metrics.reranker_used

    @pytest.mark.asyncio
    async def test_disable_query_expansion(
        self,
        hybrid_retriever: HybridRetriever,
        sample_memories: list[Memory],
    ) -> None:
        """Test disabling query expansion."""
        hybrid_retriever.index_memories("user-1", sample_memories)

        _, metrics = await hybrid_retriever.retrieve(
            "database", "user-1", top_k=5, expand_query=False
        )

        assert not metrics.query_expanded


class TestHybridRetrieverStats:
    """Tests for index statistics."""

    def test_stats_populated(
        self,
        hybrid_retriever: HybridRetriever,
        sample_memories: list[Memory],
    ) -> None:
        """Test stats for populated index."""
        hybrid_retriever.index_memories("user-1", sample_memories)

        stats = hybrid_retriever.index_stats("user-1")

        assert stats["bm25_docs"] == 5
        assert stats["vector_docs"] == 5
        assert stats["bm25_vocab_size"] > 0
        assert stats["vector_dim"] == 384

    def test_stats_empty(self, hybrid_retriever: HybridRetriever) -> None:
        """Test stats for nonexistent user."""
        stats = hybrid_retriever.index_stats("nonexistent")

        assert stats["bm25_docs"] == 0
        assert stats["vector_docs"] == 0


class TestCreateHybridRetriever:
    """Tests for factory function."""

    def test_create_with_cross_encoder(self) -> None:
        """Test creating with cross-encoder."""
        retriever = create_hybrid_retriever(use_cross_encoder=True)

        # Should have cross-encoder reranker
        from src.memory.retrieval.reranker import CrossEncoderReranker
        assert isinstance(retriever.reranker, CrossEncoderReranker)

    def test_create_without_cross_encoder(self) -> None:
        """Test creating without cross-encoder."""
        retriever = create_hybrid_retriever(use_cross_encoder=False)

        assert isinstance(retriever.reranker, FallbackReranker)

    def test_create_with_query_rewriter(self) -> None:
        """Test creating with query rewriter."""
        retriever = create_hybrid_retriever(use_query_rewriter=True)

        assert retriever.query_rewriter is not None

    def test_create_without_query_rewriter(self) -> None:
        """Test creating without query rewriter."""
        retriever = create_hybrid_retriever(use_query_rewriter=False)

        assert retriever.query_rewriter is None

    def test_create_custom_weights(self) -> None:
        """Test creating with custom weights."""
        retriever = create_hybrid_retriever(
            bm25_weight=2.0, vector_weight=0.5
        )

        assert retriever.bm25_weight == 2.0
        assert retriever.vector_weight == 0.5


class TestHybridResult:
    """Tests for HybridResult dataclass."""

    def test_hybrid_result_creation(self) -> None:
        """Test creating a HybridResult."""
        now = datetime.now(timezone.utc)
        memory = Memory(
            user_id="user-1",
            content="Test content",
            memory_type=MemoryType.FACT,
            source="test",
            created_at=now,
            last_accessed_at=now,
        )

        result = HybridResult(
            memory=memory,
            score=0.95,
            memory_id="mem-1",
            source_scores={"bm25": 0.8, "vector": 0.9},
            source_ranks={"bm25": 1, "vector": 2},
        )

        assert result.memory == memory
        assert result.score == 0.95
        assert result.memory_id == "mem-1"
        assert result.source_scores["bm25"] == 0.8
        assert result.source_ranks["vector"] == 2


class TestRetrievalMetrics:
    """Tests for RetrievalMetrics dataclass."""

    def test_metrics_defaults(self) -> None:
        """Test default metrics values."""
        metrics = RetrievalMetrics()

        assert metrics.total_time_ms == 0.0
        assert metrics.stage1_time_ms == 0.0
        assert metrics.stage2_time_ms == 0.0
        assert metrics.bm25_candidates == 0
        assert metrics.vector_candidates == 0
        assert metrics.fused_candidates == 0
        assert metrics.final_results == 0
        assert not metrics.query_expanded
        assert not metrics.reranker_used

    def test_metrics_custom_values(self) -> None:
        """Test custom metrics values."""
        metrics = RetrievalMetrics(
            total_time_ms=100.0,
            stage1_time_ms=50.0,
            stage2_time_ms=50.0,
            bm25_candidates=30,
            vector_candidates=40,
            fused_candidates=60,
            final_results=10,
            query_expanded=True,
            reranker_used=True,
        )

        assert metrics.total_time_ms == 100.0
        assert metrics.final_results == 10
        assert metrics.query_expanded
        assert metrics.reranker_used
