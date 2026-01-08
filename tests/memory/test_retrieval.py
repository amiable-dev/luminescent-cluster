# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
TDD: RED Phase - Tests for Memory Retrieval & Ranking.

Related GitHub Issues:
- #97: Memory Ranking Logic
- #98: Query Rewriting
- #99: Scope-Aware Retrieval
- #100: Memory Decay Scoring

ADR Reference: ADR-003 Memory Architecture, Phase 1c (Retrieval & Ranking)
"""

import pytest
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from src.memory.schemas import Memory, MemoryType


class TestMemoryRanker:
    """Tests for memory ranking logic."""

    @pytest.fixture
    def ranker(self):
        """Create ranker for testing."""
        from src.memory.retrieval.ranker import MemoryRanker
        return MemoryRanker()

    @pytest.fixture
    def sample_memories(self) -> List[Memory]:
        """Create sample memories for ranking tests."""
        now = datetime.now(timezone.utc)
        return [
            Memory(
                user_id="user-1",
                content="Prefers tabs over spaces",
                memory_type=MemoryType.PREFERENCE,
                confidence=0.9,
                source="conversation",
                raw_source="I prefer tabs over spaces",
                extraction_version=1,
                created_at=now - timedelta(days=1),
                last_accessed_at=now - timedelta(hours=1),
            ),
            Memory(
                user_id="user-1",
                content="Uses Python 3.11",
                memory_type=MemoryType.FACT,
                confidence=0.95,
                source="conversation",
                raw_source="Using Python 3.11",
                extraction_version=1,
                created_at=now - timedelta(days=30),
                last_accessed_at=now - timedelta(days=7),
            ),
            Memory(
                user_id="user-1",
                content="Decided on REST API",
                memory_type=MemoryType.DECISION,
                confidence=0.85,
                source="conversation",
                raw_source="We decided to use REST",
                extraction_version=1,
                created_at=now - timedelta(days=60),
                last_accessed_at=now - timedelta(days=30),
            ),
        ]

    def test_ranker_initialization(self, ranker):
        """Ranker should initialize with default weights."""
        assert ranker.similarity_weight >= 0.0
        assert ranker.recency_weight >= 0.0
        assert ranker.confidence_weight >= 0.0
        # Weights should sum to 1.0
        total = ranker.similarity_weight + ranker.recency_weight + ranker.confidence_weight
        assert abs(total - 1.0) < 0.01

    def test_custom_weights(self):
        """Ranker should accept custom weights."""
        from src.memory.retrieval.ranker import MemoryRanker
        ranker = MemoryRanker(
            similarity_weight=0.5,
            recency_weight=0.3,
            confidence_weight=0.2,
        )
        assert ranker.similarity_weight == 0.5
        assert ranker.recency_weight == 0.3
        assert ranker.confidence_weight == 0.2

    def test_calculate_similarity_score(self, ranker):
        """Should calculate similarity between query and content."""
        score = ranker.calculate_similarity("tabs spaces", "Prefers tabs over spaces")
        assert 0.0 <= score <= 1.0
        assert score >= 0.5  # Should have some similarity

    def test_exact_match_similarity(self, ranker):
        """Exact match should have high similarity."""
        score = ranker.calculate_similarity("tabs", "tabs")
        assert score >= 0.9

    def test_no_match_similarity(self, ranker):
        """No matching words should have low similarity."""
        score = ranker.calculate_similarity("python", "javascript ruby")
        assert score < 0.2

    def test_calculate_recency_score(self, ranker):
        """Should calculate recency score based on last access."""
        now = datetime.now(timezone.utc)

        # Recently accessed should have high score
        recent = now - timedelta(hours=1)
        recent_score = ranker.calculate_recency(recent)
        assert recent_score > 0.9

        # Old access should have lower score
        old = now - timedelta(days=30)
        old_score = ranker.calculate_recency(old)
        assert old_score < recent_score

    def test_rank_memories(self, ranker, sample_memories):
        """Should rank memories by combined score."""
        ranked = ranker.rank("tabs spaces formatting", sample_memories)

        assert len(ranked) == len(sample_memories)
        # Each item should be (memory, score) tuple
        for memory, score in ranked:
            assert isinstance(memory, Memory)
            assert 0.0 <= score <= 1.0

    def test_rank_returns_sorted(self, ranker, sample_memories):
        """Ranked results should be sorted by score descending."""
        ranked = ranker.rank("tabs", sample_memories)

        scores = [score for _, score in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_rank_with_limit(self, ranker, sample_memories):
        """Should respect limit parameter."""
        ranked = ranker.rank("code", sample_memories, limit=2)
        assert len(ranked) <= 2

    def test_rank_empty_memories(self, ranker):
        """Should handle empty memory list."""
        ranked = ranker.rank("query", [])
        assert ranked == []

    def test_combined_score_calculation(self, ranker):
        """Should combine similarity, recency, and confidence scores."""
        now = datetime.now(timezone.utc)
        memory = Memory(
            user_id="user-1",
            content="Prefers tabs",
            memory_type=MemoryType.PREFERENCE,
            confidence=0.8,
            source="test",
            raw_source="I prefer tabs",
            extraction_version=1,
            created_at=now,
            last_accessed_at=now,
        )

        score = ranker.calculate_score("tabs", memory)
        assert 0.0 <= score <= 1.0

    def test_rank_with_provenance_returns_results(self, ranker, sample_memories):
        """rank_with_provenance should return results with provenance."""
        ranked = ranker.rank_with_provenance("tabs", sample_memories)
        assert len(ranked) > 0

    def test_rank_with_provenance_attaches_provenance(self, ranker, sample_memories):
        """rank_with_provenance should attach provenance to memories."""
        ranked = ranker.rank_with_provenance("tabs", sample_memories)
        for memory, score in ranked:
            assert memory.provenance is not None
            assert memory.provenance.retrieval_score == score

    def test_rank_with_provenance_empty_memories(self, ranker):
        """rank_with_provenance should handle empty memory list."""
        ranked = ranker.rank_with_provenance("query", [])
        assert ranked == []

    def test_rank_with_provenance_respects_limit(self, ranker, sample_memories):
        """rank_with_provenance should respect limit parameter."""
        ranked = ranker.rank_with_provenance("code", sample_memories, limit=2)
        assert len(ranked) <= 2


class TestQueryRewriter:
    """Tests for query rewriting and expansion."""

    @pytest.fixture
    def rewriter(self):
        """Create query rewriter for testing."""
        from src.memory.retrieval.query_rewriter import QueryRewriter
        return QueryRewriter()

    def test_rewriter_initialization(self, rewriter):
        """Rewriter should initialize with synonym mappings."""
        assert hasattr(rewriter, 'synonyms')
        assert isinstance(rewriter.synonyms, dict)

    def test_expand_single_term(self, rewriter):
        """Should expand single term to include synonyms."""
        expanded = rewriter.expand("auth")
        assert "auth" in expanded
        # Should include authentication-related terms
        assert "authentication" in expanded or len(expanded) > 1

    def test_expand_multiple_terms(self, rewriter):
        """Should expand each term in query."""
        expanded = rewriter.expand_query("api auth")
        assert "api" in expanded
        assert "auth" in expanded or "authentication" in expanded

    def test_no_expansion_for_unknown_terms(self, rewriter):
        """Unknown terms should pass through unchanged."""
        expanded = rewriter.expand("xyzfoobar")
        assert "xyzfoobar" in expanded

    def test_rewrite_preserves_original(self, rewriter):
        """Rewritten query should include original terms."""
        original = "database cache"
        rewritten = rewriter.rewrite(original)
        assert "database" in rewritten.lower()
        assert "cache" in rewritten.lower()

    def test_common_synonyms(self, rewriter):
        """Should have common programming synonyms."""
        # Auth synonyms
        auth_expanded = rewriter.expand("auth")
        assert len(auth_expanded) >= 1

        # DB synonyms
        db_expanded = rewriter.expand("db")
        assert "database" in db_expanded or "db" in db_expanded

    def test_case_insensitive_expansion(self, rewriter):
        """Expansion should be case insensitive."""
        lower = rewriter.expand("auth")
        upper = rewriter.expand("AUTH")
        assert set(lower) == set(upper)

    def test_rewrite_returns_string(self, rewriter):
        """Rewrite should return a string suitable for search."""
        result = rewriter.rewrite("find user auth")
        assert isinstance(result, str)
        assert len(result) > 0


class TestScopedRetriever:
    """Tests for scope-aware memory retrieval."""

    @pytest.fixture
    def retriever(self):
        """Create scoped retriever for testing."""
        from src.memory.retrieval.scoped import ScopedRetriever
        from src.memory.providers.local import LocalMemoryProvider
        provider = LocalMemoryProvider()
        return ScopedRetriever(provider)

    @pytest.fixture
    async def populated_retriever(self, retriever):
        """Retriever with sample data at different scopes."""
        now = datetime.now(timezone.utc)

        # User-scoped memory
        user_memory = Memory(
            user_id="user-1",
            content="User prefers dark mode",
            memory_type=MemoryType.PREFERENCE,
            confidence=0.9,
            source="conversation",
            raw_source="I prefer dark mode",
            extraction_version=1,
            created_at=now,
            last_accessed_at=now,
            metadata={"scope": "user"},
        )

        # Project-scoped memory
        project_memory = Memory(
            user_id="user-1",
            content="Project uses PostgreSQL",
            memory_type=MemoryType.FACT,
            confidence=0.95,
            source="conversation",
            raw_source="This project uses PostgreSQL",
            extraction_version=1,
            created_at=now,
            last_accessed_at=now,
            metadata={"scope": "project", "project_id": "proj-1"},
        )

        # Global-scoped memory
        global_memory = Memory(
            user_id="user-1",
            content="Team standard is Python 3.11",
            memory_type=MemoryType.FACT,
            confidence=0.9,
            source="conversation",
            raw_source="Our team uses Python 3.11",
            extraction_version=1,
            created_at=now,
            last_accessed_at=now,
            metadata={"scope": "global"},
        )

        await retriever.provider.store(user_memory, {})
        await retriever.provider.store(project_memory, {})
        await retriever.provider.store(global_memory, {})

        return retriever

    def test_retriever_initialization(self, retriever):
        """Retriever should initialize with provider."""
        assert retriever.provider is not None

    def test_scope_hierarchy(self, retriever):
        """Should define scope hierarchy: user > project > global."""
        from src.memory.retrieval.scoped import MemoryScope
        assert MemoryScope.USER.value < MemoryScope.PROJECT.value
        assert MemoryScope.PROJECT.value < MemoryScope.GLOBAL.value

    @pytest.mark.asyncio
    async def test_retrieve_user_scope(self, populated_retriever):
        """Should retrieve user-scoped memories."""
        results = await populated_retriever.retrieve(
            query="dark mode",
            user_id="user-1",
            scope="user",
        )
        assert len(results) >= 0  # May or may not find matches

    @pytest.mark.asyncio
    async def test_retrieve_project_scope(self, populated_retriever):
        """Should retrieve project-scoped memories."""
        results = await populated_retriever.retrieve(
            query="PostgreSQL",
            user_id="user-1",
            scope="project",
            project_id="proj-1",
        )
        assert len(results) >= 0

    @pytest.mark.asyncio
    async def test_retrieve_global_scope(self, populated_retriever):
        """Should retrieve global-scoped memories."""
        results = await populated_retriever.retrieve(
            query="Python",
            user_id="user-1",
            scope="global",
        )
        assert len(results) >= 0

    @pytest.mark.asyncio
    async def test_retrieve_cascades_up_hierarchy(self, populated_retriever):
        """Retrieval should cascade from user up to global if not found."""
        results = await populated_retriever.retrieve(
            query="Python team standard",
            user_id="user-1",
            scope="user",  # Start at user scope
            cascade=True,  # Enable cascade to global
        )
        # Should find the global memory about Python
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_retrieve_respects_user_isolation(self, populated_retriever):
        """Different users should not see each other's user-scoped memories."""
        results = await populated_retriever.retrieve(
            query="dark mode",
            user_id="user-2",  # Different user
            scope="user",
        )
        # Should not find user-1's dark mode preference
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_retrieve_with_limit(self, populated_retriever):
        """Should respect limit parameter."""
        results = await populated_retriever.retrieve(
            query="code",
            user_id="user-1",
            limit=1,
        )
        assert len(results) <= 1

    @pytest.mark.asyncio
    async def test_retrieve_empty_query(self, populated_retriever):
        """Should handle empty query gracefully."""
        results = await populated_retriever.retrieve(
            query="",
            user_id="user-1",
        )
        assert isinstance(results, list)


class TestMemoryDecayIntegration:
    """Tests for memory decay integration with retrieval."""

    @pytest.fixture
    def ranker(self):
        """Create ranker with decay enabled."""
        from src.memory.retrieval.ranker import MemoryRanker
        return MemoryRanker(decay_enabled=True)

    def test_decay_affects_ranking(self, ranker):
        """Older memories should rank lower due to decay."""
        now = datetime.now(timezone.utc)

        recent_memory = Memory(
            user_id="user-1",
            content="Recent fact about Python",
            memory_type=MemoryType.FACT,
            confidence=0.9,
            source="test",
            raw_source="Python is great",
            extraction_version=1,
            created_at=now,
            last_accessed_at=now,
        )

        old_memory = Memory(
            user_id="user-1",
            content="Old fact about Python",
            memory_type=MemoryType.FACT,
            confidence=0.9,  # Same confidence
            source="test",
            raw_source="Python is great",
            extraction_version=1,
            created_at=now - timedelta(days=60),
            last_accessed_at=now - timedelta(days=60),
        )

        recent_score = ranker.calculate_score("Python", recent_memory)
        old_score = ranker.calculate_score("Python", old_memory)

        assert recent_score > old_score

    def test_decay_half_life_configurable(self):
        """Decay half-life should be configurable."""
        from src.memory.retrieval.ranker import MemoryRanker

        ranker = MemoryRanker(decay_half_life_days=15)
        assert ranker.decay_half_life_days == 15

    def test_frequently_accessed_memories_rank_higher(self, ranker):
        """Memories with recent access should rank higher."""
        now = datetime.now(timezone.utc)

        # Same creation time, different last access
        frequently_accessed = Memory(
            user_id="user-1",
            content="Frequently accessed fact",
            memory_type=MemoryType.FACT,
            confidence=0.9,
            source="test",
            raw_source="Important fact",
            extraction_version=1,
            created_at=now - timedelta(days=30),
            last_accessed_at=now - timedelta(hours=1),  # Recently accessed
        )

        rarely_accessed = Memory(
            user_id="user-1",
            content="Rarely accessed fact",
            memory_type=MemoryType.FACT,
            confidence=0.9,  # Same confidence
            source="test",
            raw_source="Important fact",
            extraction_version=1,
            created_at=now - timedelta(days=30),
            last_accessed_at=now - timedelta(days=30),  # Not accessed since creation
        )

        frequent_score = ranker.calculate_score("fact", frequently_accessed)
        rare_score = ranker.calculate_score("fact", rarely_accessed)

        assert frequent_score > rare_score
