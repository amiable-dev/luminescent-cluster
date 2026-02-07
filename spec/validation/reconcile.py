#!/usr/bin/env python3
"""
Spec/Ledger Reconciliation Script

Bidirectional validation between spec/ledger.yml and actual test files.

Exit Codes:
    0: All requirements have mapped tests, all mapped tests exist
    1: Reconciliation failures found
    2: Configuration/parsing error (or warning-only issues in strict mode)

Usage:
    python spec/validation/reconcile.py             # Run full reconciliation
    python spec/validation/reconcile.py --warn      # Run in warning mode (always exit 0)
    python spec/validation/reconcile.py --verbose   # Show detailed output
    python spec/validation/reconcile.py --update-baseline  # Update baseline after improvements
    python spec/validation/reconcile.py --check-skips      # Check for skipped tests
    python spec/validation/reconcile.py --check-orphans    # Check for orphan tests

See ADR-009 for the reconciliation system design.
See ADR-010 for the validation system enhancements.
"""

import argparse
import ast
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

# =============================================================================
# Schema Validation Constants (ADR-010 Layer 1)
# =============================================================================

VALID_STATUS = {"active", "deprecated", "proposed", "manual"}
VALID_PRIORITY = {"critical", "high", "medium", "low"}
REQUIRED_FIELDS = {"title", "source", "status", "priority"}

# =============================================================================
# Priority Thresholds (ADR-009 Phase 2/3)
# =============================================================================

PRIORITY_THRESHOLDS: dict[str, float] = {
    "critical": 100.0,  # 100% coverage required
    "high": 95.0,  # 95% coverage required
    "medium": 85.0,  # 85% coverage required
    "low": 75.0,  # 75% coverage required
}

# =============================================================================
# Skip Detection Taxonomy (ADR-010 Layer 3)
# =============================================================================

# Tiered skip policy per ADR-010
# - @pytest.skip (unconditional): Warning - indicates potential rot
# - @pytest.skipif (conditional): Info - legitimate platform logic
# - @pytest.mark.xfail: Info - known failures being tracked
SKIP_SEVERITY = {
    "unconditional": "warning",  # @pytest.skip without condition
    "conditional": "info",  # @pytest.skipif
    "xfail": "info",  # @pytest.mark.xfail
}


def get_effective_priority(req_id: str, declared_priority: str) -> str:
    """Get effective priority, upgrading security to critical.

    SEC-* requirements always use critical threshold regardless of
    declared priority.

    Args:
        req_id: Requirement ID (e.g., REQ-SEC-001)
        declared_priority: Priority from ledger.yml

    Returns:
        Effective priority (critical for SEC-*, otherwise declared)
    """
    # Extract domain from requirement ID
    domain = extract_domain(req_id)

    # Security domain always uses critical threshold
    if domain == "SEC":
        return "critical"

    return declared_priority


def extract_domain(req_id: str) -> str:
    """Extract domain from requirement ID.

    Args:
        req_id: Requirement ID (e.g., REQ-MCP-001, NEG-SEC-002)

    Returns:
        Domain code (e.g., MCP, SEC, MEM)
    """
    # Pattern: (REQ|NEG)-DOMAIN-NNN
    match = re.match(r"(?:REQ|NEG)-([A-Z]+)-\d+", req_id)
    if match:
        return match.group(1)
    return "UNKNOWN"


# =============================================================================
# Schema Validation (ADR-010 Layer 1)
# =============================================================================


@dataclass
class SchemaValidationResult:
    """Result of schema validation."""

    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_requirement_schema(req_id: str, req_data: dict[str, Any]) -> SchemaValidationResult:
    """Validate a single requirement against the schema.

    Args:
        req_id: Requirement ID (e.g., REQ-MCP-001)
        req_data: Requirement data from ledger

    Returns:
        SchemaValidationResult with errors/warnings
    """
    result = SchemaValidationResult()

    if not isinstance(req_data, dict):
        result.valid = False
        result.errors.append(f"{req_id}: Invalid requirement format (expected dict)")
        return result

    # Check required fields
    for field_name in REQUIRED_FIELDS:
        if field_name not in req_data:
            result.valid = False
            result.errors.append(f"{req_id}: Missing required field '{field_name}'")

    # Validate status
    status = req_data.get("status")
    if status and status not in VALID_STATUS:
        result.valid = False
        result.errors.append(
            f"{req_id}: Invalid status '{status}'. "
            f"Must be one of: {', '.join(sorted(VALID_STATUS))}"
        )

    # Validate priority
    priority = req_data.get("priority")
    if priority and priority not in VALID_PRIORITY:
        result.valid = False
        result.errors.append(
            f"{req_id}: Invalid priority '{priority}'. "
            f"Must be one of: {', '.join(sorted(VALID_PRIORITY))}"
        )

    # Validate tests is a list
    tests = req_data.get("tests")
    if tests is not None and not isinstance(tests, list):
        result.valid = False
        result.errors.append(f"{req_id}: 'tests' must be a list")

    # Validate requirement ID format
    if not re.match(r"(REQ|NEG)-[A-Z]+-\d+", req_id):
        result.warnings.append(
            f"{req_id}: Non-standard requirement ID format. Expected (REQ|NEG)-DOMAIN-NNN"
        )

    return result


def validate_ledger_schema(ledger: dict[str, Any]) -> SchemaValidationResult:
    """Validate the entire ledger against the schema.

    Args:
        ledger: Parsed ledger data

    Returns:
        SchemaValidationResult with all errors/warnings
    """
    result = SchemaValidationResult()

    # Check top-level structure
    if "requirements" not in ledger:
        result.valid = False
        result.errors.append("Ledger missing 'requirements' section")
        return result

    if "version" not in ledger:
        result.warnings.append("Ledger missing 'version' field")

    requirements = ledger.get("requirements", {})

    if not isinstance(requirements, dict):
        result.valid = False
        result.errors.append("'requirements' must be a dictionary")
        return result

    # Validate each requirement
    for req_id, req_data in requirements.items():
        req_result = validate_requirement_schema(req_id, req_data)
        if not req_result.valid:
            result.valid = False
        result.errors.extend(req_result.errors)
        result.warnings.extend(req_result.warnings)

    return result


# =============================================================================
# AST Test Introspection (ADR-010 Layer 1)
# =============================================================================


@dataclass
class TestIntrospectionResult:
    """Result of test file introspection."""

    functions: set[str] = field(default_factory=set)
    classes: dict[str, set[str]] = field(default_factory=dict)  # class -> methods
    errors: list[str] = field(default_factory=list)
    parametrized: set[str] = field(default_factory=set)  # functions with @parametrize


def introspect_test_file(file_path: Path) -> TestIntrospectionResult:
    """Parse a test file using AST to extract test functions and classes.

    Args:
        file_path: Path to the test file

    Returns:
        TestIntrospectionResult with discovered test symbols
    """
    result = TestIntrospectionResult()

    if not file_path.exists():
        result.errors.append(f"File not found: {file_path}")
        return result

    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError as e:
        result.errors.append(f"SyntaxError in {file_path}: {e}")
        return result
    except UnicodeDecodeError as e:
        result.errors.append(f"UnicodeDecodeError in {file_path}: {e}")
        return result

    for node in ast.walk(tree):
        # Handle both sync and async test functions
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
            "test_"
        ):
            # Top-level test function
            result.functions.add(node.name)
            # Check for parametrize decorator
            for decorator in node.decorator_list:
                if _is_parametrize_decorator(decorator):
                    result.parametrized.add(node.name)

        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            # Test class
            methods = set()
            for item in node.body:
                # Handle both sync and async test methods
                if isinstance(
                    item, (ast.FunctionDef, ast.AsyncFunctionDef)
                ) and item.name.startswith("test_"):
                    methods.add(item.name)
                    # Check for parametrize decorator
                    for decorator in item.decorator_list:
                        if _is_parametrize_decorator(decorator):
                            result.parametrized.add(f"{node.name}::{item.name}")
            if methods:
                result.classes[node.name] = methods

    return result


def _is_parametrize_decorator(decorator: ast.expr) -> bool:
    """Check if a decorator is @pytest.mark.parametrize."""
    # Handle @pytest.mark.parametrize
    if isinstance(decorator, ast.Call):
        func = decorator.func
        if isinstance(func, ast.Attribute):
            if func.attr == "parametrize":
                return True
    # Handle @pytest.mark.parametrize without call (rare)
    if isinstance(decorator, ast.Attribute):
        if decorator.attr == "parametrize":
            return True
    return False


def verify_test_reference(
    test_path: str, project_root: Path, introspection_cache: dict[str, TestIntrospectionResult]
) -> tuple[bool, str | None]:
    """Verify that a test reference (path::function) exists.

    Supports formats:
    - tests/test_foo.py (file only - just check existence)
    - tests/test_foo.py::test_bar (function)
    - tests/test_foo.py::TestClass::test_method (class method)

    Args:
        test_path: Test reference from ledger
        project_root: Root directory of the project
        introspection_cache: Cache of introspected test files

    Returns:
        Tuple of (exists, error_message)
    """
    # Parse the test path
    parts = test_path.split("::")

    file_path_str = parts[0]
    # Normalize path separators (handle Windows vs Linux)
    file_path_str = file_path_str.replace("\\", "/")
    file_path = project_root / file_path_str

    # Check file exists
    if not file_path.exists():
        return False, f"Test file not found: {file_path_str}"

    # If only file path, return True
    if len(parts) == 1:
        return True, None

    # Get or create introspection result
    cache_key = str(file_path)
    if cache_key not in introspection_cache:
        introspection_cache[cache_key] = introspect_test_file(file_path)

    introspection = introspection_cache[cache_key]

    # Handle parse errors
    if introspection.errors:
        # File has syntax errors - report as warning but don't fail
        return True, f"Warning: {introspection.errors[0]}"

    # Handle different reference formats
    if len(parts) == 2:
        # tests/test_foo.py::test_bar OR tests/test_foo.py::TestClass
        name = parts[1]
        if name in introspection.functions:
            return True, None
        if name in introspection.classes:
            return True, None
        # Check if it's a parametrized test (may have [param] suffix)
        base_name = name.split("[")[0]
        if base_name in introspection.functions:
            return True, None
        return False, f"Test function/class not found: {name} in {file_path_str}"

    elif len(parts) == 3:
        # tests/test_foo.py::TestClass::test_method
        class_name = parts[1]
        method_name = parts[2]
        if class_name in introspection.classes:
            if method_name in introspection.classes[class_name]:
                return True, None
            # Check for parametrized test
            base_method = method_name.split("[")[0]
            if base_method in introspection.classes[class_name]:
                return True, None
            return False, f"Method not found: {class_name}::{method_name} in {file_path_str}"
        return False, f"Test class not found: {class_name} in {file_path_str}"

    return False, f"Invalid test reference format: {test_path}"


# =============================================================================
# Skip Detection (ADR-010 Layer 3)
# =============================================================================


@dataclass
class SkipInfo:
    """Information about a skipped test."""

    test_path: str
    skip_type: str  # "unconditional", "conditional", "xfail"
    reason: str | None = None


def detect_skips_in_file(file_path: Path) -> list[SkipInfo]:
    """Detect skipped tests in a file using AST.

    Args:
        file_path: Path to the test file

    Returns:
        List of SkipInfo for skipped tests
    """
    skips = []

    if not file_path.exists():
        return skips

    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError):
        return skips

    file_str = str(file_path)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("test_"):
                continue

            for decorator in node.decorator_list:
                skip_info = _check_skip_decorator(decorator, file_str, node.name)
                if skip_info:
                    skips.append(skip_info)

    return skips


def _check_skip_decorator(decorator: ast.expr, file_path: str, func_name: str) -> SkipInfo | None:
    """Check if a decorator is a skip-related decorator.

    Args:
        decorator: AST decorator node
        file_path: Path to the file
        func_name: Name of the function

    Returns:
        SkipInfo if this is a skip decorator, None otherwise
    """
    test_path = f"{file_path}::{func_name}"

    # Handle @pytest.skip
    if isinstance(decorator, ast.Call):
        func = decorator.func
        # @pytest.skip(reason="...")
        if isinstance(func, ast.Attribute) and func.attr == "skip":
            reason = _extract_reason(decorator)
            return SkipInfo(test_path, "unconditional", reason)
        # @pytest.mark.skip(reason="...")
        if isinstance(func, ast.Attribute) and func.attr == "skip":
            if isinstance(func.value, ast.Attribute) and func.value.attr == "mark":
                reason = _extract_reason(decorator)
                return SkipInfo(test_path, "unconditional", reason)
        # @pytest.mark.skipif(condition, reason="...")
        if isinstance(func, ast.Attribute) and func.attr == "skipif":
            reason = _extract_reason(decorator)
            return SkipInfo(test_path, "conditional", reason)
        # @pytest.mark.xfail(reason="...")
        if isinstance(func, ast.Attribute) and func.attr == "xfail":
            reason = _extract_reason(decorator)
            return SkipInfo(test_path, "xfail", reason)

    # Handle @pytest.mark.skip (without call)
    if isinstance(decorator, ast.Attribute):
        if decorator.attr == "skip":
            return SkipInfo(test_path, "unconditional", None)
        if decorator.attr == "xfail":
            return SkipInfo(test_path, "xfail", None)

    return None


def _extract_reason(call: ast.Call) -> str | None:
    """Extract reason from a decorator call."""
    for keyword in call.keywords:
        if keyword.arg == "reason" and isinstance(keyword.value, ast.Constant):
            return str(keyword.value.value)
    return None


# =============================================================================
# Orphan Detection (ADR-010 Layer 3)
# =============================================================================


def find_orphan_requirement_markers(
    project_root: Path, ledger_requirements: set[str]
) -> list[tuple[str, str]]:
    """Find tests with @pytest.mark.requirement pointing to non-existent requirements.

    This is the inverse of ledger→test validation. It checks if tests reference
    requirements that don't exist in the ledger.

    Args:
        project_root: Root directory of the project
        ledger_requirements: Set of requirement IDs from ledger

    Returns:
        List of (test_path, orphan_requirement_id) tuples
    """
    orphans = []
    tests_dir = project_root / "tests"

    if not tests_dir.exists():
        return orphans

    for test_file in tests_dir.rglob("test_*.py"):
        try:
            source = test_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(test_file))
        except (SyntaxError, UnicodeDecodeError):
            continue

        relative_path = str(test_file.relative_to(project_root))

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for decorator in node.decorator_list:
                    req_ids = _extract_requirement_marker(decorator)
                    for req_id in req_ids:
                        if req_id not in ledger_requirements:
                            test_path = f"{relative_path}::{node.name}"
                            orphans.append((test_path, req_id))

    return orphans


def _extract_requirement_marker(decorator: ast.expr) -> list[str]:
    """Extract requirement IDs from @pytest.mark.requirement decorator.

    Args:
        decorator: AST decorator node

    Returns:
        List of requirement IDs (empty if not a requirement marker)
    """
    req_ids = []

    if isinstance(decorator, ast.Call):
        func = decorator.func
        # @pytest.mark.requirement("REQ-XXX-NNN")
        if isinstance(func, ast.Attribute) and func.attr == "requirement":
            for arg in decorator.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    req_ids.append(arg.value)

    return req_ids


# =============================================================================
# Baseline Schema (ADR-009 Phase 3)
# =============================================================================


@dataclass
class BaselineSchema:
    """Schema for .spec-baseline.json file."""

    version: str
    timestamp: str
    coverage: dict[str, Any]


def load_baseline(path: Path) -> BaselineSchema | None:
    """Load baseline from JSON file.

    Args:
        path: Path to .spec-baseline.json

    Returns:
        BaselineSchema if file exists, None otherwise
    """
    if not path.exists():
        return None

    try:
        with open(path) as f:
            data = json.load(f)
        return BaselineSchema(
            version=data.get("version", "1.0"),
            timestamp=data.get("timestamp", ""),
            coverage=data.get("coverage", {}),
        )
    except (json.JSONDecodeError, KeyError):
        return None


def save_baseline(baseline: BaselineSchema, path: Path) -> None:
    """Save baseline to JSON file.

    Args:
        baseline: BaselineSchema to save
        path: Path to .spec-baseline.json
    """
    data = {
        "version": baseline.version,
        "timestamp": baseline.timestamp,
        "coverage": baseline.coverage,
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def check_ratchet(baseline: dict[str, Any], current: dict[str, Any]) -> list[str]:
    """Check if current coverage meets baseline (ratchet).

    The baseline ratchet prevents coverage regression. Current coverage
    must be >= baseline for all metrics.

    Args:
        baseline: Baseline coverage data
        current: Current coverage data

    Returns:
        List of violation messages (empty if ratchet passes)
    """
    violations = []

    # Check overall coverage
    baseline_overall = baseline.get("overall", 0.0)
    current_overall = current.get("overall", 0.0)
    if current_overall < baseline_overall:
        violations.append(
            f"overall coverage decreased: {current_overall:.1f}% < {baseline_overall:.1f}%"
        )

    # Check priority coverage
    baseline_priority = baseline.get("by_priority", {})
    current_priority = current.get("by_priority", {})
    for priority, baseline_value in baseline_priority.items():
        current_value = current_priority.get(priority, 0.0)
        if current_value < baseline_value:
            violations.append(
                f"{priority} coverage decreased: {current_value:.1f}% < {baseline_value:.1f}%"
            )

    # Check domain coverage
    baseline_domain = baseline.get("by_domain", {})
    current_domain = current.get("by_domain", {})
    for domain, baseline_value in baseline_domain.items():
        current_value = current_domain.get(domain, 0.0)
        if current_value < baseline_value:
            violations.append(
                f"{domain} domain coverage decreased: {current_value:.1f}% < {baseline_value:.1f}%"
            )

    return violations


@dataclass
class ReconciliationResult:
    """Result of reconciliation check."""

    total_requirements: int = 0
    active_requirements: int = 0
    with_tests: int = 0
    without_tests: int = 0
    missing_test_files: list[str] = field(default_factory=list)
    missing_test_functions: list[str] = field(default_factory=list)  # ADR-010
    orphaned_tests: list[str] = field(default_factory=list)
    orphan_markers: list[tuple[str, str]] = field(default_factory=list)  # ADR-010
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)  # ADR-010
    coverage_by_priority: dict[str, float] = field(default_factory=dict)
    coverage_by_domain: dict[str, float] = field(default_factory=dict)
    ratchet_violations: list[str] = field(default_factory=list)
    schema_errors: list[str] = field(default_factory=list)  # ADR-010
    schema_warnings: list[str] = field(default_factory=list)  # ADR-010
    skipped_tests: list[SkipInfo] = field(default_factory=list)  # ADR-010
    syntax_errors: list[str] = field(default_factory=list)  # ADR-010

    @property
    def coverage(self) -> float:
        """Calculate test coverage percentage."""
        if self.active_requirements == 0:
            return 0.0
        return (self.with_tests / self.active_requirements) * 100

    @property
    def passed(self) -> bool:
        """Check if reconciliation passed.

        Checks:
        1. No errors
        2. No missing test files
        3. No missing test functions (ADR-010)
        4. No schema errors (ADR-010)
        5. Overall coverage >= 90%
        6. Priority-specific thresholds met (if coverage_by_priority is populated)
        7. No ratchet violations
        """
        # Basic checks
        if len(self.errors) > 0:
            return False
        if len(self.missing_test_files) > 0:
            return False
        if len(self.missing_test_functions) > 0:
            return False
        if len(self.schema_errors) > 0:
            return False
        if self.coverage < 90.0:
            return False
        if len(self.ratchet_violations) > 0:
            return False

        # Check priority-specific thresholds
        if self.coverage_by_priority:
            for priority, threshold in PRIORITY_THRESHOLDS.items():
                current = self.coverage_by_priority.get(priority, 100.0)
                if current < threshold:
                    return False

        return True

    @property
    def has_warnings(self) -> bool:
        """Check if there are any warnings (exit code 2 in strict mode).

        Warnings include:
        - Unconditionally skipped tests
        - Orphan test markers (tests referencing deleted requirements)
        - Schema warnings
        """
        if self.schema_warnings:
            return True
        if self.orphan_markers:
            return True
        # Count unconditional skips
        unconditional_skips = [s for s in self.skipped_tests if s.skip_type == "unconditional"]
        if unconditional_skips:
            return True
        return False


def load_ledger(ledger_path: Path) -> dict[str, Any]:
    """Load and parse the ledger YAML file."""
    if not ledger_path.exists():
        raise FileNotFoundError(f"Ledger file not found: {ledger_path}")

    with open(ledger_path) as f:
        return yaml.safe_load(f)


def find_test_files(project_root: Path) -> set[str]:
    """Find all test files in the project."""
    test_files = set()

    tests_dir = project_root / "tests"
    if tests_dir.exists():
        for test_file in tests_dir.rglob("test_*.py"):
            relative = test_file.relative_to(project_root)
            test_files.add(str(relative))

    return test_files


def parse_test_path(test_path: str) -> tuple[str, str | None]:
    """Parse a test path into file path and optional test name.

    Examples:
        "tests/test_foo.py::test_bar" -> ("tests/test_foo.py", "test_bar")
        "tests/test_foo.py" -> ("tests/test_foo.py", None)
    """
    if "::" in test_path:
        file_path, test_name = test_path.split("::", 1)
        return file_path, test_name
    return test_path, None


def reconcile(
    ledger_path: Path,
    project_root: Path,
    verbose: bool = False,
    check_skips: bool = False,
    check_orphans: bool = False,
    introspect_functions: bool = True,
) -> ReconciliationResult:
    """Run bidirectional reconciliation.

    Checks:
    1. Ledger schema validation (ADR-010)
    2. All requirements have mapped tests
    3. All mapped test files exist
    4. Test function/method existence via AST introspection (ADR-010)
    5. Coverage meets threshold (90%)
    6. Priority-specific thresholds met
    7. Domain-specific coverage tracked
    8. Skip detection (ADR-010, optional)
    9. Orphan marker detection (ADR-010, optional)
    """
    result = ReconciliationResult()

    # Load ledger
    try:
        ledger = load_ledger(ledger_path)
    except FileNotFoundError as e:
        result.errors.append(str(e))
        return result
    except yaml.YAMLError as e:
        result.errors.append(f"YAML parsing error: {e}")
        return result

    # Schema validation (ADR-010 Layer 1)
    if verbose:
        print("Running schema validation...")
    schema_result = validate_ledger_schema(ledger)
    result.schema_errors = schema_result.errors
    result.schema_warnings = schema_result.warnings
    if verbose and schema_result.errors:
        print(f"  Schema errors: {len(schema_result.errors)}")
    if verbose and schema_result.warnings:
        print(f"  Schema warnings: {len(schema_result.warnings)}")

    # Find existing test files
    existing_test_files = find_test_files(project_root)
    if verbose:
        print(f"Found {len(existing_test_files)} test files")

    # Get requirements
    requirements = ledger.get("requirements", {})
    result.total_requirements = len(requirements)

    # Track referenced test files
    referenced_test_files = set()

    # Cache for AST introspection (ADR-010)
    introspection_cache: dict[str, TestIntrospectionResult] = {}

    # Track coverage by priority and domain
    priority_counts: dict[str, dict[str, int]] = {
        "critical": {"total": 0, "covered": 0},
        "high": {"total": 0, "covered": 0},
        "medium": {"total": 0, "covered": 0},
        "low": {"total": 0, "covered": 0},
    }
    domain_counts: dict[str, dict[str, int]] = {}

    # Validate each requirement
    for req_id, req_data in requirements.items():
        if not isinstance(req_data, dict):
            result.errors.append(f"{req_id}: Invalid requirement format")
            continue

        status = req_data.get("status", "active")
        if status != "active":
            if verbose:
                print(f"  {req_id}: Skipped (status={status})")
            continue

        result.active_requirements += 1

        # Get priority and domain
        declared_priority = req_data.get("priority", "medium")
        effective_priority = get_effective_priority(req_id, declared_priority)
        domain = extract_domain(req_id)

        # Initialize domain counts if needed
        if domain not in domain_counts:
            domain_counts[domain] = {"total": 0, "covered": 0}

        # Increment totals
        if effective_priority in priority_counts:
            priority_counts[effective_priority]["total"] += 1
        domain_counts[domain]["total"] += 1

        tests = req_data.get("tests", [])

        if not tests:
            result.without_tests += 1
            if verbose:
                print(f"  {req_id}: No tests mapped")
            continue

        result.with_tests += 1

        # Increment covered counts
        if effective_priority in priority_counts:
            priority_counts[effective_priority]["covered"] += 1
        domain_counts[domain]["covered"] += 1

        # Verify test files and functions exist
        for test_path in tests:
            file_path, test_name = parse_test_path(test_path)
            # Normalize path separators
            file_path = file_path.replace("\\", "/")
            referenced_test_files.add(file_path)

            if file_path not in existing_test_files:
                result.missing_test_files.append(f"{req_id}: {file_path}")
                if verbose:
                    print(f"  {req_id}: Missing test file {file_path}")
            elif introspect_functions and "::" in test_path:
                # AST introspection for function/method existence (ADR-010)
                exists, error = verify_test_reference(test_path, project_root, introspection_cache)
                if not exists:
                    result.missing_test_functions.append(f"{req_id}: {test_path}")
                    if verbose:
                        print(f"  {req_id}: {error}")
                elif error and error.startswith("Warning:"):
                    # Syntax errors are reported as warnings
                    result.syntax_errors.append(error)

    # Calculate coverage by priority
    for priority, counts in priority_counts.items():
        if counts["total"] > 0:
            result.coverage_by_priority[priority] = (counts["covered"] / counts["total"]) * 100
        else:
            result.coverage_by_priority[priority] = 100.0  # No requirements = 100%

    # Calculate coverage by domain
    for domain, counts in domain_counts.items():
        if counts["total"] > 0:
            result.coverage_by_domain[domain] = (counts["covered"] / counts["total"]) * 100
        else:
            result.coverage_by_domain[domain] = 100.0

    # Find orphaned tests (test files not referenced by any requirement)
    # Note: This is informational, not a failure
    orphaned = existing_test_files - referenced_test_files
    result.orphaned_tests = list(sorted(orphaned))

    # Skip detection (ADR-010 Layer 3, optional)
    if check_skips:
        if verbose:
            print("Running skip detection...")
        for test_file in existing_test_files:
            full_path = project_root / test_file
            skips = detect_skips_in_file(full_path)
            result.skipped_tests.extend(skips)
        if verbose:
            print(f"  Found {len(result.skipped_tests)} skipped tests")

    # Orphan marker detection (ADR-010 Layer 3, optional)
    if check_orphans:
        if verbose:
            print("Running orphan marker detection...")
        ledger_req_ids = set(requirements.keys())
        result.orphan_markers = find_orphan_requirement_markers(project_root, ledger_req_ids)
        if verbose:
            print(f"  Found {len(result.orphan_markers)} orphan markers")

    return result


def print_report(result: ReconciliationResult, verbose: bool = False) -> None:
    """Print reconciliation report."""
    print("\n" + "=" * 60)
    print("SPEC/LEDGER RECONCILIATION REPORT (ADR-010)")
    print("=" * 60)

    # Schema Validation (ADR-010)
    if result.schema_errors or result.schema_warnings:
        print("\nSchema Validation:")
        if result.schema_errors:
            print(f"  Errors:   {len(result.schema_errors)}")
            status = "FAIL"
        else:
            status = "PASS"
        if result.schema_warnings:
            print(f"  Warnings: {len(result.schema_warnings)}")
        print(f"  Status:   {status}")
    elif verbose:
        print("\nSchema Validation: PASS")

    print(f"\nRequirements:")
    print(f"  Total:            {result.total_requirements}")
    print(f"  Active:           {result.active_requirements}")
    print(f"  With tests:       {result.with_tests}")
    print(f"  Without tests:    {result.without_tests}")
    print(f"  Coverage:         {result.coverage:.1f}%")

    # Show coverage by priority
    if result.coverage_by_priority:
        print(f"\nCoverage by Priority:")
        for priority in ["critical", "high", "medium", "low"]:
            if priority in result.coverage_by_priority:
                coverage = result.coverage_by_priority[priority]
                threshold = PRIORITY_THRESHOLDS.get(priority, 0)
                status = "OK" if coverage >= threshold else "FAIL"
                print(
                    f"  {priority.capitalize():10} {coverage:5.1f}% (threshold: {threshold:.0f}%) [{status}]"
                )

    # Show coverage by domain in verbose mode
    if verbose and result.coverage_by_domain:
        print(f"\nCoverage by Domain:")
        for domain in sorted(result.coverage_by_domain.keys()):
            coverage = result.coverage_by_domain[domain]
            print(f"  {domain:10} {coverage:5.1f}%")

    # Schema errors (ADR-010)
    if result.schema_errors:
        print(f"\nSchema Errors ({len(result.schema_errors)}):")
        for error in result.schema_errors[:10]:
            print(f"  - {error}")
        if len(result.schema_errors) > 10:
            print(f"  ... and {len(result.schema_errors) - 10} more")

    # Schema warnings (ADR-010)
    if verbose and result.schema_warnings:
        print(f"\nSchema Warnings ({len(result.schema_warnings)}):")
        for warning in result.schema_warnings[:10]:
            print(f"  - {warning}")
        if len(result.schema_warnings) > 10:
            print(f"  ... and {len(result.schema_warnings) - 10} more")

    if result.missing_test_files:
        print(f"\nMissing Test Files ({len(result.missing_test_files)}):")
        for item in result.missing_test_files[:10]:
            print(f"  - {item}")
        if len(result.missing_test_files) > 10:
            print(f"  ... and {len(result.missing_test_files) - 10} more")

    # Missing test functions (ADR-010)
    if result.missing_test_functions:
        print(f"\nMissing Test Functions ({len(result.missing_test_functions)}):")
        for item in result.missing_test_functions[:10]:
            print(f"  - {item}")
        if len(result.missing_test_functions) > 10:
            print(f"  ... and {len(result.missing_test_functions) - 10} more")

    # Syntax errors (ADR-010)
    if result.syntax_errors:
        print(f"\nSyntax Errors in Test Files ({len(result.syntax_errors)}):")
        for error in result.syntax_errors[:5]:
            print(f"  - {error}")
        if len(result.syntax_errors) > 5:
            print(f"  ... and {len(result.syntax_errors) - 5} more")

    if verbose and result.orphaned_tests:
        print(f"\nOrphaned Test Files ({len(result.orphaned_tests)}):")
        for item in result.orphaned_tests[:10]:
            print(f"  - {item}")
        if len(result.orphaned_tests) > 10:
            print(f"  ... and {len(result.orphaned_tests) - 10} more")

    # Orphan markers (ADR-010)
    if result.orphan_markers:
        print(f"\nOrphan Requirement Markers ({len(result.orphan_markers)}):")
        for test_path, req_id in result.orphan_markers[:10]:
            print(f"  - {test_path} references non-existent {req_id}")
        if len(result.orphan_markers) > 10:
            print(f"  ... and {len(result.orphan_markers) - 10} more")

    # Skipped tests (ADR-010)
    if result.skipped_tests:
        # Group by skip type
        unconditional = [s for s in result.skipped_tests if s.skip_type == "unconditional"]
        conditional = [s for s in result.skipped_tests if s.skip_type == "conditional"]
        xfail = [s for s in result.skipped_tests if s.skip_type == "xfail"]

        print(f"\nSkipped Tests ({len(result.skipped_tests)}):")
        if unconditional:
            print(f"  Unconditional (@skip) [WARNING]: {len(unconditional)}")
            if verbose:
                for skip in unconditional[:5]:
                    reason = f" - {skip.reason}" if skip.reason else ""
                    print(f"    - {skip.test_path}{reason}")
        if conditional:
            print(f"  Conditional (@skipif) [INFO]: {len(conditional)}")
        if xfail:
            print(f"  Expected fail (@xfail) [INFO]: {len(xfail)}")

    if result.ratchet_violations:
        print(f"\nRatchet Violations ({len(result.ratchet_violations)}):")
        for violation in result.ratchet_violations:
            print(f"  - {violation}")

    if result.errors:
        print(f"\nErrors ({len(result.errors)}):")
        for error in result.errors:
            print(f"  - {error}")

    print("\n" + "-" * 60)
    if result.passed:
        if result.has_warnings:
            print("Reconciliation PASSED with WARNINGS!")
        else:
            print("Reconciliation PASSED!")
    else:
        print("Reconciliation FAILED!")
        if result.schema_errors:
            print(f"  - {len(result.schema_errors)} schema errors")
        if result.coverage < 90.0:
            print(f"  - Coverage {result.coverage:.1f}% below threshold (90%)")
        if result.missing_test_files:
            print(f"  - {len(result.missing_test_files)} missing test files")
        if result.missing_test_functions:
            print(f"  - {len(result.missing_test_functions)} missing test functions")
        if result.ratchet_violations:
            print(f"  - {len(result.ratchet_violations)} ratchet violations")
        # Check priority thresholds
        for priority, threshold in PRIORITY_THRESHOLDS.items():
            current = result.coverage_by_priority.get(priority, 100.0)
            if current < threshold:
                print(f"  - {priority} coverage {current:.1f}% below threshold ({threshold:.0f}%)")
        if result.errors:
            print(f"  - {len(result.errors)} errors")
    print("-" * 60 + "\n")


def main() -> int:
    """Main entry point.

    Exit codes (ADR-010):
        0: All validations passed
        1: Reconciliation failures (missing files, schema errors, etc.)
        2: Configuration/parsing error OR warnings in strict mode
    """
    parser = argparse.ArgumentParser(
        description="Spec/Ledger reconciliation validation (ADR-009, ADR-010)"
    )
    parser.add_argument(
        "--warn",
        action="store_true",
        help="Warning mode: always exit 0, print warnings only",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Strict mode: treat warnings as failures (exit 2)",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument(
        "--ledger",
        type=Path,
        default=Path("spec/ledger.yml"),
        help="Path to ledger.yml",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path("."),
        help="Project root directory",
    )
    parser.add_argument(
        "--check-skips",
        action="store_true",
        help="Enable skip detection (ADR-010 Layer 3)",
    )
    parser.add_argument(
        "--check-orphans",
        action="store_true",
        help="Enable orphan marker detection (ADR-010 Layer 3)",
    )
    parser.add_argument(
        "--no-introspection",
        action="store_true",
        help="Disable AST test function introspection",
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Update the baseline file with current coverage",
    )

    args = parser.parse_args()

    # Resolve paths
    ledger_path = args.project_root / args.ledger
    if not ledger_path.is_absolute():
        ledger_path = Path.cwd() / ledger_path

    project_root = args.project_root
    if not project_root.is_absolute():
        project_root = Path.cwd() / project_root

    # Run reconciliation
    try:
        result = reconcile(
            ledger_path,
            project_root,
            verbose=args.verbose,
            check_skips=args.check_skips,
            check_orphans=args.check_orphans,
            introspect_functions=not args.no_introspection,
        )
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    # Print report
    print_report(result, args.verbose)

    # Handle baseline update
    if args.update_baseline:
        baseline_path = project_root / ".spec-baseline.json"
        baseline = BaselineSchema(
            version="1.0",
            timestamp=datetime.now(timezone.utc).isoformat(),
            coverage={
                "overall": result.coverage,
                "by_priority": result.coverage_by_priority,
                "by_domain": result.coverage_by_domain,
            },
        )
        save_baseline(baseline, baseline_path)
        print(f"Baseline updated: {baseline_path}")

    # Determine exit code (ADR-010)
    if args.warn:
        return 0

    if not result.passed:
        return 1

    if args.strict and result.has_warnings:
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
