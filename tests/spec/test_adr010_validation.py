# Copyright 2024-2026 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
TDD Tests for ADR-010 validation enhancements.

ADR-010: Test Ledger & Documentation Freshness Validation

These tests verify:
- Schema validation for ledger entries
- AST-based test function introspection
- Skip detection (tiered taxonomy)
- Orphan marker detection
- Link checking
- ADR-ledger synchronization
"""

import tempfile
from pathlib import Path

import pytest
import yaml


class TestSchemaValidation:
    """Tests for ledger schema validation (ADR-010 Layer 1)."""

    def test_valid_status_constants(self):
        """Valid status values should be defined."""
        from spec.validation.reconcile import VALID_STATUS

        assert "active" in VALID_STATUS
        assert "deprecated" in VALID_STATUS
        assert "proposed" in VALID_STATUS
        assert "manual" in VALID_STATUS

    def test_valid_priority_constants(self):
        """Valid priority values should be defined."""
        from spec.validation.reconcile import VALID_PRIORITY

        assert "critical" in VALID_PRIORITY
        assert "high" in VALID_PRIORITY
        assert "medium" in VALID_PRIORITY
        assert "low" in VALID_PRIORITY

    def test_required_fields_defined(self):
        """Required fields should be defined."""
        from spec.validation.reconcile import REQUIRED_FIELDS

        assert "title" in REQUIRED_FIELDS
        assert "source" in REQUIRED_FIELDS
        assert "status" in REQUIRED_FIELDS
        assert "priority" in REQUIRED_FIELDS

    def test_validate_valid_requirement(self):
        """Valid requirement should pass schema validation."""
        from spec.validation.reconcile import validate_requirement_schema

        req_data = {
            "title": "Test Requirement",
            "source": "ADR-001",
            "status": "active",
            "priority": "high",
            "tests": ["tests/test_foo.py"],
        }

        result = validate_requirement_schema("REQ-TEST-001", req_data)

        assert result.valid is True
        assert len(result.errors) == 0

    def test_validate_missing_required_field(self):
        """Missing required field should fail validation."""
        from spec.validation.reconcile import validate_requirement_schema

        req_data = {
            "title": "Test Requirement",
            # Missing: source, status, priority
        }

        result = validate_requirement_schema("REQ-TEST-001", req_data)

        assert result.valid is False
        assert any("source" in e for e in result.errors)

    def test_validate_invalid_status(self):
        """Invalid status should fail validation."""
        from spec.validation.reconcile import validate_requirement_schema

        req_data = {
            "title": "Test Requirement",
            "source": "ADR-001",
            "status": "unknonw",  # Typo - invalid
            "priority": "high",
        }

        result = validate_requirement_schema("REQ-TEST-001", req_data)

        assert result.valid is False
        assert any("status" in e.lower() for e in result.errors)

    def test_validate_invalid_priority(self):
        """Invalid priority should fail validation."""
        from spec.validation.reconcile import validate_requirement_schema

        req_data = {
            "title": "Test Requirement",
            "source": "ADR-001",
            "status": "active",
            "priority": "super-critical",  # Invalid
        }

        result = validate_requirement_schema("REQ-TEST-001", req_data)

        assert result.valid is False
        assert any("priority" in e.lower() for e in result.errors)

    def test_validate_ledger_schema(self):
        """Entire ledger should be validated."""
        from spec.validation.reconcile import validate_ledger_schema

        ledger = {
            "version": "1.0",
            "requirements": {
                "REQ-TEST-001": {
                    "title": "Test",
                    "source": "ADR-001",
                    "status": "active",
                    "priority": "high",
                }
            },
        }

        result = validate_ledger_schema(ledger)

        assert result.valid is True

    def test_validate_ledger_missing_requirements(self):
        """Ledger without requirements section should fail."""
        from spec.validation.reconcile import validate_ledger_schema

        ledger = {"version": "1.0"}

        result = validate_ledger_schema(ledger)

        assert result.valid is False
        assert any("requirements" in e.lower() for e in result.errors)


class TestASTIntrospection:
    """Tests for AST-based test introspection (ADR-010 Layer 1)."""

    def test_introspect_functions(self):
        """Should find top-level test functions."""
        from spec.validation.reconcile import introspect_test_file

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("""
def test_something():
    pass

def test_another():
    pass

def helper_function():
    pass
""")
            f.flush()

            result = introspect_test_file(Path(f.name))

        assert "test_something" in result.functions
        assert "test_another" in result.functions
        assert "helper_function" not in result.functions

    def test_introspect_classes(self):
        """Should find test classes and their methods."""
        from spec.validation.reconcile import introspect_test_file

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("""
class TestFoo:
    def test_bar(self):
        pass

    def test_baz(self):
        pass

    def helper(self):
        pass

class NotATest:
    def test_method(self):
        pass
""")
            f.flush()

            result = introspect_test_file(Path(f.name))

        assert "TestFoo" in result.classes
        assert "test_bar" in result.classes["TestFoo"]
        assert "test_baz" in result.classes["TestFoo"]
        assert "helper" not in result.classes["TestFoo"]
        assert "NotATest" not in result.classes

    def test_handle_syntax_error(self):
        """Should handle syntax errors gracefully."""
        from spec.validation.reconcile import introspect_test_file

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def broken(\n")  # Invalid Python
            f.flush()

            result = introspect_test_file(Path(f.name))

        assert len(result.errors) > 0
        assert "SyntaxError" in result.errors[0]

    def test_verify_test_reference_function(self):
        """Should verify test function exists."""
        from spec.validation.reconcile import verify_test_reference

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            test_file = tmpdir / "tests" / "test_foo.py"
            test_file.parent.mkdir(parents=True)
            test_file.write_text("""
def test_bar():
    pass
""")

            cache = {}
            exists, error = verify_test_reference(
                "tests/test_foo.py::test_bar", tmpdir, cache
            )

        assert exists is True
        assert error is None

    def test_verify_test_reference_class_method(self):
        """Should verify test class method exists."""
        from spec.validation.reconcile import verify_test_reference

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            test_file = tmpdir / "tests" / "test_foo.py"
            test_file.parent.mkdir(parents=True)
            test_file.write_text("""
class TestFoo:
    def test_bar(self):
        pass
""")

            cache = {}
            exists, error = verify_test_reference(
                "tests/test_foo.py::TestFoo::test_bar", tmpdir, cache
            )

        assert exists is True
        assert error is None

    def test_verify_missing_function(self):
        """Should detect missing test function."""
        from spec.validation.reconcile import verify_test_reference

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            test_file = tmpdir / "tests" / "test_foo.py"
            test_file.parent.mkdir(parents=True)
            test_file.write_text("# Empty file")

            cache = {}
            exists, error = verify_test_reference(
                "tests/test_foo.py::test_nonexistent", tmpdir, cache
            )

        assert exists is False
        assert "not found" in error.lower()


class TestSkipDetection:
    """Tests for skip detection (ADR-010 Layer 3)."""

    def test_skip_severity_defined(self):
        """Skip severity taxonomy should be defined."""
        from spec.validation.reconcile import SKIP_SEVERITY

        assert SKIP_SEVERITY["unconditional"] == "warning"
        assert SKIP_SEVERITY["conditional"] == "info"
        assert SKIP_SEVERITY["xfail"] == "info"

    def test_detect_unconditional_skip(self):
        """Should detect @pytest.mark.skip decorator."""
        from spec.validation.reconcile import detect_skips_in_file

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("""
import pytest

@pytest.mark.skip(reason="Not implemented")
def test_something():
    pass
""")
            f.flush()

            skips = detect_skips_in_file(Path(f.name))

        assert len(skips) == 1
        assert skips[0].skip_type == "unconditional"
        assert "Not implemented" in skips[0].reason

    def test_detect_conditional_skip(self):
        """Should detect @pytest.mark.skipif decorator."""
        from spec.validation.reconcile import detect_skips_in_file

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("""
import pytest
import sys

@pytest.mark.skipif(sys.platform == "win32", reason="Unix only")
def test_something():
    pass
""")
            f.flush()

            skips = detect_skips_in_file(Path(f.name))

        assert len(skips) == 1
        assert skips[0].skip_type == "conditional"

    def test_detect_xfail(self):
        """Should detect @pytest.mark.xfail decorator."""
        from spec.validation.reconcile import detect_skips_in_file

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("""
import pytest

@pytest.mark.xfail(reason="Known issue")
def test_something():
    pass
""")
            f.flush()

            skips = detect_skips_in_file(Path(f.name))

        assert len(skips) == 1
        assert skips[0].skip_type == "xfail"


class TestOrphanDetection:
    """Tests for orphan marker detection (ADR-010 Layer 3)."""

    def test_find_orphan_markers(self):
        """Should find tests referencing non-existent requirements."""
        from spec.validation.reconcile import find_orphan_requirement_markers

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            test_file = tmpdir / "tests" / "test_foo.py"
            test_file.parent.mkdir(parents=True)
            test_file.write_text("""
import pytest

@pytest.mark.requirement("REQ-DELETED-001")
def test_something():
    pass
""")

            ledger_reqs = {"REQ-TEST-001"}  # REQ-DELETED-001 not in ledger
            orphans = find_orphan_requirement_markers(tmpdir, ledger_reqs)

        assert len(orphans) == 1
        assert orphans[0][1] == "REQ-DELETED-001"

    def test_no_orphans_when_requirement_exists(self):
        """Should not flag tests when requirement exists."""
        from spec.validation.reconcile import find_orphan_requirement_markers

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            test_file = tmpdir / "tests" / "test_foo.py"
            test_file.parent.mkdir(parents=True)
            test_file.write_text("""
import pytest

@pytest.mark.requirement("REQ-TEST-001")
def test_something():
    pass
""")

            ledger_reqs = {"REQ-TEST-001"}
            orphans = find_orphan_requirement_markers(tmpdir, ledger_reqs)

        assert len(orphans) == 0


class TestReconciliationResultWarnings:
    """Tests for warning handling in ReconciliationResult."""

    def test_has_warnings_with_orphan_markers(self):
        """has_warnings should be True when orphan markers exist."""
        from spec.validation.reconcile import ReconciliationResult

        result = ReconciliationResult()
        result.orphan_markers = [("test.py::test_foo", "REQ-DELETED-001")]

        assert result.has_warnings is True

    def test_has_warnings_with_unconditional_skips(self):
        """has_warnings should be True when unconditional skips exist."""
        from spec.validation.reconcile import ReconciliationResult, SkipInfo

        result = ReconciliationResult()
        result.skipped_tests = [SkipInfo("test.py::test_foo", "unconditional", None)]

        assert result.has_warnings is True

    def test_no_warnings_with_conditional_skips(self):
        """has_warnings should be False for conditional skips only."""
        from spec.validation.reconcile import ReconciliationResult, SkipInfo

        result = ReconciliationResult()
        result.skipped_tests = [SkipInfo("test.py::test_foo", "conditional", None)]

        assert result.has_warnings is False


class TestDocFreshnessLinkChecker:
    """Tests for documentation link checker (ADR-010 Layer 2)."""

    def test_is_external_link(self):
        """Should detect external links."""
        from spec.validation.doc_freshness import is_external_link

        assert is_external_link("https://example.com") is True
        assert is_external_link("http://example.com") is True
        assert is_external_link("mailto:user@example.com") is True
        assert is_external_link("#anchor") is True
        assert is_external_link("./local-file.md") is False
        assert is_external_link("../sibling.md") is False

    def test_extract_links_from_markdown(self):
        """Should extract links from markdown content."""
        from spec.validation.doc_freshness import extract_links_from_markdown

        content = """
# Test

[Link 1](./foo.md)
[Link 2](https://example.com)
[Link 3](#anchor)
"""

        links = extract_links_from_markdown(content)

        assert len(links) == 3
        targets = [l[2] for l in links]
        assert "./foo.md" in targets
        assert "https://example.com" in targets
        assert "#anchor" in targets

    def test_skip_links_in_code_blocks(self):
        """Should skip links inside code blocks."""
        from spec.validation.doc_freshness import extract_links_from_markdown

        content = """
# Test

[Real Link](./real.md)

```
[Link in code block](./fake.md)
```

More text.
"""

        links = extract_links_from_markdown(content)

        assert len(links) == 1
        assert links[0][2] == "./real.md"

    def test_skip_links_in_inline_code(self):
        """Should skip links inside inline code backticks."""
        from spec.validation.doc_freshness import extract_links_from_markdown

        content = """
# Test

Example: `[link](404.md)` is broken.

[Real Link](./real.md)
"""

        links = extract_links_from_markdown(content)

        assert len(links) == 1
        assert links[0][2] == "./real.md"

    def test_check_all_links(self):
        """Should check all links in documentation."""
        from spec.validation.doc_freshness import check_all_links

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            docs_dir = tmpdir / "docs"
            docs_dir.mkdir()

            # Create a doc with valid link
            (docs_dir / "index.md").write_text("# Index\n[Other](./other.md)")
            (docs_dir / "other.md").write_text("# Other")

            result = check_all_links(docs_dir)

        assert result.passed is True
        assert len(result.broken_links) == 0


class TestADRLedgerSync:
    """Tests for ADR-ledger synchronization (ADR-010 Layer 2)."""

    def test_extract_requirements_from_adr(self):
        """Should extract requirement IDs from ADR content."""
        from spec.validation.doc_freshness import extract_requirements_from_adr

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("""
# ADR-001

This ADR defines REQ-MCP-001 and REQ-MCP-002.
Also includes NEG-SEC-001 for security.
""")
            f.flush()

            reqs = extract_requirements_from_adr(Path(f.name))

        assert "REQ-MCP-001" in reqs
        assert "REQ-MCP-002" in reqs
        assert "NEG-SEC-001" in reqs

    def test_check_adr_ledger_sync_passes(self):
        """ADR-ledger sync should pass when all requirements exist."""
        from spec.validation.doc_freshness import check_adr_ledger_sync

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create ADR
            adrs_dir = tmpdir / "adrs"
            adrs_dir.mkdir()
            (adrs_dir / "ADR-001.md").write_text("Defines REQ-TEST-001")

            # Create ledger
            ledger = {
                "requirements": {
                    "REQ-TEST-001": {
                        "title": "Test",
                        "source": "ADR-001",
                        "status": "active",
                        "priority": "high",
                    }
                }
            }
            ledger_path = tmpdir / "ledger.yml"
            ledger_path.write_text(yaml.dump(ledger))

            result = check_adr_ledger_sync(adrs_dir, ledger_path)

        assert result.passed is True

    def test_check_adr_ledger_sync_detects_missing(self):
        """ADR-ledger sync should detect requirements missing from ledger."""
        from spec.validation.doc_freshness import check_adr_ledger_sync

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create ADR referencing a requirement not in ledger
            adrs_dir = tmpdir / "adrs"
            adrs_dir.mkdir()
            (adrs_dir / "ADR-001.md").write_text("Defines REQ-MISSING-001")

            # Create ledger without the requirement
            ledger = {"requirements": {}}
            ledger_path = tmpdir / "ledger.yml"
            ledger_path.write_text(yaml.dump(ledger))

            result = check_adr_ledger_sync(adrs_dir, ledger_path)

        assert result.passed is False
        missing = [i for i in result.issues if i.issue_type == "missing_in_ledger"]
        assert len(missing) == 1
        assert missing[0].requirement_id == "REQ-MISSING-001"
