# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Hedge word detection for grounded memory ingestion.

Detects speculative language that indicates ungrounded claims.
Content with hedge words is blocked (Tier 3) to prevent hallucination write-back.

From ADR-003 Phase 2:
> TIER 3: Block (low confidence)
>   - Speculative content ("maybe", "might", "could be")
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class HedgeDetectionResult:
    """Result of hedge word detection.

    Attributes:
        is_speculative: True if speculative language detected.
        hedge_words_found: List of hedge words found.
        speculation_score: Score from 0.0 (certain) to 1.0 (speculative).
        has_assertions: True if strong assertion markers found.
    """

    is_speculative: bool
    hedge_words_found: list[str]
    speculation_score: float
    has_assertions: bool


class HedgeDetector:
    """Detects speculative language in memory content.

    Identifies hedge words and phrases that indicate uncertainty,
    which should block memory ingestion per ADR-003 Phase 2.

    Example:
        >>> detector = HedgeDetector()
        >>> result = detector.analyze("Maybe we should use Redis")
        >>> result.is_speculative
        True
        >>> result.hedge_words_found
        ['maybe']
    """

    # Hedge words and phrases indicating speculation
    # Organized by category for maintainability
    MODAL_HEDGES = [
        "maybe",
        "might",
        "could",
        "may",
        "would",
        "should",  # "should" alone isn't always speculation
    ]

    EPISTEMIC_HEDGES = [
        "perhaps",
        "possibly",
        "probably",
        "presumably",
        "seemingly",
        "apparently",
        "supposedly",
    ]

    PERSONAL_UNCERTAINTY = [
        "i think",
        "i believe",
        "i guess",
        "i assume",
        "i suppose",
        "i imagine",
        "i suspect",
        "i wonder",
        "not sure",
        "not certain",
        "uncertain",
        "unsure",
    ]

    APPROXIMATION = [
        "seems like",
        "seems to",
        "appears to",
        "looks like",
        "kind of",
        "sort of",
        "somewhat",
        "roughly",
        "approximately",
    ]

    CONDITIONAL = [
        "if i recall",
        "if memory serves",
        "as far as i know",
        "to my knowledge",
        "from what i understand",
        "i could be wrong",
    ]

    # All hedge words/phrases combined
    HEDGE_WORDS: list[str] = (
        MODAL_HEDGES
        + EPISTEMIC_HEDGES
        + PERSONAL_UNCERTAINTY
        + APPROXIMATION
        + CONDITIONAL
    )

    # Strong assertion markers that can override hedge words
    # SECURITY: Only include specific, unambiguous assertion markers
    # that require actual supporting evidence to be meaningful.
    # Generic phrases like "according to" are excluded as they can
    # be trivially added to bypass hedge detection.
    # These markers should reduce speculation score but NOT flip is_speculative
    # unless corroborated by an actual citation (handled in validator).
    ASSERTION_MARKERS = [
        "confirmed",
        "verified",
        "definitely",
        "certainly",
    ]

    # Patterns that look like hedge words but aren't in context
    FALSE_POSITIVE_PATTERNS = [
        # "May 2024" - month, not modal verb
        re.compile(r"\bmay\s+\d{4}\b", re.IGNORECASE),
        # "might as well" - idiomatic, often asserted
        re.compile(r"\bmight\s+as\s+well\b", re.IGNORECASE),
        # "could not" / "couldn't" - negation often indicates certainty
        re.compile(r"\bcould\s*n[o']t\b", re.IGNORECASE),
        # "should be" followed by factual description
        re.compile(r"\bshould\s+be\s+\d+", re.IGNORECASE),
    ]

    def __init__(
        self,
        additional_hedge_words: Optional[list[str]] = None,
        additional_assertions: Optional[list[str]] = None,
    ):
        """Initialize the hedge detector.

        Args:
            additional_hedge_words: Extra hedge words to detect.
            additional_assertions: Extra assertion markers.
        """
        self.hedge_words = self.HEDGE_WORDS.copy()
        if additional_hedge_words:
            self.hedge_words.extend(additional_hedge_words)

        self.assertion_markers = self.ASSERTION_MARKERS.copy()
        if additional_assertions:
            self.assertion_markers.extend(additional_assertions)

        # Sort by length descending for greedy matching
        self.hedge_words.sort(key=len, reverse=True)
        self.assertion_markers.sort(key=len, reverse=True)

    def contains_hedge_words(self, content: str) -> tuple[bool, list[str]]:
        """Check if content contains hedge words.

        Args:
            content: Text to analyze.

        Returns:
            Tuple of (is_speculative, list of hedge words found).
        """
        result = self.analyze(content)
        return result.is_speculative, result.hedge_words_found

    def analyze(self, content: str) -> HedgeDetectionResult:
        """Analyze content for speculative language.

        Args:
            content: Text to analyze.

        Returns:
            HedgeDetectionResult with analysis details.
        """
        content_lower = content.lower()

        # Check for false positive patterns first
        for pattern in self.FALSE_POSITIVE_PATTERNS:
            content_lower = pattern.sub("", content_lower)

        # Find hedge words
        hedge_words_found: list[str] = []
        for hedge in self.hedge_words:
            # Use word boundary matching for short words
            if len(hedge) <= 4:
                pattern = rf"\b{re.escape(hedge)}\b"
            else:
                pattern = re.escape(hedge)

            if re.search(pattern, content_lower, re.IGNORECASE):
                if hedge not in hedge_words_found:
                    hedge_words_found.append(hedge)

        # Check for assertion markers
        has_assertions = False
        for assertion in self.assertion_markers:
            if assertion.lower() in content_lower:
                has_assertions = True
                break

        # Calculate speculation score
        speculation_score = self._calculate_speculation_score(
            content_lower,
            hedge_words_found,
            has_assertions,
        )

        # Determine if speculative
        # - If has hedge words AND no strong assertions: speculative
        # - If assertion markers present: reduce speculation confidence
        is_speculative = len(hedge_words_found) > 0 and not has_assertions

        return HedgeDetectionResult(
            is_speculative=is_speculative,
            hedge_words_found=hedge_words_found,
            speculation_score=speculation_score,
            has_assertions=has_assertions,
        )

    def _calculate_speculation_score(
        self,
        content_lower: str,
        hedge_words_found: list[str],
        has_assertions: bool,
    ) -> float:
        """Calculate speculation score from 0.0 to 1.0.

        Higher scores indicate more speculative content.

        Args:
            content_lower: Lowercased content.
            hedge_words_found: Hedge words found in content.
            has_assertions: Whether assertion markers were found.

        Returns:
            Speculation score between 0.0 and 1.0.
        """
        if not hedge_words_found:
            return 0.0

        # Base score from number of hedge words
        base_score = min(0.6, len(hedge_words_found) * 0.2)

        # Boost for strong speculation indicators
        strong_speculation = [
            "i don't know",
            "not sure",
            "i guess",
            "could be",
            "might be",
        ]
        for phrase in strong_speculation:
            if phrase in content_lower:
                base_score += 0.15

        # Reduce score if assertion markers present
        if has_assertions:
            base_score *= 0.3

        return min(1.0, base_score)

    def get_speculation_score(self, content: str) -> float:
        """Get the speculation score for content.

        Args:
            content: Text to analyze.

        Returns:
            Score from 0.0 (certain) to 1.0 (speculative).
        """
        return self.analyze(content).speculation_score

    def is_grounded(self, content: str) -> bool:
        """Check if content appears grounded (not speculative).

        Args:
            content: Text to analyze.

        Returns:
            True if content appears grounded.
        """
        return not self.analyze(content).is_speculative

    def get_hedge_word_positions(
        self,
        content: str,
    ) -> list[tuple[str, int, int]]:
        """Find positions of hedge words in content.

        Args:
            content: Text to analyze.

        Returns:
            List of (hedge_word, start, end) tuples.
        """
        content_lower = content.lower()
        positions: list[tuple[str, int, int]] = []

        for hedge in self.hedge_words:
            if len(hedge) <= 4:
                pattern = rf"\b{re.escape(hedge)}\b"
            else:
                pattern = re.escape(hedge)

            for match in re.finditer(pattern, content_lower, re.IGNORECASE):
                positions.append((hedge, match.start(), match.end()))

        # Sort by position
        positions.sort(key=lambda x: x[1])
        return positions
