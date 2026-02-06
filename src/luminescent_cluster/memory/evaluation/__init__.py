# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
Memory Evaluation module (ADR-003).

Provides evaluation harness, reporting, and metrics for memory system quality,
plus Phase 2 token efficiency measurement and HNSW recall health monitoring.

Related GitHub Issues:
- #78: Create Evaluation Harness (Phase 0)
- #116: Phase 2: Memory Blocks Architecture

ADR Reference: ADR-003 Memory Architecture
"""

from .baseline import BaselineStore, RecallBaseline
from .brute_force import BruteForceResult, BruteForceSearcher, Document
from .embedding_version import EmbeddingVersion, EmbeddingVersionTracker
from .harness import EvaluationHarness
from .metrics import f1_score, precision, recall
from .recall_health import RecallHealthMonitor, RecallHealthResult
from .reporter import EvaluationReport
from .token_efficiency import TokenEfficiencyMetric

__all__ = [
    # Phase 0 evaluation
    "EvaluationHarness",
    "EvaluationReport",
    "precision",
    "recall",
    "f1_score",
    # Phase 0 HNSW recall health monitoring
    "BruteForceSearcher",
    "BruteForceResult",
    "Document",
    "RecallHealthMonitor",
    "RecallHealthResult",
    "BaselineStore",
    "RecallBaseline",
    "EmbeddingVersionTracker",
    "EmbeddingVersion",
    # Phase 2 token efficiency
    "TokenEfficiencyMetric",
]
