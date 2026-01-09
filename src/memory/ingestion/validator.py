# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Main ingestion validator for grounded memory ingestion.

Orchestrates citation detection, hedge word detection, and deduplication
to implement the 3-tier provenance model from ADR-003 Phase 2.

Validation Flow:
1. Citation detection - check for ADR/commit/URL references
2. Hedge word detection - check for speculative language
3. Deduplication - check for >0.92 similarity to existing memories
4. Tier determination based on results

Exit Criteria (ADR-003):
- Zero hallucination write-back in grounded ingestion tests
"""

from datetime import datetime, timezone
from typing import Any, Optional

from src.memory.ingestion.citation_detector import CitationDetector
from src.memory.ingestion.dedup_checker import DedupChecker, MemoryProviderProtocol
from src.memory.ingestion.evidence import EvidenceObject
from src.memory.ingestion.hedge_detector import HedgeDetector
from src.memory.ingestion.result import IngestionTier, ValidationResult


class IngestionValidator:
    """Validates memory content for grounded ingestion.

    Implements the 3-tier provenance model from ADR-003 Phase 2:

    Tier 1 (Auto-approve):
        - Content with explicit ADR/commit/doc links
        - User-stated facts (source="user" or "conversation")
        - Decision discussions with clear context

    Tier 2 (Flag for review):
        - AI-synthesized claims without citations
        - Factual assertions about external systems/APIs

    Tier 3 (Block):
        - Speculative content (hedge words detected)
        - Content with >0.92 similarity to existing memory

    Example:
        >>> validator = IngestionValidator(provider)
        >>> result = await validator.validate(
        ...     content="Per ADR-003, we use PostgreSQL",
        ...     memory_type="decision",
        ...     source="conversation",
        ...     user_id="user-1",
        ... )
        >>> result.tier
        <IngestionTier.AUTO_APPROVE: 'tier_1'>
    """

    # Sources considered trustworthy for auto-approval
    TRUSTED_SOURCES = {
        "user",
        "user-stated",
        "adr",
        "commit",
        "documentation",
        "docs",
        "manual",
    }

    def __init__(
        self,
        provider: Optional[MemoryProviderProtocol] = None,
        citation_detector: Optional[CitationDetector] = None,
        hedge_detector: Optional[HedgeDetector] = None,
        dedup_checker: Optional[DedupChecker] = None,
        enable_dedup: bool = True,
    ):
        """Initialize the ingestion validator.

        Args:
            provider: Memory provider for deduplication checks.
            citation_detector: Custom citation detector (or use default).
            hedge_detector: Custom hedge detector (or use default).
            dedup_checker: Custom dedup checker (or use default with provider).
            enable_dedup: Whether to enable deduplication checks.
        """
        self.citation_detector = citation_detector or CitationDetector()
        self.hedge_detector = hedge_detector or HedgeDetector()
        self.enable_dedup = enable_dedup and provider is not None

        if dedup_checker:
            self.dedup_checker = dedup_checker
        elif provider and enable_dedup:
            self.dedup_checker = DedupChecker(provider)
        else:
            self.dedup_checker = None

    async def validate(
        self,
        content: str,
        memory_type: str,
        source: str,
        user_id: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> ValidationResult:
        """Validate memory content and determine ingestion tier.

        Runs all validation checks and determines the appropriate
        tier based on ADR-003 Phase 2 requirements.

        Args:
            content: Memory content to validate.
            memory_type: Type of memory (preference, fact, decision).
            source: Source of the memory (user, conversation, ai_synthesis, etc.).
            user_id: User ID for deduplication scope.
            metadata: Optional additional metadata.

        Returns:
            ValidationResult with tier, evidence, and check details.
        """
        checks_passed: list[str] = []
        checks_failed: list[str] = []
        similarity_score: Optional[float] = None
        conflicting_memory_id: Optional[str] = None

        # === Check 1: Citation presence ===
        citations = self.citation_detector.detect_citations(content)
        has_citation = len(citations) > 0

        if has_citation:
            checks_passed.append("citation_present")
            source_id = citations[0].to_source_id()
        else:
            checks_failed.append("no_citation")
            source_id = None

        # === Check 2: Hedge word detection ===
        hedge_result = self.hedge_detector.analyze(content)
        has_hedge_words = hedge_result.is_speculative

        if has_hedge_words:
            hedge_list = ", ".join(hedge_result.hedge_words_found[:5])
            checks_failed.append(f"hedge_words_detected: {hedge_list}")
        else:
            checks_passed.append("no_speculation")

        # === Check 3: Deduplication ===
        is_duplicate = False
        if self.dedup_checker and self.enable_dedup:
            dedup_result = await self.dedup_checker.check_duplicate(
                content, user_id, memory_type
            )
            is_duplicate = dedup_result.is_duplicate
            similarity_score = dedup_result.similarity_score

            if is_duplicate:
                checks_failed.append(
                    f"duplicate_detected: {dedup_result.existing_memory_id}"
                )
                conflicting_memory_id = dedup_result.existing_memory_id
            else:
                checks_passed.append("unique_content")

        # === Determine tier ===
        tier = self._determine_tier(
            has_citation=has_citation,
            has_hedge_words=has_hedge_words,
            is_duplicate=is_duplicate,
            source=source,
            memory_type=memory_type,
        )

        # === Build evidence object ===
        evidence = EvidenceObject(
            claim=content,
            source_id=source_id,
            capture_time=datetime.now(timezone.utc),
            confidence=tier.confidence_level,
            metadata=metadata or {},
        )

        # === Build reason ===
        reason = self._build_reason(tier, checks_passed, checks_failed, source)

        return ValidationResult(
            tier=tier,
            approved=tier.is_approved,
            reason=reason,
            evidence=evidence,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            similarity_score=similarity_score,
            conflicting_memory_id=conflicting_memory_id,
        )

    def _determine_tier(
        self,
        has_citation: bool,
        has_hedge_words: bool,
        is_duplicate: bool,
        source: str,
        memory_type: str,
    ) -> IngestionTier:
        """Determine the ingestion tier based on validation results.

        Decision Matrix:
        - BLOCK (Tier 3): hedge words OR duplicate
        - AUTO_APPROVE (Tier 1): citation OR trusted source OR decision with context
        - FLAG_REVIEW (Tier 2): everything else

        Args:
            has_citation: Whether content has citations.
            has_hedge_words: Whether speculative language detected.
            is_duplicate: Whether content duplicates existing memory.
            source: Source of the memory.
            memory_type: Type of memory.

        Returns:
            Appropriate IngestionTier.
        """
        # === Tier 3: Block ===
        # Speculative content must be blocked
        if has_hedge_words:
            return IngestionTier.BLOCK

        # Duplicates must be blocked
        if is_duplicate:
            return IngestionTier.BLOCK

        # === Tier 1: Auto-approve ===
        # Content with citations is grounded
        if has_citation:
            return IngestionTier.AUTO_APPROVE

        # Trusted sources (user, adr, documentation) are grounded
        source_lower = source.lower()
        if source_lower in self.TRUSTED_SOURCES:
            return IngestionTier.AUTO_APPROVE

        # Decisions from conversations are typically intentional
        if memory_type == "decision" and source_lower == "conversation":
            return IngestionTier.AUTO_APPROVE

        # Preferences stated by users are grounded
        if memory_type == "preference" and source_lower in ("conversation", "chat"):
            return IngestionTier.AUTO_APPROVE

        # === Tier 2: Flag for review ===
        # AI-synthesized claims without sources need review
        return IngestionTier.FLAG_REVIEW

    def _build_reason(
        self,
        tier: IngestionTier,
        checks_passed: list[str],
        checks_failed: list[str],
        source: str,
    ) -> str:
        """Build human-readable reason for the tier decision.

        Args:
            tier: The determined tier.
            checks_passed: Checks that passed.
            checks_failed: Checks that failed.
            source: Memory source.

        Returns:
            Explanation string.
        """
        if tier == IngestionTier.BLOCK:
            if any("hedge_words" in c for c in checks_failed):
                return "Blocked: Speculative content detected. Memory claims must be grounded."
            if any("duplicate" in c for c in checks_failed):
                return "Blocked: Content duplicates existing memory."
            return "Blocked: Content did not pass validation checks."

        if tier == IngestionTier.AUTO_APPROVE:
            if "citation_present" in checks_passed:
                return "Approved: Content contains verifiable citation."
            if source.lower() in self.TRUSTED_SOURCES:
                return f"Approved: Trusted source ({source})."
            return "Approved: Content meets grounding requirements."

        # FLAG_REVIEW
        return "Flagged for review: Content lacks citations or trusted source attribution."

    def validate_sync(
        self,
        content: str,
        memory_type: str,
        source: str,
        user_id: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> ValidationResult:
        """Synchronous validation (without deduplication check).

        Use this for quick validation when async is not available.
        Note: Deduplication check is skipped.

        Args:
            content: Memory content to validate.
            memory_type: Type of memory.
            source: Source of the memory.
            user_id: User ID.
            metadata: Optional metadata.

        Returns:
            ValidationResult (without dedup check).
        """
        checks_passed: list[str] = []
        checks_failed: list[str] = []

        # Citation check
        citations = self.citation_detector.detect_citations(content)
        has_citation = len(citations) > 0
        if has_citation:
            checks_passed.append("citation_present")
            source_id = citations[0].to_source_id()
        else:
            checks_failed.append("no_citation")
            source_id = None

        # Hedge word check
        hedge_result = self.hedge_detector.analyze(content)
        if hedge_result.is_speculative:
            hedge_list = ", ".join(hedge_result.hedge_words_found[:5])
            checks_failed.append(f"hedge_words_detected: {hedge_list}")
        else:
            checks_passed.append("no_speculation")

        # Determine tier (no dedup)
        tier = self._determine_tier(
            has_citation=has_citation,
            has_hedge_words=hedge_result.is_speculative,
            is_duplicate=False,  # Skip dedup in sync mode
            source=source,
            memory_type=memory_type,
        )

        evidence = EvidenceObject(
            claim=content,
            source_id=source_id,
            capture_time=datetime.now(timezone.utc),
            confidence=tier.confidence_level,
            metadata=metadata or {},
        )

        reason = self._build_reason(tier, checks_passed, checks_failed, source)

        return ValidationResult(
            tier=tier,
            approved=tier.is_approved,
            reason=reason,
            evidence=evidence,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
        )

    def quick_check(self, content: str) -> IngestionTier:
        """Quick tier check without full validation.

        Useful for filtering before expensive operations.

        Args:
            content: Content to check.

        Returns:
            Likely IngestionTier (may miss duplicates).
        """
        # Check hedge words first (immediate blocker)
        hedge_result = self.hedge_detector.analyze(content)
        if hedge_result.is_speculative:
            return IngestionTier.BLOCK

        # Check citations (immediate approval)
        if self.citation_detector.has_any_citation(content):
            return IngestionTier.AUTO_APPROVE

        # Default to flag for review
        return IngestionTier.FLAG_REVIEW
