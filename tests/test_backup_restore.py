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
Tests for backup/restore utility (scripts/backup_restore.py).

These tests verify that the backup/restore utility can:
1. Backup knowledge base data to Parquet files
2. Recreate tables with fresh UDFs
3. Restore data with embeddings recomputed
4. Update version markers appropriately

Use this utility when:
- Intentionally upgrading Python versions
- Recovering from corrupted databases
- Creating backups before major changes

Related: ADR-001, GitHub Issue #10
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime
import pytest


class TestBackupExport:
    """Test suite for backup (data export) functionality."""

    def test_export_data_creates_parquet_files(self, tmp_path):
        """export_data should create Parquet files in specified directory."""
        from scripts.backup_restore import export_data

        with patch("scripts.backup_restore.get_knowledge_base") as mock_kb:
            mock_table = MagicMock()
            # Mock the select and collect to return sample data
            mock_table.select.return_value.collect.return_value = [
                {"type": "code", "path": "/test.py", "content": "test"}
            ]
            mock_kb.return_value = mock_table

            result = export_data(export_dir=tmp_path)

        assert result["success"] is True
        assert "export_path" in result
        # Should create a parquet file
        assert any(f.suffix == ".parquet" for f in tmp_path.iterdir())

    def test_export_data_returns_row_count(self, tmp_path):
        """export_data should return the number of rows exported."""
        from scripts.backup_restore import export_data

        with patch("scripts.backup_restore.get_knowledge_base") as mock_kb:
            mock_table = MagicMock()
            mock_table.select.return_value.collect.return_value = [
                {"type": "code", "path": "/test1.py", "content": "test1"},
                {"type": "code", "path": "/test2.py", "content": "test2"},
                {"type": "decision", "path": "/adr/001.md", "content": "adr"},
            ]
            mock_kb.return_value = mock_table

            result = export_data(export_dir=tmp_path)

        assert result["row_count"] == 3

    def test_export_data_handles_empty_table(self, tmp_path):
        """export_data should handle empty tables gracefully."""
        from scripts.backup_restore import export_data

        with patch("scripts.backup_restore.get_knowledge_base") as mock_kb:
            mock_table = MagicMock()
            mock_table.select.return_value.collect.return_value = []
            mock_kb.return_value = mock_table

            result = export_data(export_dir=tmp_path)

        assert result["success"] is True
        assert result["row_count"] == 0


class TestTableRecreation:
    """Test suite for table recreation functionality."""

    def test_recreate_table_drops_and_creates(self):
        """recreate_table should drop old table and create new one."""
        from scripts.backup_restore import recreate_table

        with patch("scripts.backup_restore.pxt") as mock_pxt:
            mock_pxt.get_table.return_value = MagicMock()
            mock_pxt.udf = lambda fn: MagicMock(return_value=MagicMock())

            with patch("scripts.backup_restore._lazy_import_pixeltable"):
                result = recreate_table()

        mock_pxt.drop_table.assert_called()
        mock_pxt.create_table.assert_called()
        assert result["success"] is True

    def test_recreate_table_creates_fresh_udfs(self):
        """recreate_table should create fresh UDFs with current Python."""
        from scripts.backup_restore import recreate_table

        with patch("scripts.backup_restore.pxt") as mock_pxt:
            mock_pxt.get_table.return_value = MagicMock()
            mock_pxt.udf = lambda fn: MagicMock(return_value=MagicMock())
            mock_pxt.create_table.return_value = MagicMock()

            with patch("scripts.backup_restore._lazy_import_pixeltable"):
                result = recreate_table()

        # Should have created table with computed columns
        create_call = mock_pxt.create_table.call_args
        assert create_call is not None
        assert result["success"] is True


class TestRestoreImport:
    """Test suite for restore (data import) functionality."""

    def test_import_data_reads_parquet(self, tmp_path):
        """import_data should read from Parquet files."""
        from scripts.backup_restore import import_data

        # Create a mock parquet file
        parquet_file = tmp_path / "export.parquet"
        parquet_file.touch()

        with patch("scripts.backup_restore.get_knowledge_base") as mock_kb:
            mock_table = MagicMock()
            mock_kb.return_value = mock_table

            with patch("scripts.backup_restore.pd") as mock_pd:
                mock_df = MagicMock()
                mock_df.to_dict.return_value = [
                    {"type": "code", "path": "/test.py", "content": "test"}
                ]
                mock_pd.read_parquet.return_value = mock_df

                result = import_data(parquet_file)

        mock_pd.read_parquet.assert_called_once_with(parquet_file)
        assert result["success"] is True

    def test_import_data_inserts_rows(self, tmp_path):
        """import_data should insert rows into knowledge base."""
        from scripts.backup_restore import import_data

        parquet_file = tmp_path / "export.parquet"
        parquet_file.touch()

        with patch("scripts.backup_restore.get_knowledge_base") as mock_kb:
            mock_table = MagicMock()
            mock_kb.return_value = mock_table

            with patch("scripts.backup_restore.pd") as mock_pd:
                mock_df = MagicMock()
                mock_df.to_dict.return_value = [
                    {"type": "code", "path": "/test.py", "content": "test"}
                ]
                mock_pd.read_parquet.return_value = mock_df

                result = import_data(parquet_file)

        assert mock_table.insert.called
        assert result["rows_imported"] >= 1

    def test_import_data_handles_missing_file(self, tmp_path):
        """import_data should fail gracefully with missing file."""
        from scripts.backup_restore import import_data

        missing_file = tmp_path / "nonexistent.parquet"

        result = import_data(missing_file)

        assert result["success"] is False
        assert "error" in result


class TestVersionMarker:
    """Test suite for version marker updates."""

    def test_update_version_marker(self, tmp_path):
        """update_version_marker should update the marker file."""
        from scripts.backup_restore import update_version_marker

        pixeltable_dir = tmp_path / ".pixeltable"
        pixeltable_dir.mkdir()

        # Create old marker
        version_marker = pixeltable_dir / ".python_version"
        version_marker.write_text("3.11\n")

        with patch.dict(os.environ, {"PIXELTABLE_HOME": str(pixeltable_dir)}):
            result = update_version_marker()

        # Should be updated to current version
        current_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        assert version_marker.read_text().startswith(current_version)
        assert result["success"] is True


class TestFullBackupRestore:
    """Test suite for full backup/restore workflow."""

    def test_full_backup_restore_requires_confirmation(self):
        """full_backup_restore should require explicit confirmation."""
        from scripts.backup_restore import full_backup_restore

        result = full_backup_restore(confirm=False)

        assert result["success"] is False
        assert "requires confirmation" in result["message"].lower()

    def test_full_backup_restore_workflow(self, tmp_path):
        """full_backup_restore should run all steps in order."""
        from scripts.backup_restore import full_backup_restore

        with patch("scripts.backup_restore.export_data") as mock_export:
            mock_export.return_value = {
                "success": True,
                "export_path": str(tmp_path / "export.parquet"),
                "row_count": 10,
            }

            with patch("scripts.backup_restore.recreate_table") as mock_recreate:
                mock_recreate.return_value = {"success": True}

                with patch("scripts.backup_restore.import_data") as mock_import:
                    mock_import.return_value = {"success": True, "rows_imported": 10}

                    with patch("scripts.backup_restore.update_version_marker") as mock_marker:
                        mock_marker.return_value = {"success": True}

                        result = full_backup_restore(confirm=True, export_dir=tmp_path)

        # All steps should be called
        assert mock_export.called
        assert mock_recreate.called
        assert mock_import.called
        assert mock_marker.called
        assert result["success"] is True

    def test_full_backup_restore_stops_on_export_failure(self, tmp_path):
        """full_backup_restore should stop if backup fails."""
        from scripts.backup_restore import full_backup_restore

        with patch("scripts.backup_restore.export_data") as mock_export:
            mock_export.return_value = {"success": False, "error": "Export failed"}

            with patch("scripts.backup_restore.recreate_table") as mock_recreate:
                result = full_backup_restore(confirm=True, export_dir=tmp_path)

        assert result["success"] is False
        assert not mock_recreate.called  # Should not proceed


class TestBackupRestoreCLI:
    """Test suite for CLI interface."""

    def test_main_without_confirm_shows_warning(self):
        """Running --backup-restore without --confirm should show warning."""
        from scripts.backup_restore import main

        with patch("sys.argv", ["backup_restore.py", "--backup-restore"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code != 0

    def test_main_with_confirm_runs_backup_restore(self, tmp_path):
        """Running with --confirm should run backup/restore."""
        from scripts.backup_restore import main

        with patch("scripts.backup_restore.full_backup_restore") as mock_br:
            mock_br.return_value = {"success": True}

            with patch("sys.argv", ["backup_restore.py", "--backup-restore", "--confirm"]):
                with pytest.raises(SystemExit) as exc_info:
                    main()

            mock_br.assert_called()
            assert exc_info.value.code == 0

    def test_main_backup_only(self, tmp_path):
        """--backup should only export/backup data."""
        from scripts.backup_restore import main

        with patch("scripts.backup_restore.export_data") as mock_export:
            mock_export.return_value = {
                "success": True,
                "export_path": str(tmp_path / "export.parquet"),
                "row_count": 10,
            }

            with patch(
                "sys.argv", ["backup_restore.py", "--backup", "--export-dir", str(tmp_path)]
            ):
                with pytest.raises(SystemExit) as exc_info:
                    main()

            mock_export.assert_called()
            assert exc_info.value.code == 0
