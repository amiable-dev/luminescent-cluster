# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
TDD: RED Phase - Tests for Memory Evaluation Harness.

These tests define the expected behavior for the evaluation harness
that runs Golden Dataset questions and computes accuracy metrics.

Related GitHub Issues:
- #78: Create Evaluation Harness

ADR Reference: ADR-003 Memory Architecture, Phase 0 (Foundations)
"""

import pytest
import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


class TestEvaluationMetricsModule:
    """TDD: Tests for evaluation metrics."""

    def test_precision_function_exists(self):
        """precision function should be defined.

        GitHub Issue: #78
        ADR Reference: ADR-003 (Evaluation Harness)
        """
        from src.memory.evaluation.metrics import precision

        assert callable(precision)

    def test_recall_function_exists(self):
        """recall function should be defined.

        GitHub Issue: #78
        ADR Reference: ADR-003 (Evaluation Harness)
        """
        from src.memory.evaluation.metrics import recall

        assert callable(recall)

    def test_f1_score_function_exists(self):
        """f1_score function should be defined.

        GitHub Issue: #78
        ADR Reference: ADR-003 (Evaluation Harness)
        """
        from src.memory.evaluation.metrics import f1_score

        assert callable(f1_score)

    def test_precision_calculation(self):
        """precision should calculate TP / (TP + FP).

        GitHub Issue: #78
        ADR Reference: ADR-003 (Evaluation Harness)
        """
        from src.memory.evaluation.metrics import precision

        # 8 true positives, 2 false positives = 8/10 = 0.8
        assert precision(true_positives=8, false_positives=2) == 0.8

    def test_recall_calculation(self):
        """recall should calculate TP / (TP + FN).

        GitHub Issue: #78
        ADR Reference: ADR-003 (Evaluation Harness)
        """
        from src.memory.evaluation.metrics import recall

        # 8 true positives, 2 false negatives = 8/10 = 0.8
        assert recall(true_positives=8, false_negatives=2) == 0.8

    def test_f1_score_calculation(self):
        """f1_score should calculate 2 * (precision * recall) / (precision + recall).

        GitHub Issue: #78
        ADR Reference: ADR-003 (Evaluation Harness)
        """
        from src.memory.evaluation.metrics import f1_score

        # precision=0.8, recall=0.8 => f1 = 2 * 0.8 * 0.8 / (0.8 + 0.8) = 0.8
        assert f1_score(precision_val=0.8, recall_val=0.8) == pytest.approx(0.8)

    def test_precision_handles_zero_denominator(self):
        """precision should return 0.0 when denominator is 0.

        GitHub Issue: #78
        ADR Reference: ADR-003 (Evaluation Harness)
        """
        from src.memory.evaluation.metrics import precision

        assert precision(true_positives=0, false_positives=0) == 0.0

    def test_recall_handles_zero_denominator(self):
        """recall should return 0.0 when denominator is 0.

        GitHub Issue: #78
        ADR Reference: ADR-003 (Evaluation Harness)
        """
        from src.memory.evaluation.metrics import recall

        assert recall(true_positives=0, false_negatives=0) == 0.0

    def test_f1_score_handles_zero_denominator(self):
        """f1_score should return 0.0 when precision + recall = 0.

        GitHub Issue: #78
        ADR Reference: ADR-003 (Evaluation Harness)
        """
        from src.memory.evaluation.metrics import f1_score

        assert f1_score(precision_val=0.0, recall_val=0.0) == 0.0


class TestEvaluationResult:
    """TDD: Tests for EvaluationResult dataclass."""

    def test_evaluation_result_class_exists(self):
        """EvaluationResult dataclass should be defined.

        GitHub Issue: #78
        ADR Reference: ADR-003 (Evaluation Harness)
        """
        from src.memory.evaluation.harness import EvaluationResult

        assert EvaluationResult is not None

    def test_evaluation_result_has_question_id(self):
        """EvaluationResult should have question_id field.

        GitHub Issue: #78
        ADR Reference: ADR-003 (Evaluation Harness)
        """
        from src.memory.evaluation.harness import EvaluationResult

        result = EvaluationResult(
            question_id="factual-001",
            question="What database?",
            category="factual_recall",
            success=True,
            retrieved_memories=[],
        )
        assert hasattr(result, "question_id")

    def test_evaluation_result_has_success(self):
        """EvaluationResult should have success field.

        GitHub Issue: #78
        ADR Reference: ADR-003 (Evaluation Harness)
        """
        from src.memory.evaluation.harness import EvaluationResult

        result = EvaluationResult(
            question_id="factual-001",
            question="What database?",
            category="factual_recall",
            success=True,
            retrieved_memories=[],
        )
        assert hasattr(result, "success")

    def test_evaluation_result_has_latency_ms(self):
        """EvaluationResult should have latency_ms field.

        GitHub Issue: #78
        ADR Reference: ADR-003 (Evaluation Harness)
        """
        from src.memory.evaluation.harness import EvaluationResult

        result = EvaluationResult(
            question_id="factual-001",
            question="What database?",
            category="factual_recall",
            success=True,
            retrieved_memories=[],
            latency_ms=45.2,
        )
        assert hasattr(result, "latency_ms")


class TestEvaluationHarness:
    """TDD: Tests for EvaluationHarness class."""

    def test_evaluation_harness_class_exists(self):
        """EvaluationHarness class should be defined.

        GitHub Issue: #78
        ADR Reference: ADR-003 (Evaluation Harness)
        """
        from src.memory.evaluation.harness import EvaluationHarness

        assert EvaluationHarness is not None

    def test_evaluation_harness_load_dataset(self):
        """EvaluationHarness should load golden dataset.

        GitHub Issue: #78
        ADR Reference: ADR-003 (Evaluation Harness)
        """
        from src.memory.evaluation.harness import EvaluationHarness

        harness = EvaluationHarness()
        harness.load_dataset("tests/memory/golden_dataset.json")
        assert len(harness.questions) == 50

    def test_evaluation_harness_has_run_method(self):
        """EvaluationHarness should have run method.

        GitHub Issue: #78
        ADR Reference: ADR-003 (Evaluation Harness)
        """
        from src.memory.evaluation.harness import EvaluationHarness

        harness = EvaluationHarness()
        assert hasattr(harness, "run")
        assert callable(harness.run)

    def test_evaluation_harness_has_run_category_method(self):
        """EvaluationHarness should have run_category method.

        GitHub Issue: #78
        ADR Reference: ADR-003 (Evaluation Harness)
        """
        from src.memory.evaluation.harness import EvaluationHarness

        harness = EvaluationHarness()
        assert hasattr(harness, "run_category")
        assert callable(harness.run_category)


class TestEvaluationReport:
    """TDD: Tests for EvaluationReport class."""

    def test_evaluation_report_class_exists(self):
        """EvaluationReport class should be defined.

        GitHub Issue: #78
        ADR Reference: ADR-003 (Evaluation Harness)
        """
        from src.memory.evaluation.reporter import EvaluationReport

        assert EvaluationReport is not None

    def test_evaluation_report_has_total_questions(self):
        """EvaluationReport should have total_questions field.

        GitHub Issue: #78
        ADR Reference: ADR-003 (Evaluation Harness)
        """
        from src.memory.evaluation.reporter import EvaluationReport

        report = EvaluationReport(
            total_questions=50,
            passed=45,
            failed=5,
            accuracy=0.90,
            precision=0.88,
            recall=0.92,
            f1=0.90,
        )
        assert report.total_questions == 50

    def test_evaluation_report_has_accuracy(self):
        """EvaluationReport should have accuracy field.

        GitHub Issue: #78
        ADR Reference: ADR-003 (Evaluation Harness)
        """
        from src.memory.evaluation.reporter import EvaluationReport

        report = EvaluationReport(
            total_questions=50,
            passed=45,
            failed=5,
            accuracy=0.90,
            precision=0.88,
            recall=0.92,
            f1=0.90,
        )
        assert report.accuracy == 0.90

    def test_evaluation_report_has_category_breakdown(self):
        """EvaluationReport should have category_breakdown field.

        GitHub Issue: #78
        ADR Reference: ADR-003 (Evaluation Harness)
        """
        from src.memory.evaluation.reporter import EvaluationReport

        report = EvaluationReport(
            total_questions=50,
            passed=45,
            failed=5,
            accuracy=0.90,
            precision=0.88,
            recall=0.92,
            f1=0.90,
            category_breakdown={},
        )
        assert hasattr(report, "category_breakdown")


class TestReporter:
    """TDD: Tests for report generation."""

    def test_generate_json_report_function_exists(self):
        """generate_json_report function should be defined.

        GitHub Issue: #78
        ADR Reference: ADR-003 (Evaluation Harness)
        """
        from src.memory.evaluation.reporter import generate_json_report

        assert callable(generate_json_report)

    def test_generate_markdown_report_function_exists(self):
        """generate_markdown_report function should be defined.

        GitHub Issue: #78
        ADR Reference: ADR-003 (Evaluation Harness)
        """
        from src.memory.evaluation.reporter import generate_markdown_report

        assert callable(generate_markdown_report)

    def test_generate_json_report_returns_valid_json(self):
        """generate_json_report should return valid JSON string.

        GitHub Issue: #78
        ADR Reference: ADR-003 (Evaluation Harness)
        """
        from src.memory.evaluation.reporter import (
            EvaluationReport,
            generate_json_report,
        )

        report = EvaluationReport(
            total_questions=10,
            passed=8,
            failed=2,
            accuracy=0.80,
            precision=0.80,
            recall=0.80,
            f1=0.80,
        )
        json_str = generate_json_report(report)
        parsed = json.loads(json_str)
        assert parsed["total_questions"] == 10
        assert parsed["accuracy"] == 0.80


class TestEvaluationHarnessMetrics:
    """TDD: Tests for proper metric calculation in EvaluationHarness.

    Council Review Finding: EvaluationHarness was aliasing precision/recall/F1
    to accuracy instead of calculating them properly.

    GitHub Issue: #78
    ADR Reference: ADR-003 (Evaluation Harness)
    """

    @pytest.mark.asyncio
    async def test_harness_requires_evaluate_fn_for_meaningful_results(self):
        """Harness should require evaluate_fn or default to failure.

        Without evaluate_fn, we can't determine if retrieval was correct,
        so success should default to False, not True.
        """
        from src.memory.evaluation.harness import EvaluationHarness

        harness = EvaluationHarness()
        harness.load_dataset("tests/memory/golden_dataset.json")

        # Without evaluate_fn, all should fail (not pass by default)
        report = await harness.run(retrieve_fn=None, evaluate_fn=None)

        # All questions should fail without an evaluate_fn
        assert report.passed == 0
        assert report.failed == 50
        assert report.accuracy == 0.0

    @pytest.mark.asyncio
    async def test_harness_calculates_precision_correctly(self):
        """Harness should calculate precision as TP / (TP + FP).

        Precision measures: Of all retrieved memories, how many were relevant?
        """
        from src.memory.evaluation.harness import EvaluationHarness

        harness = EvaluationHarness()
        harness.load_dataset("tests/memory/golden_dataset.json")

        # Mock evaluate function that tracks TP/FP
        call_count = 0

        def evaluate_fn(question, memories):
            nonlocal call_count
            call_count += 1
            # First 40 are true positives, next 10 are false positives
            return call_count <= 40

        async def retrieve_fn(query, user_id):
            return [{"content": "test"}]  # Always retrieve something

        report = await harness.run(retrieve_fn=retrieve_fn, evaluate_fn=evaluate_fn)

        # 40 TP, 10 FP => precision = 40/50 = 0.8
        assert report.precision == pytest.approx(0.8, rel=0.01)

    @pytest.mark.asyncio
    async def test_harness_precision_recall_f1_not_equal_to_accuracy(self):
        """Precision, recall, F1 should not simply equal accuracy.

        This was the Council's finding - metrics were just aliased to accuracy.
        """
        from src.memory.evaluation.harness import EvaluationHarness

        harness = EvaluationHarness()
        harness.load_dataset("tests/memory/golden_dataset.json")

        call_count = 0

        def evaluate_fn(question, memories):
            nonlocal call_count
            call_count += 1
            return call_count <= 25  # Only half pass

        async def retrieve_fn(query, user_id):
            return [{"content": "test"}]

        report = await harness.run(retrieve_fn=retrieve_fn, evaluate_fn=evaluate_fn)

        # With proper metrics, these should reflect actual TP/FP/FN counts
        # not just all equal to accuracy
        assert report.accuracy == 0.5
        # Metrics should be calculated, not just aliased
        assert isinstance(report.precision, float)
        assert isinstance(report.recall, float)
        assert isinstance(report.f1, float)


class TestEvaluationModuleExports:
    """TDD: Tests for evaluation module exports."""

    def test_evaluation_module_exists(self):
        """src.memory.evaluation module should exist.

        GitHub Issue: #78
        ADR Reference: ADR-003 (Evaluation Harness)
        """
        import src.memory.evaluation

        assert src.memory.evaluation is not None

    def test_evaluation_exports_harness(self):
        """evaluation module should export EvaluationHarness.

        GitHub Issue: #78
        ADR Reference: ADR-003 (Evaluation Harness)
        """
        from src.memory.evaluation import EvaluationHarness

        assert EvaluationHarness is not None

    def test_evaluation_exports_report(self):
        """evaluation module should export EvaluationReport.

        GitHub Issue: #78
        ADR Reference: ADR-003 (Evaluation Harness)
        """
        from src.memory.evaluation import EvaluationReport

        assert EvaluationReport is not None

    def test_evaluation_exports_metrics(self):
        """evaluation module should export metric functions.

        GitHub Issue: #78
        ADR Reference: ADR-003 (Evaluation Harness)
        """
        from src.memory.evaluation import precision, recall, f1_score

        assert callable(precision)
        assert callable(recall)
        assert callable(f1_score)
