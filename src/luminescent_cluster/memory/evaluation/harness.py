# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Evaluation harness for memory system.

Provides the EvaluationHarness class for running golden dataset
evaluations and computing metrics, including HNSW recall health monitoring.

Related GitHub Issues:
- #78: Create Evaluation Harness

ADR Reference: ADR-003 Memory Architecture, Phase 0 (Foundations, HNSW Recall Health)
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional

from luminescent_cluster.memory.evaluation.reporter import EvaluationReport

if TYPE_CHECKING:
    from luminescent_cluster.memory.evaluation.baseline import BaselineStore
    from luminescent_cluster.memory.evaluation.brute_force import BruteForceSearcher
    from luminescent_cluster.memory.evaluation.recall_health import (
        RecallHealthMonitor,
        RecallHealthResult,
        SearchResult,
    )


@dataclass
class EvaluationResult:
    """Result of evaluating a single question.

    Attributes:
        question_id: Unique identifier for the question.
        question: The question text.
        category: Category of the question (e.g., factual_recall).
        success: Whether the evaluation was successful.
        retrieved_memories: List of memories retrieved for this question.
        expected_memory_type: Expected type of memory (fact, preference, decision).
        latency_ms: Time taken to retrieve memories in milliseconds.
        error: Error message if evaluation failed.
    """

    question_id: str
    question: str
    category: str
    success: bool
    retrieved_memories: list[Any] = field(default_factory=list)
    expected_memory_type: Optional[str] = None
    latency_ms: Optional[float] = None
    error: Optional[str] = None


@dataclass
class GoldenDatasetQuestion:
    """A question from the golden dataset.

    Attributes:
        id: Unique identifier for the question.
        category: Category of the question.
        question: The question text.
        expected_memory_type: Expected type of memory.
        expected_scope: Expected scope of memory (user, project, global).
        expected_source: Expected source of memory (adr, code, conversation).
    """

    id: str
    category: str
    question: str
    expected_memory_type: str
    expected_scope: str
    expected_source: str


class EvaluationHarness:
    """Harness for running golden dataset evaluations.

    The harness loads a golden dataset, runs each question against
    a memory provider, and computes accuracy metrics.

    Example:
        >>> harness = EvaluationHarness()
        >>> harness.load_dataset("tests/memory/golden_dataset.json")
        >>> report = await harness.run(memory_provider)
        >>> print(f"Accuracy: {report.accuracy}")
    """

    def __init__(self):
        """Initialize the evaluation harness."""
        self.questions: list[GoldenDatasetQuestion] = []
        self.dataset_version: Optional[str] = None
        self.results: list[EvaluationResult] = []

    def load_dataset(self, path: str) -> None:
        """Load a golden dataset from a JSON file.

        Args:
            path: Path to the golden dataset JSON file.

        Raises:
            FileNotFoundError: If the file does not exist.
            json.JSONDecodeError: If the file is not valid JSON.
        """
        dataset_path = Path(path)
        with open(dataset_path) as f:
            data = json.load(f)

        self.dataset_version = data.get("version", "unknown")
        self.questions = []

        for q in data.get("questions", []):
            self.questions.append(
                GoldenDatasetQuestion(
                    id=q["id"],
                    category=q["category"],
                    question=q["question"],
                    expected_memory_type=q["expected_memory_type"],
                    expected_scope=q["expected_scope"],
                    expected_source=q["expected_source"],
                )
            )

    async def run(
        self,
        retrieve_fn: Optional[Callable] = None,
        evaluate_fn: Optional[Callable] = None,
    ) -> EvaluationReport:
        """Run evaluation on all questions in the dataset.

        Args:
            retrieve_fn: Async function to retrieve memories for a question.
                         Signature: async (query: str, user_id: str) -> list[Memory]
            evaluate_fn: Function to evaluate if retrieved memories are correct.
                         Signature: (question: GoldenDatasetQuestion, memories: list) -> bool

        Returns:
            EvaluationReport with accuracy metrics.
        """
        self.results = []
        passed = 0
        failed = 0
        category_results: dict[str, dict[str, int]] = {}

        for question in self.questions:
            # Initialize category tracking
            if question.category not in category_results:
                category_results[question.category] = {"passed": 0, "failed": 0}

            start_time = time.perf_counter()

            try:
                # Retrieve memories
                memories = []
                if retrieve_fn:
                    memories = await retrieve_fn(question.question, "test-user")

                # Evaluate success - default to False if no evaluate_fn
                # (Council Review: Can't determine correctness without evaluation)
                success = False
                if evaluate_fn:
                    success = evaluate_fn(question, memories)

                latency_ms = (time.perf_counter() - start_time) * 1000

                result = EvaluationResult(
                    question_id=question.id,
                    question=question.question,
                    category=question.category,
                    success=success,
                    retrieved_memories=memories,
                    expected_memory_type=question.expected_memory_type,
                    latency_ms=latency_ms,
                )

                if success:
                    passed += 1
                    category_results[question.category]["passed"] += 1
                else:
                    failed += 1
                    category_results[question.category]["failed"] += 1

            except Exception as e:
                latency_ms = (time.perf_counter() - start_time) * 1000
                result = EvaluationResult(
                    question_id=question.id,
                    question=question.question,
                    category=question.category,
                    success=False,
                    latency_ms=latency_ms,
                    error=str(e),
                )
                failed += 1
                category_results[question.category]["failed"] += 1

            self.results.append(result)

        # Calculate metrics using the metrics module
        # (Council Review: Use proper metric calculations, not aliases)
        # (Council Review 2: Properly distinguish FP vs FN)
        from luminescent_cluster.memory.evaluation.metrics import (
            accuracy as calc_accuracy,
            f1_score,
            precision as calc_precision,
            recall as calc_recall,
        )

        total = len(self.questions)
        accuracy_val = calc_accuracy(passed, total)

        # Count true positives, false positives, false negatives from results
        # - TP: passed (evaluate_fn returned True, memories were correct)
        # - FP: failed WITH non-empty retrieval (got wrong results)
        # - FN: failed WITH empty retrieval (missed relevant results)
        true_positives = passed
        false_positives = 0
        false_negatives = 0

        for result in self.results:
            if not result.success:
                if result.retrieved_memories:
                    false_positives += 1  # Retrieved but wrong
                else:
                    false_negatives += 1  # Should have retrieved but didn't

        precision_val = calc_precision(true_positives, false_positives)
        recall_val = calc_recall(true_positives, false_negatives)
        f1_val = f1_score(precision_val, recall_val)

        # Build category breakdown
        category_breakdown = {}
        for cat, counts in category_results.items():
            cat_total = counts["passed"] + counts["failed"]
            category_breakdown[cat] = {
                "passed": counts["passed"],
                "failed": counts["failed"],
                "accuracy": counts["passed"] / cat_total if cat_total > 0 else 0.0,
            }

        return EvaluationReport(
            total_questions=total,
            passed=passed,
            failed=failed,
            accuracy=accuracy_val,
            precision=precision_val,
            recall=recall_val,
            f1=f1_val,
            category_breakdown=category_breakdown,
        )

    async def run_category(
        self,
        category: str,
        retrieve_fn: Optional[Callable] = None,
        evaluate_fn: Optional[Callable] = None,
    ) -> EvaluationReport:
        """Run evaluation on questions in a specific category.

        Args:
            category: Category to run (e.g., "factual_recall").
            retrieve_fn: Async function to retrieve memories.
            evaluate_fn: Function to evaluate success.

        Returns:
            EvaluationReport for the category.
        """
        # Filter to category
        original_questions = self.questions
        self.questions = [q for q in self.questions if q.category == category]

        try:
            report = await self.run(retrieve_fn, evaluate_fn)
        finally:
            self.questions = original_questions

        return report

    # ─────────────────────────────────────────────────────────────────────────
    # HNSW Recall Health Monitoring (ADR-003 Phase 0)
    # ─────────────────────────────────────────────────────────────────────────

    def configure_recall_monitoring(
        self,
        brute_force: "BruteForceSearcher",
        hnsw_search: Callable[[str, int], list["SearchResult"]],
        baseline_store: "BaselineStore",
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
        embedding_version: str = "unknown",
    ) -> None:
        """Enable HNSW recall health monitoring.

        This configures the harness to measure Recall@k by comparing
        HNSW approximate search results against brute-force exact search.

        Args:
            brute_force: Brute-force searcher for ground truth.
            hnsw_search: Function that performs HNSW search.
            baseline_store: Store for loading/saving recall baselines.
            embedding_model: Model ID for baseline compatibility.
            embedding_version: Version hash for baseline compatibility.

        Example:
            >>> harness = EvaluationHarness()
            >>> harness.load_dataset("tests/memory/golden_dataset.json")
            >>> harness.configure_recall_monitoring(
            ...     brute_force=brute_force_searcher,
            ...     hnsw_search=pixeltable_search,
            ...     baseline_store=BaselineStore(Path("/data/baselines")),
            ... )
            >>> result = harness.run_recall_health_check()
        """
        from luminescent_cluster.memory.evaluation.recall_health import RecallHealthMonitor

        self._recall_monitor = RecallHealthMonitor(
            brute_force=brute_force,
            hnsw_search=hnsw_search,
            baseline_store=baseline_store,
            embedding_model=embedding_model,
            embedding_version=embedding_version,
        )

    def run_recall_health_check(
        self,
        k: int = 10,
        use_golden_queries: bool = True,
        queries: list[str] | None = None,
    ) -> "RecallHealthResult":
        """Run recall health check.

        Measures Recall@k for the HNSW search against brute-force
        ground truth and checks against thresholds.

        Args:
            k: Number of results to consider.
            use_golden_queries: If True, use questions from loaded dataset.
            queries: Custom queries (used if use_golden_queries=False).

        Returns:
            RecallHealthResult with pass/fail status.

        Raises:
            RuntimeError: If recall monitoring not configured.
            ValueError: If no queries available.
        """
        if not hasattr(self, "_recall_monitor") or self._recall_monitor is None:
            raise RuntimeError(
                "Recall monitoring not configured. "
                "Call configure_recall_monitoring() first."
            )

        if use_golden_queries:
            if not self.questions:
                raise ValueError(
                    "No golden queries loaded. Call load_dataset() first."
                )
            query_list = [q.question for q in self.questions]
        else:
            if not queries:
                raise ValueError("No queries provided.")
            query_list = queries

        return self._recall_monitor.check_health(query_list, k)

    def establish_recall_baseline(
        self,
        k: int = 10,
        use_golden_queries: bool = True,
        queries: list[str] | None = None,
    ) -> None:
        """Establish a new recall baseline.

        Use after reindexing or initial setup to create a baseline
        for future drift detection.

        Args:
            k: Number of results to consider.
            use_golden_queries: If True, use questions from loaded dataset.
            queries: Custom queries (used if use_golden_queries=False).

        Raises:
            RuntimeError: If recall monitoring not configured.
        """
        if not hasattr(self, "_recall_monitor") or self._recall_monitor is None:
            raise RuntimeError(
                "Recall monitoring not configured. "
                "Call configure_recall_monitoring() first."
            )

        if use_golden_queries:
            if not self.questions:
                raise ValueError(
                    "No golden queries loaded. Call load_dataset() first."
                )
            query_list = [q.question for q in self.questions]
        else:
            if not queries:
                raise ValueError("No queries provided.")
            query_list = queries

        self._recall_monitor.establish_baseline(query_list, k)
