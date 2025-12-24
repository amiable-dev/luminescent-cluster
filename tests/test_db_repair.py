# Copyright 2024-2025 Amiable Development
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Tests for database health check utility (scripts/db_repair.py).

These tests verify that the health check utility can:
1. Detect database health issues (corrupted UDFs, duplicate indices)
2. Detect missing computed columns
3. Detect version marker mismatches
4. Provide actionable diagnostics

Note: Repair-in-place functionality was removed per LLM Council review.
Use scripts/backup_restore.py for recovery operations.

Related: ADR-001, GitHub Issues #8
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest


class TestHealthCheck:
    """Test suite for health check functionality."""

    # ========================================
    # Test: Health Check Returns Status Dict
    # ========================================
    def test_check_health_returns_dict(self):
        """check_health should return a dictionary with health status."""
        from scripts.db_repair import check_health

        result = check_health()

        assert isinstance(result, dict), "Should return a dictionary"
        assert "healthy" in result, "Should have 'healthy' key"
        assert "issues" in result, "Should have 'issues' key"
        assert isinstance(result["issues"], list), "Issues should be a list"

    def test_check_health_healthy_db_returns_healthy(self):
        """Healthy database should return healthy=True with empty issues."""
        from scripts.db_repair import check_health

        with patch("scripts.db_repair.get_knowledge_base") as mock_kb:
            # Mock a healthy knowledge base
            mock_table = MagicMock()
            mock_table.columns = {
                "content": MagicMock(),
                "is_adr": MagicMock(),
                "summary": MagicMock(),
            }
            mock_kb.return_value = mock_table

            # Mock embedding index check
            with patch("scripts.db_repair._get_embedding_indices") as mock_indices:
                mock_indices.return_value = [{"name": "idx1", "column": "content"}]

                with patch("scripts.db_repair._check_version_marker") as mock_version:
                    mock_version.return_value = None  # No version issues

                    result = check_health()

        assert result["healthy"] is True, "Should be healthy"
        assert len(result["issues"]) == 0, "Should have no issues"

    # ========================================
    # Test: Computed Column Detection
    # ========================================
    def test_detect_missing_computed_columns(self):
        """Should detect when computed columns are missing."""
        from scripts.db_repair import check_health

        with patch("scripts.db_repair.get_knowledge_base") as mock_kb:
            # Mock knowledge base missing computed columns
            mock_table = MagicMock()
            mock_table.columns = {"content": MagicMock()}  # Missing is_adr, summary
            mock_kb.return_value = mock_table

            with patch("scripts.db_repair._get_embedding_indices") as mock_indices:
                mock_indices.return_value = [{"name": "idx1", "column": "content"}]

                with patch("scripts.db_repair._check_version_marker") as mock_version:
                    mock_version.return_value = None

                    result = check_health()

        assert result["healthy"] is False, "Should not be healthy"
        issues = [i["type"] for i in result["issues"]]
        assert "missing_computed_column" in issues, "Should detect missing computed column"

    def test_detect_all_required_computed_columns(self):
        """Should check for both 'is_adr' and 'summary' computed columns."""
        from scripts.db_repair import REQUIRED_COMPUTED_COLUMNS

        assert "is_adr" in REQUIRED_COMPUTED_COLUMNS, "is_adr should be required"
        assert "summary" in REQUIRED_COMPUTED_COLUMNS, "summary should be required"

    # ========================================
    # Test: Duplicate Index Detection
    # ========================================
    def test_detect_duplicate_embedding_indices(self):
        """Should detect duplicate embedding indices on same column."""
        from scripts.db_repair import check_health

        with patch("scripts.db_repair.get_knowledge_base") as mock_kb:
            mock_table = MagicMock()
            mock_table.columns = {
                "content": MagicMock(),
                "is_adr": MagicMock(),
                "summary": MagicMock(),
            }
            mock_kb.return_value = mock_table

            # Mock duplicate indices on content column
            with patch("scripts.db_repair._get_embedding_indices") as mock_indices:
                mock_indices.return_value = [
                    {"name": "idx1", "column": "content"},
                    {"name": "idx5", "column": "content"},  # Duplicate
                ]

                with patch("scripts.db_repair._check_version_marker") as mock_version:
                    mock_version.return_value = None

                    result = check_health()

        assert result["healthy"] is False, "Should not be healthy"
        issues = [i["type"] for i in result["issues"]]
        assert "duplicate_index" in issues, "Should detect duplicate index"

    # ========================================
    # Test: Version Mismatch Detection
    # ========================================
    def test_detect_version_mismatch(self):
        """Should detect when Python version marker doesn't match."""
        from scripts.db_repair import check_health

        with patch("scripts.db_repair.get_knowledge_base") as mock_kb:
            mock_table = MagicMock()
            mock_table.columns = {
                "content": MagicMock(),
                "is_adr": MagicMock(),
                "summary": MagicMock(),
            }
            mock_kb.return_value = mock_table

            with patch("scripts.db_repair._get_embedding_indices") as mock_indices:
                mock_indices.return_value = [{"name": "idx1", "column": "content"}]

                with patch("scripts.db_repair._check_version_marker") as mock_version:
                    mock_version.return_value = {
                        "type": "version_mismatch",
                        "message": "Marker: 3.11, Current: 3.13",
                        "marker_version": "3.11",
                        "current_version": "3.13",
                    }

                    result = check_health()

        assert result["healthy"] is False, "Should not be healthy"
        issues = [i["type"] for i in result["issues"]]
        assert "version_mismatch" in issues, "Should detect version mismatch"

    # ========================================
    # Test: Missing Embedding Index Detection
    # ========================================
    def test_detect_missing_embedding_index(self):
        """Should detect when content column has no embedding index."""
        from scripts.db_repair import check_health

        with patch("scripts.db_repair.get_knowledge_base") as mock_kb:
            mock_table = MagicMock()
            mock_table.columns = {
                "content": MagicMock(),
                "is_adr": MagicMock(),
                "summary": MagicMock(),
            }
            mock_kb.return_value = mock_table

            with patch("scripts.db_repair._get_embedding_indices") as mock_indices:
                mock_indices.return_value = []  # No indices

                with patch("scripts.db_repair._check_version_marker") as mock_version:
                    mock_version.return_value = None

                    result = check_health()

        assert result["healthy"] is False, "Should not be healthy"
        issues = [i["type"] for i in result["issues"]]
        assert "missing_embedding_index" in issues, "Should detect missing embedding index"

    # ========================================
    # Test: Health Check Exit Codes
    # ========================================
    def test_check_health_cli_exit_code_0_when_healthy(self):
        """CLI should exit with code 0 when database is healthy."""
        from scripts.db_repair import check_health_cli

        with patch("scripts.db_repair.check_health") as mock_check:
            mock_check.return_value = {"healthy": True, "issues": []}

            with pytest.raises(SystemExit) as exc_info:
                check_health_cli()

            assert exc_info.value.code == 0, "Should exit with code 0"

    def test_check_health_cli_exit_code_1_when_unhealthy(self):
        """CLI should exit with code 1 when issues are found."""
        from scripts.db_repair import check_health_cli

        with patch("scripts.db_repair.check_health") as mock_check:
            mock_check.return_value = {
                "healthy": False,
                "issues": [{"type": "test_issue", "message": "Test"}],
            }

            with pytest.raises(SystemExit) as exc_info:
                check_health_cli()

            assert exc_info.value.code == 1, "Should exit with code 1"


class TestHelperFunctions:
    """Test suite for helper functions."""

    # ========================================
    # Test: Get Knowledge Base
    # ========================================
    def test_get_knowledge_base_returns_table(self):
        """get_knowledge_base should return the org_knowledge table."""
        from scripts.db_repair import get_knowledge_base

        with patch("scripts.db_repair.pxt") as mock_pxt:
            mock_table = MagicMock()
            mock_pxt.get_table.return_value = mock_table

            result = get_knowledge_base()

        mock_pxt.get_table.assert_called_with("org_knowledge")
        assert result == mock_table

    def test_get_knowledge_base_handles_missing_table(self):
        """Should raise appropriate error if table doesn't exist."""
        from scripts.db_repair import get_knowledge_base

        with patch("scripts.db_repair.pxt") as mock_pxt:
            mock_pxt.get_table.side_effect = Exception("Table does not exist")

            with pytest.raises(Exception) as exc_info:
                get_knowledge_base()

            assert "does not exist" in str(exc_info.value).lower()

    # ========================================
    # Test: Version Marker Check
    # ========================================
    def test_check_version_marker_returns_none_when_match(self, tmp_path):
        """Should return None when version markers match."""
        from scripts.db_repair import _check_version_marker

        pixeltable_dir = tmp_path / ".pixeltable"
        pixeltable_dir.mkdir()

        # Create marker with current version
        version_marker = pixeltable_dir / ".python_version"
        current_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        version_marker.write_text(f"{current_version}\n")

        with patch.dict(os.environ, {"PIXELTABLE_HOME": str(pixeltable_dir)}):
            result = _check_version_marker()

        assert result is None, "Should return None when versions match"

    def test_check_version_marker_returns_issue_on_mismatch(self, tmp_path):
        """Should return issue dict when versions don't match."""
        from scripts.db_repair import _check_version_marker

        pixeltable_dir = tmp_path / ".pixeltable"
        pixeltable_dir.mkdir()

        # Create marker with different version
        version_marker = pixeltable_dir / ".python_version"
        version_marker.write_text("3.99\n")  # Fake version

        with patch.dict(os.environ, {"PIXELTABLE_HOME": str(pixeltable_dir)}):
            result = _check_version_marker()

        assert result is not None, "Should return issue"
        assert result["type"] == "version_mismatch"

    # ========================================
    # Test: Get Embedding Indices
    # ========================================
    def test_get_embedding_indices_returns_list(self):
        """_get_embedding_indices should return list of index info."""
        from scripts.db_repair import _get_embedding_indices

        with patch("scripts.db_repair.get_knowledge_base") as mock_kb:
            mock_table = MagicMock()
            # Mock the indices attribute/method
            mock_kb.return_value = mock_table

            result = _get_embedding_indices()

        assert isinstance(result, list), "Should return a list"


class TestUDFDefinitions:
    """Tests for UDF definitions used in repair."""

    def test_is_architecture_decision_detects_adr_path(self):
        """is_architecture_decision UDF should detect /adr/ in path."""
        from scripts.db_repair import is_architecture_decision_impl

        result = is_architecture_decision_impl("/docs/adr/001-decision.md", "Some content")
        assert result is True

    def test_is_architecture_decision_detects_adr_header(self):
        """is_architecture_decision UDF should detect ADR headers."""
        from scripts.db_repair import is_architecture_decision_impl

        content = "# ADR-001: Use PostgreSQL for persistence"
        result = is_architecture_decision_impl("/docs/decision.md", content)
        assert result is True

    def test_is_architecture_decision_rejects_non_adr(self):
        """is_architecture_decision UDF should reject non-ADR content."""
        from scripts.db_repair import is_architecture_decision_impl

        result = is_architecture_decision_impl("/src/main.py", "def hello(): pass")
        assert result is False

    def test_generate_summary_short_content(self):
        """generate_summary should return content unchanged if short."""
        from scripts.db_repair import generate_summary_impl

        short_content = "This is short."
        result = generate_summary_impl(short_content)
        assert result == short_content

    def test_generate_summary_truncates_long_content(self):
        """generate_summary should truncate long content."""
        from scripts.db_repair import generate_summary_impl

        long_content = "x" * 1000
        result = generate_summary_impl(long_content)
        assert len(result) < len(long_content)
        assert "Summary:" in result


class TestCLIInterface:
    """Tests for CLI interface."""

    def test_main_with_check_flag(self):
        """Running with --check flag should run health check."""
        from scripts.db_repair import main

        with patch("scripts.db_repair.check_health_cli") as mock_check:
            with patch("sys.argv", ["db_repair.py", "--check"]):
                try:
                    main()
                except SystemExit:
                    pass

            mock_check.assert_called_once()

    def test_main_without_flags_shows_help(self):
        """Running without flags should show help."""
        from scripts.db_repair import main

        with patch("sys.argv", ["db_repair.py"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

            # Should exit with code 0 (help displayed)
            assert exc_info.value.code == 0
