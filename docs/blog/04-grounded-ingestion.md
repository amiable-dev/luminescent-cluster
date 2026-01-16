# Grounded Ingestion: Preventing AI Hallucination Write-Back

**When AI agents have write access to your knowledge base, hallucinations become persistent. Here's how we built a provenance system that blocks ungrounded claims.**

---

AI agents are increasingly trusted to not just read but write. They synthesize information, make inferences, and store conclusions for future reference. The problem? AI confidently states things that aren't true. And if those hallucinations get written to your knowledge base, they become persistent misinformation.

"The API uses OAuth2 for authentication." Sounds authoritative. But did the AI actually verify this, or did it hallucinate a plausible-sounding claim? Once stored, future sessions will retrieve this "fact" and build on it.

Grounded ingestion solves this by classifying every memory claim into one of three tiers based on its provenance evidence.

## The 3-Tier Provenance Model

```
┌─────────────────────────────────────────────────────────────────┐
│                    Incoming Memory Claim                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────┐   ┌────────────┐   ┌────────────┐              │
│  │  Citation  │   │   Hedge    │   │   Dedup    │              │
│  │  Detector  │   │  Detector  │   │  Checker   │              │
│  └─────┬──────┘   └─────┬──────┘   └─────┬──────┘              │
│        │                │                │                      │
│        └────────────────┼────────────────┘                      │
│                         ▼                                        │
│              ┌──────────────────────┐                           │
│              │   Tier Determination │                           │
│              └──────────────────────┘                           │
│                         │                                        │
│        ┌────────────────┼────────────────┐                      │
│        ▼                ▼                ▼                      │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐                  │
│  │  TIER 1  │    │  TIER 2  │    │  TIER 3  │                  │
│  │  AUTO-   │    │  FLAG    │    │  BLOCK   │                  │
│  │  APPROVE │    │  REVIEW  │    │          │                  │
│  └──────────┘    └──────────┘    └──────────┘                  │
│       │                │                │                       │
│       ▼                ▼                ▼                       │
│    Stored          Queued           Rejected                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Tier 1: Auto-Approve (High Confidence)

Claims with explicit grounding evidence are stored immediately:

- **Has citation**: ADR reference, commit hash, URL, issue number
- **Trusted source**: User-stated, documentation, manual entry
- **Decision in context**: Explicit decisions from conversations

Examples:
```
"Per ADR-003, we use Pixeltable for memory storage"  → AUTO (has ADR citation)
"Fixed in commit a1b2c3d4e5f6"                       → AUTO (has commit hash)
"See https://docs.example.com/api"                   → AUTO (has URL)
"I prefer tabs over spaces" (source=user)            → AUTO (trusted source)
```

### Tier 2: Flag for Review (Medium Confidence)

Claims that aren't obviously grounded or speculative need human verification:

- **AI synthesis without citation**: Factual assertions from AI without explicit sources
- **Dedup check failed**: Provider error means we can't verify uniqueness
- **Ambiguous claims**: Could be true but unverified

Examples:
```
"The API returns JSON for REST responses"            → REVIEW (AI synthesis, no citation)
"OAuth2 is the authentication mechanism"             → REVIEW (factual assertion, ungrounded)
"The service uses PostgreSQL 15"                     → REVIEW (could be true, needs verification)
```

### Tier 3: Block (Low Confidence)

Claims that are explicitly speculative or duplicate are rejected:

- **Strong speculation**: "I think", "I guess", "maybe" without any grounding
- **Duplicate content**: >92% similarity to existing memory
- **Personal uncertainty**: Language expressing the speaker doesn't know

Examples:
```
"I think we should use Redis"                        → BLOCK (personal speculation)
"I guess the API supports this"                      → BLOCK (admitted uncertainty)
"Maybe we could try GraphQL"                         → BLOCK (ungrounded suggestion)
"Per ADR-003, we use PostgreSQL" (already stored)   → BLOCK (duplicate)
```

**Note:** Technical hedges like "may", "typically", or "often" are treated differently—see Hedge Detection below.

## Detection Mechanisms

### Citation Detection & Verification

Grounding requires two steps: **detection** (finding citation patterns) and **verification** (checking they're real).

**Step 1: Detection**

The `CitationDetector` uses regex patterns to identify potential grounding evidence:

```python
PATTERNS = {
    "adr": r"\[?ADR[-\s]?(\d+)\]?",           # [ADR-003], ADR-003, ADR 003
    "commit": r"\b[a-f0-9]{7,40}\b",           # 7-40 hex chars (not colors)
    "url": r"https?://[^\s<>\"]+",             # http:// or https://
    "issue": r"(?:#(\d+)|GH-(\d+))",           # #123 or GH-456
}
```

**Smart filtering:**
- Excludes 6-character hex codes (colors like `#abc123`)
- Strips URLs before commit detection (no false positives in URL paths)
- Returns citation type, position, and extracted ID

**Step 2: Verification (Critical)**

Detection alone is insufficient—AI can hallucinate plausible-looking citations. Verification checks that cited artifacts actually exist:

```python
async def verify_citation(citation: Citation) -> VerificationResult:
    """Verify that a detected citation actually exists."""
    match citation.type:
        case "url":
            # Check URL resolves (HTTP HEAD request)
            response = await http_client.head(citation.value, timeout=5)
            return VerificationResult(
                valid=response.status_code == 200,
                reason=f"HTTP {response.status_code}"
            )

        case "commit":
            # Check commit exists in repo
            result = subprocess.run(
                ["git", "cat-file", "-t", citation.value],
                capture_output=True
            )
            return VerificationResult(
                valid=result.returncode == 0,
                reason="Commit exists" if result.returncode == 0 else "Unknown commit"
            )

        case "adr":
            # Check ADR file exists
            adr_path = f"docs/adrs/ADR-{citation.value}-*.md"
            exists = len(glob.glob(adr_path)) > 0
            return VerificationResult(valid=exists, reason="ADR file exists" if exists else "ADR not found")

        case "issue":
            # Check issue exists (requires API call to GitHub/GitLab)
            # Implementation depends on your issue tracker
            ...
```

**Why verification matters:** LLMs confidently fabricate citations. We've seen:
- URLs that return 404
- Commit hashes that don't exist
- ADR numbers that were never written

Detection + verification together provide actual grounding.

### Hedge Detection

The `HedgeDetector` identifies uncertainty language, but not all hedges are equal. We distinguish between **personal speculation** (block) and **technical hedges** (review).

**Hedge categories and actions:**

| Category | Examples | Action |
|----------|----------|--------|
| Personal speculation | I think, I guess, I believe, I assume | **Block** |
| Admitted uncertainty | I don't know, not sure, I could be wrong | **Block** |
| Suggestions | maybe we should, perhaps we could | **Block** |
| Technical hedges | may, might, typically, often, usually | **Review** |
| Approximations | approximately, around, roughly | **Review** |

**Why the distinction?** Legitimate technical documentation uses hedges appropriately:
- "The server may timeout under load" — valid engineering guidance
- "Connections typically complete in <100ms" — accurate qualification
- "I think we should use Redis" — ungrounded personal opinion

```python
detector = HedgeDetector()

# Personal speculation → Block
result = detector.analyze("I think we should use Redis")
# HedgeResult(is_speculative=True, action=BLOCK, hedge_words=["I think"])

# Technical hedge → Review
result = detector.analyze("The API may return errors under load")
# HedgeResult(is_speculative=True, action=REVIEW, hedge_words=["may"])

# No hedges → Continue to other checks
result = detector.analyze("Per ADR-003, we use PostgreSQL")
# HedgeResult(is_speculative=False, action=CONTINUE)
```

**Bypass prevention:** The trivial bypass "I think X, definitely" doesn't work—personal speculation markers always trigger regardless of assertion markers.

**False positive filtering:**
- "May 2024" → Month name, not modal verb
- "couldn't" → Negation often indicates certainty
- "should be 5" → Factual numeric description

### Deduplication

The `DedupChecker` prevents duplicate memories using word-level Jaccard similarity:

```
Jaccard(A, B) = |A ∩ B| / |A ∪ B|
```

Where A and B are sets of lowercase tokens from each text.

**Threshold:** 92% similarity = duplicate (per ADR-003)

```python
from collections import Counter

def jaccard_similarity(text1: str, text2: str) -> float:
    """Calculate word-level Jaccard similarity."""
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())

    intersection = len(words1 & words2)
    union = len(words1 | words2)

    return intersection / union if union > 0 else 0.0

# Usage
checker = DedupChecker(provider=memory_provider, threshold=0.92)

result = await checker.check_duplicate(
    content="Per ADR-003, we use Pixeltable for storage",
    user_id="user-123",
    memory_type="decision"
)
# DuplicateResult(is_duplicate=True, similarity=0.95, existing_memory_id="mem-456")
```

**Why Jaccard over semantic similarity?**

| Approach | Speed | Catches | Misses |
|----------|-------|---------|--------|
| Jaccard (word overlap) | <1ms | Copy-paste, minor edits | Paraphrasing, synonyms |
| Vector similarity | 50-200ms | Semantic duplicates | Requires embedding model |
| MinHash/SimHash | <5ms | Near-duplicates at scale | Needs preprocessing |

We chose Jaccard for **speed**—it runs on every ingestion without latency impact. The 92% threshold catches most copy-paste duplicates while allowing legitimate variations.

**Known limitation:** Jaccard misses semantic duplicates where AI rephrases the same claim. For higher-value knowledge bases, consider upgrading to vector-based deduplication or MinHash for scale:

```python
# Future: Semantic deduplication (slower but catches paraphrasing)
async def semantic_dedup(content: str, user_id: str) -> DuplicateResult:
    embedding = await embed(content)
    similar = await vector_index.search(embedding, threshold=0.95)
    return DuplicateResult(is_duplicate=len(similar) > 0, ...)
```

## The Decision Tree

```python
from enum import Enum
from dataclasses import dataclass

class Tier(Enum):
    AUTO_APPROVE = "tier_1"
    FLAG_REVIEW = "tier_2"
    BLOCK = "tier_3"

class HedgeAction(Enum):
    BLOCK = "block"      # Personal speculation
    REVIEW = "review"    # Technical hedges
    CONTINUE = "none"    # No hedges

TRUSTED_SOURCES = {"user", "documentation", "adr", "commit", "manual"}

def determine_tier(
    hedge_result: HedgeAction,
    is_duplicate: bool,
    dedup_failed: bool,
    has_verified_citation: bool,
    source: str,
    memory_type: str
) -> tuple[Tier, str]:
    """
    Determine ingestion tier based on grounding evidence.

    Returns (tier, reason) tuple.
    """
    # Tier 3: Block personal speculation
    if hedge_result == HedgeAction.BLOCK:
        return Tier.BLOCK, "Contains personal speculation"

    # Tier 3: Block duplicates
    if is_duplicate:
        return Tier.BLOCK, "Duplicate of existing memory"

    # Tier 2: Technical hedges need review
    if hedge_result == HedgeAction.REVIEW:
        return Tier.FLAG_REVIEW, "Contains technical hedges - needs verification"

    # Tier 2: Dedup check failed (fail-closed)
    if dedup_failed:
        return Tier.FLAG_REVIEW, "Dedup check failed - cannot verify uniqueness"

    # Tier 1: Verified citation
    if has_verified_citation:
        return Tier.AUTO_APPROVE, "Has verified citation"

    # Tier 1: Trusted source
    if source in TRUSTED_SOURCES:
        return Tier.AUTO_APPROVE, f"From trusted source: {source}"

    # Tier 1: User-stated decisions/preferences
    if memory_type == "decision" and source == "conversation":
        return Tier.AUTO_APPROVE, "Decision stated in conversation"

    if memory_type == "preference" and source in ("conversation", "chat"):
        return Tier.AUTO_APPROVE, "Preference stated by user"

    # Tier 2: Everything else needs review
    return Tier.FLAG_REVIEW, "Ungrounded assertion needs verification"
```

**Key design choices:**
- **Fail-closed**: Provider errors (like dedup failures) route to review, never auto-approve
- **Hedge nuance**: Personal speculation blocks; technical hedges go to review
- **Verification required**: Citations must be verified, not just detected

## The Review Queue

Tier 2 memories enter a review queue for human verification:

```python
@dataclass
class PendingMemory:
    queue_id: str           # Unique identifier
    user_id: str            # Owner
    content: str            # The claim
    memory_type: str        # preference/fact/decision
    source: str             # Origin
    evidence: EvidenceObject  # Provenance metadata
    submitted_at: datetime  # UTC timestamp
```

**Queue operations:**

```python
queue = ReviewQueue(store_callback=store_memory)

# Enqueue a flagged memory
queue_id = await queue.enqueue(
    user_id="user-123",
    content="The API uses OAuth2",
    memory_type="fact",
    source="ai_synthesis",
    evidence=evidence,
    validation_result=result,
)

# User reviews their pending memories
pending = await queue.get_pending("user-123", limit=10)

# User approves (stores the memory)
memory_id = await queue.approve(queue_id, reviewer="user-123")

# Or rejects (discards with reason)
await queue.reject(queue_id, reviewer="user-123", reason="Incorrect, we use JWT")
```

**Security properties:**

| Property | Implementation |
|----------|----------------|
| Authorization | Only owner can approve/reject (reviewer == user_id) |
| Isolation | get_by_id requires user_id match (prevents IDOR) |
| DoS prevention | Per-user limit (100), total limit (10,000) |
| Race-free | Atomic removal before store callback |
| Audit trail | All actions recorded with timestamp |

## Evidence Objects

Every memory carries provenance metadata:

```python
@dataclass
class EvidenceObject:
    claim: str                           # The content
    capture_time: datetime               # When captured
    confidence: str                      # high/medium/low
    source_id: Optional[str] = None      # ADR-003, commit:a1b2c3d, URL
    validity_horizon: Optional[datetime] = None  # Expiration
    metadata: dict = {}                  # Extensible
```

This enables downstream systems to:
- Filter by confidence level
- Trace claims back to sources
- Expire time-sensitive information
- Audit memory provenance

## Validation Results

The complete output of ingestion validation:

```python
@dataclass
class ValidationResult:
    tier: IngestionTier           # AUTO_APPROVE, FLAG_REVIEW, or BLOCK
    approved: bool                # True only for Tier 1
    reason: str                   # Human-readable explanation
    evidence: EvidenceObject      # Provenance metadata
    checks_passed: list[str]      # ["citation_present", "no_speculation"]
    checks_failed: list[str]      # ["hedge_words_detected: maybe"]
    similarity_score: Optional[float]    # If duplicate found
    conflicting_memory_id: Optional[str] # ID of duplicate
```

## Usage Example

```python
from src.memory.ingestion import IngestionValidator, ReviewQueue

# Create validator with deduplication
validator = IngestionValidator(
    provider=memory_provider,
    enable_dedup=True
)

# Validate an incoming claim
result = await validator.validate(
    content="Per ADR-003, we use Pixeltable for memory storage",
    memory_type="decision",
    source="conversation",
    user_id="user-123"
)

# Route based on tier
if result.tier == IngestionTier.AUTO_APPROVE:
    # Store immediately
    memory_id = await store_memory(result.evidence)
    print(f"Stored: {memory_id}")

elif result.tier == IngestionTier.FLAG_REVIEW:
    # Queue for review
    queue = ReviewQueue(store_callback=store_memory)
    queue_id = await queue.enqueue(
        user_id="user-123",
        content=result.evidence.claim,
        memory_type="decision",
        source="conversation",
        evidence=result.evidence,
        validation_result=result,
    )
    print(f"Queued for review: {queue_id}")

else:  # BLOCK
    print(f"Rejected: {result.reason}")
    print(f"Failed checks: {result.checks_failed}")
```

## What Gets Blocked vs Accepted

### Always Blocked (Tier 3)

```python
# Personal speculation
"I think we should use Redis"                  # personal opinion
"I guess the API supports this"                # admitted uncertainty
"Maybe we could try GraphQL"                   # ungrounded suggestion

# Duplicates
"Per ADR-003, we use PostgreSQL"               # (if already stored)

# Bypass attempts
"I think we should use Redis, definitely"      # personal speculation still blocks
```

### Always Accepted (Tier 1)

```python
# Has VERIFIED citation (not just detected)
"Per ADR-003, we use PostgreSQL"               # ADR file exists
"Fixed in commit a1b2c3d4e5"                   # commit exists in repo
"See https://docs.example.com/api"             # URL returns 200

# Trusted source
"I prefer tabs over spaces" (source=user)      # user-stated
"OAuth2 is required" (source=documentation)    # documentation

# Decisions in context
"We decided to use PostgreSQL" (type=decision, source=conversation)
```

### Flagged for Review (Tier 2)

```python
# Technical hedges (legitimate uncertainty)
"The server may timeout under load"            # technical "may"
"Connections typically complete in <100ms"     # "typically" is qualified

# AI synthesis without citation
"The API returns JSON for REST responses"
"OAuth2 is the authentication mechanism"

# Citation detected but NOT verified
"Per ADR-999, we use magic"                    # ADR-999 doesn't exist

# Dedup check failed
(any content when provider throws an error)
```

## The Security Model

Grounded ingestion implements defense-in-depth:

1. **Hedge detection**: First line. Blocks personal speculation, reviews technical hedges.
2. **Deduplication**: Second line. Prevents duplicate pollution (lexical).
3. **Citation verification**: Third line. Confirms cited artifacts exist.
4. **Source trust**: Fourth line. Trusts verified sources.
5. **Review queue**: Fifth line. Human verification for uncertain claims.
6. **Fail-closed**: Sixth line. Errors flag for review, never auto-approve.

**The goal:** Minimize hallucination write-back while keeping friction low.

## Limitations

This system isn't perfect. Know what it can't catch:

### Evasion Risks

| Attack | Can We Catch It? | Mitigation |
|--------|------------------|------------|
| Confident hallucination ("The API uses OAuth2.") | **No** | Goes to Tier 2 review |
| Fabricated but valid-looking URL | **Partial** | Verification catches 404s, not wrong content |
| Paraphrased duplicate | **No** | Jaccard misses semantic duplicates |
| Prompt injection teaching AI to avoid hedges | **No** | Out of scope (input validation problem) |
| Correct citation, wrong claim | **No** | Citation verification doesn't check relevance |

### What This System Can't Do

1. **Verify claim-citation relevance**: We check that ADR-003 exists, not that it actually supports the claim
2. **Catch confident hallucinations**: "X is true" without hedges goes to review, not block
3. **Scale to semantic deduplication**: Jaccard is fast but shallow
4. **Replace human judgment**: Tier 2 still requires human review

### Recommendations for High-Stakes Use

For production knowledge bases with compliance requirements:

```python
# Upgrade path for stricter grounding
config = GroundedIngestionConfig(
    # Semantic deduplication (slower but thorough)
    dedup_method="vector",
    dedup_threshold=0.95,

    # LLM-based claim verification (expensive but accurate)
    verify_claim_relevance=True,

    # All AI synthesis goes to review (safest)
    auto_approve_ai_synthesis=False,
)
```

The current implementation optimizes for **speed and low friction** over **maximum accuracy**. Adjust based on your risk tolerance.

## Performance Characteristics

| Check | Latency | Notes |
|-------|---------|-------|
| Citation detection | <1ms | Regex patterns |
| Hedge detection | <1ms | Word matching |
| Deduplication | 10-50ms | Provider query + Jaccard |
| Queue operations | <1ms | In-memory dict |
| **Total validation** | **~50ms** | Dominated by dedup |

For high-throughput scenarios, you can disable dedup:

```python
validator = IngestionValidator(enable_dedup=False)
# Faster, but won't catch duplicates
```

## Why This Matters

AI systems are moving from read-only to read-write. They don't just retrieve information—they synthesize, infer, and persist conclusions. Without provenance tracking, hallucinations compound:

1. AI hallucinates "The API uses OAuth2"
2. Gets stored as a "fact"
3. Future queries retrieve it
4. AI builds on it: "Since we use OAuth2, we need refresh tokens"
5. More hallucinations stored
6. Knowledge base drifts from reality

Grounded ingestion breaks this cycle. Every claim goes through provenance checking:
- **Grounded + Verified**: Auto-approved with citation trail
- **Uncertain**: Flagged for human review
- **Speculative**: Blocked before it enters the knowledge base

This isn't a perfect solution—confident hallucinations still need human review, and sophisticated evasion is possible. But it dramatically reduces the rate at which ungrounded claims pollute your knowledge base, and it creates an audit trail for everything that does get stored.

The goal isn't zero hallucinations (that's impossible with current AI). The goal is **traceable provenance**: knowing where every stored claim came from and why it was trusted.

---

*Grounded ingestion is part of ADR-003 Phase 2. See the [full ADR](../adrs/ADR-003-project-intent-persistent-context.md) for implementation details and security considerations.*
