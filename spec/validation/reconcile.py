#!/usr/bin/env python3
"""
Spec/Ledger Reconciliation Script

Bidirectional validation between spec/ledger.yml and actual test files.

Exit Codes:
    0: All requirements have mapped tests, all mapped tests exist
    1: Reconciliation failures found
    2: Configuration/parsing error

Usage:
    python spec/validation/reconcile.py          # Run full reconciliation
    python spec/validation/reconcile.py --warn   # Run in warning mode (always exit 0)
    python spec/validation/reconcile.py --verbose # Show detailed output
    python spec/validation/reconcile.py --update-baseline # Update baseline after improvements

See ADR-009 for the reconciliation system design.
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

# =============================================================================
# Priority Thresholds (ADR-009 Phase 2/3)
# =============================================================================

PRIORITY_THRESHOLDS: dict[str, float] = {
    "critical": 100.0,  # 100% coverage required
    "high": 95.0,       # 95% coverage required
    "medium": 85.0,     # 85% coverage required
    "low": 75.0,        # 75% coverage required
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


def check_ratchet(
    baseline: dict[str, Any], current: dict[str, Any]
) -> list[str]:
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
    orphaned_tests: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    coverage_by_priority: dict[str, float] = field(default_factory=dict)
    coverage_by_domain: dict[str, float] = field(default_factory=dict)
    ratchet_violations: list[str] = field(default_factory=list)

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
        3. Overall coverage >= 90%
        4. Priority-specific thresholds met (if coverage_by_priority is populated)
        5. No ratchet violations
        """
        # Basic checks
        if len(self.errors) > 0:
            return False
        if len(self.missing_test_files) > 0:
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
    ledger_path: Path, project_root: Path, verbose: bool = False
) -> ReconciliationResult:
    """Run bidirectional reconciliation.

    Checks:
    1. All requirements have mapped tests
    2. All mapped test files exist
    3. Coverage meets threshold (90%)
    4. Priority-specific thresholds met
    5. Domain-specific coverage tracked
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

    # Find existing test files
    existing_test_files = find_test_files(project_root)
    if verbose:
        print(f"Found {len(existing_test_files)} test files")

    # Get requirements
    requirements = ledger.get("requirements", {})
    result.total_requirements = len(requirements)

    # Track referenced test files
    referenced_test_files = set()

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

        # Verify test files exist
        for test_path in tests:
            file_path, _ = parse_test_path(test_path)
            referenced_test_files.add(file_path)

            if file_path not in existing_test_files:
                result.missing_test_files.append(f"{req_id}: {file_path}")
                if verbose:
                    print(f"  {req_id}: Missing test file {file_path}")

    # Calculate coverage by priority
    for priority, counts in priority_counts.items():
        if counts["total"] > 0:
            result.coverage_by_priority[priority] = (
                counts["covered"] / counts["total"]
            ) * 100
        else:
            result.coverage_by_priority[priority] = 100.0  # No requirements = 100%

    # Calculate coverage by domain
    for domain, counts in domain_counts.items():
        if counts["total"] > 0:
            result.coverage_by_domain[domain] = (
                counts["covered"] / counts["total"]
            ) * 100
        else:
            result.coverage_by_domain[domain] = 100.0

    # Find orphaned tests (test files not referenced by any requirement)
    # Note: This is informational, not a failure
    orphaned = existing_test_files - referenced_test_files
    result.orphaned_tests = list(sorted(orphaned))

    return result


def print_report(result: ReconciliationResult, verbose: bool = False) -> None:
    """Print reconciliation report."""
    print("\n" + "=" * 60)
    print("SPEC/LEDGER RECONCILIATION REPORT")
    print("=" * 60)

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
                print(f"  {priority.capitalize():10} {coverage:5.1f}% (threshold: {threshold:.0f}%) [{status}]")

    # Show coverage by domain in verbose mode
    if verbose and result.coverage_by_domain:
        print(f"\nCoverage by Domain:")
        for domain in sorted(result.coverage_by_domain.keys()):
            coverage = result.coverage_by_domain[domain]
            print(f"  {domain:10} {coverage:5.1f}%")

    if result.missing_test_files:
        print(f"\nMissing Test Files ({len(result.missing_test_files)}):")
        for item in result.missing_test_files[:10]:
            print(f"  - {item}")
        if len(result.missing_test_files) > 10:
            print(f"  ... and {len(result.missing_test_files) - 10} more")

    if verbose and result.orphaned_tests:
        print(f"\nOrphaned Test Files ({len(result.orphaned_tests)}):")
        for item in result.orphaned_tests[:10]:
            print(f"  - {item}")
        if len(result.orphaned_tests) > 10:
            print(f"  ... and {len(result.orphaned_tests) - 10} more")

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
        print("Reconciliation PASSED!")
    else:
        print("Reconciliation FAILED!")
        if result.coverage < 90.0:
            print(f"  - Coverage {result.coverage:.1f}% below threshold (90%)")
        if result.missing_test_files:
            print(f"  - {len(result.missing_test_files)} missing test files")
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
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Spec/Ledger reconciliation validation"
    )
    parser.add_argument(
        "--warn",
        action="store_true",
        help="Warning mode: always exit 0, print warnings only",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Verbose output"
    )
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
        result = reconcile(ledger_path, project_root, args.verbose)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    # Print report
    print_report(result, args.verbose)

    # Determine exit code
    if args.warn:
        return 0
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
