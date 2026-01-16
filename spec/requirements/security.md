# Security Requirements

Requirements for security, ACLs, rate limiting, and threat mitigations.

**Primary ADRs**: ADR-006, ADR-007

---

## Memory Security

### REQ-SEC-001: User Isolation
**Source**: ADR-003 Phase 1
**Status**: Active
**Priority**: Critical

Memory retrieval MUST enforce user-level isolation. Users MUST NOT be able to access memories belonging to other users.

**Test Mapping**:
- `tests/memory/test_isolation.py::test_user_isolation`
- `tests/memory/test_isolation.py::test_cross_user_blocked`

---

### REQ-SEC-002: Scope Hierarchy
**Source**: ADR-003 Phase 4.2
**Status**: Active
**Priority**: High

Memory scope MUST follow hierarchy: user > project > global. Agents cannot read above their max scope.

**Test Mapping**:
- `tests/memory/test_maas.py::test_scope_hierarchy`
- `tests/memory/test_maas.py::test_scope_enforcement`

---

### REQ-SEC-003: Capacity Limits
**Source**: ADR-003 Phase 4.2
**Status**: Active
**Priority**: High

MaaS registries MUST enforce capacity limits to prevent DoS:
- RegistryCapacityError
- PoolCapacityError
- HandoffCapacityError

**Test Mapping**:
- `tests/memory/test_maas.py::test_registry_capacity`
- `tests/memory/test_maas.py::test_pool_capacity`
- `tests/memory/test_maas.py::test_handoff_capacity`

---

### REQ-SEC-004: Audit Logging
**Source**: ADR-003 Phase 4.2
**Status**: Active
**Priority**: High

All MaaS operations MUST be logged via MaaSAuditLogger for forensic analysis.

**Test Mapping**:
- `tests/memory/test_maas.py::test_audit_logging`
- `tests/memory/test_maas.py::test_audit_completeness`

---

### REQ-SEC-005: ID Entropy
**Source**: ADR-003 Phase 4.2
**Status**: Active
**Priority**: High

All identifiers (agent IDs, pool IDs, handoff IDs) MUST use 128-bit UUIDs to prevent ID guessing attacks.

**Test Mapping**:
- `tests/memory/test_maas.py::test_id_entropy`

---

### REQ-SEC-006: Defensive Copies
**Source**: ADR-003 Phase 4.2
**Status**: Active
**Priority**: High

All MaaS API inputs/outputs MUST be copied to prevent state mutation attacks.

**Test Mapping**:
- `tests/memory/test_maas.py::test_defensive_copies`

---

## Ingestion Security

### REQ-SEC-010: Citation Detection
**Source**: ADR-003 Phase 2
**Status**: Active
**Priority**: High

Ingestion MUST detect citations (ADR references, commit hashes, URLs) to determine provenance tier.

**Test Mapping**:
- `tests/memory/test_ingestion.py::test_citation_detection`
- `tests/memory/test_ingestion.py::test_adr_reference`
- `tests/memory/test_ingestion.py::test_commit_hash`

---

### REQ-SEC-011: Hedge Word Detection
**Source**: ADR-003 Phase 2
**Status**: Active
**Priority**: High

Ingestion MUST detect speculative language ("maybe", "might", "could be", "I don't know") and block Tier 3 content.

**Test Mapping**:
- `tests/memory/test_ingestion.py::test_hedge_detection`
- `tests/memory/test_ingestion.py::test_speculation_blocking`

---

### REQ-SEC-012: Deduplication Safety
**Source**: ADR-003 Phase 2
**Status**: Active
**Priority**: High

Deduplication failure MUST raise DedupCheckError and flag for review, not fail open.

**Test Mapping**:
- `tests/memory/test_ingestion.py::test_dedup_failure_handling`
- `tests/memory/test_ingestion.py::test_no_fail_open`

---

## Provenance Security

### REQ-SEC-020: Bounded Storage
**Source**: ADR-003 Phase 2
**Status**: Active
**Priority**: High

ProvenanceService MUST use bounded LRU storage to prevent memory exhaustion.

**Test Mapping**:
- `tests/memory/test_provenance.py::test_bounded_storage`
- `tests/memory/test_provenance.py::test_lru_eviction`

---

### REQ-SEC-021: Input Validation
**Source**: ADR-003 Phase 2
**Status**: Active
**Priority**: High

ProvenanceService MUST validate:
- String identifier length limits
- Metadata bounds
- Recursive nested structure depth
- UTF-8 byte size
- Score range (0.0-1.0)

**Test Mapping**:
- `tests/memory/test_provenance.py::test_input_validation`
- `tests/memory/test_provenance.py::test_depth_limit`
- `tests/memory/test_provenance.py::test_score_range`

---

### REQ-SEC-022: TOCTOU Prevention
**Source**: ADR-003 Phase 2
**Status**: Active
**Priority**: High

ProvenanceService MUST use deep copy to prevent time-of-check-time-of-use attacks.

**Test Mapping**:
- `tests/memory/test_provenance.py::test_toctou_prevention`
- `tests/memory/test_provenance.py::test_deep_copy`

---

## Chatbot Security

### REQ-SEC-030: Sensitive Data Filtering
**Source**: ADR-006 Access Control
**Status**: Active
**Priority**: High

Chatbot responses in public channels MUST filter sensitive patterns (passwords, API keys, credentials).

**Test Mapping**:
- `tests/chatbot/test_access_control.py::test_sensitive_filtering`

---

### REQ-SEC-031: Channel Authorization
**Source**: ADR-006 Access Control
**Status**: Active
**Priority**: High

Chatbot MUST enforce channel allow/block lists when ConfigurableAccessControlPolicy is active.

**Test Mapping**:
- `tests/chatbot/test_access_control.py::test_channel_authorization`

---

## Negative Obligations

### NEG-SEC-001: No Secret Storage
**Source**: ADR-003 Non-Goals
**Status**: Active
**Priority**: Critical

The memory system MUST NOT store PII or secrets. Sensitive data MUST be excluded by policy.

**Test Mapping**:
- `tests/memory/test_ingestion.py::test_secret_exclusion`

---

### NEG-SEC-002: No Cross-Tenant Access
**Source**: ADR-005 Multi-tenancy
**Status**: Active
**Priority**: Critical

When TenantProvider is active, cross-tenant data access MUST be impossible.

**Test Mapping**:
- `tests/test_extensions.py::test_tenant_isolation`

---

### NEG-SEC-003: No Review Queue Cross-Access
**Source**: ADR-003 Phase 2
**Status**: Active
**Priority**: Critical

Users MUST NOT be able to access other users' review queue items, even with known IDs.

**Test Mapping**:
- `tests/memory/test_ingestion.py::test_review_queue_isolation`
