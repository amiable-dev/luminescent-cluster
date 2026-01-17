# ADR-010: Test Ledger & Documentation Validation System

**Status**: Accepted
**Date**: 2026-01-17
**Decision Makers**: Development Team
**Owners**: @christopherjoseph
**Version**: 1.0 (Council Approved)

## Decision Summary

Implement a multi-layer validation system for **requirements traceability** - ensuring the spec/ledger stays synchronized with test files and documentation links remain valid.

| Aspect | Decision |
|--------|----------|
| Scope | Ledger schema validation, test introspection, link checking, ADR-ledger sync |
| Link Checker | Internal links only (fast, no network dependencies) |
| Skip Detection | Tiered warnings (unconditional=warn, conditional=info, xfail=info) |
| Test Reference Format | `path/to/file.py::ClassName::method_name` |
| Out of Scope | Semantic drift (test quality), memory freshness (handled by product) |

---

## Scope Clarification

### What This ADR Is (Internal Tooling)

This ADR proposes **internal tooling for requirements traceability**:
- Validates that `spec/ledger.yml` maps to real test functions
- Validates that documentation links resolve correctly
- Validates that ADR references in ledger are accurate
- Detects skipped tests that won't execute

### What This ADR Is NOT (Product Features)

This is **NOT about memory freshness** - the product already handles that:

| Concern | Owner | Implementation |
|---------|-------|----------------|
| **Memory Freshness** (Product) | `src/memory/lifecycle/` | Temporal decay (30-day half-life), TTL policies, reindex triggers |
| **Memory Quality** (Product) | `src/memory/ingestion/` | Grounded ingestion, citation detection, hedge detection |
| **Ledger Quality** (Internal) | `spec/validation/` | This ADR - reconciliation, schema validation, skip detection |

### Synergies with Product Features

Potential future integration points (post-MVP):
- Memory ingestion could validate ADR sources exist
- ADR-ledger sync could flag memories for re-validation when ADRs change
- Both systems share test quality validation patterns

---

## Context

### The Problem: Silent Structural Drift

The current `spec/validation/reconcile.py` only validates ~30% of what could make the ledger stale:

**What it validates:**
- Ledger YAML loads successfully
- Test file paths exist on disk
- Coverage thresholds by priority
- Baseline ratchet (prevents coverage regression)

**What it doesn't validate:**
- Tests can be skipped/broken without detection
- Test function names (only file paths checked)
- Ledger YAML schema (invalid fields silently ignored)
- ADR-to-ledger synchronization
- Documentation link validity
- Content freshness

### Impact Analysis

| Gap | Impact | Example Failure Mode |
|-----|--------|---------------------|
| Tests can be skipped | HIGH | `@pytest.skip` on requirement test passes reconciliation |
| Test function names not validated | HIGH | `tests/foo.py::test_bar` passes if file exists but `test_bar` doesn't |
| No schema validation | MEDIUM | Typo in `status: unknonw` silently ignored |
| ADR changes don't cascade | HIGH | New requirement in ADR never added to ledger |
| No link checking | MEDIUM | Broken `[link](404.md)` in docs not caught |

---

## Decision

### Multi-Layer Validation Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Validation Layers                         │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: Ledger Validation (reconcile.py)                  │
│    ├── YAML Schema Validation                               │
│    ├── Test File Existence (existing)                       │
│    ├── Test Function Introspection (AST)                    │
│    └── Coverage Thresholds (existing)                       │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: Documentation Freshness (doc_freshness.py)        │
│    ├── Internal Link Checker                                │
│    ├── ADR-Ledger Sync Checker                              │
│    └── Content Freshness Indicators                         │
├─────────────────────────────────────────────────────────────┤
│  Layer 3: Cross-Reference Validation                        │
│    ├── Requirements ↔ Ledger Sync                           │
│    └── Pytest Skip Detection                                │
├─────────────────────────────────────────────────────────────┤
│  Layer 4: CI Enforcement                                    │
│    ├── Blocking mode on PRs                                 │
│    └── Summary reports                                      │
└─────────────────────────────────────────────────────────────┘
```

### Layer 1: Enhanced Ledger Validation

**Schema Validation:**
```python
VALID_STATUS = {"active", "deprecated", "proposed", "manual"}
VALID_PRIORITY = {"critical", "high", "medium", "low"}
REQUIRED_FIELDS = {"title", "source", "status", "priority"}
```

**Test Function Introspection:**
- Use Python AST to parse test files for function names
- Handle class-based tests: `TestClass::test_method`
- Handle parametrized tests via `pytest --collect-only` fallback
- Verify `::test_name` references exist as functions/methods
- Report mismatches as errors
- Handle `SyntaxError` gracefully (report file as unparseable)

### Layer 2: Documentation Freshness

**Link Checker:**
- Scan `docs/**/*.md` for markdown links
- Validate internal links resolve to existing files
- Report broken links with file:line references

**ADR-Ledger Sync:**
- Parse ADRs for `REQ-*` and `NEG-*` patterns
- Verify referenced requirements exist in ledger
- Verify ledger `source` fields point to valid ADRs

### Layer 3: Skip Detection (via pytest --collect-only)

**Approach:** Use pytest collection, NOT test execution
- Run `pytest --collect-only` to resolve parametrized test IDs
- Alternatively, consume JUnit XML from previous CI step
- Apply tiered skip policy:

| Skip Type | Policy | Rationale |
|-----------|--------|-----------|
| `@pytest.skip` (unconditional) | **Warning** | Indicates potential rot/abandonment |
| `@pytest.skipif` (conditional) | **Info** | Legitimate platform/environment logic |
| `@pytest.mark.xfail` | **Info** | Known failures being tracked |

**NOT Implemented:** Test execution validation (out of scope - handled by separate CI job)

### Layer 4: CI Enforcement

**Updates to workflows:**
- Enable blocking mode in `reconcile.yml`
- Add doc freshness checks to `docs.yml`
- Generate summary reports as artifacts
- Aggregate all errors (don't stop at first)

---

## Explicit Out of Scope

Per council review, the following are **explicitly out of scope**:

| Out of Scope | Reason | Handled By |
|--------------|--------|------------|
| **Semantic Drift** | Test exists but doesn't verify requirement | Peer review, test quality audits |
| **Test Execution** | Actually running tests | Separate CI job (`pytest`) |
| **Memory Freshness** | Stale memories in knowledge base | `src/memory/lifecycle/decay.py` |
| **External Links** | URLs to external sites | Network dependencies, false positives |
| **Test Coverage %** | Code coverage metrics | `pytest-cov`, separate tooling |

**Semantic drift example** (NOT detected by this system):
```python
# Ledger maps REQ-SEC-001 to this test
def test_prevent_idor_attacks():
    assert True  # ← Passes structurally, but doesn't test IDOR
```

This is a **peer review concern**, not an automated validation concern.

---

## Implementation Phases

| Phase | Scope | Files |
|-------|-------|-------|
| 1 | Schema validation, AST test introspection | `spec/validation/reconcile.py` |
| 2 | Documentation link checker | `spec/validation/doc_freshness.py` |
| 3 | ADR-ledger synchronization | `spec/validation/doc_freshness.py` |
| 4 | Pytest skip detection | `spec/validation/reconcile.py` |
| 5 | CI enforcement & reporting | `.github/workflows/*.yml` |

---

## Alternatives Considered

### Alternative 1: External Tooling Only

Use existing tools like `markdownlint`, `lychee`, and `jsonschema` without custom integration.

**Rejected because:**
- Doesn't handle ADR-ledger bidirectional sync
- No understanding of requirement ID conventions
- Can't integrate with existing reconcile.py

### Alternative 2: Full Test Execution Validation

Run all tests to verify they pass, not just exist.

**Deferred because:**
- Significant CI time increase
- Reconciliation should be fast (<30s)
- Test execution is already in separate CI job

### Alternative 3: External Link Checking

Include external URL validation in link checker.

**Rejected because:**
- Network dependencies slow down CI
- False positives from timeouts
- External sites change independently

---

## Consequences

### Positive
- **Catch ledger drift early**: Invalid entries detected before merge
- **Documentation quality**: Broken links surfaced automatically
- **ADR discipline**: Requirements must exist in ledger
- **Test coverage accuracy**: Skipped tests visible in reports
- **Fast feedback**: All checks complete in <30s

### Negative
- **Maintenance overhead**: New validation code to maintain
- **False positives possible**: AST parsing may miss edge cases
- **Learning curve**: Team must understand new validations

### Mitigations
- Comprehensive test suite for validation code
- Warning mode for new checks initially
- Clear error messages with fix suggestions

---

## Verification

```bash
# Phase 1: Schema and AST validation
python spec/validation/reconcile.py --verbose
# Expect: Schema Validation: PASSED, Test Function Existence: PASSED

# Phase 2: Link checker
python spec/validation/doc_freshness.py --check-links
# Expect: Report of any broken internal links

# Phase 3: ADR-ledger sync
python spec/validation/doc_freshness.py --check-adr-sync
# Expect: Sync status per ADR

# Phase 4: Skip detection
python spec/validation/reconcile.py --check-skips
# Expect: Warning for skipped requirement tests

# Full suite
python spec/validation/reconcile.py --verbose --check-skips && \
python spec/validation/doc_freshness.py --check-links --check-adr-sync
```

---

## Related Decisions

- **ADR-008**: MkDocs Documentation Site (doc deployment)
- **ADR-009**: Spec/Ledger Reconciliation (foundation for this ADR)

---

## Council Review (Round 2) - FINAL

**Review Date**: 2026-01-17
**Verdict**: **APPROVED** ✅
**Status**: Ready for Implementation

### Council Rankings (Round 2)
| Model | Score |
|-------|-------|
| openai/gpt-5.2 | 1.000 |
| google/gemini-3-pro-preview | 0.667 |
| anthropic/claude-opus-4.5 | 0.167 |
| x-ai/grok-4.1-fast | 0.111 |

### Key Findings (Round 2)

1. **Scope Clarification**: Resolved. Internal tooling vs product features is now unambiguous.
2. **Overlaps**: None identified. Clean separation achieved.
3. **Framing**: Accurate. "Test Ledger" correctly implies static accounting of requirements vs tests.

### Implementation Mandates (Round 2)

1. **Exit Codes for CI**:
   - `0` (Pass): All mappings resolve, docs link correctly
   - `1` (Fail): Broken references, missing required tests, malformed ledger
   - `2` (Warning): Unconditional `@skip`, orphan mappings; allow strict mode to fail

2. **pytest --collect-only Risks**:
   - Collection imports modules (potential side effects)
   - Consider pytest plugin hook (`pytest_collection_modifyitems`) for JSON export
   - Cache collection results keyed by commit hash

3. **Canonical Identifier Normalization**:
   - Handle Windows `\` vs Linux `/` path separators
   - Document parametrization syntax (`test_name[param1]`)

4. **Bi-Directional Validation (Orphan Problem)**:
   - Ledger→Test: Does every requirement have a test? (implemented)
   - Test→Ledger: Are there tests referencing deleted requirements? (add as warning)

5. **CLI Entry Point**: `make validate-ledger` or `python spec/validation/reconcile.py --full`

6. **Synergies as Future Work**: Explicitly label ADR-triggered memory re-validation as out of scope for v1.0

---

## Council Review (Round 1)

**Review Date**: 2026-01-17
**Verdict**: APPROVED with Technical Amendments
**Consensus Strength**: 0.78

### Council Rankings
| Model | Score |
|-------|-------|
| openai/gpt-5.2 | 0.778 |
| anthropic/claude-opus-4.5 | 0.667 |
| google/gemini-3-pro-preview | 0.500 |
| x-ai/grok-4.1-fast | 0.000 |

### Key Findings

#### 1. Structural vs Semantic Drift (Unanimous)

**Finding**: This proposal addresses **structural drift** (reference integrity) but NOT **semantic drift** (test quality).

**Example**:
- ✅ Catches: `test_login` was renamed to `test_auth` but ledger still references `test_login`
- ❌ Misses: `test_login` exists but only asserts `True`

**Amendment**: Explicitly scope out semantic verification. Focus on "the pointed-to symbol exists."

#### 2. Parametrized Tests Gap (High Priority)

**Finding**: AST parsing cannot handle pytest parametrization:
```python
@pytest.mark.parametrize("x", [1, 2, 3])
def test_foo(x): ...
# Generates: test_foo[1], test_foo[2], test_foo[3]
```

**Amendment**: Use `pytest --collect-only` instead of pure AST for Layer 3. This resolves parametrized test IDs.

#### 3. Canonical Test Reference Format (Required)

**Finding**: Need to define explicit format for test references.

**Amendment**: Adopt format: `path/to/file.py::ClassName::method_name`
- File-only: `tests/test_foo.py`
- Function: `tests/test_foo.py::test_bar`
- Class method: `tests/test_foo.py::TestClass::test_method`

#### 4. Skip Detection Taxonomy (High Priority)

**Finding**: Not all skips indicate staleness. Council recommends tiered policy:

| Skip Type | MVP Policy | Future Policy |
|-----------|------------|---------------|
| `@pytest.skip` (unconditional) | Warning | Block (indicates rot) |
| `@pytest.skipif` (conditional) | Info | Allow (legitimate) |
| `@pytest.mark.xfail` | Info | Allow (if has ticket) |

**Amendment**: Implement tiered skip detection with configurable escalation.

#### 5. Orphan Detection (Medium Priority)

**Finding**: Proposal checks ledger→tests but not tests→ledger.

**Amendment**: Add inverse check - identify tests NOT mapped in ledger.

#### 6. AST Security/Performance (Confirmed Safe)

**Finding**: AST parsing is:
- **Safe**: Does not execute code (unlike `import`)
- **Fast**: ~1-5ms per file
- **Robust**: Must handle `SyntaxError` gracefully

**Amendment**: Add `SyntaxError` handling to report unparseable files.

### Implementation Mandates

1. **Refine Layer 3**: Switch from test execution to `pytest --collect-only` + JUnit XML parsing
2. **Define Schema**: Explicit test reference format in specification
3. **Update Scope**: Add "semantic verification is out of scope" statement
4. **Add Metadata**: Support skip justification fields (`skip_reason`, `ticket_link`)

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 0.1 | 2026-01-17 | Initial draft |
| 0.2 | 2026-01-17 | Council Review Round 1: Added technical amendments |
| 0.3 | 2026-01-17 | Overlap analysis: Clarified scope as internal tooling vs product features, added Out of Scope section, updated skip detection taxonomy |
| 1.0 | 2026-01-17 | Council Review Round 2: APPROVED. Added exit codes, orphan detection, CLI entry point, implementation mandates |
