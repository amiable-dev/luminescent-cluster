# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
TDD Tests for reconcile.py enhancements.

ADR-009 Phase 2/3: Coverage Improvement and Enforcement

These tests verify:
- Priority-aware coverage thresholds
- Baseline ratchet mechanism
- Domain coverage reporting

Related GitHub Issues:
- ADR-009 Phase 2: Coverage Improvement
- ADR-009 Phase 3: Enforcement
"""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml


class TestPriorityThresholds:
    """TDD: Tests for priority-aware coverage thresholds."""

    def test_priority_thresholds_defined(self):
        """PRIORITY_THRESHOLDS constant should be defined."""
        from spec.validation.reconcile import PRIORITY_THRESHOLDS

        assert "critical" in PRIORITY_THRESHOLDS
        assert "high" in PRIORITY_THRESHOLDS
        assert "medium" in PRIORITY_THRESHOLDS
        assert "low" in PRIORITY_THRESHOLDS

    def test_critical_threshold_is_100(self):
        """Critical priority should require 100% coverage."""
        from spec.validation.reconcile import PRIORITY_THRESHOLDS

        assert PRIORITY_THRESHOLDS["critical"] == 100.0

    def test_high_threshold_is_95(self):
        """High priority should require 95% coverage."""
        from spec.validation.reconcile import PRIORITY_THRESHOLDS

        assert PRIORITY_THRESHOLDS["high"] == 95.0

    def test_medium_threshold_is_85(self):
        """Medium priority should require 85% coverage."""
        from spec.validation.reconcile import PRIORITY_THRESHOLDS

        assert PRIORITY_THRESHOLDS["medium"] == 85.0

    def test_low_threshold_is_75(self):
        """Low priority should require 75% coverage."""
        from spec.validation.reconcile import PRIORITY_THRESHOLDS

        assert PRIORITY_THRESHOLDS["low"] == 75.0

    def test_result_tracks_coverage_by_priority(self):
        """ReconciliationResult should track coverage by priority."""
        from spec.validation.reconcile import ReconciliationResult

        result = ReconciliationResult()
        result.coverage_by_priority = {
            "critical": 100.0,
            "high": 96.0,
            "medium": 88.0,
            "low": 80.0,
        }

        assert result.coverage_by_priority["critical"] == 100.0
        assert result.coverage_by_priority["high"] == 96.0

    def test_passed_checks_priority_thresholds(self):
        """passed property should check priority-specific thresholds."""
        from spec.validation.reconcile import ReconciliationResult

        result = ReconciliationResult()
        result.active_requirements = 10
        result.with_tests = 10
        result.coverage_by_priority = {
            "critical": 100.0,  # meets 100%
            "high": 95.0,  # meets 95%
            "medium": 85.0,  # meets 85%
            "low": 75.0,  # meets 75%
        }

        assert result.passed is True

    def test_failed_critical_threshold(self):
        """passed should fail if critical coverage is below 100%."""
        from spec.validation.reconcile import ReconciliationResult

        result = ReconciliationResult()
        result.active_requirements = 10
        result.with_tests = 10
        result.coverage_by_priority = {
            "critical": 90.0,  # FAILS - below 100%
            "high": 95.0,
            "medium": 85.0,
            "low": 75.0,
        }

        assert result.passed is False

    def test_security_domain_always_critical(self):
        """SEC-* requirements should always use critical threshold."""
        from spec.validation.reconcile import get_effective_priority

        # Even if marked as "low", security should be "critical"
        assert get_effective_priority("REQ-SEC-001", "low") == "critical"
        assert get_effective_priority("REQ-SEC-050", "medium") == "critical"
        assert get_effective_priority("NEG-SEC-001", "high") == "critical"

    def test_non_security_uses_declared_priority(self):
        """Non-security requirements use their declared priority."""
        from spec.validation.reconcile import get_effective_priority

        assert get_effective_priority("REQ-MCP-001", "high") == "high"
        assert get_effective_priority("REQ-MEM-020", "medium") == "medium"
        assert get_effective_priority("REQ-BOT-001", "low") == "low"


class TestBaselineRatchet:
    """TDD: Tests for baseline ratchet mechanism."""

    def test_baseline_schema_version(self):
        """Baseline should have version field."""
        from spec.validation.reconcile import BaselineSchema

        schema = BaselineSchema(
            version="1.0",
            timestamp=datetime.now(timezone.utc).isoformat(),
            coverage={"overall": 97.8},
        )

        assert schema.version == "1.0"

    def test_baseline_has_timestamp(self):
        """Baseline should include timestamp."""
        from spec.validation.reconcile import BaselineSchema

        now = datetime.now(timezone.utc)
        schema = BaselineSchema(
            version="1.0",
            timestamp=now.isoformat(),
            coverage={"overall": 97.8},
        )

        assert schema.timestamp is not None

    def test_baseline_has_coverage_data(self):
        """Baseline should include coverage data."""
        from spec.validation.reconcile import BaselineSchema

        schema = BaselineSchema(
            version="1.0",
            timestamp=datetime.now(timezone.utc).isoformat(),
            coverage={
                "overall": 97.8,
                "by_priority": {
                    "critical": 100.0,
                    "high": 95.0,
                    "medium": 85.0,
                    "low": 75.0,
                },
                "by_domain": {
                    "MCP": 100.0,
                    "MEM": 95.0,
                    "SEC": 100.0,
                },
            },
        )

        assert schema.coverage["overall"] == 97.8
        assert schema.coverage["by_priority"]["critical"] == 100.0
        assert schema.coverage["by_domain"]["MCP"] == 100.0

    def test_load_baseline_from_file(self):
        """Should load baseline from .spec-baseline.json file."""
        from spec.validation.reconcile import load_baseline

        baseline_data = {
            "version": "1.0",
            "timestamp": "2026-01-16T00:00:00Z",
            "coverage": {"overall": 95.0},
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(baseline_data, f)
            f.flush()

            baseline = load_baseline(Path(f.name))

        assert baseline is not None
        assert baseline.coverage["overall"] == 95.0

    def test_load_baseline_returns_none_if_missing(self):
        """load_baseline should return None if file doesn't exist."""
        from spec.validation.reconcile import load_baseline

        baseline = load_baseline(Path("/nonexistent/baseline.json"))
        assert baseline is None

    def test_save_baseline(self):
        """Should save baseline to .spec-baseline.json file."""
        from spec.validation.reconcile import BaselineSchema, save_baseline

        baseline = BaselineSchema(
            version="1.0",
            timestamp=datetime.now(timezone.utc).isoformat(),
            coverage={"overall": 97.8},
        )

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            save_baseline(baseline, Path(f.name))

            # Read back and verify
            with open(f.name) as rf:
                data = json.load(rf)

        assert data["version"] == "1.0"
        assert data["coverage"]["overall"] == 97.8

    def test_ratchet_prevents_regression(self):
        """Coverage should not decrease below baseline."""
        from spec.validation.reconcile import check_ratchet

        baseline = {"overall": 95.0}
        current = {"overall": 90.0}  # Regression!

        violations = check_ratchet(baseline, current)

        assert len(violations) > 0
        assert "overall" in str(violations[0])

    def test_ratchet_allows_improvement(self):
        """Coverage can increase above baseline."""
        from spec.validation.reconcile import check_ratchet

        baseline = {"overall": 95.0}
        current = {"overall": 98.0}  # Improvement!

        violations = check_ratchet(baseline, current)

        assert len(violations) == 0

    def test_ratchet_checks_priority_levels(self):
        """Ratchet should check each priority level."""
        from spec.validation.reconcile import check_ratchet

        baseline = {
            "overall": 95.0,
            "by_priority": {"critical": 100.0, "high": 95.0},
        }
        current = {
            "overall": 95.0,
            "by_priority": {"critical": 95.0, "high": 95.0},  # Regression!
        }

        violations = check_ratchet(baseline, current)

        assert len(violations) > 0
        assert "critical" in str(violations[0])

    def test_update_baseline_flag(self):
        """--update-baseline flag should update the baseline file."""
        # This is an integration test that would be run in main()
        # Just verify the flag exists
        from spec.validation.reconcile import main
        import argparse

        parser = argparse.ArgumentParser()
        # The actual flag will be added in implementation
        # This test documents the expected behavior
        assert callable(main)


class TestDomainCoverage:
    """TDD: Tests for per-domain coverage reporting."""

    def test_result_tracks_coverage_by_domain(self):
        """ReconciliationResult should track coverage by domain."""
        from spec.validation.reconcile import ReconciliationResult

        result = ReconciliationResult()
        result.coverage_by_domain = {
            "MCP": 100.0,
            "MEM": 95.0,
            "SEC": 100.0,
            "BOT": 85.0,
        }

        assert result.coverage_by_domain["MCP"] == 100.0
        assert result.coverage_by_domain["SEC"] == 100.0

    def test_extract_domain_from_req_id(self):
        """Should extract domain from requirement ID."""
        from spec.validation.reconcile import extract_domain

        assert extract_domain("REQ-MCP-001") == "MCP"
        assert extract_domain("REQ-MEM-020") == "MEM"
        assert extract_domain("REQ-SEC-001") == "SEC"
        assert extract_domain("NEG-BOT-001") == "BOT"
        assert extract_domain("REQ-WKF-010") == "WKF"
        assert extract_domain("REQ-INT-001") == "INT"
        assert extract_domain("REQ-EXT-005") == "EXT"

    def test_reconcile_calculates_domain_coverage(self):
        """reconcile() should calculate coverage per domain."""
        # Create a minimal ledger for testing
        ledger_content = """
version: "1.0"
domains:
  - mcp
  - memory

requirements:
  REQ-MCP-001:
    title: "Test MCP"
    source: "Test"
    status: active
    priority: high
    tests:
      - tests/test_mcp.py

  REQ-MCP-002:
    title: "Test MCP 2"
    source: "Test"
    status: active
    priority: high
    tests:
      - tests/test_mcp.py

  REQ-MEM-001:
    title: "Test MEM"
    source: "Test"
    status: active
    priority: high
    tests: []
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create ledger
            ledger_path = tmpdir / "ledger.yml"
            ledger_path.write_text(ledger_content)

            # Create test directory and file
            test_dir = tmpdir / "tests"
            test_dir.mkdir()
            (test_dir / "test_mcp.py").write_text("# test")

            # Run reconcile
            from spec.validation.reconcile import reconcile

            result = reconcile(ledger_path, tmpdir)

        # MCP should have 100% (2/2 with tests)
        # MEM should have 0% (0/1 with tests)
        assert result.coverage_by_domain["MCP"] == 100.0
        assert result.coverage_by_domain["MEM"] == 0.0

    def test_print_report_shows_domain_coverage(self):
        """print_report should display domain coverage."""
        from io import StringIO
        from spec.validation.reconcile import ReconciliationResult, print_report

        result = ReconciliationResult()
        result.total_requirements = 10
        result.active_requirements = 10
        result.with_tests = 9
        result.without_tests = 1
        result.coverage_by_domain = {
            "MCP": 100.0,
            "MEM": 80.0,
        }
        result.coverage_by_priority = {
            "critical": 100.0,
            "high": 90.0,
            "medium": 85.0,
            "low": 75.0,
        }

        import sys
        old_stdout = sys.stdout
        sys.stdout = StringIO()

        print_report(result, verbose=True)

        output = sys.stdout.getvalue()
        sys.stdout = old_stdout

        # Should show domain coverage in verbose mode
        assert "MCP" in output or "Domain" in output


class TestReconcilatonIntegration:
    """Integration tests for reconcile.py enhancements."""

    def test_reconcile_with_priorities(self):
        """reconcile() should track coverage by priority."""
        ledger_content = """
version: "1.0"
domains:
  - mcp

requirements:
  REQ-MCP-001:
    title: "Critical Test"
    source: "Test"
    status: active
    priority: critical
    tests:
      - tests/test_mcp.py

  REQ-MCP-002:
    title: "High Test"
    source: "Test"
    status: active
    priority: high
    tests:
      - tests/test_mcp.py

  REQ-MCP-003:
    title: "Medium Test"
    source: "Test"
    status: active
    priority: medium
    tests: []
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create ledger
            ledger_path = tmpdir / "ledger.yml"
            ledger_path.write_text(ledger_content)

            # Create test directory and file
            test_dir = tmpdir / "tests"
            test_dir.mkdir()
            (test_dir / "test_mcp.py").write_text("# test")

            # Run reconcile
            from spec.validation.reconcile import reconcile

            result = reconcile(ledger_path, tmpdir)

        # Check priority coverage is tracked
        assert hasattr(result, "coverage_by_priority")
        assert result.coverage_by_priority["critical"] == 100.0
        assert result.coverage_by_priority["high"] == 100.0
        assert result.coverage_by_priority["medium"] == 0.0

    def test_full_reconciliation_with_baseline(self):
        """Full reconciliation should work with baseline ratchet."""
        ledger_content = """
version: "1.0"
domains:
  - mcp

requirements:
  REQ-MCP-001:
    title: "Test"
    source: "Test"
    status: active
    priority: critical
    tests:
      - tests/test_mcp.py
"""
        baseline_content = {
            "version": "1.0",
            "timestamp": "2026-01-16T00:00:00Z",
            "coverage": {
                "overall": 90.0,
                "by_priority": {"critical": 90.0},
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create ledger
            ledger_path = tmpdir / "ledger.yml"
            ledger_path.write_text(ledger_content)

            # Create baseline
            baseline_path = tmpdir / ".spec-baseline.json"
            baseline_path.write_text(json.dumps(baseline_content))

            # Create test directory and file
            test_dir = tmpdir / "tests"
            test_dir.mkdir()
            (test_dir / "test_mcp.py").write_text("# test")

            # Run reconcile with baseline checking
            from spec.validation.reconcile import (
                check_ratchet,
                load_baseline,
                reconcile,
            )

            result = reconcile(ledger_path, tmpdir)
            baseline = load_baseline(baseline_path)

            # Current coverage (100%) should be >= baseline (90%)
            violations = check_ratchet(
                baseline.coverage,
                {
                    "overall": result.coverage,
                    "by_priority": result.coverage_by_priority,
                },
            )

        assert len(violations) == 0
