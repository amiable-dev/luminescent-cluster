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
Python Version Guard for Pixeltable MCP Servers (ADR-001)

This module prevents silent segfaults by detecting Python version mismatches
before Pixeltable is imported. Pixeltable serializes UDFs using pickle, which
is incompatible across Python minor versions.

IMPORTANT: This module must be imported BEFORE any pixeltable imports.

Exit Codes (following sysexits.h convention):
- 0: Success (version matches or fresh install)
- 78 (EX_CONFIG): Version mismatch detected
- 65 (EX_DATAERR): Legacy database without version marker

Usage:
    # At the top of your MCP server entry point:
    from luminescent_cluster.version_guard import enforce_python_version
    enforce_python_version()

    # Only import pixeltable AFTER the guard passes
    import pixeltable as pxt

See ADR-001 for full documentation:
    docs/adrs/ADR-001-python-version-requirement-for-mcp-servers.md
"""

import sys
import os
import logging
from pathlib import Path
from typing import Callable

# Exit codes (following sysexits.h convention)
EX_CONFIG = 78  # Configuration error - version mismatch
EX_DATAERR = 65  # Legacy database without version marker

# Set up logging for monitoring (Layer 7)
logger = logging.getLogger("pixeltable.version_guard")

# Cross-platform file locking
# Critical: fcntl is Unix-only, msvcrt is Windows-only
try:
    import fcntl

    def lock_file(f) -> None:
        """Acquire exclusive lock on file (Unix)."""
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)

    def unlock_file(f) -> None:
        """Release lock on file (Unix)."""
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)

except ImportError:
    # Windows fallback
    import msvcrt

    def lock_file(f) -> None:
        """Acquire exclusive lock on file (Windows)."""
        msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)

    def unlock_file(f) -> None:
        """Release lock on file (Windows)."""
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)


def get_pixeltable_dir() -> Path:
    """
    Get Pixeltable directory, respecting PIXELTABLE_HOME if set.

    Returns:
        Path to Pixeltable data directory
    """
    pixeltable_home = os.environ.get("PIXELTABLE_HOME")
    if pixeltable_home:
        return Path(pixeltable_home)
    return Path.home() / ".pixeltable"


def has_existing_database(pixeltable_dir: Path) -> bool:
    """
    Check if a Pixeltable database already exists (legacy or current).

    Args:
        pixeltable_dir: Path to the Pixeltable data directory

    Returns:
        True if database artifacts exist, False otherwise
    """
    if not pixeltable_dir.exists():
        return False

    # Check for common Pixeltable artifacts (metadata, data directories, db file)
    indicators = ["metadata", "data", "pgdata", ".pixeltable.db"]
    return any((pixeltable_dir / ind).exists() for ind in indicators)


def enforce_python_version() -> None:
    """
    Check for Python version mismatch with Pixeltable database.
    EXIT immediately if mismatch detected - do not proceed to segfault.

    This function handles four scenarios:
    1. Version marker exists and matches: proceed normally
    2. Version marker exists but mismatches: exit with code 78 (EX_CONFIG)
    3. No marker but DB exists (legacy): exit with code 65 (EX_DATAERR)
    4. No marker and no DB: create marker (fresh install)

    Note: Patch version changes (3.11.0 -> 3.11.9) are SAFE.
    Only minor/major version changes cause pickle incompatibility.

    Raises:
        SystemExit: With code 78 or 65 if version issues detected
    """
    pixeltable_dir = get_pixeltable_dir()
    version_marker = pixeltable_dir / ".python_version"
    lock_file_path = pixeltable_dir / ".version.lock"
    current_version = f"{sys.version_info.major}.{sys.version_info.minor}"

    # Ensure directory exists for lock file
    pixeltable_dir.mkdir(parents=True, exist_ok=True)

    # Use file locking to prevent race conditions in parallel environments
    with open(lock_file_path, "w") as lock:
        lock_file(lock)
        try:
            if version_marker.exists():
                # Read stored version (first line is major.minor)
                stored_version = version_marker.read_text().strip().split("\n")[0]

                if stored_version != current_version:
                    # Version mismatch - this WILL cause a segfault
                    logger.error(
                        "version_check_failed",
                        extra={
                            "stored_version": stored_version,
                            "current_version": current_version,
                            "pixeltable_home": str(pixeltable_dir),
                        },
                    )
                    print(
                        f"\n"
                        f"╔══════════════════════════════════════════════════════════════╗\n"
                        f"║  PYTHON VERSION MISMATCH - DATABASE INCOMPATIBLE             ║\n"
                        f"╠══════════════════════════════════════════════════════════════╣\n"
                        f"║  Database created with: Python {stored_version:<10}                    ║\n"
                        f"║  Currently running:     Python {current_version:<10}                    ║\n"
                        f"║                                                              ║\n"
                        f"║  OPTIONS:                                                    ║\n"
                        f"║  1. Use correct Python version:                              ║\n"
                        f"║       uv venv --python {stored_version}                                ║\n"
                        f"║       source .venv/bin/activate                              ║\n"
                        f"║                                                              ║\n"
                        f"║  2. Fresh install (deletes all data):                        ║\n"
                        f"║       rm -rf {str(pixeltable_dir):<45} ║\n"
                        f"║                                                              ║\n"
                        f"║  3. Backup and restore (preserves data):                     ║\n"
                        f"║       python -m scripts.backup_restore --backup-restore      ║\n"
                        f"╚══════════════════════════════════════════════════════════════╝\n",
                        file=sys.stderr,
                    )
                    sys.exit(EX_CONFIG)  # 78

                # Version matches - log success and proceed
                logger.info(
                    "version_check_passed",
                    extra={
                        "stored_version": stored_version,
                        "current_version": current_version,
                        "pixeltable_home": str(pixeltable_dir),
                    },
                )

            elif has_existing_database(pixeltable_dir):
                # CRITICAL: Legacy database exists without version marker
                # We cannot safely determine what version created it
                logger.error(
                    "legacy_database_detected",
                    extra={
                        "current_version": current_version,
                        "pixeltable_home": str(pixeltable_dir),
                    },
                )
                print(
                    f"\n"
                    f"╔══════════════════════════════════════════════════════════════╗\n"
                    f"║  LEGACY DATABASE DETECTED - NO VERSION MARKER                ║\n"
                    f"╠══════════════════════════════════════════════════════════════╣\n"
                    f"║  Database location: {str(pixeltable_dir):<40} ║\n"
                    f"║  Currently running: Python {current_version:<10}                      ║\n"
                    f"║                                                              ║\n"
                    f"║  This database was created before version tracking was       ║\n"
                    f"║  implemented. Running may cause a segmentation fault.        ║\n"
                    f"║                                                              ║\n"
                    f"║  OPTIONS:                                                    ║\n"
                    f"║  1. Create marker manually (if you know the Python version): ║\n"
                    f"║       echo '3.XX' > {str(version_marker):<39} ║\n"
                    f"║                                                              ║\n"
                    f"║  2. Fresh install (deletes all data):                        ║\n"
                    f"║       rm -rf {str(pixeltable_dir):<45} ║\n"
                    f"╚══════════════════════════════════════════════════════════════╝\n",
                    file=sys.stderr,
                )
                sys.exit(EX_DATAERR)  # 65

            else:
                # Fresh install - safe to create marker
                version_marker.write_text(f"{current_version}\n{sys.version}")
                logger.info(
                    "version_marker_created",
                    extra={
                        "version": current_version,
                        "pixeltable_home": str(pixeltable_dir),
                    },
                )

        finally:
            unlock_file(lock)


# Convenience function for direct invocation
if __name__ == "__main__":
    enforce_python_version()
    print(
        f"Version guard passed. Python {sys.version_info.major}.{sys.version_info.minor} is compatible."
    )
