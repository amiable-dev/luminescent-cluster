# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Mock extractor for testing without API calls.

Provides a pattern-based extractor for development and testing.

Related GitHub Issues:
- #91: Extraction UDF Interface

ADR Reference: ADR-003 Memory Architecture, Phase 1b (Async Extraction)
"""

import re
from typing import List

from src.memory.extraction.confidence import calculate_confidence
from src.memory.extraction.types import ExtractionResult

# Patterns for preference detection
PREFERENCE_PATTERNS = [
    (r"i (?:prefer|like|use|always use|want) (.+?)(?:\.|$)", "preference"),
    (r"my (?:favorite|preferred) (.+?)(?:\.|$)", "preference"),
    (r"i (?:always|usually|typically) (.+?)(?:\.|$)", "preference"),
]

# Patterns for fact detection
FACT_PATTERNS = [
    (r"(?:the|our|this) (?:api|system|service|project) (?:uses|has|runs on) (.+?)(?:\.|$)", "fact"),
    (r"(?:we use|using|built with) (.+?)(?:\.|$)", "fact"),
    (r"(.+?) is (?:the|our) (?:database|framework|language)", "fact"),
]

# Patterns for decision detection
DECISION_PATTERNS = [
    (r"(?:we|i) (?:decided|chose|selected|picked|opted) (?:to )?(.+?)(?:\.|$)", "decision"),
    (r"(?:decided|chose) (.+?) (?:over|instead of) (.+?)(?:\.|$)", "decision"),
    (r"we (?:went with|are going with) (.+?)(?:\.|$)", "decision"),
]


class MockExtractor:
    """Pattern-based memory extractor for testing.

    Uses regular expressions to detect preferences, facts, and decisions
    without requiring API calls. Suitable for development and testing.

    Example:
        >>> extractor = MockExtractor()
        >>> results = await extractor.extract("I prefer tabs over spaces")
        >>> print(results[0].memory_type)
        'preference'
    """

    async def extract(self, text: str) -> List[ExtractionResult]:
        """Extract memories from text using pattern matching.

        Args:
            text: Conversation text to analyze.

        Returns:
            List of ExtractionResult objects.
        """
        results: List[ExtractionResult] = []
        text_lower = text.lower()

        # Check preference patterns
        for pattern, memory_type in PREFERENCE_PATTERNS:
            for match in re.finditer(pattern, text_lower, re.IGNORECASE):
                content = self._clean_extraction(match.group(0))
                confidence = calculate_confidence(content, text, memory_type)
                results.append(
                    ExtractionResult(
                        content=content,
                        memory_type=memory_type,
                        confidence=confidence,
                        raw_source=text,
                    )
                )

        # Check fact patterns
        for pattern, memory_type in FACT_PATTERNS:
            for match in re.finditer(pattern, text_lower, re.IGNORECASE):
                content = self._clean_extraction(match.group(0))
                confidence = calculate_confidence(content, text, memory_type)
                results.append(
                    ExtractionResult(
                        content=content,
                        memory_type=memory_type,
                        confidence=confidence,
                        raw_source=text,
                    )
                )

        # Check decision patterns
        for pattern, memory_type in DECISION_PATTERNS:
            for match in re.finditer(pattern, text_lower, re.IGNORECASE):
                content = self._clean_extraction(match.group(0))
                confidence = calculate_confidence(content, text, memory_type)
                results.append(
                    ExtractionResult(
                        content=content,
                        memory_type=memory_type,
                        confidence=confidence,
                        raw_source=text,
                    )
                )

        return results

    def _clean_extraction(self, text: str) -> str:
        """Clean extracted text."""
        # Capitalize first letter
        text = text.strip()
        if text:
            text = text[0].upper() + text[1:]
        # Remove trailing punctuation
        text = text.rstrip(".")
        return text
