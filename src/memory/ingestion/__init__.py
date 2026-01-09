# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Grounded Memory Ingestion - ADR-003 Phase 2.

Prevents hallucination write-back by validating memory content before storage
using a 3-tier provenance model.

Tiers:
- Tier 1 (Auto-approve): Content with citations, user-stated facts
- Tier 2 (Flag for review): AI claims without sources
- Tier 3 (Block): Speculative content, duplicates
"""

from src.memory.ingestion.citation_detector import Citation, CitationDetector
from src.memory.ingestion.dedup_checker import DedupCheckError, DedupChecker
from src.memory.ingestion.evidence import EvidenceObject
from src.memory.ingestion.hedge_detector import HedgeDetector
from src.memory.ingestion.result import IngestionTier, ValidationResult
from src.memory.ingestion.review_queue import PendingMemory, ReviewQueue
from src.memory.ingestion.validator import IngestionValidator

__all__ = [
    # Core types
    "EvidenceObject",
    "ValidationResult",
    "IngestionTier",
    # Detectors
    "CitationDetector",
    "Citation",
    "HedgeDetector",
    "DedupChecker",
    "DedupCheckError",
    # Validator
    "IngestionValidator",
    # Review queue
    "ReviewQueue",
    "PendingMemory",
]
