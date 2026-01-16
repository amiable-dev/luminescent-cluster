# MCP Server Requirements

Requirements for MCP server behavior, tools, and Python version safety.

**Primary ADRs**: ADR-001, ADR-003

---

## Version Guard Requirements

### REQ-MCP-001: Version Mismatch Exit Code
**Source**: ADR-001 Layer 3
**Status**: Active
**Priority**: Critical

The version guard MUST exit with code 78 (EX_CONFIG) when a Python version mismatch is detected between the current Python interpreter and the version stored in the `.python_version` marker file.

**Rationale**: Exit code 78 follows sysexits.h convention for configuration errors, enabling proper error handling by supervisors.

**Test Mapping**:
- `tests/test_version_guard.py::test_version_mismatch_exit_code`
- `tests/test_version_guard.py::test_version_mismatch_message`

---

### REQ-MCP-002: Version Marker Creation
**Source**: ADR-001 Layer 3
**Status**: Active
**Priority**: High

On fresh install (no existing Pixeltable database), the version guard MUST create a `.python_version` marker file in the Pixeltable directory containing the current Python major.minor version.

**Test Mapping**:
- `tests/test_version_guard.py::test_fresh_install_creates_marker`
- `tests/test_version_guard.py::test_marker_contains_version`

---

### REQ-MCP-003: Legacy Database Detection
**Source**: ADR-001 Layer 3
**Status**: Active
**Priority**: Critical

When an existing Pixeltable database is detected but no `.python_version` marker exists (legacy database), the version guard MUST exit with code 65 (EX_DATAERR).

**Test Mapping**:
- `tests/test_version_guard.py::test_legacy_database_exit_code`

---

### REQ-MCP-004: Version Guard Before Import
**Source**: ADR-001 Layer 3
**Status**: Active
**Priority**: Critical

The version guard MUST execute BEFORE any Pixeltable imports to prevent segfaults from incompatible UDF deserialization.

**Test Mapping**:
- `tests/test_version_guard.py::test_guard_runs_before_import`

---

### REQ-MCP-005: Cross-Platform File Locking
**Source**: ADR-001 Layer 3
**Status**: Active
**Priority**: High

The version guard MUST use cross-platform file locking (fcntl on Unix, msvcrt on Windows) to prevent race conditions in parallel environments.

**Test Mapping**:
- `tests/test_version_guard.py::test_file_locking`
- `tests/test_version_guard.py::test_windows_fallback`

---

### REQ-MCP-006: PIXELTABLE_HOME Support
**Source**: ADR-001 Layer 3
**Status**: Active
**Priority**: Medium

The version guard MUST respect the `PIXELTABLE_HOME` environment variable for the Pixeltable directory location, defaulting to `~/.pixeltable`.

**Test Mapping**:
- `tests/test_version_guard.py::test_pixeltable_home_env`

---

### REQ-MCP-007: Patch Version Safety
**Source**: ADR-001 Layer 3
**Status**: Active
**Priority**: High

The version guard MUST allow patch version differences (e.g., 3.11.0 to 3.11.9) while blocking minor version differences (e.g., 3.11.x to 3.12.x).

**Test Mapping**:
- `tests/test_version_guard.py::test_patch_version_allowed`
- `tests/test_version_guard.py::test_minor_version_blocked`

---

### REQ-MCP-008: Successful Check Logging
**Source**: ADR-001 Layer 7
**Status**: Active
**Priority**: Low

The version guard SHOULD log successful version checks (not just failures) for observability and debugging.

**Test Mapping**:
- `tests/test_version_guard.py::test_successful_check_logged`

---

## Negative Obligations

### NEG-MCP-001: No Warning-Only Mode
**Source**: ADR-001 Layer 3
**Status**: Active
**Priority**: Critical

The version guard MUST NOT operate in warning-only mode for version mismatches. The silent segfault failure mode requires hard exit.

**Test Mapping**:
- `tests/test_version_guard.py::test_no_warning_only_mode`

---

### NEG-MCP-002: No Automatic Migration
**Source**: ADR-001 Layer 6
**Status**: Active
**Priority**: High

The version guard MUST NOT automatically migrate data on version mismatch. Migration requires explicit user action due to the risk of data loss.

**Test Mapping**:
- `tests/test_version_guard.py::test_no_auto_migration`
