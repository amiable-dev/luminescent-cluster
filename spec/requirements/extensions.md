# Extension System Requirements

Requirements for extension protocols, registry, and OSS/Paid separation.

**Primary ADR**: ADR-005

---

## Extension Registry

### REQ-EXT-001: Singleton Pattern
**Source**: ADR-005 Repository Structure
**Status**: Active
**Priority**: High

The ExtensionRegistry MUST be a singleton, accessible via `ExtensionRegistry.get()`.

**Test Mapping**:
- `tests/test_extensions.py::test_singleton_pattern`
- `tests/test_extensions.py::test_get_returns_same_instance`

---

### REQ-EXT-002: Protocol-Based Extensions
**Source**: ADR-005 Repository Structure
**Status**: Active
**Priority**: High

Extensions MUST implement Python Protocols (duck typing), not require inheritance.

**Test Mapping**:
- `tests/test_extensions.py::test_protocol_compliance`
- `tests/test_extensions.py::test_duck_typing`

---

### REQ-EXT-003: Graceful Degradation
**Source**: ADR-005 Feature Separation
**Status**: Active
**Priority**: High

When extensions are not registered (OSS mode), the system MUST function with graceful degradation, not errors.

**Test Mapping**:
- `tests/test_extensions.py::test_graceful_degradation`
- `tests/test_extensions.py::test_oss_mode_functional`

---

### REQ-EXT-004: Mode Detection
**Source**: ADR-005 Repository Structure
**Status**: Active
**Priority**: Medium

The registry MUST expose mode detection via `get_status()` returning `{'mode': 'oss'}` or `{'mode': 'cloud'}`.

**Test Mapping**:
- `tests/test_extensions.py::test_mode_detection`
- `tests/test_extensions.py::test_oss_status`
- `tests/test_extensions.py::test_cloud_status`

---

## Protocol Definitions

### REQ-EXT-010: TenantProvider Protocol
**Source**: ADR-005 Repository Structure
**Status**: Active
**Priority**: High

TenantProvider MUST define:
- `get_tenant_id(ctx: dict) -> str`
- `get_tenant_filter(tenant_id: str) -> dict`
- `validate_tenant_access(tenant_id, user_id, resource) -> bool`

**Test Mapping**:
- `tests/test_extensions.py::test_tenant_provider_protocol`

---

### REQ-EXT-011: UsageTracker Protocol
**Source**: ADR-005 Repository Structure
**Status**: Active
**Priority**: High

UsageTracker MUST define methods for metering and quota management.

**Test Mapping**:
- `tests/test_extensions.py::test_usage_tracker_protocol`

---

### REQ-EXT-012: AuditLogger Protocol
**Source**: ADR-005 Repository Structure
**Status**: Active
**Priority**: High

AuditLogger MUST define methods for compliance audit logging.

**Test Mapping**:
- `tests/test_extensions.py::test_audit_logger_protocol`

---

### REQ-EXT-013: MemoryProvider Export
**Source**: ADR-005 Dual-Repo Compliance
**Status**: Active
**Priority**: High

`MemoryProvider`, `ResponseFilter`, and `MEMORY_PROVIDER_VERSION` MUST be exported from `src.extensions`.

**Test Mapping**:
- `tests/test_extensions.py::test_memory_provider_export`
- `tests/test_extensions.py::test_response_filter_export`
- `tests/test_extensions.py::test_version_export`

---

## OSS vs Paid Separation

### REQ-EXT-020: Free Tier Features
**Source**: ADR-005 Feature Separation
**Status**: Active
**Priority**: High

Free tier MUST include:
- Local Pixeltable storage
- Read-only GitHub/GitLab via PAT
- Single user mode
- All platform adapters

**Test Mapping**:
- `tests/test_extensions.py::test_free_tier_features`

---

### REQ-EXT-021: Paid Tier Gates
**Source**: ADR-005 Feature Separation
**Status**: Active
**Priority**: High

Paid-only features MUST be gated by extension presence:
- Multi-tenancy (TenantProvider)
- Usage metering (UsageTracker)
- Centralized audit (AuditLogger)

**Test Mapping**:
- `tests/test_extensions.py::test_paid_tier_gates`

---

## Negative Obligations

### NEG-EXT-001: No Auth in Internal APIs
**Source**: ADR-003 Phase 4.2 Trust Model
**Status**: Active
**Priority**: High

Internal registry APIs MUST NOT implement authentication. Authentication is the responsibility of the MCP server / CLI layer.

**Test Mapping**:
- `tests/test_extensions.py::test_no_internal_auth`

---

### NEG-EXT-002: No Proprietary Code in OSS
**Source**: ADR-005 Repository Organization
**Status**: Active
**Priority**: Critical

The public repository MUST NOT contain proprietary cloud implementations.

**Test Mapping**:
- Manual code review
