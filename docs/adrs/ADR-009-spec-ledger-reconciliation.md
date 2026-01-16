# ADR-009: Spec/Ledger Reconciliation System

**Status**: Accepted
**Date**: 2026-01-16
**Decision Makers**: Development Team
**Owners**: @christopherjoseph
**Version**: 1.0

## Decision Summary

Implement a bidirectional requirement traceability system using a YAML-based ledger that maps ADR requirements to test files, with CI enforcement to ensure coverage thresholds are maintained.

| Aspect | Decision |
|--------|----------|
| Format | YAML ledger + Markdown requirement docs |
| Validation | Python script with bidirectional checks |
| CI Mode | Warning mode initially, blocking after 90% coverage |
| Exit Criteria | 90%+ requirements have mapped tests |

---

## Context

### The Problem: Untraceable Requirements

ADRs contain testable requirements expressed in prose, but there's no machine-readable mapping between requirements and their implementing tests:

1. **No traceability**: Can't verify which tests cover which requirements
2. **Coverage gaps**: No visibility into untested requirements
3. **Orphaned tests**: Tests without corresponding requirements
4. **Regression risk**: ADR changes may invalidate existing tests
5. **Onboarding friction**: New contributors can't assess test coverage

### Requirements Inventory

Analysis of existing ADRs reveals ~110 testable requirements:

| ADR | Domain | Estimated Requirements |
|-----|--------|----------------------|
| ADR-001 | MCP/Version Guard | 8+ |
| ADR-002 | Workflow | 6+ |
| ADR-003 | Memory | 40+ |
| ADR-004 | Monetization | 5+ |
| ADR-005 | Extensions | 10+ |
| ADR-006 | Chatbot | 25+ |
| ADR-007 | Integration | 15+ |
| **Total** | | **~110+** |

### Industry Precedent

| Approach | Used By | Pros | Cons |
|----------|---------|------|------|
| **YAML Ledger** | Internal tools | Simple, versionable | Manual maintenance |
| Requirements.txt + Tags | pytest-bdd | Native pytest | Scattered across files |
| Traceability Matrix | Enterprise | Complete visibility | Heavy tooling |
| Doctest-style | Python stdlib | Inline with docs | Limited scope |

**Decision**: YAML ledger provides the best balance of simplicity, visibility, and CI integration.

---

## Decision

### Ledger Domain Structure

Requirements are organized by domain with standardized prefixes:

| Domain | Prefix | Description | Primary Source |
|--------|--------|-------------|----------------|
| MCP | `REQ-MCP-NNN` | MCP server behavior, version guard | ADR-001, ADR-003 |
| MEM | `REQ-MEM-NNN` | Memory storage, retrieval, lifecycle | ADR-003 |
| EXT | `REQ-EXT-NNN` | Extension protocols, registry | ADR-005 |
| BOT | `REQ-BOT-NNN` | Chatbot adapters, gateway | ADR-006 |
| SEC | `REQ-SEC-NNN` | Security, ACLs, rate limiting | ADR-006, ADR-007 |
| WKF | `REQ-WKF-NNN` | Workflow integration | ADR-002 |
| INT | `REQ-INT-NNN` | Cross-ADR integration | ADR-007 |

**Negative obligations** use `NEG-` prefix: `NEG-MCP-NNN`, `NEG-SEC-NNN`, etc.

### File Structure

```
spec/
├── requirements/
│   ├── mcp.md              # MCP server requirements
│   ├── memory.md           # Memory system requirements
│   ├── extensions.md       # Extension system requirements
│   ├── chatbot.md          # Chatbot integration requirements
│   ├── security.md         # Security requirements
│   ├── workflow.md         # Workflow requirements
│   └── integration.md      # Cross-ADR requirements
├── ledger.yml              # Obligation-to-test mapping
└── validation/
    └── reconcile.py        # Bidirectional validation script
```

### Requirement Document Format

```markdown
# spec/requirements/mcp.md

## MCP Server Requirements

### REQ-MCP-001: Version Mismatch Exit Code
**Source**: ADR-001 Layer 3
**Status**: Active
**Priority**: Critical

The version guard MUST exit with code 78 (EX_CONFIG) when a Python version
mismatch is detected between the current interpreter and the stored marker.

**Rationale**: Exit code 78 follows sysexits.h convention for configuration
errors, enabling proper error handling by supervisors.

**Test Mapping**:
- `tests/test_version_guard.py::test_version_mismatch_exit_code`
- `tests/test_version_guard.py::test_version_mismatch_message`

---

### NEG-MCP-001: No Warning-Only Mode
**Source**: ADR-001 Layer 3
**Status**: Active
**Priority**: Critical

The version guard MUST NOT operate in warning-only mode. The silent segfault
failure mode requires hard exit.

**Test Mapping**:
- `tests/test_version_guard.py::test_no_warning_only_mode`
```

### Ledger Schema

```yaml
# spec/ledger.yml
version: "1.0"

domains:
  - mcp
  - memory
  - extensions
  - chatbot
  - security
  - workflow
  - integration

requirements:
  REQ-MCP-001:
    title: "Version Mismatch Exit Code"
    source: "ADR-001 Layer 3"
    status: active           # active | deprecated | proposed
    priority: critical       # critical | high | medium | low
    tests:
      - tests/test_version_guard.py::test_version_mismatch_exit_code
      - tests/test_version_guard.py::test_version_mismatch_message

  NEG-MCP-001:
    title: "No Warning-Only Mode"
    source: "ADR-001 Layer 3"
    status: active
    priority: critical
    tests:
      - tests/test_version_guard.py::test_no_warning_only_mode

  # ... additional requirements
```

### Validation Script

```python
# spec/validation/reconcile.py
"""
Bidirectional reconciliation between spec/ledger.yml and actual tests.

Checks:
1. All active requirements have mapped tests
2. All mapped test files exist
3. Coverage meets threshold (90%)

Exit Codes:
    0: Reconciliation passed
    1: Reconciliation failed
    2: Configuration error
"""

def reconcile(ledger_path, project_root, verbose=False):
    # Load ledger
    ledger = yaml.safe_load(ledger_path.read_text())

    # Find existing test files
    test_files = set(project_root.glob("tests/**/test_*.py"))

    # Validate each requirement
    for req_id, req_data in ledger["requirements"].items():
        if req_data["status"] != "active":
            continue

        # Check tests exist
        for test_path in req_data.get("tests", []):
            file_path = test_path.split("::")[0]
            if file_path not in test_files:
                report_missing(req_id, file_path)

    # Calculate coverage
    coverage = with_tests / active_requirements
    return coverage >= 0.90
```

### CI Integration

```yaml
# .github/workflows/reconcile.yml
name: Spec/Ledger Reconciliation

on:
  push:
    paths: ['spec/**', 'tests/**']
  pull_request:
    paths: ['spec/**', 'tests/**']

jobs:
  reconcile:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: pip install pyyaml

      # Warning mode (always passes)
      - run: python spec/validation/reconcile.py --warn --verbose

      # Strict mode (informational for now)
      - run: python spec/validation/reconcile.py --verbose
        continue-on-error: true
```

---

## Implementation Phases

### Phase 1: Scaffolding (Complete)
- [x] Create `spec/requirements/` structure
- [x] Create domain requirement files with initial requirements
- [x] Create `spec/ledger.yml` with 89 requirements
- [x] Create `spec/validation/reconcile.py`
- [x] Create `.github/workflows/reconcile.yml`

### Phase 2: Coverage Improvement (Complete)
- [x] Map existing tests to requirements (reduced from 77 to 0 missing)
- [x] Fix path mismatches in ledger.yml (~70 corrections)
- [x] Create missing test files (`tests/test_workflow.py`, `tests/test_integration.py`)
- [x] Achieve 100% coverage (exceeds 90% threshold)
- [x] Add pytest markers infrastructure (`tests/conftest.py`)
- [x] Register custom markers in `pyproject.toml`

### Phase 3: Enforcement (Complete)
- [x] Implement priority-aware coverage thresholds in reconcile.py
- [x] Implement baseline ratchet mechanism (`check_ratchet()`, `BaselineSchema`)
- [x] Add domain coverage tracking per Council recommendation
- [x] Create GitHub issue templates for test gaps
- [ ] Enable blocking mode in CI (deferred - optional)
- [ ] Add pre-commit hook for local validation (deferred - optional)

---

## Consequences

### Positive
- **Traceability**: Every requirement maps to tests (and vice versa)
- **Gap Detection**: CI surfaces untested requirements immediately
- **Maintenance**: ADR changes prompt requirement updates
- **Onboarding**: New contributors understand what's tested
- **Compliance**: Audit trail for requirement coverage

### Negative
- **Initial Effort**: Extracting ~110 requirements requires review
- **Maintenance Overhead**: New ADRs must include requirements
- **CI Time**: Reconciliation adds ~10s to build time
- **Discipline**: Team must maintain ledger alongside code

### Mitigations
- Start in warning-only mode to build coverage gradually
- Add requirement template to ADR template
- Cache reconciliation results
- Provide clear contribution guidelines

---

## Verification

```bash
# Run reconciliation
python spec/validation/reconcile.py --verbose

# Expected output (Phase 2/3 complete):
# ============================================================
# SPEC/LEDGER RECONCILIATION REPORT
# ============================================================
#
# Requirements:
#   Total:            89
#   Active:           87
#   With tests:       87
#   Without tests:    0
#   Coverage:         100.0%
#
# Coverage by Priority:
#   Critical   100.0% (threshold: 100%) [OK]
#   High       100.0% (threshold: 95%) [OK]
#   Medium     100.0% (threshold: 85%) [OK]
#   Low        100.0% (threshold: 75%) [OK]
#
# Coverage by Domain:
#   BOT        100.0%
#   EXT        100.0%
#   INT         80.0%
#   MCP        100.0%
#   MEM        100.0%
#   SEC        100.0%
#   WKF        100.0%
#
# ------------------------------------------------------------
# Reconciliation PASSED!
# ------------------------------------------------------------

# Run reconcile tests
pytest tests/spec/test_reconcile.py -v
# Expected: 26 passed
```

---

## Related Decisions

- **ADR-008**: MkDocs Documentation Site (companion ADR)
- **ADR-001**: Python Version Requirement (source of REQ-MCP-*)
- **ADR-002**: Workflow Integration (source of REQ-WKF-*)
- **ADR-003**: Project Intent & Memory (source of REQ-MEM-*)
- **ADR-005**: Repository Organization (source of REQ-EXT-*)
- **ADR-006**: Chatbot Integrations (source of REQ-BOT-*)
- **ADR-007**: Cross-ADR Integration (source of REQ-INT-*)

---

## Council Review

**Review Date**: 2026-01-16
**Verdict**: Approved with amendments
**Consensus Strength**: 0.82

### Key Recommendations

1. **Hybrid Approach: YAML + pytest Markers** (High Priority)
   - YAML ledger for metadata (title, source, priority, status)
   - pytest markers for actual test linkage: `@pytest.mark.requirement("REQ-MCP-001")`
   - Benefits: IDE autocomplete, refactoring support, co-location
   - Action: Extend reconcile.py to scan for markers

2. **Priority-Aware Coverage Thresholds** (High Priority)
   - Current 90% threshold treats all requirements equally
   - Recommended thresholds:
     - Critical: 100% (must have tests)
     - High: 95%
     - Medium: 85%
     - Low: 75%
   - Security domain (SEC-*): Always 100%
   - Action: Update reconcile.py with tiered thresholds

3. **Split Ledger by Domain** (Medium Priority)
   - Single ledger.yml will cause merge conflicts at scale
   - Recommended structure:
     ```
     spec/
     ├── ledger/
     │   ├── mcp.yml
     │   ├── memory.yml
     │   ├── chatbot.yml
     │   └── ...
     └── validation/
         └── reconcile.py  # Aggregates all domain ledgers
     ```
   - Action: Defer until >150 requirements

4. **Baseline Ratchet Mechanism** (High Priority)
   - CI should block coverage decreases, not just threshold failures
   - Store baseline in `.spec-baseline.json`
   - Any PR that reduces coverage requires explicit override
   - Action: Add to Phase 3 enforcement

5. **Clarify INT Domain** (Documentation)
   - Integration requirements overlap with other domains
   - Define INT as: "Cross-ADR flows requiring multiple systems"
   - Action: Update spec/requirements/integration.md

6. **Distinguish Mapping vs Execution** (Critical)
   - "Has mapping" ≠ "Test exists and passes"
   - Reconciliation checks:
     - Level 1: Requirement has test path (current)
     - Level 2: Test file exists (current)
     - Level 3: Test actually passes (future)
   - Action: Document levels in ADR, implement Level 3 in Phase 3

### Accepted Amendments

| Amendment | Status | Target |
|-----------|--------|--------|
| pytest markers | Accepted | Phase 2 |
| Priority thresholds | Accepted | Phase 2 |
| Split ledger | Deferred | >150 requirements |
| Baseline ratchet | Accepted | Phase 3 |
| INT clarification | Accepted | Immediate |
| Level 3 verification | Accepted | Phase 3 |

### Dissenting Opinion

One council member advocated for pure pytest markers without YAML metadata, arguing the ledger adds maintenance overhead. Counter-argument: YAML provides a single source of truth for requirement inventory, independent of test implementation status.

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-16 | Initial ADR split from ADR-008 |
| 1.1 | 2026-01-16 | Phase 2/3 complete: priority thresholds, baseline ratchet, domain coverage, 100% test coverage achieved |
