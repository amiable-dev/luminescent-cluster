# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Tests for BM25 sparse keyword search.

ADR Reference: ADR-003 Memory Architecture, Phase 3 (Two-Stage Retrieval)
"""

from datetime import datetime, timezone

import pytest

from luminescent_cluster.memory.retrieval.bm25 import BM25Index, BM25Search
from luminescent_cluster.memory.schemas import Memory, MemoryType


@pytest.fixture
def bm25_search() -> BM25Search:
    """Create a BM25Search instance."""
    return BM25Search()


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


class TestBM25SearchTokenization:
    """Tests for BM25 tokenization."""

    def test_tokenize_basic(self, bm25_search: BM25Search) -> None:
        """Test basic tokenization."""
        tokens = bm25_search.tokenize("The quick brown fox")
        assert "quick" in tokens
        assert "brown" in tokens
        assert "fox" in tokens
        # "The" should be filtered as stop word
        assert "the" not in tokens

    def test_tokenize_with_punctuation(self, bm25_search: BM25Search) -> None:
        """Test tokenization removes punctuation."""
        tokens = bm25_search.tokenize("Hello, world! How are you?")
        assert "hello" in tokens
        assert "world" in tokens
        assert "," not in tokens
        assert "!" not in tokens

    def test_tokenize_lowercase(self, bm25_search: BM25Search) -> None:
        """Test tokenization lowercases."""
        tokens = bm25_search.tokenize("PostgreSQL DATABASE")
        assert "postgresql" in tokens
        assert "database" in tokens

    def test_tokenize_min_length(self, bm25_search: BM25Search) -> None:
        """Test minimum term length filtering."""
        tokens = bm25_search.tokenize("I am a test")
        # Single character tokens should be filtered
        assert "i" not in tokens
        assert "a" not in tokens

    def test_tokenize_stop_words(self, bm25_search: BM25Search) -> None:
        """Test stop word filtering."""
        tokens = bm25_search.tokenize("the is a for with and or")
        assert len(tokens) == 0

    def test_tokenize_technical_terms(self, bm25_search: BM25Search) -> None:
        """Test technical terms are preserved."""
        tokens = bm25_search.tokenize("PostgreSQL API JWT OAuth2")
        assert "postgresql" in tokens
        assert "api" in tokens
        assert "jwt" in tokens
        assert "oauth2" in tokens


class TestBM25SearchIndexing:
    """Tests for BM25 indexing."""

    def test_index_memories(
        self, bm25_search: BM25Search, sample_memories: list[Memory]
    ) -> None:
        """Test indexing memories."""
        bm25_search.index_memories("user-1", sample_memories)

        assert bm25_search.has_index("user-1")
        stats = bm25_search.index_stats("user-1")
        assert stats["total_docs"] == 5
        assert stats["avg_doc_length"] > 0
        assert stats["vocabulary_size"] > 0

    def test_index_memories_with_ids(
        self, bm25_search: BM25Search, sample_memories: list[Memory]
    ) -> None:
        """Test indexing with explicit IDs."""
        memory_ids = ["id-a", "id-b", "id-c", "id-d", "id-e"]
        bm25_search.index_memories("user-1", sample_memories, memory_ids)

        # Verify IDs are used
        results = bm25_search.search("user-1", "database", top_k=10)
        assert any(mem_id.startswith("id-") for mem_id, _ in results)

    def test_index_empty_memories(self, bm25_search: BM25Search) -> None:
        """Test indexing empty list."""
        bm25_search.index_memories("user-1", [])

        assert bm25_search.has_index("user-1")
        stats = bm25_search.index_stats("user-1")
        assert stats["total_docs"] == 0

    def test_add_memory(
        self, bm25_search: BM25Search, sample_memories: list[Memory]
    ) -> None:
        """Test adding a single memory."""
        # Start with some memories
        bm25_search.index_memories("user-1", sample_memories[:2])
        assert bm25_search.index_stats("user-1")["total_docs"] == 2

        # Add one more
        bm25_search.add_memory("user-1", sample_memories[2], "new-mem")
        assert bm25_search.index_stats("user-1")["total_docs"] == 3

    def test_add_memory_to_new_user(
        self, bm25_search: BM25Search, sample_memories: list[Memory]
    ) -> None:
        """Test adding memory for a new user creates index."""
        assert not bm25_search.has_index("new-user")

        bm25_search.add_memory("new-user", sample_memories[0], "mem-1")

        assert bm25_search.has_index("new-user")
        assert bm25_search.index_stats("new-user")["total_docs"] == 1

    def test_remove_memory(
        self, bm25_search: BM25Search, sample_memories: list[Memory]
    ) -> None:
        """Test removing a memory."""
        bm25_search.index_memories("user-1", sample_memories)
        initial_count = bm25_search.index_stats("user-1")["total_docs"]

        removed = bm25_search.remove_memory("user-1", "mem-1")
        assert removed is True
        assert bm25_search.index_stats("user-1")["total_docs"] == initial_count - 1

    def test_remove_nonexistent_memory(
        self, bm25_search: BM25Search, sample_memories: list[Memory]
    ) -> None:
        """Test removing a nonexistent memory."""
        bm25_search.index_memories("user-1", sample_memories)

        removed = bm25_search.remove_memory("user-1", "nonexistent")
        assert removed is False

    def test_remove_from_nonexistent_user(self, bm25_search: BM25Search) -> None:
        """Test removing from nonexistent user."""
        removed = bm25_search.remove_memory("nonexistent", "mem-1")
        assert removed is False

    def test_clear_index(
        self, bm25_search: BM25Search, sample_memories: list[Memory]
    ) -> None:
        """Test clearing an index."""
        bm25_search.index_memories("user-1", sample_memories)
        assert bm25_search.has_index("user-1")

        bm25_search.clear_index("user-1")
        assert not bm25_search.has_index("user-1")


class TestBM25SearchScoring:
    """Tests for BM25 scoring."""

    def test_search_basic(
        self, bm25_search: BM25Search, sample_memories: list[Memory]
    ) -> None:
        """Test basic search."""
        bm25_search.index_memories("user-1", sample_memories)

        results = bm25_search.search("user-1", "database", top_k=5)

        assert len(results) > 0
        # Database-related memories should rank high
        memory_ids = [mem_id for mem_id, _ in results]
        assert "mem-1" in memory_ids or "mem-5" in memory_ids

    def test_search_exact_term_match(
        self, bm25_search: BM25Search, sample_memories: list[Memory]
    ) -> None:
        """Test exact term matching."""
        bm25_search.index_memories("user-1", sample_memories)

        results = bm25_search.search("user-1", "PostgreSQL", top_k=5)

        assert len(results) > 0
        # mem-1 contains PostgreSQL
        memory_ids = [mem_id for mem_id, _ in results]
        assert "mem-1" in memory_ids

    def test_search_multiple_terms(
        self, bm25_search: BM25Search, sample_memories: list[Memory]
    ) -> None:
        """Test multi-term search."""
        bm25_search.index_memories("user-1", sample_memories)

        results = bm25_search.search("user-1", "Redis caching", top_k=5)

        assert len(results) > 0
        # mem-2 contains both Redis and caching
        memory_ids = [mem_id for mem_id, _ in results]
        assert "mem-2" in memory_ids

    def test_search_ranking_order(
        self, bm25_search: BM25Search, sample_memories: list[Memory]
    ) -> None:
        """Test results are ranked by score descending."""
        bm25_search.index_memories("user-1", sample_memories)

        results = bm25_search.search("user-1", "database", top_k=5)

        scores = [score for _, score in results]
        assert scores == sorted(scores, reverse=True)

    def test_search_top_k_limit(
        self, bm25_search: BM25Search, sample_memories: list[Memory]
    ) -> None:
        """Test top_k limit is respected."""
        bm25_search.index_memories("user-1", sample_memories)

        results = bm25_search.search("user-1", "database uses", top_k=2)

        assert len(results) <= 2

    def test_search_no_match(
        self, bm25_search: BM25Search, sample_memories: list[Memory]
    ) -> None:
        """Test search with no matches."""
        bm25_search.index_memories("user-1", sample_memories)

        results = bm25_search.search("user-1", "xyznonexistent123", top_k=5)

        assert len(results) == 0

    def test_search_nonexistent_user(self, bm25_search: BM25Search) -> None:
        """Test search for nonexistent user."""
        results = bm25_search.search("nonexistent", "database", top_k=5)
        assert len(results) == 0

    def test_search_empty_query(
        self, bm25_search: BM25Search, sample_memories: list[Memory]
    ) -> None:
        """Test search with empty query."""
        bm25_search.index_memories("user-1", sample_memories)

        results = bm25_search.search("user-1", "", top_k=5)
        assert len(results) == 0

    def test_search_stop_words_only(
        self, bm25_search: BM25Search, sample_memories: list[Memory]
    ) -> None:
        """Test search with only stop words."""
        bm25_search.index_memories("user-1", sample_memories)

        results = bm25_search.search("user-1", "the is a for", top_k=5)
        assert len(results) == 0


class TestBM25SearchWithMemories:
    """Tests for search_with_memories."""

    def test_search_with_memories(
        self, bm25_search: BM25Search, sample_memories: list[Memory]
    ) -> None:
        """Test search_with_memories returns Memory objects."""
        bm25_search.index_memories("user-1", sample_memories)

        results = bm25_search.search_with_memories("user-1", "database", top_k=5)

        assert len(results) > 0
        for memory, score in results:
            assert isinstance(memory, Memory)
            assert isinstance(score, float)
            assert score > 0

    def test_get_memory(
        self, bm25_search: BM25Search, sample_memories: list[Memory]
    ) -> None:
        """Test get_memory retrieves indexed memory."""
        bm25_search.index_memories("user-1", sample_memories)

        memory = bm25_search.get_memory("user-1", "mem-1")
        assert memory is not None
        assert "PostgreSQL" in memory.content

    def test_get_memory_not_found(
        self, bm25_search: BM25Search, sample_memories: list[Memory]
    ) -> None:
        """Test get_memory returns None for missing memory."""
        bm25_search.index_memories("user-1", sample_memories)

        memory = bm25_search.get_memory("user-1", "nonexistent")
        assert memory is None


class TestBM25IDFCalculation:
    """Tests for IDF calculation."""

    def test_idf_rare_term(
        self, bm25_search: BM25Search, sample_memories: list[Memory]
    ) -> None:
        """Test rare terms have higher IDF."""
        bm25_search.index_memories("user-1", sample_memories)

        # PostgreSQL appears in 1 document
        # "the" (if not filtered) would appear in multiple
        results = bm25_search.search("user-1", "PostgreSQL", top_k=5)

        # Should have results since PostgreSQL is in mem-1
        assert len(results) > 0
        # Score should be positive
        assert results[0][1] > 0

    def test_idf_empty_index(self, bm25_search: BM25Search) -> None:
        """Test IDF calculation with empty index."""
        bm25_search.index_memories("user-1", [])

        results = bm25_search.search("user-1", "test", top_k=5)
        assert len(results) == 0


class TestBM25Parameters:
    """Tests for BM25 parameter tuning."""

    def test_custom_k1(self, sample_memories: list[Memory]) -> None:
        """Test custom k1 parameter."""
        search_low_k1 = BM25Search(k1=0.5)
        search_high_k1 = BM25Search(k1=2.0)

        search_low_k1.index_memories("user-1", sample_memories)
        search_high_k1.index_memories("user-1", sample_memories)

        # Both should return results
        results_low = search_low_k1.search("user-1", "database", top_k=5)
        results_high = search_high_k1.search("user-1", "database", top_k=5)

        assert len(results_low) > 0
        assert len(results_high) > 0

    def test_custom_b(self, sample_memories: list[Memory]) -> None:
        """Test custom b parameter."""
        search_no_norm = BM25Search(b=0.0)
        search_full_norm = BM25Search(b=1.0)

        search_no_norm.index_memories("user-1", sample_memories)
        search_full_norm.index_memories("user-1", sample_memories)

        # Both should return results
        results_no_norm = search_no_norm.search("user-1", "database", top_k=5)
        results_full_norm = search_full_norm.search("user-1", "database", top_k=5)

        assert len(results_no_norm) > 0
        assert len(results_full_norm) > 0


class TestBM25MultiTenant:
    """Tests for multi-tenant support."""

    def test_separate_user_indexes(
        self, bm25_search: BM25Search, sample_memories: list[Memory]
    ) -> None:
        """Test users have separate indexes."""
        # Index for user-1
        bm25_search.index_memories("user-1", sample_memories)

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
        bm25_search.index_memories("user-2", user2_memories)

        # Search user-1 for PostgreSQL - should find
        results_u1 = bm25_search.search("user-1", "PostgreSQL", top_k=5)
        assert len(results_u1) > 0

        # Search user-2 for PostgreSQL - should NOT find
        results_u2 = bm25_search.search("user-2", "PostgreSQL", top_k=5)
        assert len(results_u2) == 0

        # Search user-2 for MongoDB - should find
        results_u2_mongo = bm25_search.search("user-2", "MongoDB", top_k=5)
        assert len(results_u2_mongo) > 0


class TestBM25IndexStats:
    """Tests for index statistics."""

    def test_stats_populated_index(
        self, bm25_search: BM25Search, sample_memories: list[Memory]
    ) -> None:
        """Test stats for populated index."""
        bm25_search.index_memories("user-1", sample_memories)

        stats = bm25_search.index_stats("user-1")

        assert stats["total_docs"] == 5
        assert stats["avg_doc_length"] > 0
        assert stats["vocabulary_size"] > 10  # Should have multiple unique terms

    def test_stats_nonexistent_user(self, bm25_search: BM25Search) -> None:
        """Test stats for nonexistent user."""
        stats = bm25_search.index_stats("nonexistent")

        assert stats["total_docs"] == 0
        assert stats["avg_doc_length"] == 0.0
        assert stats["vocabulary_size"] == 0
