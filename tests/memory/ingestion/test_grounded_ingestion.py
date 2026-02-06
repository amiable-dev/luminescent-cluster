# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Tests for grounded memory ingestion (ADR-003 Phase 2).

Tests the 3-tier provenance model:
- Tier 1: Auto-approve (citations, trusted sources)
- Tier 2: Flag for review (unsourced claims)
- Tier 3: Block (speculative content, duplicates)

Exit Criteria: Zero hallucination write-back
"""

from datetime import datetime, timedelta, timezone

import pytest

from luminescent_cluster.memory.ingestion.citation_detector import Citation, CitationDetector, CitationType
from luminescent_cluster.memory.ingestion.dedup_checker import DedupChecker, DuplicateCheckResult
from luminescent_cluster.memory.ingestion.evidence import EvidenceObject
from luminescent_cluster.memory.ingestion.hedge_detector import HedgeDetector
from luminescent_cluster.memory.ingestion.result import IngestionTier, ValidationResult
from luminescent_cluster.memory.ingestion.review_queue import PendingMemory, ReviewQueue
from luminescent_cluster.memory.ingestion.validator import IngestionValidator


# =============================================================================
# EvidenceObject Tests
# =============================================================================


class TestEvidenceObject:
    """Tests for EvidenceObject dataclass."""

    def test_create_evidence_basic(self):
        """Test basic evidence creation."""
        evidence = EvidenceObject.create(
            claim="We use PostgreSQL",
            source_id="ADR-003",
            confidence="high",
        )
        assert evidence.claim == "We use PostgreSQL"
        assert evidence.source_id == "ADR-003"
        assert evidence.confidence == "high"
        assert evidence.capture_time is not None

    def test_create_evidence_with_validity_horizon(self):
        """Test evidence with expiration."""
        future = datetime.now(timezone.utc) + timedelta(days=30)
        evidence = EvidenceObject.create(
            claim="API version 2.0 is current",
            confidence="medium",
            validity_horizon=future,
        )
        assert evidence.validity_horizon == future
        assert not evidence.is_expired()

    def test_evidence_expired(self):
        """Test expiration detection."""
        past = datetime.now(timezone.utc) - timedelta(days=1)
        evidence = EvidenceObject(
            claim="Old fact",
            capture_time=datetime.now(timezone.utc) - timedelta(days=2),
            validity_horizon=past,
            confidence="medium",
        )
        assert evidence.is_expired()

    def test_evidence_validation(self):
        """Test validation in __post_init__."""
        with pytest.raises(ValueError, match="claim cannot be empty"):
            EvidenceObject(
                claim="",
                capture_time=datetime.now(timezone.utc),
                confidence="high",
            )

        with pytest.raises(ValueError, match="confidence must be"):
            EvidenceObject(
                claim="test",
                capture_time=datetime.now(timezone.utc),
                confidence="invalid",  # type: ignore
            )

    def test_evidence_serialization(self):
        """Test to_dict and from_dict."""
        original = EvidenceObject.create(
            claim="Test claim",
            source_id="ADR-001",
            confidence="high",
            metadata={"key": "value"},
        )
        data = original.to_dict()
        restored = EvidenceObject.from_dict(data)

        assert restored.claim == original.claim
        assert restored.source_id == original.source_id
        assert restored.confidence == original.confidence

    def test_with_source(self):
        """Test immutable update of source."""
        original = EvidenceObject.create(claim="Test", confidence="low")
        updated = original.with_source("ADR-005")

        assert original.source_id is None
        assert updated.source_id == "ADR-005"
        assert updated.claim == original.claim


# =============================================================================
# CitationDetector Tests
# =============================================================================


class TestCitationDetector:
    """Tests for citation detection."""

    @pytest.fixture
    def detector(self):
        return CitationDetector()

    def test_detect_adr_formats(self, detector):
        """Test various ADR citation formats."""
        test_cases = [
            ("Per ADR-003, we use PostgreSQL", "ADR-003"),
            ("See [ADR-005] for details", "ADR-005"),
            ("As noted in ADR 007", "ADR-007"),
            ("Reference: adr-001", "ADR-001"),
        ]
        for content, expected in test_cases:
            citations = detector.detect_citations(content)
            assert len(citations) >= 1, f"No citation found in: {content}"
            assert citations[0].value == expected

    def test_detect_commit_hash(self, detector):
        """Test commit hash detection."""
        content = "Fixed in commit a1b2c3d4e5f6a7b"
        citations = detector.detect_citations(content)
        commit_citations = [c for c in citations if c.type == CitationType.COMMIT]
        assert len(commit_citations) >= 1

    def test_detect_url(self, detector):
        """Test URL detection."""
        content = "See https://docs.example.com/api for reference"
        citations = detector.detect_citations(content)
        url_citations = [c for c in citations if c.type == CitationType.URL]
        assert len(url_citations) == 1
        assert "docs.example.com" in url_citations[0].value

    def test_detect_issue_reference(self, detector):
        """Test issue/PR detection."""
        test_cases = [
            "Fixed in #123",
            "See GH-456 for context",
        ]
        for content in test_cases:
            citations = detector.detect_citations(content)
            issue_citations = [c for c in citations if c.type == CitationType.ISSUE]
            assert len(issue_citations) >= 1, f"No issue found in: {content}"

    def test_has_any_citation(self, detector):
        """Test quick citation check."""
        assert detector.has_any_citation("Per ADR-003")
        assert detector.has_any_citation("See https://example.com")
        assert not detector.has_any_citation("User prefers tabs")

    def test_extract_source_id(self, detector):
        """Test source ID extraction."""
        # ADRs should be prioritized
        content = "Per ADR-003 (see https://example.com)"
        source_id = detector.extract_source_id(content)
        assert source_id == "ADR-003"

        # No citation returns None
        assert detector.extract_source_id("No citations here") is None

    def test_skip_hex_colors(self, detector):
        """Test that hex colors are not detected as commits."""
        content = "Use color #abc123 for the button"
        citations = detector.detect_citations(content)
        # Should not detect abc123 as a commit
        commit_citations = [c for c in citations if c.type == CitationType.COMMIT]
        assert len(commit_citations) == 0


# =============================================================================
# HedgeDetector Tests
# =============================================================================


class TestHedgeDetector:
    """Tests for hedge word detection."""

    @pytest.fixture
    def detector(self):
        return HedgeDetector()

    def test_detect_modal_hedges(self, detector):
        """Test detection of modal hedge words."""
        test_cases = [
            "Maybe we should use Redis",
            "We might need to refactor",
            "Could be a performance issue",
        ]
        for content in test_cases:
            is_spec, words = detector.contains_hedge_words(content)
            assert is_spec, f"Should detect speculation in: {content}"
            assert len(words) > 0

    def test_detect_epistemic_hedges(self, detector):
        """Test detection of epistemic hedges."""
        test_cases = [
            "Perhaps we should reconsider",
            "Probably uses JWT tokens",
            "Possibly a cache issue",
        ]
        for content in test_cases:
            is_spec, words = detector.contains_hedge_words(content)
            assert is_spec, f"Should detect speculation in: {content}"

    def test_detect_personal_uncertainty(self, detector):
        """Test detection of personal uncertainty phrases."""
        test_cases = [
            "I think the API supports this",
            "I believe it's async",
            "I'm not sure about the format",
        ]
        for content in test_cases:
            is_spec, words = detector.contains_hedge_words(content)
            assert is_spec, f"Should detect uncertainty in: {content}"

    def test_allow_grounded_statements(self, detector):
        """Test that grounded statements pass."""
        test_cases = [
            "We use PostgreSQL for the database",
            "The API returns JSON",
            "Per ADR-003, authentication uses OAuth2",
        ]
        for content in test_cases:
            is_spec, _ = detector.contains_hedge_words(content)
            assert not is_spec, f"Should not flag: {content}"

    def test_assertion_markers_tracked_but_not_override(self, detector):
        """Test that assertion markers are tracked but do NOT override hedge words.

        SECURITY: Adding "definitely" to speculative content must not bypass
        the hedge detection. Assertion markers only reduce speculation_score.
        """
        # Content with no hedge words - not speculative
        content = "We definitely chose PostgreSQL"
        result = detector.analyze(content)
        assert result.has_assertions
        assert not result.is_speculative  # No hedge words = not speculative

        # SECURITY: Adding "definitely" to speculative content must STILL be speculative
        bypass_attempt = "Maybe we should use Redis, definitely"
        bypass_result = detector.analyze(bypass_attempt)
        assert bypass_result.has_assertions  # Has "definitely"
        assert bypass_result.is_speculative  # But STILL speculative due to "maybe"
        assert "maybe" in bypass_result.hedge_words_found

    def test_false_positive_month_may(self, detector):
        """Test that 'May 2024' is not detected as hedge."""
        content = "Released in May 2024"
        result = detector.analyze(content)
        # The false positive pattern should filter this out
        assert "may" not in result.hedge_words_found

    def test_speculation_score(self, detector):
        """Test speculation score calculation."""
        # High speculation
        high_spec = "I guess maybe we could try"
        score_high = detector.get_speculation_score(high_spec)

        # Low speculation
        low_spec = "We use PostgreSQL"
        score_low = detector.get_speculation_score(low_spec)

        assert score_high > score_low
        assert score_low == 0.0


# =============================================================================
# DedupChecker Tests
# =============================================================================


class MockProvider:
    """Mock provider for testing deduplication."""

    def __init__(self, memories: list[dict] = None):
        self.memories = memories or []

    async def search(self, user_id: str, filters: dict, limit: int = 10):
        return [m for m in self.memories if m.get("user_id") == user_id][:limit]


class TestDedupChecker:
    """Tests for duplicate detection."""

    @pytest.mark.asyncio
    async def test_detect_exact_duplicate(self):
        """Test detection of exact duplicate."""
        provider = MockProvider([
            {"id": "mem-1", "user_id": "user-1", "content": "Uses PostgreSQL database"}
        ])
        checker = DedupChecker(provider)

        result = await checker.check_duplicate(
            "Uses PostgreSQL database", "user-1"
        )
        assert result.is_duplicate
        assert result.similarity_score >= 0.92
        assert result.existing_memory_id == "mem-1"

    @pytest.mark.asyncio
    async def test_allow_different_content(self):
        """Test that different content is allowed."""
        provider = MockProvider([
            {"id": "mem-1", "user_id": "user-1", "content": "Uses PostgreSQL database"}
        ])
        checker = DedupChecker(provider)

        result = await checker.check_duplicate(
            "Prefers tabs for Python files", "user-1"
        )
        assert not result.is_duplicate
        assert result.similarity_score < 0.92

    @pytest.mark.asyncio
    async def test_allow_similar_but_distinct(self):
        """Test that similar but distinct content is allowed."""
        provider = MockProvider([
            {"id": "mem-1", "user_id": "user-1", "content": "Uses PostgreSQL for users table"}
        ])
        checker = DedupChecker(provider)

        # Similar but different detail
        result = await checker.check_duplicate(
            "Uses PostgreSQL for sessions table", "user-1"
        )
        # Should not be exact duplicate
        assert result.similarity_score < 1.0

    @pytest.mark.asyncio
    async def test_empty_provider(self):
        """Test with no existing memories."""
        provider = MockProvider([])
        checker = DedupChecker(provider)

        result = await checker.check_duplicate("New memory", "user-1")
        assert not result.is_duplicate
        assert result.checked_count == 0

    def test_calculate_similarity(self):
        """Test similarity calculation."""
        provider = MockProvider([])
        checker = DedupChecker(provider)

        # Exact match
        sim = checker.calculate_similarity(
            "Uses PostgreSQL", "Uses PostgreSQL"
        )
        assert sim == 1.0

        # No overlap
        sim = checker.calculate_similarity(
            "Uses PostgreSQL", "Prefers tabs"
        )
        assert sim == 0.0

        # Partial overlap
        sim = checker.calculate_similarity(
            "Uses PostgreSQL database", "Uses MySQL database"
        )
        assert 0 < sim < 1


# =============================================================================
# IngestionValidator Tests
# =============================================================================


class TestIngestionValidator:
    """Tests for the main ingestion validator."""

    @pytest.fixture
    def validator(self):
        return IngestionValidator(enable_dedup=False)

    @pytest.fixture
    def validator_with_dedup(self):
        provider = MockProvider([])
        return IngestionValidator(provider=provider, enable_dedup=True)

    @pytest.mark.asyncio
    async def test_tier1_citation_auto_approve(self, validator):
        """Test Tier 1: Content with citations is auto-approved."""
        result = await validator.validate(
            content="Per ADR-003, we use PostgreSQL for the database",
            memory_type="decision",
            source="conversation",
            user_id="user-1",
        )
        assert result.tier == IngestionTier.AUTO_APPROVE
        assert result.approved
        assert "citation_present" in result.checks_passed

    @pytest.mark.asyncio
    async def test_tier1_trusted_source_auto_approve(self, validator):
        """Test Tier 1: Trusted sources are auto-approved."""
        trusted_sources = ["user", "adr", "documentation", "commit"]

        for source in trusted_sources:
            result = await validator.validate(
                content="We use PostgreSQL",
                memory_type="fact",
                source=source,
                user_id="user-1",
            )
            assert result.tier == IngestionTier.AUTO_APPROVE, f"Source {source} should be trusted"

    @pytest.mark.asyncio
    async def test_tier1_decision_from_conversation(self, validator):
        """Test Tier 1: Decisions from conversations are auto-approved."""
        result = await validator.validate(
            content="We decided to use PostgreSQL",
            memory_type="decision",
            source="conversation",
            user_id="user-1",
        )
        assert result.tier == IngestionTier.AUTO_APPROVE

    @pytest.mark.asyncio
    async def test_tier2_unsourced_ai_claim(self, validator):
        """Test Tier 2: AI claims without sources are flagged."""
        result = await validator.validate(
            content="The API uses OAuth2 for authentication",
            memory_type="fact",
            source="ai_synthesis",
            user_id="user-1",
        )
        assert result.tier == IngestionTier.FLAG_REVIEW
        assert not result.approved

    @pytest.mark.asyncio
    async def test_tier3_speculative_blocked(self, validator):
        """Test Tier 3: Speculative content is blocked."""
        speculative_contents = [
            "Maybe we should use Redis",
            "I think the API might support this",
            "Probably uses JWT tokens",
            "Perhaps we could try GraphQL",
            "Not sure but I believe it's async",
        ]

        for content in speculative_contents:
            result = await validator.validate(
                content=content,
                memory_type="fact",
                source="conversation",
                user_id="user-1",
            )
            assert result.tier == IngestionTier.BLOCK, f"Should block: {content}"
            assert not result.approved
            assert result.is_speculative

    @pytest.mark.asyncio
    async def test_tier3_duplicate_blocked(self):
        """Test Tier 3: Duplicates are blocked."""
        provider = MockProvider([
            {"id": "mem-1", "user_id": "user-1", "content": "Uses PostgreSQL database"}
        ])
        validator = IngestionValidator(provider=provider, enable_dedup=True)

        result = await validator.validate(
            content="Uses PostgreSQL database",
            memory_type="fact",
            source="user",
            user_id="user-1",
        )
        assert result.tier == IngestionTier.BLOCK
        assert result.is_duplicate

    @pytest.mark.asyncio
    async def test_evidence_attached(self, validator):
        """Test that evidence is attached to results."""
        result = await validator.validate(
            content="Per ADR-003, we use PostgreSQL",
            memory_type="decision",
            source="conversation",
            user_id="user-1",
        )
        assert result.evidence is not None
        assert result.evidence.claim == "Per ADR-003, we use PostgreSQL"
        assert result.evidence.source_id == "ADR-003"
        assert result.evidence.confidence == "high"  # Tier 1

    def test_quick_check(self, validator):
        """Test quick tier check."""
        # Citation -> AUTO_APPROVE
        tier = validator.quick_check("Per ADR-003, we use PostgreSQL")
        assert tier == IngestionTier.AUTO_APPROVE

        # Hedge words -> BLOCK
        tier = validator.quick_check("Maybe we should use Redis")
        assert tier == IngestionTier.BLOCK

        # No citation, no hedge -> FLAG_REVIEW
        tier = validator.quick_check("The API returns JSON")
        assert tier == IngestionTier.FLAG_REVIEW

    def test_validate_sync(self, validator):
        """Test synchronous validation."""
        result = validator.validate_sync(
            content="Per ADR-003, we use PostgreSQL",
            memory_type="decision",
            source="conversation",
            user_id="user-1",
        )
        assert result.tier == IngestionTier.AUTO_APPROVE


# =============================================================================
# ReviewQueue Tests
# =============================================================================


class TestReviewQueue:
    """Tests for the review queue."""

    @pytest.fixture
    def queue(self):
        return ReviewQueue()

    @pytest.fixture
    def sample_evidence(self):
        return EvidenceObject.create(
            claim="Test claim",
            confidence="medium",
        )

    @pytest.fixture
    def sample_result(self, sample_evidence):
        return ValidationResult.flagged_result(
            evidence=sample_evidence,
            reason="Flagged for review",
        )

    @pytest.mark.asyncio
    async def test_enqueue_and_get(self, queue, sample_evidence, sample_result):
        """Test enqueue and retrieval."""
        queue_id = await queue.enqueue(
            user_id="user-1",
            content="Test memory",
            memory_type="fact",
            source="ai_synthesis",
            evidence=sample_evidence,
            validation_result=sample_result,
        )

        assert queue_id is not None

        pending = await queue.get_pending("user-1")
        assert len(pending) == 1
        assert pending[0].queue_id == queue_id
        assert pending[0].content == "Test memory"

    @pytest.mark.asyncio
    async def test_approve(self, queue, sample_evidence, sample_result):
        """Test approve workflow."""
        queue_id = await queue.enqueue(
            user_id="user-1",
            content="Test memory",
            memory_type="fact",
            source="ai_synthesis",
            evidence=sample_evidence,
            validation_result=sample_result,
        )

        # Owner approves their own pending memory
        result = await queue.approve(queue_id, "user-1")
        assert result is not None

        # Should be removed from queue
        pending = await queue.get_pending("user-1")
        assert len(pending) == 0

    @pytest.mark.asyncio
    async def test_reject(self, queue, sample_evidence, sample_result):
        """Test reject workflow."""
        queue_id = await queue.enqueue(
            user_id="user-1",
            content="Test memory",
            memory_type="fact",
            source="ai_synthesis",
            evidence=sample_evidence,
            validation_result=sample_result,
        )

        # Owner rejects their own pending memory
        await queue.reject(queue_id, "user-1", "Not grounded")

        # Should be removed from queue
        pending = await queue.get_pending("user-1")
        assert len(pending) == 0

    @pytest.mark.asyncio
    async def test_max_pending_per_user(self, sample_evidence, sample_result):
        """Test user pending limit."""
        queue = ReviewQueue(max_pending_per_user=2)

        await queue.enqueue(
            user_id="user-1", content="Mem 1", memory_type="fact",
            source="ai", evidence=sample_evidence, validation_result=sample_result
        )
        await queue.enqueue(
            user_id="user-1", content="Mem 2", memory_type="fact",
            source="ai", evidence=sample_evidence, validation_result=sample_result
        )

        with pytest.raises(ValueError, match="maximum pending"):
            await queue.enqueue(
                user_id="user-1", content="Mem 3", memory_type="fact",
                source="ai", evidence=sample_evidence, validation_result=sample_result
            )

    @pytest.mark.asyncio
    async def test_pending_count(self, queue, sample_evidence, sample_result):
        """Test pending count."""
        assert queue.pending_count() == 0
        assert queue.pending_count("user-1") == 0

        await queue.enqueue(
            user_id="user-1", content="Mem 1", memory_type="fact",
            source="ai", evidence=sample_evidence, validation_result=sample_result
        )

        assert queue.pending_count() == 1
        assert queue.pending_count("user-1") == 1
        assert queue.pending_count("user-2") == 0


# =============================================================================
# Exit Criteria Tests
# =============================================================================


class TestExitCriteria:
    """Tests for ADR-003 Phase 2 exit criteria.

    Exit Criteria: Zero hallucination write-back in grounded ingestion tests
    """

    @pytest.fixture
    def validator(self):
        return IngestionValidator(enable_dedup=False)

    @pytest.mark.asyncio
    async def test_no_speculative_content_approved(self, validator):
        """Verify speculative content is never approved."""
        speculative_contents = [
            "Maybe we should use Redis for caching",
            "I think the API might support GraphQL",
            "Probably uses JWT tokens for auth",
            "Perhaps we could try a microservices approach",
            "Not sure but I believe the database is PostgreSQL",
            "Could be a performance issue with the query",
            "Might need to add more indexes",
            "I guess we should refactor this",
            "Possibly a race condition",
            "I assume it uses REST endpoints",
        ]

        for content in speculative_contents:
            result = await validator.validate(
                content=content,
                memory_type="fact",
                source="conversation",
                user_id="test-user",
            )
            assert result.tier == IngestionTier.BLOCK, f"Should block: {content}"
            assert not result.approved, f"Should not approve: {content}"

    @pytest.mark.asyncio
    async def test_no_duplicates_approved(self):
        """Verify duplicates are never approved."""
        provider = MockProvider([
            {"id": "mem-1", "user_id": "user-1", "content": "Uses PostgreSQL for the main database"},
            {"id": "mem-2", "user_id": "user-1", "content": "Team prefers tabs over spaces"},
        ])
        validator = IngestionValidator(provider=provider, enable_dedup=True)

        # Exact duplicate
        result = await validator.validate(
            content="Uses PostgreSQL for the main database",
            memory_type="fact",
            source="user",
            user_id="user-1",
        )
        assert result.tier == IngestionTier.BLOCK
        assert not result.approved

    @pytest.mark.asyncio
    async def test_grounded_content_approved(self, validator):
        """Verify well-grounded content is approved."""
        grounded_contents = [
            ("Per ADR-003, memory architecture uses Pixeltable", "decision"),
            ("Commit a1b2c3d4e5 fixed the authentication bug", "fact"),
            ("See https://docs.example.com/api for the specification", "fact"),
            ("Fixed in #123 - the cache invalidation issue", "fact"),
        ]

        for content, mem_type in grounded_contents:
            result = await validator.validate(
                content=content,
                memory_type=mem_type,
                source="conversation",
                user_id="test-user",
            )
            assert result.tier == IngestionTier.AUTO_APPROVE, f"Should approve: {content}"
            assert result.approved

    @pytest.mark.asyncio
    async def test_user_stated_facts_approved(self, validator):
        """Verify user-stated facts are approved."""
        result = await validator.validate(
            content="I prefer using PostgreSQL",
            memory_type="preference",
            source="user",
            user_id="test-user",
        )
        assert result.tier == IngestionTier.AUTO_APPROVE

    @pytest.mark.asyncio
    async def test_ai_synthesis_flagged(self, validator):
        """Verify AI-synthesized claims without sources are flagged."""
        result = await validator.validate(
            content="The API uses OAuth2 for authentication",
            memory_type="fact",
            source="ai_synthesis",
            user_id="test-user",
        )
        assert result.tier == IngestionTier.FLAG_REVIEW
        assert not result.approved

    @pytest.mark.asyncio
    async def test_evidence_confidence_matches_tier(self, validator):
        """Verify evidence confidence matches tier."""
        # Tier 1 -> high confidence
        result = await validator.validate(
            content="Per ADR-003, we use PostgreSQL",
            memory_type="decision",
            source="conversation",
            user_id="test-user",
        )
        assert result.evidence.confidence == "high"

        # Tier 2 -> medium confidence
        result = await validator.validate(
            content="The API returns JSON",
            memory_type="fact",
            source="ai_synthesis",
            user_id="test-user",
        )
        assert result.evidence.confidence == "medium"

        # Tier 3 -> low confidence
        result = await validator.validate(
            content="Maybe we should use Redis",
            memory_type="fact",
            source="conversation",
            user_id="test-user",
        )
        assert result.evidence.confidence == "low"


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for the full ingestion flow."""

    @pytest.mark.asyncio
    async def test_full_flow_approve(self):
        """Test full flow from validation to approval."""
        provider = MockProvider([])
        validator = IngestionValidator(provider=provider, enable_dedup=True)

        # Validate grounded content
        result = await validator.validate(
            content="Per ADR-003, we use Pixeltable for memory storage",
            memory_type="decision",
            source="conversation",
            user_id="user-1",
        )

        assert result.tier == IngestionTier.AUTO_APPROVE
        assert result.evidence.source_id == "ADR-003"
        assert "citation_present" in result.checks_passed

    @pytest.mark.asyncio
    async def test_full_flow_flag_and_approve(self):
        """Test full flow with review queue."""
        provider = MockProvider([])
        validator = IngestionValidator(provider=provider, enable_dedup=True)
        queue = ReviewQueue()

        # Validate unsourced content -> FLAG_REVIEW
        result = await validator.validate(
            content="The API uses REST endpoints",
            memory_type="fact",
            source="ai_synthesis",
            user_id="user-1",
        )

        assert result.tier == IngestionTier.FLAG_REVIEW

        # Enqueue for review
        queue_id = await queue.enqueue(
            user_id="user-1",
            content="The API uses REST endpoints",
            memory_type="fact",
            source="ai_synthesis",
            evidence=result.evidence,
            validation_result=result,
        )

        # Approve after review (owner approves their own)
        memory_id = await queue.approve(queue_id, "user-1")
        assert memory_id is not None

    @pytest.mark.asyncio
    async def test_full_flow_block(self):
        """Test full flow with blocked content."""
        provider = MockProvider([])
        validator = IngestionValidator(provider=provider, enable_dedup=True)

        # Validate speculative content -> BLOCK
        result = await validator.validate(
            content="Maybe we should consider using MongoDB",
            memory_type="decision",
            source="conversation",
            user_id="user-1",
        )

        assert result.tier == IngestionTier.BLOCK
        assert not result.approved
        assert result.is_speculative


# =============================================================================
# Security Tests - Multi-Tenant Authorization
# =============================================================================


class TestReviewQueueAuthorization:
    """Security tests for multi-tenant authorization in ReviewQueue."""

    @pytest.fixture
    def queue(self):
        """Create a ReviewQueue instance."""
        return ReviewQueue()

    @pytest.fixture
    def evidence(self):
        """Create a test EvidenceObject."""
        return EvidenceObject.create(
            claim="Test claim",
            source_id=None,
            confidence="medium",
        )

    @pytest.fixture
    def validation_result(self, evidence):
        """Create a test ValidationResult."""
        return ValidationResult(
            tier=IngestionTier.FLAG_REVIEW,
            approved=False,
            reason="Test",
            evidence=evidence,
            checks_passed=[],
            checks_failed=["no_citation"],
        )

    @pytest.mark.asyncio
    async def test_owner_can_approve_own_memory(
        self, queue, evidence, validation_result
    ):
        """Memory owner should be able to approve their own pending memory."""
        queue_id = await queue.enqueue(
            user_id="user-1",
            content="Test memory",
            memory_type="fact",
            source="test",
            evidence=evidence,
            validation_result=validation_result,
        )

        # Owner approves - should succeed
        memory_id = await queue.approve(queue_id, "user-1")
        assert memory_id is not None

    @pytest.mark.asyncio
    async def test_other_user_cannot_approve_memory(
        self, queue, evidence, validation_result
    ):
        """Non-owner should not be able to approve another user's memory."""
        queue_id = await queue.enqueue(
            user_id="user-1",
            content="Test memory",
            memory_type="fact",
            source="test",
            evidence=evidence,
            validation_result=validation_result,
        )

        # Different user tries to approve - should fail
        with pytest.raises(ValueError, match="Unauthorized"):
            await queue.approve(queue_id, "user-2")

    @pytest.mark.asyncio
    async def test_owner_can_reject_own_memory(
        self, queue, evidence, validation_result
    ):
        """Memory owner should be able to reject their own pending memory."""
        queue_id = await queue.enqueue(
            user_id="user-1",
            content="Test memory",
            memory_type="fact",
            source="test",
            evidence=evidence,
            validation_result=validation_result,
        )

        # Owner rejects their own - should succeed
        await queue.reject(queue_id, "user-1", "Changed my mind")

        # Should be removed from queue
        pending = await queue.get_pending("user-1")
        assert len(pending) == 0

    @pytest.mark.asyncio
    async def test_other_user_cannot_reject_memory(
        self, queue, evidence, validation_result
    ):
        """Non-owner should not be able to reject another user's memory."""
        queue_id = await queue.enqueue(
            user_id="user-1",
            content="Test memory",
            memory_type="fact",
            source="test",
            evidence=evidence,
            validation_result=validation_result,
        )

        # Different user tries to reject - should fail
        with pytest.raises(ValueError, match="Unauthorized"):
            await queue.reject(queue_id, "user-2", "Not my memory")

    @pytest.mark.asyncio
    async def test_bulk_approve_skips_unauthorized(
        self, queue, evidence, validation_result
    ):
        """Bulk approve should skip items the user is not authorized for."""
        # User 1's memory
        queue_id_1 = await queue.enqueue(
            user_id="user-1",
            content="User 1 memory",
            memory_type="fact",
            source="test",
            evidence=evidence,
            validation_result=validation_result,
        )

        # User 2's memory
        queue_id_2 = await queue.enqueue(
            user_id="user-2",
            content="User 2 memory",
            memory_type="fact",
            source="test",
            evidence=evidence,
            validation_result=validation_result,
        )

        # User 1 tries to bulk approve both - only their own should succeed
        results = await queue.bulk_approve([queue_id_1, queue_id_2], "user-1")
        assert len(results) == 1  # Only one succeeded

        # User 2's memory should still be pending
        pending = await queue.get_pending("user-2")
        assert len(pending) == 1


class TestHedgeDetectorSecurity:
    """Security tests for HedgeDetector."""

    def test_generic_phrases_do_not_override_hedge_words(self):
        """Generic assertion markers should not bypass hedge word detection."""
        detector = HedgeDetector()

        # "It is" should NOT override speculation
        result = detector.analyze("It is maybe a good idea")
        assert result.is_speculative is True
        assert "maybe" in result.hedge_words_found

        # "According to" should NOT override speculation (was removed)
        result = detector.analyze("According to docs, this might work")
        assert result.is_speculative is True
        assert "might" in result.hedge_words_found

        # "This is" should NOT override speculation
        result = detector.analyze("This is probably wrong")
        assert result.is_speculative is True
        assert "probably" in result.hedge_words_found

    def test_assertion_markers_never_override_hedge_words(self):
        """SECURITY: Assertion markers must NEVER override hedge words.

        This is the critical security fix: adding "confirmed" or "verified"
        to speculative content must NOT bypass hedge detection.
        """
        detector = HedgeDetector()

        # "Confirmed" is tracked but does NOT override "might"
        result = detector.analyze("Confirmed: we might need this feature")
        assert result.is_speculative is True  # MUST stay speculative
        assert result.has_assertions is True  # But we track the assertion
        assert "might" in result.hedge_words_found

        # "Verified" is tracked but does NOT override "probably"
        result = detector.analyze("Verified that we should probably use this")
        assert result.is_speculative is True  # MUST stay speculative
        assert result.has_assertions is True
        assert "probably" in result.hedge_words_found

    def test_weak_phrases_do_not_override(self):
        """Removed assertion markers should NOT override hedge words."""
        detector = HedgeDetector()

        # "We decided" was removed - too easy to fake
        result = detector.analyze("We decided this might be the solution")
        assert result.is_speculative is True

        # "According to" was removed - too easy to fake
        result = detector.analyze("According to the API, maybe it works")
        assert result.is_speculative is True

    def test_strong_speculation_phrases_are_detected(self):
        """Strong speculation phrases must be detected and block ingestion."""
        detector = HedgeDetector()

        # "i don't know" must be detected
        result = detector.analyze("I don't know if this will work")
        assert result.is_speculative is True
        assert "i don't know" in result.hedge_words_found

        # "i do not know" must also be detected
        result = detector.analyze("I do not know the answer")
        assert result.is_speculative is True
        assert "i do not know" in result.hedge_words_found


class TestReviewQueueMultiTenant:
    """Multi-tenant security tests for ReviewQueue."""

    @pytest.fixture
    def evidence(self):
        from luminescent_cluster.memory.ingestion.evidence import EvidenceObject

        return EvidenceObject(
            claim="Test claim",
            capture_time=datetime.now(timezone.utc),
            confidence="medium",
        )

    @pytest.fixture
    def validation_result(self):
        from luminescent_cluster.memory.ingestion.result import IngestionTier, ValidationResult

        return ValidationResult(
            tier=IngestionTier.FLAG_REVIEW,
            approved=False,
            reason="Test",
            evidence=None,
            checks_passed=[],
            checks_failed=[],
        )

    @pytest.mark.asyncio
    async def test_get_review_history_filters_by_user(
        self, evidence, validation_result
    ):
        """get_review_history should only return actions for the specified user.

        SECURITY: Prevents cross-tenant data leakage.
        """
        queue = ReviewQueue()

        # Enqueue items for two users
        queue_id_1 = await queue.enqueue(
            user_id="user-1",
            content="Content 1",
            memory_type="fact",
            source="test",
            evidence=evidence,
            validation_result=validation_result,
        )
        queue_id_2 = await queue.enqueue(
            user_id="user-2",
            content="Content 2",
            memory_type="fact",
            source="test",
            evidence=evidence,
            validation_result=validation_result,
        )

        # Approve both
        await queue.approve(queue_id_1, "user-1")
        await queue.approve(queue_id_2, "user-2")

        # SECURITY: User 1 should only see their own history
        user1_history = await queue.get_review_history(user_id="user-1")
        assert len(user1_history) == 1
        assert user1_history[0].user_id == "user-1"

        # SECURITY: User 2 should only see their own history
        user2_history = await queue.get_review_history(user_id="user-2")
        assert len(user2_history) == 1
        assert user2_history[0].user_id == "user-2"

    @pytest.mark.asyncio
    async def test_queue_at_capacity_rejects_instead_of_evicting(
        self, evidence, validation_result
    ):
        """When queue is at capacity, new items should be rejected.

        SECURITY: Prevents cross-tenant DoS via eviction.
        """
        # Create queue with low max total
        queue = ReviewQueue(max_pending_per_user=100)
        queue.MAX_TOTAL_PENDING = 2  # Very low for testing

        # Fill the queue
        await queue.enqueue(
            user_id="user-1",
            content="Content 1",
            memory_type="fact",
            source="test",
            evidence=evidence,
            validation_result=validation_result,
        )
        await queue.enqueue(
            user_id="user-2",
            content="Content 2",
            memory_type="fact",
            source="test",
            evidence=evidence,
            validation_result=validation_result,
        )

        # SECURITY: Third item should be REJECTED, not evict user-1's item
        with pytest.raises(ValueError, match="at capacity"):
            await queue.enqueue(
                user_id="user-3",
                content="Content 3",
                memory_type="fact",
                source="test",
                evidence=evidence,
                validation_result=validation_result,
            )

        # Verify user-1 and user-2 items are still present
        assert queue.pending_count() == 2
        assert queue.pending_count("user-1") == 1
        assert queue.pending_count("user-2") == 1

    @pytest.mark.asyncio
    async def test_get_by_id_requires_authorization(self, evidence, validation_result):
        """get_by_id should only return memories for authorized user.

        SECURITY: Prevents IDOR vulnerability.
        """
        queue = ReviewQueue()

        # Enqueue for user-1
        queue_id = await queue.enqueue(
            user_id="user-1",
            content="Content 1",
            memory_type="fact",
            source="test",
            evidence=evidence,
            validation_result=validation_result,
        )

        # Owner can access
        pending = await queue.get_by_id(queue_id, user_id="user-1")
        assert pending is not None
        assert pending.content == "Content 1"

        # SECURITY: Other user cannot access (IDOR prevention)
        pending = await queue.get_by_id(queue_id, user_id="user-2")
        assert pending is None  # Silently returns None, no error leakage


class TestDedupCheckerSecurity:
    """Security tests for DedupChecker."""

    @pytest.mark.asyncio
    async def test_dedup_check_raises_on_provider_error(self):
        """DedupChecker should raise DedupCheckError on provider failure.

        SECURITY: Fail-closed - errors should not allow content through.
        """
        from unittest.mock import AsyncMock

        from luminescent_cluster.memory.ingestion.dedup_checker import DedupCheckError, DedupChecker

        # Create a provider that always fails
        mock_provider = AsyncMock()
        mock_provider.search.side_effect = Exception("Database connection failed")

        checker = DedupChecker(mock_provider)

        with pytest.raises(DedupCheckError) as exc_info:
            await checker.check_duplicate("Some content", "user-1")

        assert "provider error" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_validator_flags_for_review_on_dedup_failure(self):
        """Validator should flag for review when dedup check fails.

        SECURITY: Cannot verify uniqueness = cannot auto-approve.
        """
        from unittest.mock import AsyncMock

        from luminescent_cluster.memory.ingestion.dedup_checker import DedupChecker
        from luminescent_cluster.memory.ingestion.result import IngestionTier
        from luminescent_cluster.memory.ingestion.validator import IngestionValidator

        # Create a provider that always fails
        mock_provider = AsyncMock()
        mock_provider.search.side_effect = Exception("Database connection failed")

        validator = IngestionValidator(
            provider=mock_provider,
            enable_dedup=True,
        )

        # Content that would otherwise be auto-approved (trusted source)
        result = await validator.validate(
            content="User prefers dark mode",
            memory_type="preference",
            source="user",
            user_id="user-1",
        )

        # SECURITY: Even with trusted source, dedup failure → flag for review
        assert result.tier == IngestionTier.FLAG_REVIEW
        assert "dedup_check_failed" in str(result.checks_failed)
        assert "cannot verify uniqueness" in result.reason.lower()
