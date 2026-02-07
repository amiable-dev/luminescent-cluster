# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Citation detection for grounded memory ingestion.

Detects citations in memory content using regex patterns (no LLM calls).
Citations indicate grounded content that can be auto-approved.

Supported citation types:
- ADR references: [ADR-003], ADR-003, ADR 003
- Commit hashes: 7-40 hex characters
- URLs: http:// or https://
- Issue/PR references: #123, GH-123

SECURITY NOTE: Citation detection is for PROVENANCE TRACKING, not truth verification.
A citation means "this claim references an external artifact" - it does NOT verify
that the artifact exists or that the claim accurately represents it.

Design Trade-off (ADR-003):
- Pro: Provides audit trail for claims, enables post-hoc verification
- Pro: No external API calls (fast, reliable, no dependencies)
- Con: Fake citations can be added to bypass checks
- Mitigation: Citations create an auditable trail; abuse can be detected and actioned

If strict verification is needed, callers should validate citations against
actual artifacts (e.g., verify ADR-003 exists, verify commit hash is real).
This detector provides the FIRST line of defense; external verification is SECOND.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class CitationType(str, Enum):
    """Types of citations that can be detected."""

    ADR = "adr"
    COMMIT = "commit"
    URL = "url"
    ISSUE = "issue"


@dataclass
class Citation:
    """A detected citation in content.

    Attributes:
        type: Type of citation (adr, commit, url, issue).
        value: Normalized value (e.g., "ADR-003", commit hash).
        raw_match: Original matched text.
        start: Start position in content.
        end: End position in content.
    """

    type: CitationType
    value: str
    raw_match: str
    start: int
    end: int

    def to_source_id(self) -> str:
        """Convert citation to source_id format for EvidenceObject.

        Returns:
            Formatted source identifier.
        """
        if self.type == CitationType.ADR:
            return self.value
        elif self.type == CitationType.COMMIT:
            # Use short hash (7 chars) for readability
            return f"commit:{self.value[:7]}"
        elif self.type == CitationType.URL:
            return self.value
        elif self.type == CitationType.ISSUE:
            return f"issue:{self.value}"
        return self.value


class CitationDetector:
    """Regex-based citation detection for memory grounding.

    Detects various citation formats in content to determine if
    the memory claim is grounded in verifiable sources.

    Example:
        >>> detector = CitationDetector()
        >>> citations = detector.detect_citations("Per ADR-003, we use PostgreSQL")
        >>> len(citations) > 0
        True
        >>> citations[0].type
        <CitationType.ADR: 'adr'>
    """

    # ADR patterns: [ADR-003], ADR-003, ADR 003, adr-003
    ADR_PATTERN = re.compile(
        r"\[?ADR[-\s]?(\d{3})\]?",
        re.IGNORECASE,
    )

    # Commit hash: 7-40 hex characters, word boundary
    # Exclude patterns that look like hex colors (#abc123) or other non-commits
    COMMIT_PATTERN = re.compile(
        r"(?<![#/])(?<![a-f0-9])\b([a-f0-9]{7,40})\b(?![a-f0-9])",
        re.IGNORECASE,
    )

    # URL pattern: http:// or https:// followed by valid URL chars
    URL_PATTERN = re.compile(
        r"(https?://[^\s<>\"'(){}\[\]]+)",
        re.IGNORECASE,
    )

    # Issue/PR pattern: #123 or GH-123
    ISSUE_PATTERN = re.compile(
        r"(?:#|GH-)(\d+)\b",
        re.IGNORECASE,
    )

    # Documentation file patterns
    DOC_PATTERN = re.compile(
        r"\b(README|CHANGELOG|CONTRIBUTING|docs/\S+\.md)\b",
        re.IGNORECASE,
    )

    def detect_citations(self, content: str) -> list[Citation]:
        """Detect all citations in content.

        Args:
            content: Text to search for citations.

        Returns:
            List of Citation objects found in content.
        """
        citations: list[Citation] = []

        # Detect ADR references
        for match in self.ADR_PATTERN.finditer(content):
            adr_num = match.group(1)
            citations.append(
                Citation(
                    type=CitationType.ADR,
                    value=f"ADR-{adr_num}",
                    raw_match=match.group(0),
                    start=match.start(),
                    end=match.end(),
                )
            )

        # Detect URLs (check first to exclude from commit hash detection)
        url_ranges: set[tuple[int, int]] = set()
        for match in self.URL_PATTERN.finditer(content):
            url = match.group(1).rstrip(".,;:!?)")  # Clean trailing punctuation
            citations.append(
                Citation(
                    type=CitationType.URL,
                    value=url,
                    raw_match=match.group(0),
                    start=match.start(),
                    end=match.end(),
                )
            )
            url_ranges.add((match.start(), match.end()))

        # Detect commit hashes (excluding those within URLs)
        for match in self.COMMIT_PATTERN.finditer(content):
            # Skip if this match is within a URL
            in_url = any(start <= match.start() < end for start, end in url_ranges)
            if in_url:
                continue

            commit_hash = match.group(1).lower()

            # Additional validation: skip if looks like a hex color
            # (6 chars) or timestamp-like pattern
            if len(commit_hash) == 6:
                continue  # Likely a hex color

            citations.append(
                Citation(
                    type=CitationType.COMMIT,
                    value=commit_hash,
                    raw_match=match.group(0),
                    start=match.start(),
                    end=match.end(),
                )
            )

        # Detect issue/PR references
        for match in self.ISSUE_PATTERN.finditer(content):
            issue_num = match.group(1)
            citations.append(
                Citation(
                    type=CitationType.ISSUE,
                    value=issue_num,
                    raw_match=match.group(0),
                    start=match.start(),
                    end=match.end(),
                )
            )

        # Sort by position in content
        citations.sort(key=lambda c: c.start)
        return citations

    def has_any_citation(self, content: str) -> bool:
        """Check if content contains any citation.

        Args:
            content: Text to search.

        Returns:
            True if at least one citation is found.
        """
        # Fast path: check patterns without full extraction
        if self.ADR_PATTERN.search(content):
            return True
        if self.URL_PATTERN.search(content):
            return True
        if self.ISSUE_PATTERN.search(content):
            return True
        # Commit requires more careful checking
        for match in self.COMMIT_PATTERN.finditer(content):
            # Exclude 6-char matches (hex colors)
            if len(match.group(1)) > 6:
                return True
        return False

    def extract_source_id(self, content: str) -> Optional[str]:
        """Extract the primary source ID from content.

        Returns the first citation found as a source_id string,
        prioritizing ADRs over other citation types.

        Args:
            content: Text to search.

        Returns:
            Source ID string or None if no citation found.
        """
        citations = self.detect_citations(content)
        if not citations:
            return None

        # Prioritize ADRs
        for citation in citations:
            if citation.type == CitationType.ADR:
                return citation.to_source_id()

        # Return first citation of any type
        return citations[0].to_source_id()

    def get_citation_summary(self, content: str) -> dict[str, list[str]]:
        """Get a summary of citations grouped by type.

        Args:
            content: Text to search.

        Returns:
            Dictionary mapping citation type to list of values.
        """
        citations = self.detect_citations(content)
        summary: dict[str, list[str]] = {}

        for citation in citations:
            type_key = citation.type.value
            if type_key not in summary:
                summary[type_key] = []
            if citation.value not in summary[type_key]:
                summary[type_key].append(citation.value)

        return summary

    def count_citations(self, content: str) -> int:
        """Count the number of citations in content.

        Args:
            content: Text to search.

        Returns:
            Number of citations found.
        """
        return len(self.detect_citations(content))
