"""
Tests for the Python version guard (ADR-001).

These tests verify that the version guard:
1. Creates version marker on fresh install
2. Allows matching versions to proceed
3. Exits with code 78 (EX_CONFIG) on version mismatch
4. Exits with code 65 (EX_DATAERR) for legacy databases without markers
5. Supports PIXELTABLE_HOME environment variable
6. Uses cross-platform file locking
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

# Import will be from luminescent_cluster.version_guard once implemented
# For now, we import to verify tests fail (TDD Red phase)


class TestVersionGuard:
    """Test suite for version_guard module."""

    @pytest.fixture
    def temp_pixeltable_dir(self, tmp_path):
        """Create a temporary directory for Pixeltable data."""
        pixeltable_dir = tmp_path / ".pixeltable"
        pixeltable_dir.mkdir()
        return pixeltable_dir

    @pytest.fixture
    def mock_version_info(self):
        """Mock sys.version_info for testing different Python versions."""
        original = sys.version_info
        yield
        # Restore after test

    # ========================================
    # Test: Fresh Install (no marker, no DB)
    # ========================================
    def test_fresh_install_creates_version_marker(self, tmp_path):
        """On fresh install, version guard should create .python_version marker."""
        from luminescent_cluster.version_guard import enforce_python_version, get_pixeltable_dir

        pixeltable_dir = tmp_path / ".pixeltable"
        # Don't create directory - let the guard do it

        with patch.dict(os.environ, {"PIXELTABLE_HOME": str(pixeltable_dir)}):
            # Should not raise or exit
            result = enforce_python_version()

        # Marker should be created
        version_marker = pixeltable_dir / ".python_version"
        assert version_marker.exists(), "Version marker should be created on fresh install"

        # Should contain current version
        content = version_marker.read_text()
        expected_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        assert content.startswith(expected_version), f"Marker should start with {expected_version}"

    # ========================================
    # Test: Version Match
    # ========================================
    def test_version_match_proceeds_normally(self, tmp_path):
        """When version matches, guard should allow execution to continue."""
        from luminescent_cluster.version_guard import enforce_python_version

        pixeltable_dir = tmp_path / ".pixeltable"
        pixeltable_dir.mkdir()

        # Create marker with current version
        version_marker = pixeltable_dir / ".python_version"
        current_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        version_marker.write_text(f"{current_version}\n{sys.version}")

        with patch.dict(os.environ, {"PIXELTABLE_HOME": str(pixeltable_dir)}):
            # Should not raise or exit
            result = enforce_python_version()

        # Should succeed (no exception)
        assert True, "Version match should proceed normally"

    # ========================================
    # Test: Version Mismatch (Exit 78)
    # ========================================
    def test_version_mismatch_exits_with_code_78(self, tmp_path):
        """When version mismatches, guard should exit with code 78 (EX_CONFIG)."""
        from luminescent_cluster.version_guard import enforce_python_version, EX_CONFIG

        pixeltable_dir = tmp_path / ".pixeltable"
        pixeltable_dir.mkdir()

        # Create marker with different version
        version_marker = pixeltable_dir / ".python_version"
        version_marker.write_text("3.99\n")  # Fake future version

        with patch.dict(os.environ, {"PIXELTABLE_HOME": str(pixeltable_dir)}):
            with pytest.raises(SystemExit) as exc_info:
                enforce_python_version()

        assert exc_info.value.code == EX_CONFIG, f"Should exit with code {EX_CONFIG} (EX_CONFIG)"

    # ========================================
    # Test: Legacy Database (Exit 65)
    # ========================================
    def test_legacy_database_exits_with_code_65(self, tmp_path):
        """When database exists but no marker, guard should exit with code 65."""
        from luminescent_cluster.version_guard import enforce_python_version, EX_DATAERR

        pixeltable_dir = tmp_path / ".pixeltable"
        pixeltable_dir.mkdir()

        # Create database artifacts without version marker
        (pixeltable_dir / "metadata").mkdir()
        (pixeltable_dir / "data").mkdir()

        with patch.dict(os.environ, {"PIXELTABLE_HOME": str(pixeltable_dir)}):
            with pytest.raises(SystemExit) as exc_info:
                enforce_python_version()

        assert exc_info.value.code == EX_DATAERR, f"Should exit with code {EX_DATAERR} (EX_DATAERR)"

    # ========================================
    # Test: PIXELTABLE_HOME Environment Variable
    # ========================================
    def test_respects_pixeltable_home_env_var(self, tmp_path):
        """Guard should respect PIXELTABLE_HOME environment variable."""
        from luminescent_cluster.version_guard import get_pixeltable_dir

        custom_dir = tmp_path / "custom_pixeltable"

        with patch.dict(os.environ, {"PIXELTABLE_HOME": str(custom_dir)}):
            result = get_pixeltable_dir()

        assert result == custom_dir, "Should use PIXELTABLE_HOME when set"

    def test_defaults_to_home_pixeltable(self):
        """Without PIXELTABLE_HOME, should default to ~/.pixeltable."""
        from luminescent_cluster.version_guard import get_pixeltable_dir

        # Ensure PIXELTABLE_HOME is not set
        env = os.environ.copy()
        env.pop("PIXELTABLE_HOME", None)

        with patch.dict(os.environ, env, clear=True):
            with patch.dict(os.environ, {"HOME": "/home/testuser"}):
                result = get_pixeltable_dir()

        expected = Path("/home/testuser") / ".pixeltable"
        assert result == expected, f"Should default to ~/.pixeltable, got {result}"

    # ========================================
    # Test: Database Detection
    # ========================================
    def test_detects_metadata_directory_as_database(self, tmp_path):
        """Should detect 'metadata' directory as existing database."""
        from luminescent_cluster.version_guard import has_existing_database

        pixeltable_dir = tmp_path / ".pixeltable"
        pixeltable_dir.mkdir()
        (pixeltable_dir / "metadata").mkdir()

        assert has_existing_database(pixeltable_dir), "Should detect metadata directory"

    def test_detects_data_directory_as_database(self, tmp_path):
        """Should detect 'data' directory as existing database."""
        from luminescent_cluster.version_guard import has_existing_database

        pixeltable_dir = tmp_path / ".pixeltable"
        pixeltable_dir.mkdir()
        (pixeltable_dir / "data").mkdir()

        assert has_existing_database(pixeltable_dir), "Should detect data directory"

    def test_detects_pgdata_directory_as_database(self, tmp_path):
        """Should detect 'pgdata' directory as existing database."""
        from luminescent_cluster.version_guard import has_existing_database

        pixeltable_dir = tmp_path / ".pixeltable"
        pixeltable_dir.mkdir()
        (pixeltable_dir / "pgdata").mkdir()

        assert has_existing_database(pixeltable_dir), "Should detect pgdata directory"

    def test_detects_pixeltable_db_file_as_database(self, tmp_path):
        """Should detect '.pixeltable.db' file as existing database."""
        from luminescent_cluster.version_guard import has_existing_database

        pixeltable_dir = tmp_path / ".pixeltable"
        pixeltable_dir.mkdir()
        (pixeltable_dir / ".pixeltable.db").touch()

        assert has_existing_database(pixeltable_dir), "Should detect .pixeltable.db file"

    def test_empty_directory_is_not_database(self, tmp_path):
        """Empty directory should not be detected as database."""
        from luminescent_cluster.version_guard import has_existing_database

        pixeltable_dir = tmp_path / ".pixeltable"
        pixeltable_dir.mkdir()

        assert not has_existing_database(pixeltable_dir), (
            "Empty dir should not be detected as database"
        )

    def test_nonexistent_directory_is_not_database(self, tmp_path):
        """Non-existent directory should not be detected as database."""
        from luminescent_cluster.version_guard import has_existing_database

        pixeltable_dir = tmp_path / ".pixeltable"
        # Don't create it

        assert not has_existing_database(pixeltable_dir), "Non-existent dir should not be database"

    # ========================================
    # Test: File Locking
    # ========================================
    def test_lock_file_functions_exist(self):
        """Lock and unlock functions should be available (cross-platform)."""
        from luminescent_cluster.version_guard import lock_file, unlock_file

        assert callable(lock_file), "lock_file should be callable"
        assert callable(unlock_file), "unlock_file should be callable"

    def test_file_locking_works(self, tmp_path):
        """File locking should work without errors."""
        from luminescent_cluster.version_guard import lock_file, unlock_file

        lock_path = tmp_path / "test.lock"

        with open(lock_path, "w") as f:
            # Should not raise
            lock_file(f)
            f.write("locked")
            unlock_file(f)

        assert lock_path.read_text() == "locked", "File should be written while locked"

    # ========================================
    # Test: Exit Codes
    # ========================================
    def test_exit_code_constants(self):
        """Exit code constants should match sysexits.h convention."""
        from luminescent_cluster.version_guard import EX_CONFIG, EX_DATAERR

        assert EX_CONFIG == 78, "EX_CONFIG should be 78"
        assert EX_DATAERR == 65, "EX_DATAERR should be 65"

    # ========================================
    # Test: Version Marker Format
    # ========================================
    def test_version_marker_contains_full_version(self, tmp_path):
        """Version marker should contain both short and full version."""
        from luminescent_cluster.version_guard import enforce_python_version

        pixeltable_dir = tmp_path / ".pixeltable"

        with patch.dict(os.environ, {"PIXELTABLE_HOME": str(pixeltable_dir)}):
            enforce_python_version()

        version_marker = pixeltable_dir / ".python_version"
        content = version_marker.read_text()
        lines = content.strip().split("\n")

        # First line: major.minor
        expected_short = f"{sys.version_info.major}.{sys.version_info.minor}"
        assert lines[0] == expected_short, f"First line should be {expected_short}"

        # Second line: full version string
        assert len(lines) >= 2, "Should have at least 2 lines"
        assert sys.version_info.major.__str__() in lines[1], (
            "Second line should contain version info"
        )

    # ========================================
    # Test: Patch Version Safety
    # ========================================
    def test_patch_version_difference_is_safe(self, tmp_path):
        """Patch version changes (3.11.0 -> 3.11.9) should be allowed."""
        from luminescent_cluster.version_guard import enforce_python_version

        pixeltable_dir = tmp_path / ".pixeltable"
        pixeltable_dir.mkdir()

        # Create marker with same major.minor but different patch
        version_marker = pixeltable_dir / ".python_version"
        current_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        # Marker has same major.minor, different full version
        version_marker.write_text(
            f"{current_version}\n3.{sys.version_info.minor}.0 (different patch)"
        )

        with patch.dict(os.environ, {"PIXELTABLE_HOME": str(pixeltable_dir)}):
            # Should not raise - patch versions are safe
            enforce_python_version()

        assert True, "Patch version difference should be allowed"


class TestVersionGuardIntegration:
    """Integration tests for version guard in MCP server context."""

    def test_guard_runs_before_pixeltable_import(self, tmp_path):
        """Version guard should be designed to run before pixeltable import."""
        # This is a design test - the guard module should not import pixeltable
        from luminescent_cluster import version_guard

        # Check that pixeltable is not in the module's imports
        import_names = [name for name in dir(version_guard) if not name.startswith("_")]

        # Verify no pixeltable references (it should be imported AFTER the guard runs)
        assert "pxt" not in import_names, "Guard should not import pixeltable"
        assert "pixeltable" not in import_names, "Guard should not import pixeltable"

    def test_guard_creates_lock_file(self, tmp_path):
        """Version guard should create a lock file for concurrent access."""
        from luminescent_cluster.version_guard import enforce_python_version

        pixeltable_dir = tmp_path / ".pixeltable"

        with patch.dict(os.environ, {"PIXELTABLE_HOME": str(pixeltable_dir)}):
            enforce_python_version()

        lock_file = pixeltable_dir / ".version.lock"
        assert lock_file.exists(), "Lock file should be created"
