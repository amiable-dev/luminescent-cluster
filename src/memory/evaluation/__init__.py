# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
Memory Evaluation module (ADR-003).

Provides evaluation harness, reporting, and metrics for memory system quality,
plus Phase 2 token efficiency measurement.

Related GitHub Issues:
- #78: Create Evaluation Harness (Phase 0)
- #116: Phase 2: Memory Blocks Architecture

ADR Reference: ADR-003 Memory Architecture
"""

from .harness import EvaluationHarness
from .metrics import f1_score, precision, recall
from .reporter import EvaluationReport
from .token_efficiency import TokenEfficiencyMetric

__all__ = [
    # Phase 0 evaluation
    "EvaluationHarness",
    "EvaluationReport",
    "precision",
    "recall",
    "f1_score",
    # Phase 2 token efficiency
    "TokenEfficiencyMetric",
]
