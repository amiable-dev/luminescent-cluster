# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""HNSW Recall Health Monitoring.

Measures Recall@k of HNSW approximate nearest neighbor search against
brute-force exact search ground truth. Detects silent degradation at scale.

Related ADR: ADR-003 Memory Architecture, Phase 0 (HNSW Recall Health Monitoring)

Research Reference:
- "HNSW at Scale: Why Your RAG System Gets Worse as the Vector Database Grows"
- "12 Types of RAG" - Grounded retrieval patterns
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Protocol

from luminescent_cluster.memory.evaluation.baseline import BaselineStore, RecallBaseline
from luminescent_cluster.memory.evaluation.brute_force import BruteForceSearcher, Document


class SearchResult(Protocol):
    """Protocol for HNSW search results."""

    @property
    def document_id(self) -> str:
        """Return the document ID."""
        ...


@dataclass
class RecallHealthResult:
    """Result of a recall health check.

    Attributes:
        recall_at_k: The measured Recall@k value (0.0 to 1.0).
        k: The k value used for measurement.
        query_count: Number of queries evaluated.
        filtered: Whether filtered search was used.
        timestamp: When the measurement was taken.
        passed_absolute: True if recall >= ABSOLUTE_THRESHOLD (0.90).
        passed_drift: True if drift <= DRIFT_THRESHOLD (5%).
        baseline_recall: The baseline recall value (if available).
        drift_pct: The relative drift percentage (if baseline available).
        filter_name: Name of the filter used (if filtered).
        individual_recalls: Per-query recall values for analysis.
    """

    recall_at_k: float
    k: int
    query_count: int
    filtered: bool
    timestamp: datetime
    passed_absolute: bool
    passed_drift: bool
    baseline_recall: float | None = None
    drift_pct: float | None = None
    filter_name: str | None = None
    individual_recalls: list[float] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Return True if both absolute and drift checks passed."""
        return self.passed_absolute and self.passed_drift

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Note: filter_name is intentionally excluded to prevent PII leakage.
        Use the 'filtered' boolean to check if filtering was applied.
        """
        return {
            "recall_at_k": self.recall_at_k,
            "k": self.k,
            "query_count": self.query_count,
            "filtered": self.filtered,
            "timestamp": self.timestamp.isoformat(),
            "passed_absolute": self.passed_absolute,
            "passed_drift": self.passed_drift,
            "baseline_recall": self.baseline_recall,
            "drift_pct": self.drift_pct,
            # filter_name intentionally excluded to prevent PII exposure
            "passed": self.passed,
        }


class RecallHealthMonitor:
    """Measure HNSW recall against brute-force ground truth.

    This class compares HNSW approximate nearest neighbor results against
    exact brute-force search results to compute Recall@k. It enforces:

    1. Absolute threshold: Recall@10 >= 0.90
    2. Relative drift: <= 5% drop from baseline

    Example:
        >>> monitor = RecallHealthMonitor(
        ...     brute_force=brute_force_searcher,
        ...     hnsw_search=pixeltable_search,
        ...     baseline_store=BaselineStore(Path("/data/baselines")),
        ... )
        >>> result = monitor.check_health(["query1", "query2", ...])
        >>> if not result.passed:
        ...     print(f"Recall degraded: {result.recall_at_k:.2%}")
    """

    ABSOLUTE_THRESHOLD = 0.90
    DRIFT_THRESHOLD = 0.05  # 5%

    def __init__(
        self,
        brute_force: BruteForceSearcher,
        hnsw_search: Callable[[str, int], list[SearchResult]],
        baseline_store: BaselineStore,
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
        embedding_version: str = "unknown",
    ):
        """Initialize the recall health monitor.

        Args:
            brute_force: Brute-force searcher for ground truth.
            hnsw_search: Function that performs HNSW search.
                         Signature: (query: str, k: int) -> list[SearchResult]
            baseline_store: Store for loading/saving baselines.
            embedding_model: Model ID for baseline compatibility.
            embedding_version: Version hash for baseline compatibility.
        """
        self._brute_force = brute_force
        self._hnsw_search = hnsw_search
        self._baseline_store = baseline_store
        self._embedding_model = embedding_model
        self._embedding_version = embedding_version

    def measure_recall_at_k(
        self,
        queries: list[str],
        k: int = 10,
        filter_fn: Callable[[Document], bool] | None = None,
        hnsw_filter: Callable[[str, int], list[SearchResult]] | None = None,
        filter_name: str | None = None,
    ) -> RecallHealthResult:
        """Compute Recall@k for a set of queries.

        Recall@k = |HNSW_results ∩ exact_results| / |exact_results|

        This measures what proportion of the true top-k results from exact
        search were found by HNSW approximate search. Averaged across queries.

        Args:
            queries: List of query strings to evaluate.
            k: Number of results to consider.
            filter_fn: Optional filter for brute-force search.
            hnsw_filter: Optional filtered HNSW search function.
                        If not provided, uses default hnsw_search.
            filter_name: Name of the filter for baseline lookup.
                        Required when using filter_fn for proper baseline handling.

        Returns:
            RecallHealthResult with metrics and threshold evaluation.

        Raises:
            ValueError: If queries is empty.
            ValueError: If filter_fn is provided but filter_name is not.
        """
        if not queries:
            raise ValueError("Query list cannot be empty")

        # Validate filter_name requirement when using filters
        if filter_fn is not None and filter_name is None:
            raise ValueError(
                "filter_name is required when using filter_fn. "
                "Provide a filter_name to identify the filtered baseline."
            )

        individual_recalls = []
        skipped_queries = 0  # Track queries with no ground truth
        search_fn = hnsw_filter if hnsw_filter else self._hnsw_search

        for query in queries:
            # Get ground truth from brute-force
            if filter_fn:
                exact_results = self._brute_force.search_with_filter(query, k, filter_fn)
            else:
                exact_results = self._brute_force.search(query, k)

            exact_ids = {r.document_id for r in exact_results}

            # Get HNSW results
            hnsw_results = search_fn(query, k)
            hnsw_ids = {r.document_id for r in hnsw_results}

            # Compute recall for this query
            if len(exact_ids) == 0:
                # No ground truth results - this is a data issue that should
                # be investigated. We exclude it from recall calculation to
                # avoid masking problems. Track separately.
                skipped_queries += 1
                continue
            else:
                intersection = exact_ids & hnsw_ids
                query_recall = len(intersection) / len(exact_ids)
                individual_recalls.append(query_recall)

        # Check if any queries had results
        if not individual_recalls:
            raise ValueError(
                f"All {len(queries)} queries returned no ground truth results. "
                "This indicates a data issue - check that the corpus is indexed "
                "and that filters are not excluding all documents."
            )

        # Average recall across queries with valid results
        avg_recall = sum(individual_recalls) / len(individual_recalls)

        # Check against baseline for drift
        filtered = filter_fn is not None
        # Load baseline using the provided filter_name (None for unfiltered)
        baseline = self._baseline_store.load_baseline(filtered, filter_name)

        baseline_recall = None
        drift_pct = None
        passed_drift = True

        if baseline:
            # Validate baseline compatibility before using for drift detection
            if baseline.k != k:
                # k-value mismatch - baseline not comparable
                baseline = None
            elif baseline.embedding_model != self._embedding_model:
                # Model mismatch - baseline not comparable
                baseline = None
            elif baseline.embedding_version != self._embedding_version:
                # Version mismatch - baseline not comparable
                baseline = None

        if baseline:
            baseline_recall = baseline.recall_at_k
            drift_pct = self._baseline_store.compute_drift(avg_recall, baseline)
            passed_drift = drift_pct <= self.DRIFT_THRESHOLD

        return RecallHealthResult(
            recall_at_k=avg_recall,
            k=k,
            query_count=len(queries),
            filtered=filtered,
            timestamp=datetime.now(),
            passed_absolute=avg_recall >= self.ABSOLUTE_THRESHOLD,
            passed_drift=passed_drift,
            baseline_recall=baseline_recall,
            drift_pct=drift_pct,
            filter_name=filter_name,
            individual_recalls=individual_recalls,
        )

    def check_health(
        self,
        queries: list[str],
        k: int = 10,
    ) -> RecallHealthResult:
        """Full health check with threshold evaluation.

        This is the primary method for health checks. It measures Recall@k
        for unfiltered search and checks against both absolute and drift
        thresholds.

        Args:
            queries: List of query strings (golden query set).
            k: Number of results to consider.

        Returns:
            RecallHealthResult with pass/fail status.
        """
        return self.measure_recall_at_k(queries, k)

    def check_filtered_health(
        self,
        queries: list[str],
        filter_fn: Callable[[Document], bool],
        hnsw_filter: Callable[[str, int], list[SearchResult]],
        filter_name: str,
        k: int = 10,
    ) -> RecallHealthResult:
        """Health check for filtered (tenant/tag) search.

        This checks for "filter-induced recall collapse" where HNSW
        graph fragmentation degrades recall for filtered queries.

        Args:
            queries: List of query strings.
            filter_fn: Filter function for brute-force search.
            hnsw_filter: Filtered HNSW search function.
            filter_name: Name for the filter (e.g., "tenant_123").
            k: Number of results to consider.

        Returns:
            RecallHealthResult with filter context.
        """
        # Pass filter_name through for proper baseline lookup
        return self.measure_recall_at_k(
            queries,
            k,
            filter_fn=filter_fn,
            hnsw_filter=hnsw_filter,
            filter_name=filter_name,
        )

    def should_reindex(self, result: RecallHealthResult) -> bool:
        """Determine if recall degradation requires reindex.

        Args:
            result: Health check result.

        Returns:
            True if reindex is recommended.
        """
        return not result.passed

    def establish_baseline(
        self,
        queries: list[str],
        k: int = 10,
        filter_fn: Callable[[Document], bool] | None = None,
        filter_name: str | None = None,
    ) -> RecallBaseline:
        """Establish a new recall baseline.

        Use after reindexing or initial setup to create a new baseline
        for future drift detection.

        Args:
            queries: List of query strings.
            k: Number of results to consider.
            filter_fn: Optional filter for filtered baseline.
            filter_name: Name for filtered baseline (required if filter_fn is provided).

        Returns:
            The created RecallBaseline.

        Raises:
            ValueError: If filter_fn is provided but filter_name is not.
        """
        # Validate that filter_name is provided when using a filter
        if filter_fn is not None and filter_name is None:
            raise ValueError(
                "filter_name is required when establishing a filtered baseline. "
                "Provide a filter_name to identify this filtered baseline."
            )

        # Pass filter_name through for proper baseline handling
        result = self.measure_recall_at_k(queries, k, filter_fn=filter_fn, filter_name=filter_name)

        # Use sanitized filter name to avoid storing PII in baseline files
        # The sanitized name is safe for filenames and won't contain sensitive data
        sanitized_filter_name = None
        if filter_name:
            sanitized_filter_name = self._baseline_store._sanitize_filter_name(filter_name)

        baseline = RecallBaseline(
            recall_at_k=result.recall_at_k,
            k=k,
            query_count=len(queries),
            embedding_model=self._embedding_model,
            embedding_version=self._embedding_version,
            created_at=datetime.now(),
            corpus_size=self._brute_force.corpus_size,
            filtered=result.filtered,
            filter_description=sanitized_filter_name,  # Sanitized, not raw
        )

        self._baseline_store.save_baseline(baseline, filter_name)
        return baseline

    def get_statistics(self, result: RecallHealthResult) -> dict[str, Any]:
        """Get detailed statistics for a health check result.

        Args:
            result: Health check result.

        Returns:
            Dictionary with min, max, std, percentiles of recall values.
        """
        import statistics

        if not result.individual_recalls:
            return {}

        recalls = result.individual_recalls
        return {
            "min_recall": min(recalls),
            "max_recall": max(recalls),
            "mean_recall": result.recall_at_k,
            "std_recall": statistics.stdev(recalls) if len(recalls) > 1 else 0.0,
            "p25_recall": sorted(recalls)[len(recalls) // 4],
            "p50_recall": sorted(recalls)[len(recalls) // 2],
            "p75_recall": sorted(recalls)[3 * len(recalls) // 4],
            "queries_below_threshold": sum(1 for r in recalls if r < self.ABSOLUTE_THRESHOLD),
        }
