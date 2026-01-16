# Cross-ADR Integration Requirements

Requirements for cross-ADR integration and protocol consolidation.

**Primary ADR**: ADR-007

## Domain Definition

The INT (Integration) domain covers **cross-ADR flows requiring coordination between multiple systems**. This includes:

- Protocol consolidation across memory, chatbot, and extensions
- Phase alignment and dependency management
- Tier constraint enforcement across subsystems
- ADR cross-reference traceability

INT requirements are distinct from single-system requirements in that they test the **boundaries and contracts** between systems, not the systems themselves.

---

## Protocol Consolidation

### REQ-INT-001: Unified ContextStore
**Source**: ADR-007 Protocol Consolidation
**Status**: Active
**Priority**: High

ContextStore protocol MUST be the unified interface for all context storage across memory, chatbot, and extensions.

**Test Mapping**:
- `tests/test_integration.py::test_context_store_protocol`
- `tests/test_integration.py::test_unified_interface`

---

### REQ-INT-002: Protocol Versioning
**Source**: ADR-007 Protocol Consolidation
**Status**: Active
**Priority**: High

All protocols MUST be versioned to support backward compatibility during upgrades.

**Test Mapping**:
- `tests/test_integration.py::test_protocol_versioning`

---

## Phase Alignment

### REQ-INT-010: Phase Dependencies
**Source**: ADR-007 Phase Alignment
**Status**: Active
**Priority**: High

Implementation phases MUST respect dependencies:
- Phase 1 requires Phase 0 foundations
- Phase 2 requires Phase 1 memory
- Phase 3 requires Phase 2 context engineering

**Test Mapping**:
- `tests/test_integration.py::test_phase_dependencies`

---

### REQ-INT-011: Cross-Phase Testing
**Source**: ADR-007 Integration Testing
**Status**: Active
**Priority**: High

Integration tests MUST validate cross-phase functionality:
- Memory → Chatbot integration
- Extensions → Memory integration
- Workflow → Memory integration

**Test Mapping**:
- `tests/test_mcp_extension_integration.py::test_memory_chatbot`
- `tests/test_mcp_extension_integration.py::test_extensions_memory`

---

## Tier Constraints

### REQ-INT-020: Tier Feature Gates
**Source**: ADR-004, ADR-007
**Status**: Active
**Priority**: High

Features MUST respect tier constraints:
- Free: Local storage, single user
- Team: Cloud storage, multi-user
- Enterprise: Configurable retention, legal hold

**Test Mapping**:
- `tests/test_integration.py::test_tier_gates`

---

### REQ-INT-021: Retention Policies
**Source**: ADR-007 Section 4
**Status**: Active
**Priority**: High

Retention policies MUST be tier-specific:
- Free (OSS): User responsibility
- Team (Cloud): Auto-delete on workspace exit (GDPR Article 17)
- Enterprise: Configurable with legal hold

**Test Mapping**:
- `tests/test_integration.py::test_retention_policies`

---

## ADR Cross-References

### REQ-INT-030: ADR Traceability
**Source**: ADR-007 Related Decisions
**Status**: Active
**Priority**: Medium

All ADRs MUST maintain cross-references to related decisions for traceability.

**Test Mapping**:
- Manual verification via reconciliation

---

### REQ-INT-031: Implementation Tracker
**Source**: ADR-003 Implementation Tracker
**Status**: Active
**Priority**: Medium

ADR-003 MUST maintain an up-to-date implementation tracker with phase status and test counts.

**Test Mapping**:
- Manual verification via reconciliation

---

## Negative Obligations

### NEG-INT-001: No Circular Dependencies
**Source**: ADR-007 Architecture
**Status**: Active
**Priority**: High

Modules MUST NOT have circular dependencies. Extensions → Memory is allowed; Memory → Extensions is forbidden.

**Test Mapping**:
- `tests/test_integration.py::test_no_circular_deps`

---

### NEG-INT-002: No Phase Skipping
**Source**: ADR-007 Phase Alignment
**Status**: Active
**Priority**: High

Implementations MUST NOT skip phases. Phase 3 features cannot be implemented before Phase 2 completion.

**Test Mapping**:
- `tests/test_integration.py::test_no_phase_skip`
