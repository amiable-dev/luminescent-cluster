# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Evaluation harness for memory system.

Provides the EvaluationHarness class for running golden dataset
evaluations and computing metrics.

Related GitHub Issues:
- #78: Create Evaluation Harness

ADR Reference: ADR-003 Memory Architecture, Phase 0 (Foundations)
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from src.memory.evaluation.reporter import EvaluationReport


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

                # Evaluate success
                success = True
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

        # Calculate metrics
        total = len(self.questions)
        accuracy_val = passed / total if total > 0 else 0.0

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
            precision=accuracy_val,  # Simplified for now
            recall=accuracy_val,  # Simplified for now
            f1=accuracy_val,  # Simplified for now
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
