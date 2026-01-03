# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Memory evaluation harness for ADR-003.

This module provides the evaluation harness for running golden dataset
tests and computing accuracy metrics.

Related GitHub Issues:
- #78: Create Evaluation Harness

ADR Reference: ADR-003 Memory Architecture, Phase 0 (Foundations)
"""

from src.memory.evaluation.harness import (
    EvaluationHarness,
    EvaluationResult,
    GoldenDatasetQuestion,
)
from src.memory.evaluation.metrics import (
    accuracy,
    f1_score,
    precision,
    recall,
)
from src.memory.evaluation.reporter import (
    EvaluationReport,
    generate_json_report,
    generate_markdown_report,
)

__all__ = [
    # Harness
    "EvaluationHarness",
    "EvaluationResult",
    "GoldenDatasetQuestion",
    # Metrics
    "precision",
    "recall",
    "f1_score",
    "accuracy",
    # Reporter
    "EvaluationReport",
    "generate_json_report",
    "generate_markdown_report",
]
