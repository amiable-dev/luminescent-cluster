# Workflow Integration Requirements

Requirements for Temporal workflow integration and automation.

**Primary ADR**: ADR-002

---

## Workflow Orchestration

### REQ-WKF-001: Temporal Integration
**Source**: ADR-002 Decision
**Status**: Active
**Priority**: High

Workflow orchestration MUST use Temporal for durable workflows with:
- Deterministic replay
- Failure recovery
- State persistence

**Test Mapping**:
- `tests/test_workflow.py::test_temporal_integration`
- `tests/test_workflow.py::test_deterministic_replay`

---

### REQ-WKF-002: Checkpoint Serialization
**Source**: ADR-002 Implementation
**Status**: Active
**Priority**: High

Workflow checkpoints MUST be serializable to allow:
- State persistence
- Cross-session resume
- Debugging and replay

**Test Mapping**:
- `tests/test_workflow.py::test_checkpoint_serialization`
- `tests/test_workflow.py::test_checkpoint_restore`

---

### REQ-WKF-003: Activity Idempotency
**Source**: ADR-002 Implementation
**Status**: Active
**Priority**: High

Workflow activities MUST be idempotent to handle retries safely.

**Test Mapping**:
- `tests/test_workflow.py::test_activity_idempotency`

---

## Automated Ingestion

### REQ-WKF-010: Git Hook Triggers
**Source**: ADR-003 Risks
**Status**: Active
**Priority**: Medium

Memory ingestion SHOULD be triggered by git hooks to keep knowledge synchronized.

**Test Mapping**:
- `tests/test_workflow.py::test_git_hook_trigger`

---

### REQ-WKF-011: Async Extraction
**Source**: ADR-003 Phase 1
**Status**: Active
**Priority**: High

Memory extraction MUST run asynchronously after response to avoid blocking user interactions.

**Test Mapping**:
- `tests/memory/test_extraction.py::test_async_extraction`
- `tests/memory/test_extraction.py::test_non_blocking`

---

## Janitor Process

### REQ-WKF-020: Scheduled Consolidation
**Source**: ADR-003 Phase 1d
**Status**: Active
**Priority**: High

The janitor process MUST run as a scheduled job (nightly) for memory consolidation.

**Test Mapping**:
- `tests/memory/test_janitor.py::test_scheduled_execution`

---

### REQ-WKF-021: Expiration Cleanup
**Source**: ADR-003 Phase 1d
**Status**: Active
**Priority**: High

The janitor MUST clean up expired memories based on TTL.

**Test Mapping**:
- `tests/memory/test_janitor.py::test_expiration_cleanup`
- `tests/memory/test_janitor.py::test_ttl_enforcement`

---

## Negative Obligations

### NEG-WKF-001: No Synchronous Extraction
**Source**: ADR-003 Phase 1
**Status**: Active
**Priority**: High

Memory extraction MUST NOT run synchronously in the request path. LLM extraction kills latency.

**Test Mapping**:
- `tests/memory/test_extraction.py::test_no_sync_extraction`
