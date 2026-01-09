# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Tests for Reciprocal Rank Fusion.

ADR Reference: ADR-003 Memory Architecture, Phase 3 (Two-Stage Retrieval)
"""

import pytest

from src.memory.retrieval.fusion import FusedResult, RRFFusion


@pytest.fixture
def fusion() -> RRFFusion:
    """Create an RRFFusion instance with default k=60."""
    return RRFFusion(k=60)


@pytest.fixture
def bm25_results() -> list[tuple[str, float]]:
    """Sample BM25 results."""
    return [
        ("doc1", 5.2),
        ("doc2", 4.8),
        ("doc3", 3.5),
        ("doc4", 2.1),
    ]


@pytest.fixture
def vector_results() -> list[tuple[str, float]]:
    """Sample vector search results."""
    return [
        ("doc2", 0.95),
        ("doc5", 0.88),
        ("doc1", 0.75),
        ("doc6", 0.60),
    ]


class TestRRFFusionBasic:
    """Tests for basic RRF fusion."""

    def test_fuse_single_list(self, fusion: RRFFusion) -> None:
        """Test fusion with a single list."""
        results = [("doc1", 0.9), ("doc2", 0.8), ("doc3", 0.7)]
        fused = fusion.fuse(source1=results)

        assert len(fused) == 3
        # Scores should be 1/(60+1), 1/(60+2), 1/(60+3)
        assert fused[0] == ("doc1", pytest.approx(1 / 61))
        assert fused[1] == ("doc2", pytest.approx(1 / 62))
        assert fused[2] == ("doc3", pytest.approx(1 / 63))

    def test_fuse_two_lists(
        self,
        fusion: RRFFusion,
        bm25_results: list[tuple[str, float]],
        vector_results: list[tuple[str, float]],
    ) -> None:
        """Test fusion of two lists."""
        fused = fusion.fuse(bm25=bm25_results, vector=vector_results)

        # doc1 and doc2 appear in both lists
        assert len(fused) == 6  # Total unique docs

        # doc2 ranks high in both (rank 2 in bm25, rank 1 in vector)
        # doc1 also ranks high in both (rank 1 in bm25, rank 3 in vector)
        doc_ids = [doc_id for doc_id, _ in fused]
        assert "doc1" in doc_ids
        assert "doc2" in doc_ids

    def test_fuse_empty_list(self, fusion: RRFFusion) -> None:
        """Test fusion with no lists."""
        fused = fusion.fuse()
        assert fused == []

    def test_fuse_empty_results(self, fusion: RRFFusion) -> None:
        """Test fusion with empty result lists."""
        fused = fusion.fuse(source1=[], source2=[])
        assert fused == []

    def test_fuse_mixed_empty(
        self, fusion: RRFFusion, bm25_results: list[tuple[str, float]]
    ) -> None:
        """Test fusion with one empty list."""
        fused = fusion.fuse(bm25=bm25_results, vector=[])

        assert len(fused) == len(bm25_results)

    def test_fuse_ranking_order(self, fusion: RRFFusion) -> None:
        """Test that fused results are sorted by RRF score descending."""
        list1 = [("a", 1.0), ("b", 0.9), ("c", 0.8)]
        list2 = [("c", 1.0), ("b", 0.9), ("a", 0.8)]

        fused = fusion.fuse(list1=list1, list2=list2)

        scores = [score for _, score in fused]
        assert scores == sorted(scores, reverse=True)

    def test_rrf_formula_correctness(self) -> None:
        """Test RRF formula: score = Σ 1/(k + rank)."""
        k = 60
        fusion = RRFFusion(k=k)

        list1 = [("doc1", 1.0)]  # rank 1
        list2 = [("doc1", 0.9)]  # rank 1

        fused = fusion.fuse(list1=list1, list2=list2)

        expected_score = 1 / (k + 1) + 1 / (k + 1)  # 2 * 1/61
        assert fused[0][1] == pytest.approx(expected_score)

    def test_items_in_one_list_only(self, fusion: RRFFusion) -> None:
        """Test items that appear in only one list."""
        list1 = [("a", 1.0), ("b", 0.9)]
        list2 = [("c", 1.0), ("d", 0.9)]

        fused = fusion.fuse(list1=list1, list2=list2)

        assert len(fused) == 4
        # All items should have the same score (each appears once at some rank)
        doc_ids = [doc_id for doc_id, _ in fused]
        assert set(doc_ids) == {"a", "b", "c", "d"}


class TestRRFFusionWithDetails:
    """Tests for fuse_with_details."""

    def test_fuse_with_details(
        self,
        fusion: RRFFusion,
        bm25_results: list[tuple[str, float]],
        vector_results: list[tuple[str, float]],
    ) -> None:
        """Test fusion with detailed provenance."""
        fused = fusion.fuse_with_details(bm25=bm25_results, vector=vector_results)

        assert len(fused) == 6

        # Check structure
        for result in fused:
            assert isinstance(result, FusedResult)
            assert isinstance(result.item, str)
            assert isinstance(result.score, float)
            assert isinstance(result.source_ranks, dict)
            assert isinstance(result.source_scores, dict)

    def test_source_ranks_tracked(
        self,
        fusion: RRFFusion,
        bm25_results: list[tuple[str, float]],
        vector_results: list[tuple[str, float]],
    ) -> None:
        """Test that source ranks are correctly tracked."""
        fused = fusion.fuse_with_details(bm25=bm25_results, vector=vector_results)

        # Find doc1 which appears in both lists
        doc1_result = next(r for r in fused if r.item == "doc1")

        assert "bm25" in doc1_result.source_ranks
        assert "vector" in doc1_result.source_ranks
        assert doc1_result.source_ranks["bm25"] == 1  # First in bm25
        assert doc1_result.source_ranks["vector"] == 3  # Third in vector

    def test_source_scores_tracked(
        self,
        fusion: RRFFusion,
        bm25_results: list[tuple[str, float]],
        vector_results: list[tuple[str, float]],
    ) -> None:
        """Test that source scores are correctly tracked."""
        fused = fusion.fuse_with_details(bm25=bm25_results, vector=vector_results)

        # Find doc1
        doc1_result = next(r for r in fused if r.item == "doc1")

        assert doc1_result.source_scores["bm25"] == pytest.approx(5.2)
        assert doc1_result.source_scores["vector"] == pytest.approx(0.75)

    def test_item_in_one_source(self, fusion: RRFFusion) -> None:
        """Test item appearing in only one source."""
        list1 = [("unique", 1.0)]

        fused = fusion.fuse_with_details(list1=list1)

        result = fused[0]
        assert result.item == "unique"
        assert "list1" in result.source_ranks
        assert result.source_ranks["list1"] == 1


class TestRRFFusionLists:
    """Tests for fuse_lists (positional arguments)."""

    def test_fuse_lists_basic(
        self,
        fusion: RRFFusion,
        bm25_results: list[tuple[str, float]],
        vector_results: list[tuple[str, float]],
    ) -> None:
        """Test fuse_lists with positional arguments."""
        fused = fusion.fuse_lists(bm25_results, vector_results)

        assert len(fused) == 6

    def test_fuse_lists_empty(self, fusion: RRFFusion) -> None:
        """Test fuse_lists with no lists."""
        fused = fusion.fuse_lists()
        assert fused == []

    def test_fuse_lists_single(self, fusion: RRFFusion) -> None:
        """Test fuse_lists with single list."""
        results = [("a", 1.0), ("b", 0.9)]
        fused = fusion.fuse_lists(results)

        assert len(fused) == 2


class TestRRFWeightedFusion:
    """Tests for weighted RRF fusion."""

    def test_weighted_fuse(self, fusion: RRFFusion) -> None:
        """Test weighted fusion."""
        list1 = [("a", 1.0)]  # rank 1
        list2 = [("a", 1.0)]  # rank 1

        # Weight list1 twice as much
        fused = fusion.weighted_fuse({"list1": 2.0, "list2": 1.0}, list1=list1, list2=list2)

        # Score should be 2/(60+1) + 1/(60+1) = 3/61
        expected = 2.0 / 61 + 1.0 / 61
        assert fused[0][1] == pytest.approx(expected)

    def test_weighted_fuse_default_weight(self, fusion: RRFFusion) -> None:
        """Test that missing weights default to 1.0."""
        list1 = [("a", 1.0)]
        list2 = [("a", 1.0)]

        # Only specify weight for list1
        fused = fusion.weighted_fuse({"list1": 2.0}, list1=list1, list2=list2)

        # list2 should use default weight of 1.0
        expected = 2.0 / 61 + 1.0 / 61
        assert fused[0][1] == pytest.approx(expected)

    def test_weighted_fuse_zero_weight(self, fusion: RRFFusion) -> None:
        """Test zero weight effectively ignores a source."""
        list1 = [("a", 1.0)]
        list2 = [("a", 1.0)]

        fused = fusion.weighted_fuse({"list1": 1.0, "list2": 0.0}, list1=list1, list2=list2)

        # Only list1 should contribute
        expected = 1.0 / 61
        assert fused[0][1] == pytest.approx(expected)


class TestRRFInterleave:
    """Tests for round-robin interleaving."""

    def test_interleave_basic(self, fusion: RRFFusion) -> None:
        """Test basic interleaving."""
        list1 = [("a", 1.0), ("b", 0.9), ("c", 0.8)]
        list2 = [("d", 1.0), ("e", 0.9), ("f", 0.8)]

        interleaved = fusion.interleave(list1=list1, list2=list2)

        # Should alternate: a, d, b, e, c, f
        doc_ids = [doc_id for doc_id, _ in interleaved]
        assert doc_ids == ["a", "d", "b", "e", "c", "f"]

    def test_interleave_duplicates(self, fusion: RRFFusion) -> None:
        """Test interleaving handles duplicates."""
        list1 = [("a", 1.0), ("b", 0.9)]
        list2 = [("a", 1.0), ("c", 0.9)]  # 'a' appears in both

        interleaved = fusion.interleave(list1=list1, list2=list2)

        doc_ids = [doc_id for doc_id, _ in interleaved]
        assert len(doc_ids) == 3
        assert doc_ids.count("a") == 1  # 'a' only appears once

    def test_interleave_unequal_lengths(self, fusion: RRFFusion) -> None:
        """Test interleaving with unequal length lists."""
        list1 = [("a", 1.0), ("b", 0.9)]
        list2 = [("c", 1.0)]

        interleaved = fusion.interleave(list1=list1, list2=list2)

        doc_ids = [doc_id for doc_id, _ in interleaved]
        assert len(doc_ids) == 3

    def test_interleave_empty(self, fusion: RRFFusion) -> None:
        """Test interleaving with empty input."""
        interleaved = fusion.interleave()
        assert interleaved == []


class TestRRFNormalization:
    """Tests for score normalization."""

    def test_normalize_scores(self) -> None:
        """Test score normalization to [0, 1]."""
        results = [("a", 100.0), ("b", 50.0), ("c", 0.0)]
        normalized = RRFFusion.normalize_scores(results)

        assert normalized[0] == ("a", 1.0)
        assert normalized[1] == ("b", 0.5)
        assert normalized[2] == ("c", 0.0)

    def test_normalize_same_scores(self) -> None:
        """Test normalization when all scores are the same."""
        results = [("a", 5.0), ("b", 5.0), ("c", 5.0)]
        normalized = RRFFusion.normalize_scores(results)

        # All should be 1.0 when min == max
        for _, score in normalized:
            assert score == 1.0

    def test_normalize_empty(self) -> None:
        """Test normalization of empty list."""
        normalized = RRFFusion.normalize_scores([])
        assert normalized == []


class TestRRFTopK:
    """Tests for top-k selection."""

    def test_top_k(self) -> None:
        """Test top-k selection."""
        results = [("a", 1.0), ("b", 0.9), ("c", 0.8), ("d", 0.7)]
        top2 = RRFFusion.top_k(results, 2)

        assert len(top2) == 2
        assert top2[0] == ("a", 1.0)
        assert top2[1] == ("b", 0.9)

    def test_top_k_larger_than_list(self) -> None:
        """Test top-k when k > list length."""
        results = [("a", 1.0), ("b", 0.9)]
        top5 = RRFFusion.top_k(results, 5)

        assert len(top5) == 2


class TestRRFKParameter:
    """Tests for different k values."""

    def test_k_zero(self) -> None:
        """Test k=0 (maximum rank sensitivity)."""
        fusion = RRFFusion(k=0)
        list1 = [("a", 1.0), ("b", 0.9)]

        fused = fusion.fuse(list1=list1)

        # With k=0: rank 1 -> 1/1=1.0, rank 2 -> 1/2=0.5
        assert fused[0][1] == pytest.approx(1.0)
        assert fused[1][1] == pytest.approx(0.5)

    def test_k_high(self) -> None:
        """Test high k (reduced rank sensitivity)."""
        fusion = RRFFusion(k=1000)
        list1 = [("a", 1.0), ("b", 0.9)]

        fused = fusion.fuse(list1=list1)

        # With k=1000: scores are very close
        assert abs(fused[0][1] - fused[1][1]) < 0.001

    def test_negative_k_raises(self) -> None:
        """Test that negative k raises error."""
        with pytest.raises(ValueError):
            RRFFusion(k=-1)

    def test_default_k_is_60(self) -> None:
        """Test default k value is 60."""
        fusion = RRFFusion()
        assert fusion.k == 60


class TestRRFMultipleSources:
    """Tests for fusion with more than 2 sources."""

    def test_three_sources(self, fusion: RRFFusion) -> None:
        """Test fusion of three sources."""
        list1 = [("a", 1.0)]
        list2 = [("a", 1.0)]
        list3 = [("a", 1.0)]

        fused = fusion.fuse(list1=list1, list2=list2, list3=list3)

        # Score should be 3 * 1/61
        expected = 3.0 / 61
        assert fused[0][1] == pytest.approx(expected)

    def test_many_sources(self, fusion: RRFFusion) -> None:
        """Test fusion of many sources."""
        sources = {f"list{i}": [("a", 1.0)] for i in range(10)}

        fused = fusion.fuse(**sources)

        # Score should be 10 * 1/61
        expected = 10.0 / 61
        assert fused[0][1] == pytest.approx(expected)
