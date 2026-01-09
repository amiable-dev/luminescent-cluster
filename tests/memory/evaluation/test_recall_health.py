# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Tests for HNSW Recall Health Monitoring.

Tests brute-force exact search, recall measurement, baseline persistence,
embedding version tracking, and reindex triggers.

ADR Reference: ADR-003 Memory Architecture, Phase 0 (HNSW Recall Health Monitoring)
"""

import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from src.memory.evaluation.baseline import BaselineStore, RecallBaseline
from src.memory.evaluation.brute_force import (
    BruteForceResult,
    BruteForceSearcher,
    Document,
)
from src.memory.evaluation.embedding_version import (
    EmbeddingVersion,
    EmbeddingVersionTracker,
)
from src.memory.evaluation.recall_health import RecallHealthMonitor, RecallHealthResult
from src.memory.maintenance.reindex_trigger import ReindexTrigger


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class MockSearchResult:
    """Mock search result for testing."""

    document_id: str


class MockEmbeddingModel:
    """Mock embedding model for testing."""

    def __init__(self, dimension: int = 384):
        self.dimension = dimension

    def encode(self, texts: list[str] | str) -> np.ndarray:
        """Encode texts to random embeddings."""
        if isinstance(texts, str):
            texts = [texts]
        # Use hash of text to get deterministic embeddings
        embeddings = []
        for text in texts:
            np.random.seed(hash(text) % (2**32))
            embedding = np.random.randn(self.dimension)
            embedding = embedding / np.linalg.norm(embedding)  # Normalize
            embeddings.append(embedding)
        return np.array(embeddings)

    def get_sentence_embedding_dimension(self) -> int:
        """Return embedding dimension."""
        return self.dimension


@pytest.fixture
def mock_model() -> MockEmbeddingModel:
    """Create a mock embedding model."""
    return MockEmbeddingModel()


@pytest.fixture
def sample_documents() -> list[Document]:
    """Create sample documents for testing."""
    return [
        Document(id="1", content="The quick brown fox jumps over the lazy dog"),
        Document(id="2", content="Machine learning is a subset of artificial intelligence"),
        Document(id="3", content="Python is a popular programming language"),
        Document(id="4", content="Vector databases store embeddings for similarity search"),
        Document(id="5", content="Natural language processing enables text understanding"),
    ]


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# ─────────────────────────────────────────────────────────────────────────────
# BruteForceSearcher Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestBruteForceSearcher:
    """Tests for BruteForceSearcher."""

    def test_index_corpus(self, mock_model: MockEmbeddingModel, sample_documents: list[Document]) -> None:
        """Test indexing a corpus of documents."""
        searcher = BruteForceSearcher(mock_model)
        searcher.index_corpus(sample_documents)

        assert searcher.corpus_size == 5
        assert searcher.is_indexed

    def test_index_empty_corpus_raises(self, mock_model: MockEmbeddingModel) -> None:
        """Test that indexing empty corpus raises ValueError."""
        searcher = BruteForceSearcher(mock_model)

        with pytest.raises(ValueError, match="Cannot index empty document list"):
            searcher.index_corpus([])

    def test_search_without_index_raises(self, mock_model: MockEmbeddingModel) -> None:
        """Test that search without indexing raises RuntimeError."""
        searcher = BruteForceSearcher(mock_model)

        with pytest.raises(RuntimeError, match="Corpus not indexed"):
            searcher.search("test query", k=5)

    def test_search_returns_results(self, mock_model: MockEmbeddingModel, sample_documents: list[Document]) -> None:
        """Test that search returns correct number of results."""
        searcher = BruteForceSearcher(mock_model)
        searcher.index_corpus(sample_documents)

        results = searcher.search("machine learning AI", k=3)

        assert len(results) == 3
        assert all(isinstance(r, BruteForceResult) for r in results)
        # Cosine similarity can be negative with random embeddings
        assert all(-1.0 <= r.score <= 1.0 for r in results)

    def test_search_results_sorted_by_score(self, mock_model: MockEmbeddingModel, sample_documents: list[Document]) -> None:
        """Test that results are sorted by descending score."""
        searcher = BruteForceSearcher(mock_model)
        searcher.index_corpus(sample_documents)

        results = searcher.search("test query", k=5)

        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_search_with_filter(self, mock_model: MockEmbeddingModel, sample_documents: list[Document]) -> None:
        """Test filtered search."""
        searcher = BruteForceSearcher(mock_model)
        sample_documents[0].metadata = {"tenant": "A"}
        sample_documents[1].metadata = {"tenant": "B"}
        sample_documents[2].metadata = {"tenant": "A"}
        sample_documents[3].metadata = {"tenant": "B"}
        sample_documents[4].metadata = {"tenant": "A"}
        searcher.index_corpus(sample_documents)

        # Filter to tenant A only
        results = searcher.search_with_filter(
            "test query",
            k=5,
            filter_fn=lambda doc: doc.metadata.get("tenant") == "A",
        )

        assert len(results) == 3
        for r in results:
            assert r.document_id in ["1", "3", "5"]

    def test_search_k_larger_than_corpus(self, mock_model: MockEmbeddingModel, sample_documents: list[Document]) -> None:
        """Test search with k larger than corpus size."""
        searcher = BruteForceSearcher(mock_model)
        searcher.index_corpus(sample_documents)

        results = searcher.search("test", k=100)

        assert len(results) == 5  # Limited to corpus size

    def test_search_invalid_k_raises(self, mock_model: MockEmbeddingModel, sample_documents: list[Document]) -> None:
        """Test that k < 1 raises ValueError."""
        searcher = BruteForceSearcher(mock_model)
        searcher.index_corpus(sample_documents)

        with pytest.raises(ValueError, match="k must be at least 1"):
            searcher.search("test", k=0)


# ─────────────────────────────────────────────────────────────────────────────
# BaselineStore Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestBaselineStore:
    """Tests for BaselineStore."""

    def test_save_and_load_baseline(self, temp_dir: Path) -> None:
        """Test saving and loading a baseline."""
        store = BaselineStore(temp_dir)
        baseline = RecallBaseline(
            recall_at_k=0.95,
            k=10,
            query_count=50,
            embedding_model="all-MiniLM-L6-v2",
            embedding_version="abc123",
            created_at=datetime.now(),
            corpus_size=10000,
        )

        store.save_baseline(baseline)
        loaded = store.load_baseline()

        assert loaded is not None
        assert loaded.recall_at_k == 0.95
        assert loaded.k == 10
        assert loaded.corpus_size == 10000

    def test_load_nonexistent_baseline(self, temp_dir: Path) -> None:
        """Test loading when no baseline exists."""
        store = BaselineStore(temp_dir)

        loaded = store.load_baseline()

        assert loaded is None

    def test_save_filtered_baseline(self, temp_dir: Path) -> None:
        """Test saving filtered baseline."""
        store = BaselineStore(temp_dir)
        baseline = RecallBaseline(
            recall_at_k=0.88,
            k=10,
            query_count=50,
            embedding_model="all-MiniLM-L6-v2",
            embedding_version="abc123",
            created_at=datetime.now(),
            corpus_size=5000,
            filtered=True,
            filter_description="tenant_123",
        )

        store.save_baseline(baseline, filter_name="tenant")
        loaded = store.load_baseline(filtered=True, filter_name="tenant")

        assert loaded is not None
        assert loaded.recall_at_k == 0.88
        assert loaded.filtered is True

    def test_compute_drift_positive(self, temp_dir: Path) -> None:
        """Test drift computation when recall degrades."""
        store = BaselineStore(temp_dir)
        baseline = RecallBaseline(
            recall_at_k=0.95,
            k=10,
            query_count=50,
            embedding_model="all-MiniLM-L6-v2",
            embedding_version="abc123",
            created_at=datetime.now(),
            corpus_size=10000,
        )

        # 10% degradation
        drift = store.compute_drift(0.855, baseline)

        assert abs(drift - 0.10) < 0.001

    def test_compute_drift_negative(self, temp_dir: Path) -> None:
        """Test drift computation when recall improves."""
        store = BaselineStore(temp_dir)
        baseline = RecallBaseline(
            recall_at_k=0.90,
            k=10,
            query_count=50,
            embedding_model="all-MiniLM-L6-v2",
            embedding_version="abc123",
            created_at=datetime.now(),
            corpus_size=10000,
        )

        # Improvement
        drift = store.compute_drift(0.95, baseline)

        assert drift < 0  # Negative drift = improvement

    def test_path_traversal_prevention(self, temp_dir: Path) -> None:
        """Test that path traversal attacks are prevented via sanitization."""
        store = BaselineStore(temp_dir)

        # Path traversal attempts are sanitized to safe names
        # "../../../etc/passwd" -> "etcpasswd" (dots and slashes removed)
        path = store._get_baseline_path(filtered=True, filter_name="../../../etc/passwd")
        assert path.name == "filtered_etcpasswd.json"
        assert path.parent == temp_dir

        # Pure traversal strings with no alphanumeric content raise ValueError
        with pytest.raises(ValueError, match="must contain at least one alphanumeric"):
            store._get_baseline_path(filtered=True, filter_name="../../..")

        with pytest.raises(ValueError, match="must contain at least one alphanumeric"):
            store._get_baseline_path(filtered=True, filter_name="/.//")

    def test_sanitize_filter_name(self, temp_dir: Path) -> None:
        """Test filter name sanitization."""
        store = BaselineStore(temp_dir)

        # Normal names work
        assert store._sanitize_filter_name("tenant_123") == "tenant_123"
        assert store._sanitize_filter_name("my-filter") == "my-filter"

        # Special characters are removed
        assert store._sanitize_filter_name("tenant/123") == "tenant123"
        assert store._sanitize_filter_name("filter@name") == "filtername"

        # Long names are truncated
        long_name = "a" * 100
        assert len(store._sanitize_filter_name(long_name)) == 64

    def test_archive_previous_baseline(self, temp_dir: Path) -> None:
        """Test that previous baseline is archived."""
        store = BaselineStore(temp_dir)

        # Save first baseline
        baseline1 = RecallBaseline(
            recall_at_k=0.92,
            k=10,
            query_count=50,
            embedding_model="all-MiniLM-L6-v2",
            embedding_version="abc123",
            created_at=datetime.now() - timedelta(days=1),
            corpus_size=10000,
        )
        store.save_baseline(baseline1)

        # Save second baseline (should archive first)
        baseline2 = RecallBaseline(
            recall_at_k=0.95,
            k=10,
            query_count=50,
            embedding_model="all-MiniLM-L6-v2",
            embedding_version="def456",
            created_at=datetime.now(),
            corpus_size=12000,
        )
        store.save_baseline(baseline2)

        # Current should be newest
        current = store.load_baseline()
        assert current is not None
        assert current.recall_at_k == 0.95

        # History should contain the old one
        history = store.load_history()
        assert len(history) >= 1
        assert any(b.recall_at_k == 0.92 for b in history)


# ─────────────────────────────────────────────────────────────────────────────
# RecallHealthMonitor Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestRecallHealthMonitor:
    """Tests for RecallHealthMonitor."""

    def test_measure_recall_at_k_perfect(self, mock_model: MockEmbeddingModel, sample_documents: list[Document], temp_dir: Path) -> None:
        """Test recall measurement when HNSW returns exact same results."""
        brute_force = BruteForceSearcher(mock_model)
        brute_force.index_corpus(sample_documents)
        baseline_store = BaselineStore(temp_dir)

        # HNSW returns same results as brute force
        def perfect_hnsw(query: str, k: int) -> list[MockSearchResult]:
            bf_results = brute_force.search(query, k)
            return [MockSearchResult(document_id=r.document_id) for r in bf_results]

        monitor = RecallHealthMonitor(
            brute_force=brute_force,
            hnsw_search=perfect_hnsw,
            baseline_store=baseline_store,
        )

        result = monitor.measure_recall_at_k(["test query"], k=3)

        assert result.recall_at_k == 1.0
        assert result.passed_absolute is True

    def test_measure_recall_at_k_partial(self, mock_model: MockEmbeddingModel, sample_documents: list[Document], temp_dir: Path) -> None:
        """Test recall measurement when HNSW misses some results."""
        brute_force = BruteForceSearcher(mock_model)
        brute_force.index_corpus(sample_documents)
        baseline_store = BaselineStore(temp_dir)

        # HNSW returns different results (simulating degradation)
        def degraded_hnsw(query: str, k: int) -> list[MockSearchResult]:
            bf_results = brute_force.search(query, k)
            # Return only first half of correct results + wrong ones
            correct = bf_results[: k // 2]
            wrong = [MockSearchResult(document_id="wrong_1")]
            return [MockSearchResult(document_id=r.document_id) for r in correct] + wrong

        monitor = RecallHealthMonitor(
            brute_force=brute_force,
            hnsw_search=degraded_hnsw,
            baseline_store=baseline_store,
        )

        result = monitor.measure_recall_at_k(["test query"], k=4)

        assert result.recall_at_k < 1.0
        assert result.k == 4

    def test_absolute_threshold_pass(self, mock_model: MockEmbeddingModel, sample_documents: list[Document], temp_dir: Path) -> None:
        """Test that high recall passes absolute threshold."""
        brute_force = BruteForceSearcher(mock_model)
        brute_force.index_corpus(sample_documents)
        baseline_store = BaselineStore(temp_dir)

        def good_hnsw(query: str, k: int) -> list[MockSearchResult]:
            bf_results = brute_force.search(query, k)
            return [MockSearchResult(document_id=r.document_id) for r in bf_results]

        monitor = RecallHealthMonitor(
            brute_force=brute_force,
            hnsw_search=good_hnsw,
            baseline_store=baseline_store,
        )

        result = monitor.check_health(["query1", "query2"], k=3)

        assert result.passed_absolute is True
        assert result.recall_at_k >= RecallHealthMonitor.ABSOLUTE_THRESHOLD

    def test_absolute_threshold_fail(self, mock_model: MockEmbeddingModel, sample_documents: list[Document], temp_dir: Path) -> None:
        """Test that low recall fails absolute threshold."""
        brute_force = BruteForceSearcher(mock_model)
        brute_force.index_corpus(sample_documents)
        baseline_store = BaselineStore(temp_dir)

        # Return completely wrong results
        def bad_hnsw(query: str, k: int) -> list[MockSearchResult]:
            return [MockSearchResult(document_id="wrong_1")]

        monitor = RecallHealthMonitor(
            brute_force=brute_force,
            hnsw_search=bad_hnsw,
            baseline_store=baseline_store,
        )

        result = monitor.check_health(["query1"], k=3)

        assert result.passed_absolute is False
        assert result.recall_at_k < RecallHealthMonitor.ABSOLUTE_THRESHOLD

    def test_drift_detection(self, mock_model: MockEmbeddingModel, sample_documents: list[Document], temp_dir: Path) -> None:
        """Test that drift from baseline is detected."""
        brute_force = BruteForceSearcher(mock_model)
        brute_force.index_corpus(sample_documents)
        baseline_store = BaselineStore(temp_dir)

        # Save a high baseline
        baseline = RecallBaseline(
            recall_at_k=1.0,
            k=10,
            query_count=50,
            embedding_model="test",
            embedding_version="v1",
            created_at=datetime.now(),
            corpus_size=5,
        )
        baseline_store.save_baseline(baseline)

        # HNSW now has degraded recall
        def degraded_hnsw(query: str, k: int) -> list[MockSearchResult]:
            return [MockSearchResult(document_id="1")]  # Only 1 correct

        monitor = RecallHealthMonitor(
            brute_force=brute_force,
            hnsw_search=degraded_hnsw,
            baseline_store=baseline_store,
        )

        result = monitor.check_health(["query1"], k=3)

        assert result.drift_pct is not None
        assert result.drift_pct > 0  # Positive drift = degradation

    def test_should_reindex_true(self, mock_model: MockEmbeddingModel, sample_documents: list[Document], temp_dir: Path) -> None:
        """Test should_reindex returns True when thresholds breached."""
        brute_force = BruteForceSearcher(mock_model)
        brute_force.index_corpus(sample_documents)
        baseline_store = BaselineStore(temp_dir)

        def bad_hnsw(query: str, k: int) -> list[MockSearchResult]:
            return []

        monitor = RecallHealthMonitor(
            brute_force=brute_force,
            hnsw_search=bad_hnsw,
            baseline_store=baseline_store,
        )

        result = monitor.check_health(["query"], k=3)

        assert monitor.should_reindex(result) is True

    def test_empty_queries_raises(self, mock_model: MockEmbeddingModel, sample_documents: list[Document], temp_dir: Path) -> None:
        """Test that empty query list raises ValueError."""
        brute_force = BruteForceSearcher(mock_model)
        brute_force.index_corpus(sample_documents)
        baseline_store = BaselineStore(temp_dir)

        monitor = RecallHealthMonitor(
            brute_force=brute_force,
            hnsw_search=lambda q, k: [],
            baseline_store=baseline_store,
        )

        with pytest.raises(ValueError, match="Query list cannot be empty"):
            monitor.measure_recall_at_k([], k=3)


# ─────────────────────────────────────────────────────────────────────────────
# EmbeddingVersionTracker Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestEmbeddingVersionTracker:
    """Tests for EmbeddingVersionTracker."""

    def test_get_current_version(self, temp_dir: Path, mock_model: MockEmbeddingModel) -> None:
        """Test getting current version."""
        tracker = EmbeddingVersionTracker(temp_dir)

        version = tracker.get_current_version(
            model=mock_model,
            model_id="test-model",
        )

        assert version.model_id == "test-model"
        assert version.dimension == 384
        assert version.version_hash is not None

    def test_save_and_load_version(self, temp_dir: Path) -> None:
        """Test saving and loading version."""
        tracker = EmbeddingVersionTracker(temp_dir)
        version = EmbeddingVersion(
            model_id="all-MiniLM-L6-v2",
            version_hash="abc123",
            dimension=384,
            created_at=datetime.now(),
        )

        tracker.save_version(version)
        loaded = tracker.load_stored_version()

        assert loaded is not None
        assert loaded.model_id == "all-MiniLM-L6-v2"
        assert loaded.version_hash == "abc123"

    def test_is_compatible_same_version(self, temp_dir: Path) -> None:
        """Test compatibility with same version."""
        tracker = EmbeddingVersionTracker(temp_dir)
        version = EmbeddingVersion(
            model_id="model-v1",
            version_hash="hash123",
            dimension=384,
            created_at=datetime.now(),
        )

        assert tracker.is_compatible(version, version) is True

    def test_is_compatible_different_model(self, temp_dir: Path) -> None:
        """Test incompatibility with different model."""
        tracker = EmbeddingVersionTracker(temp_dir)
        stored = EmbeddingVersion(
            model_id="model-v1",
            version_hash="hash123",
            dimension=384,
            created_at=datetime.now(),
        )
        current = EmbeddingVersion(
            model_id="model-v2",
            version_hash="hash123",
            dimension=384,
            created_at=datetime.now(),
        )

        assert tracker.is_compatible(stored, current) is False

    def test_is_compatible_different_dimension(self, temp_dir: Path) -> None:
        """Test incompatibility with different dimension."""
        tracker = EmbeddingVersionTracker(temp_dir)
        stored = EmbeddingVersion(
            model_id="model",
            version_hash="hash123",
            dimension=384,
            created_at=datetime.now(),
        )
        current = EmbeddingVersion(
            model_id="model",
            version_hash="hash123",
            dimension=768,
            created_at=datetime.now(),
        )

        assert tracker.is_compatible(stored, current) is False

    def test_requires_reindex_no_stored(self, temp_dir: Path) -> None:
        """Test that no stored version doesn't require reindex."""
        tracker = EmbeddingVersionTracker(temp_dir)
        current = EmbeddingVersion(
            model_id="model",
            version_hash="hash123",
            dimension=384,
            created_at=datetime.now(),
        )

        assert tracker.requires_reindex(None, current) is False


# ─────────────────────────────────────────────────────────────────────────────
# ReindexTrigger Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestReindexTrigger:
    """Tests for ReindexTrigger."""

    @pytest.mark.asyncio
    async def test_check_and_trigger_no_reindex_needed(self, mock_model: MockEmbeddingModel, sample_documents: list[Document], temp_dir: Path) -> None:
        """Test that no reindex happens when recall is good."""
        brute_force = BruteForceSearcher(mock_model)
        brute_force.index_corpus(sample_documents)
        baseline_store = BaselineStore(temp_dir)

        def good_hnsw(query: str, k: int) -> list[MockSearchResult]:
            bf_results = brute_force.search(query, k)
            return [MockSearchResult(document_id=r.document_id) for r in bf_results]

        monitor = RecallHealthMonitor(
            brute_force=brute_force,
            hnsw_search=good_hnsw,
            baseline_store=baseline_store,
        )

        reindex_called = False

        async def mock_reindex() -> None:
            nonlocal reindex_called
            reindex_called = True

        trigger = ReindexTrigger(
            recall_monitor=monitor,
            reindex_callback=mock_reindex,
        )

        result = await trigger.check_and_trigger(["query1", "query2"], k=3)

        assert result is False
        assert reindex_called is False

    @pytest.mark.asyncio
    async def test_check_and_trigger_reindex_needed(self, mock_model: MockEmbeddingModel, sample_documents: list[Document], temp_dir: Path) -> None:
        """Test that reindex happens when recall degrades."""
        brute_force = BruteForceSearcher(mock_model)
        brute_force.index_corpus(sample_documents)
        baseline_store = BaselineStore(temp_dir)

        def bad_hnsw(query: str, k: int) -> list[MockSearchResult]:
            return []

        monitor = RecallHealthMonitor(
            brute_force=brute_force,
            hnsw_search=bad_hnsw,
            baseline_store=baseline_store,
        )

        reindex_called = False

        async def mock_reindex() -> None:
            nonlocal reindex_called
            reindex_called = True

        trigger = ReindexTrigger(
            recall_monitor=monitor,
            reindex_callback=mock_reindex,
        )

        result = await trigger.check_and_trigger(["query"], k=3)

        assert result is True
        assert reindex_called is True
        assert len(trigger.history) == 1

    @pytest.mark.asyncio
    async def test_cooldown_period(self, mock_model: MockEmbeddingModel, sample_documents: list[Document], temp_dir: Path) -> None:
        """Test that cooldown prevents rapid reindexing."""
        brute_force = BruteForceSearcher(mock_model)
        brute_force.index_corpus(sample_documents)
        baseline_store = BaselineStore(temp_dir)

        def bad_hnsw(query: str, k: int) -> list[MockSearchResult]:
            return []

        monitor = RecallHealthMonitor(
            brute_force=brute_force,
            hnsw_search=bad_hnsw,
            baseline_store=baseline_store,
        )

        reindex_count = 0

        async def mock_reindex() -> None:
            nonlocal reindex_count
            reindex_count += 1

        trigger = ReindexTrigger(
            recall_monitor=monitor,
            reindex_callback=mock_reindex,
            cooldown_hours=1.0,
        )

        # First trigger
        await trigger.check_and_trigger(["query"], k=3)
        # Second trigger (should be blocked by cooldown)
        await trigger.check_and_trigger(["query"], k=3)

        assert reindex_count == 1

    @pytest.mark.asyncio
    async def test_force_bypasses_cooldown(self, mock_model: MockEmbeddingModel, sample_documents: list[Document], temp_dir: Path) -> None:
        """Test that force=True bypasses cooldown."""
        brute_force = BruteForceSearcher(mock_model)
        brute_force.index_corpus(sample_documents)
        baseline_store = BaselineStore(temp_dir)

        def bad_hnsw(query: str, k: int) -> list[MockSearchResult]:
            return []

        monitor = RecallHealthMonitor(
            brute_force=brute_force,
            hnsw_search=bad_hnsw,
            baseline_store=baseline_store,
        )

        reindex_count = 0

        async def mock_reindex() -> None:
            nonlocal reindex_count
            reindex_count += 1

        trigger = ReindexTrigger(
            recall_monitor=monitor,
            reindex_callback=mock_reindex,
            cooldown_hours=1.0,
        )

        await trigger.check_and_trigger(["query"], k=3)
        await trigger.check_and_trigger(["query"], k=3, force=True)

        assert reindex_count == 2

    @pytest.mark.asyncio
    async def test_alert_callback_called(self, mock_model: MockEmbeddingModel, sample_documents: list[Document], temp_dir: Path) -> None:
        """Test that alert callback is called on reindex."""
        brute_force = BruteForceSearcher(mock_model)
        brute_force.index_corpus(sample_documents)
        baseline_store = BaselineStore(temp_dir)

        def bad_hnsw(query: str, k: int) -> list[MockSearchResult]:
            return []

        monitor = RecallHealthMonitor(
            brute_force=brute_force,
            hnsw_search=bad_hnsw,
            baseline_store=baseline_store,
        )

        alert_message = None

        def mock_alert(msg: str, result: RecallHealthResult) -> None:
            nonlocal alert_message
            alert_message = msg

        trigger = ReindexTrigger(
            recall_monitor=monitor,
            reindex_callback=lambda: None,
            alert_callback=mock_alert,
        )

        await trigger.check_and_trigger(["query"], k=3)

        assert alert_message is not None
        assert "recall" in alert_message.lower() or "degradation" in alert_message.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Integration Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestHarnessIntegration:
    """Integration tests for evaluation harness with recall monitoring."""

    def test_configure_and_run_recall_check(self, mock_model: MockEmbeddingModel, sample_documents: list[Document], temp_dir: Path) -> None:
        """Test configuring harness and running recall check."""
        from src.memory.evaluation.harness import EvaluationHarness

        harness = EvaluationHarness()

        # Simulate loading a dataset
        harness.questions = [
            MagicMock(question="What is machine learning?"),
            MagicMock(question="How do vector databases work?"),
        ]

        brute_force = BruteForceSearcher(mock_model)
        brute_force.index_corpus(sample_documents)
        baseline_store = BaselineStore(temp_dir)

        def good_hnsw(query: str, k: int) -> list[MockSearchResult]:
            bf_results = brute_force.search(query, k)
            return [MockSearchResult(document_id=r.document_id) for r in bf_results]

        harness.configure_recall_monitoring(
            brute_force=brute_force,
            hnsw_search=good_hnsw,
            baseline_store=baseline_store,
        )

        result = harness.run_recall_health_check(k=3)

        assert result.recall_at_k >= 0.0
        assert result.passed_absolute is True

    def test_run_recall_check_without_config_raises(self) -> None:
        """Test that running recall check without config raises."""
        from src.memory.evaluation.harness import EvaluationHarness

        harness = EvaluationHarness()

        with pytest.raises(RuntimeError, match="Recall monitoring not configured"):
            harness.run_recall_health_check()
