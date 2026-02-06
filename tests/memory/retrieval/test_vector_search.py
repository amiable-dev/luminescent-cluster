# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Tests for dense vector semantic search.

Uses mocked embeddings for fast unit tests.
Integration tests with real models are in benchmarks.

ADR Reference: ADR-003 Memory Architecture, Phase 3 (Two-Stage Retrieval)
"""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from numpy.typing import NDArray

from luminescent_cluster.memory.retrieval.vector_search import VectorIndex, VectorSearch
from luminescent_cluster.memory.schemas import Memory, MemoryType


class MockSentenceTransformer:
    """Mock sentence transformer for testing."""

    def __init__(self, model_name: str = "test-model"):
        self.model_name = model_name
        self._embedding_dim = 384

    def encode(
        self,
        sentences: list[str] | str,
        batch_size: int = 32,
        show_progress_bar: bool = False,
        normalize_embeddings: bool = True,
    ) -> NDArray[np.float32]:
        """Generate deterministic mock embeddings based on text content."""
        if isinstance(sentences, str):
            sentences = [sentences]

        embeddings = []
        for text in sentences:
            # Create deterministic embedding based on text hash
            np.random.seed(hash(text) % (2**32))
            embedding = np.random.randn(self._embedding_dim).astype(np.float32)
            if normalize_embeddings:
                embedding = embedding / np.linalg.norm(embedding)
            embeddings.append(embedding)

        return np.array(embeddings, dtype=np.float32)


@pytest.fixture
def mock_transformer() -> MagicMock:
    """Create a mock sentence transformer."""
    return MockSentenceTransformer()


@pytest.fixture
def vector_search(mock_transformer: MockSentenceTransformer) -> VectorSearch:
    """Create a VectorSearch instance with mocked model."""
    with patch(
        "luminescent_cluster.memory.retrieval.vector_search.VectorSearch._load_model"
    ) as mock_load:
        mock_load.return_value = mock_transformer
        search = VectorSearch(lazy_load=True)
        search._model = mock_transformer
        return search


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


class TestVectorSearchEmbedding:
    """Tests for embedding generation."""

    def test_embed_single_text(self, vector_search: VectorSearch) -> None:
        """Test embedding a single text."""
        embedding = vector_search.embed("Hello world")

        assert embedding.shape == (1, 384)
        assert embedding.dtype == np.float32

    def test_embed_multiple_texts(self, vector_search: VectorSearch) -> None:
        """Test embedding multiple texts."""
        texts = ["Hello world", "How are you", "Testing embeddings"]
        embeddings = vector_search.embed(texts)

        assert embeddings.shape == (3, 384)
        assert embeddings.dtype == np.float32

    def test_embed_single_returns_1d(self, vector_search: VectorSearch) -> None:
        """Test embed_single returns 1D array."""
        embedding = vector_search.embed_single("Hello world")

        assert embedding.shape == (384,)
        assert embedding.dtype == np.float32

    def test_embeddings_normalized(self, vector_search: VectorSearch) -> None:
        """Test embeddings are L2 normalized."""
        embedding = vector_search.embed_single("Hello world", normalize=True)

        norm = np.linalg.norm(embedding)
        assert abs(norm - 1.0) < 1e-5

    def test_deterministic_embeddings(self, vector_search: VectorSearch) -> None:
        """Test same text produces same embedding."""
        text = "Test text for consistency"
        emb1 = vector_search.embed_single(text)
        emb2 = vector_search.embed_single(text)

        np.testing.assert_array_almost_equal(emb1, emb2)

    def test_different_texts_different_embeddings(
        self, vector_search: VectorSearch
    ) -> None:
        """Test different texts produce different embeddings."""
        emb1 = vector_search.embed_single("Hello world")
        emb2 = vector_search.embed_single("Goodbye universe")

        assert not np.allclose(emb1, emb2)


class TestVectorSearchIndexing:
    """Tests for vector indexing."""

    def test_index_memories(
        self, vector_search: VectorSearch, sample_memories: list[Memory]
    ) -> None:
        """Test indexing memories."""
        vector_search.index_memories("user-1", sample_memories)

        assert vector_search.has_index("user-1")
        stats = vector_search.index_stats("user-1")
        assert stats["total_docs"] == 5
        assert stats["embedding_dim"] == 384

    def test_index_memories_with_ids(
        self, vector_search: VectorSearch, sample_memories: list[Memory]
    ) -> None:
        """Test indexing with explicit IDs."""
        memory_ids = ["id-a", "id-b", "id-c", "id-d", "id-e"]
        vector_search.index_memories("user-1", sample_memories, memory_ids)

        # Verify IDs are used
        results = vector_search.search("user-1", "database", top_k=10)
        assert any(mem_id.startswith("id-") for mem_id, _ in results)

    def test_index_empty_memories(self, vector_search: VectorSearch) -> None:
        """Test indexing empty list."""
        vector_search.index_memories("user-1", [])

        assert vector_search.has_index("user-1")
        stats = vector_search.index_stats("user-1")
        assert stats["total_docs"] == 0

    def test_add_memory(
        self, vector_search: VectorSearch, sample_memories: list[Memory]
    ) -> None:
        """Test adding a single memory."""
        vector_search.index_memories("user-1", sample_memories[:2])
        assert vector_search.index_stats("user-1")["total_docs"] == 2

        vector_search.add_memory("user-1", sample_memories[2], "new-mem")
        assert vector_search.index_stats("user-1")["total_docs"] == 3

    def test_add_memory_to_new_user(
        self, vector_search: VectorSearch, sample_memories: list[Memory]
    ) -> None:
        """Test adding memory for a new user creates index."""
        assert not vector_search.has_index("new-user")

        vector_search.add_memory("new-user", sample_memories[0], "mem-1")

        assert vector_search.has_index("new-user")
        assert vector_search.index_stats("new-user")["total_docs"] == 1

    def test_remove_memory(
        self, vector_search: VectorSearch, sample_memories: list[Memory]
    ) -> None:
        """Test removing a memory."""
        vector_search.index_memories("user-1", sample_memories)
        initial_count = vector_search.index_stats("user-1")["total_docs"]

        removed = vector_search.remove_memory("user-1", "mem-1")
        assert removed is True
        assert vector_search.index_stats("user-1")["total_docs"] == initial_count - 1

    def test_remove_nonexistent_memory(
        self, vector_search: VectorSearch, sample_memories: list[Memory]
    ) -> None:
        """Test removing a nonexistent memory."""
        vector_search.index_memories("user-1", sample_memories)

        removed = vector_search.remove_memory("user-1", "nonexistent")
        assert removed is False

    def test_clear_index(
        self, vector_search: VectorSearch, sample_memories: list[Memory]
    ) -> None:
        """Test clearing an index."""
        vector_search.index_memories("user-1", sample_memories)
        assert vector_search.has_index("user-1")

        vector_search.clear_index("user-1")
        assert not vector_search.has_index("user-1")


class TestVectorSearchSearch:
    """Tests for vector search."""

    def test_search_basic(
        self, vector_search: VectorSearch, sample_memories: list[Memory]
    ) -> None:
        """Test basic search."""
        vector_search.index_memories("user-1", sample_memories)

        results = vector_search.search("user-1", "database storage", top_k=5)

        assert len(results) > 0
        # All scores should be between -1 and 1 (cosine similarity)
        for _, score in results:
            assert -1.0 <= score <= 1.0

    def test_search_ranking_order(
        self, vector_search: VectorSearch, sample_memories: list[Memory]
    ) -> None:
        """Test results are ranked by score descending."""
        vector_search.index_memories("user-1", sample_memories)

        results = vector_search.search("user-1", "database", top_k=5)

        scores = [score for _, score in results]
        assert scores == sorted(scores, reverse=True)

    def test_search_top_k_limit(
        self, vector_search: VectorSearch, sample_memories: list[Memory]
    ) -> None:
        """Test top_k limit is respected."""
        vector_search.index_memories("user-1", sample_memories)

        results = vector_search.search("user-1", "database", top_k=2)

        assert len(results) <= 2

    def test_search_nonexistent_user(self, vector_search: VectorSearch) -> None:
        """Test search for nonexistent user."""
        results = vector_search.search("nonexistent", "database", top_k=5)
        assert len(results) == 0

    def test_search_empty_index(self, vector_search: VectorSearch) -> None:
        """Test search on empty index."""
        vector_search.index_memories("user-1", [])

        results = vector_search.search("user-1", "database", top_k=5)
        assert len(results) == 0


class TestVectorSearchWithMemories:
    """Tests for search_with_memories."""

    def test_search_with_memories(
        self, vector_search: VectorSearch, sample_memories: list[Memory]
    ) -> None:
        """Test search_with_memories returns Memory objects."""
        vector_search.index_memories("user-1", sample_memories)

        results = vector_search.search_with_memories("user-1", "database", top_k=5)

        assert len(results) > 0
        for memory, score in results:
            assert isinstance(memory, Memory)
            assert isinstance(score, float)

    def test_get_memory(
        self, vector_search: VectorSearch, sample_memories: list[Memory]
    ) -> None:
        """Test get_memory retrieves indexed memory."""
        vector_search.index_memories("user-1", sample_memories)

        memory = vector_search.get_memory("user-1", "mem-1")
        assert memory is not None
        assert "PostgreSQL" in memory.content

    def test_get_memory_not_found(
        self, vector_search: VectorSearch, sample_memories: list[Memory]
    ) -> None:
        """Test get_memory returns None for missing memory."""
        vector_search.index_memories("user-1", sample_memories)

        memory = vector_search.get_memory("user-1", "nonexistent")
        assert memory is None


class TestVectorSearchByEmbedding:
    """Tests for search_by_embedding."""

    def test_search_by_embedding(
        self, vector_search: VectorSearch, sample_memories: list[Memory]
    ) -> None:
        """Test search using pre-computed embedding."""
        vector_search.index_memories("user-1", sample_memories)

        # Get embedding for a query
        query_embedding = vector_search.embed_single("database")

        # Search with embedding
        results = vector_search.search_by_embedding("user-1", query_embedding, top_k=5)

        assert len(results) > 0
        # Should match regular search results
        regular_results = vector_search.search("user-1", "database", top_k=5)
        assert len(results) == len(regular_results)

    def test_get_embedding(
        self, vector_search: VectorSearch, sample_memories: list[Memory]
    ) -> None:
        """Test get_embedding retrieves stored embedding."""
        vector_search.index_memories("user-1", sample_memories)

        embedding = vector_search.get_embedding("user-1", "mem-1")
        assert embedding is not None
        assert embedding.shape == (384,)

    def test_get_embedding_not_found(
        self, vector_search: VectorSearch, sample_memories: list[Memory]
    ) -> None:
        """Test get_embedding returns None for missing memory."""
        vector_search.index_memories("user-1", sample_memories)

        embedding = vector_search.get_embedding("user-1", "nonexistent")
        assert embedding is None


class TestVectorSearchSimilarity:
    """Tests for similarity calculation."""

    def test_similarity_identical_texts(self, vector_search: VectorSearch) -> None:
        """Test similarity of identical texts."""
        similarity = vector_search.similarity("hello world", "hello world")
        assert abs(similarity - 1.0) < 1e-5

    def test_similarity_different_texts(self, vector_search: VectorSearch) -> None:
        """Test similarity of different texts."""
        similarity = vector_search.similarity("hello world", "goodbye universe")
        # Different texts should have lower similarity
        assert similarity < 1.0


class TestVectorSearchMultiTenant:
    """Tests for multi-tenant support."""

    def test_separate_user_indexes(
        self, vector_search: VectorSearch, sample_memories: list[Memory]
    ) -> None:
        """Test users have separate indexes."""
        # Index for user-1
        vector_search.index_memories("user-1", sample_memories)

        # Index for user-2 (different memories)
        user2_memories = [
            Memory(
                user_id="user-2",
                content="User 2 uses MongoDB for storage",
                memory_type=MemoryType.FACT,
                source="test",
                created_at=datetime.now(timezone.utc),
                last_accessed_at=datetime.now(timezone.utc),
                metadata={"memory_id": "u2-mem-1"},
            )
        ]
        vector_search.index_memories("user-2", user2_memories)

        # User indexes should be separate
        assert vector_search.index_stats("user-1")["total_docs"] == 5
        assert vector_search.index_stats("user-2")["total_docs"] == 1


class TestVectorSearchStats:
    """Tests for index statistics."""

    def test_stats_populated_index(
        self, vector_search: VectorSearch, sample_memories: list[Memory]
    ) -> None:
        """Test stats for populated index."""
        vector_search.index_memories("user-1", sample_memories)

        stats = vector_search.index_stats("user-1")

        assert stats["total_docs"] == 5
        assert stats["embedding_dim"] == 384
        assert stats["model_loaded"] is True

    def test_stats_nonexistent_user(self, vector_search: VectorSearch) -> None:
        """Test stats for nonexistent user."""
        stats = vector_search.index_stats("nonexistent")

        assert stats["total_docs"] == 0
        assert stats["embedding_dim"] == 384


class TestVectorIndex:
    """Tests for VectorIndex dataclass."""

    def test_empty_index(self) -> None:
        """Test empty index creation."""
        index = VectorIndex()
        assert index.doc_ids == []
        assert index.embeddings is None

    def test_index_with_data(self) -> None:
        """Test index with data."""
        embeddings = np.random.randn(3, 384).astype(np.float32)
        index = VectorIndex(
            doc_ids=["a", "b", "c"],
            embeddings=embeddings,
        )
        assert len(index.doc_ids) == 3
        assert index.embeddings.shape == (3, 384)
