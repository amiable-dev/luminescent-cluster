# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Confidence scoring for memory extraction.

Provides functions for calculating extraction confidence scores
based on text analysis.

Related GitHub Issues:
- #94: Confidence Scoring

ADR Reference: ADR-003 Memory Architecture, Phase 1b (Async Extraction)
"""

import re
from typing import Optional

# Keywords that indicate explicit statements (higher confidence)
EXPLICIT_PREFERENCE_KEYWORDS = [
    "prefer",
    "always use",
    "i use",
    "i like",
    "my favorite",
    "i want",
    "i need",
]

EXPLICIT_FACT_KEYWORDS = [
    "uses",
    "is",
    "has",
    "runs on",
    "built with",
    "implemented in",
]

EXPLICIT_DECISION_KEYWORDS = [
    "decided",
    "chose",
    "we went with",
    "selected",
    "picked",
    "opted for",
]

# Keywords that indicate uncertainty (lower confidence)
UNCERTAINTY_KEYWORDS = [
    "maybe",
    "might",
    "could",
    "sometimes",
    "probably",
    "possibly",
    "i think",
    "perhaps",
]


def calculate_confidence(
    extraction_text: str,
    source_text: str,
    memory_type: str,
    base_confidence: float = 0.7,
) -> float:
    """Calculate confidence score for an extraction.

    Args:
        extraction_text: The extracted memory content.
        source_text: The original source text.
        memory_type: Type of memory (preference, fact, decision).
        base_confidence: Starting confidence score.

    Returns:
        Confidence score between 0.0 and 1.0.
    """
    confidence = base_confidence
    source_lower = source_text.lower()
    extraction_lower = extraction_text.lower()

    # Check for explicit keywords based on memory type
    explicit_keywords = []
    if memory_type == "preference":
        explicit_keywords = EXPLICIT_PREFERENCE_KEYWORDS
    elif memory_type == "fact":
        explicit_keywords = EXPLICIT_FACT_KEYWORDS
    elif memory_type == "decision":
        explicit_keywords = EXPLICIT_DECISION_KEYWORDS

    # Boost confidence for explicit statements
    for keyword in explicit_keywords:
        if keyword in source_lower:
            confidence += 0.1
            break  # Only boost once

    # Reduce confidence for uncertainty
    for keyword in UNCERTAINTY_KEYWORDS:
        if keyword in source_lower:
            confidence -= 0.15
            break  # Only reduce once

    # Boost confidence if extraction closely matches source
    if extraction_lower in source_lower:
        confidence += 0.05

    # Check for first-person statements (more confident)
    if re.search(r"\bi\b|\bwe\b|\bmy\b|\bour\b", source_lower):
        confidence += 0.05

    # Clamp to [0.0, 1.0]
    return max(0.0, min(1.0, confidence))
