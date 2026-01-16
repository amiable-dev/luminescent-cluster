# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
TDD: Tests for Support Scripts (ADR-002 Phase 4).

These tests verify that the support scripts:
- install_hooks.sh: Installs git hooks correctly
- init_memory.py: Bootstraps knowledge base

Related: ADR-002 Workflow Integration, Phase 4 (Support Scripts)
"""

import os
import stat
from pathlib import Path

import pytest


class TestInstallHooksScript:
    """TDD: Tests for install_hooks.sh script."""

    def test_install_hooks_script_exists(self):
        """install_hooks.sh should exist in scripts directory.

        ADR Reference: ADR-002 Phase 4 (Support Scripts)
        """
        script_path = Path(__file__).parent.parent.parent / "scripts" / "install_hooks.sh"
        assert script_path.exists(), f"Script not found at {script_path}"

    def test_install_hooks_is_executable(self):
        """install_hooks.sh should be executable.

        ADR Reference: ADR-002 Phase 4 (Support Scripts)
        """
        script_path = Path(__file__).parent.parent.parent / "scripts" / "install_hooks.sh"
        mode = script_path.stat().st_mode
        assert mode & stat.S_IXUSR, "install_hooks.sh should be executable by owner"

    def test_install_hooks_has_shebang(self):
        """install_hooks.sh should start with bash shebang.

        ADR Reference: ADR-002 Phase 4 (Support Scripts)
        """
        script_path = Path(__file__).parent.parent.parent / "scripts" / "install_hooks.sh"
        content = script_path.read_text()
        assert content.startswith("#!/bin/bash"), "Script should start with bash shebang"

    def test_install_hooks_uses_strict_mode(self):
        """install_hooks.sh should use set -euo pipefail.

        ADR Reference: ADR-002 Phase 4 (Support Scripts)
        """
        script_path = Path(__file__).parent.parent.parent / "scripts" / "install_hooks.sh"
        content = script_path.read_text()
        assert "set -euo pipefail" in content, "Script should use strict mode"

    def test_install_hooks_references_adr(self):
        """install_hooks.sh should reference ADR-002.

        ADR Reference: ADR-002 Phase 4 (Support Scripts)
        """
        script_path = Path(__file__).parent.parent.parent / "scripts" / "install_hooks.sh"
        content = script_path.read_text()
        assert "ADR-002" in content, "Script should reference ADR-002"

    def test_install_hooks_handles_all_three_hooks(self):
        """install_hooks.sh should handle post-commit, post-merge, post-rewrite.

        ADR Reference: ADR-002 Phase 4 (Support Scripts)
        """
        script_path = Path(__file__).parent.parent.parent / "scripts" / "install_hooks.sh"
        content = script_path.read_text()
        assert "post-commit" in content, "Should handle post-commit"
        assert "post-merge" in content, "Should handle post-merge"
        assert "post-rewrite" in content, "Should handle post-rewrite"

    def test_install_hooks_backs_up_existing(self):
        """install_hooks.sh should back up existing hooks.

        ADR Reference: ADR-002 Phase 4 (Support Scripts)
        """
        script_path = Path(__file__).parent.parent.parent / "scripts" / "install_hooks.sh"
        content = script_path.read_text()
        assert "backup" in content.lower(), "Script should back up existing hooks"

    def test_install_hooks_creates_directories(self):
        """install_hooks.sh should create required directories.

        ADR Reference: ADR-002 Phase 4 (Support Scripts)
        """
        script_path = Path(__file__).parent.parent.parent / "scripts" / "install_hooks.sh"
        content = script_path.read_text()
        assert ".agent/state" in content, "Should create .agent/state"
        assert ".agent/logs" in content, "Should create .agent/logs"


class TestInitMemoryScript:
    """TDD: Tests for init_memory.py script."""

    def test_init_memory_script_exists(self):
        """init_memory.py should exist in scripts directory.

        ADR Reference: ADR-002 Phase 4 (Support Scripts)
        """
        script_path = Path(__file__).parent.parent.parent / "scripts" / "init_memory.py"
        assert script_path.exists(), f"Script not found at {script_path}"

    def test_init_memory_is_executable(self):
        """init_memory.py should be executable.

        ADR Reference: ADR-002 Phase 4 (Support Scripts)
        """
        script_path = Path(__file__).parent.parent.parent / "scripts" / "init_memory.py"
        mode = script_path.stat().st_mode
        assert mode & stat.S_IXUSR, "init_memory.py should be executable by owner"

    def test_init_memory_has_shebang(self):
        """init_memory.py should start with python shebang.

        ADR Reference: ADR-002 Phase 4 (Support Scripts)
        """
        script_path = Path(__file__).parent.parent.parent / "scripts" / "init_memory.py"
        content = script_path.read_text()
        assert content.startswith("#!/usr/bin/env python"), "Script should start with python shebang"

    def test_init_memory_references_adr(self):
        """init_memory.py should reference ADR-002.

        ADR Reference: ADR-002 Phase 4 (Support Scripts)
        """
        script_path = Path(__file__).parent.parent.parent / "scripts" / "init_memory.py"
        content = script_path.read_text()
        assert "ADR-002" in content, "Script should reference ADR-002"

    def test_init_memory_has_force_option(self):
        """init_memory.py should have --force option.

        ADR Reference: ADR-002 Phase 4 (Support Scripts)
        """
        script_path = Path(__file__).parent.parent.parent / "scripts" / "init_memory.py"
        content = script_path.read_text()
        assert "--force" in content, "Script should have --force option"

    def test_init_memory_checks_last_ingest_sha(self):
        """init_memory.py should check last_ingest_sha.

        ADR Reference: ADR-002 Phase 4 (Support Scripts)
        """
        script_path = Path(__file__).parent.parent.parent / "scripts" / "init_memory.py"
        content = script_path.read_text()
        assert "last_ingest_sha" in content, "Script should check last_ingest_sha"

    def test_init_memory_has_bootstrap_function(self):
        """init_memory.py should have bootstrap_memory function.

        ADR Reference: ADR-002 Phase 4 (Support Scripts)
        """
        script_path = Path(__file__).parent.parent.parent / "scripts" / "init_memory.py"
        content = script_path.read_text()
        assert "def bootstrap_memory" in content, "Script should have bootstrap_memory function"

    def test_init_memory_uses_pixeltable_setup(self):
        """init_memory.py should use pixeltable_setup.

        ADR Reference: ADR-002 Phase 4 (Support Scripts)
        """
        script_path = Path(__file__).parent.parent.parent / "scripts" / "init_memory.py"
        content = script_path.read_text()
        assert "pixeltable_setup" in content, "Script should use pixeltable_setup"

    def test_init_memory_creates_directories(self):
        """init_memory.py should create required directories.

        ADR Reference: ADR-002 Phase 4 (Support Scripts)
        """
        script_path = Path(__file__).parent.parent.parent / "scripts" / "init_memory.py"
        content = script_path.read_text()
        assert ".agent" in content, "Should create .agent directories"
        assert "mkdir" in content, "Should create directories"

    def test_init_memory_has_main_guard(self):
        """init_memory.py should have if __name__ == '__main__' guard.

        ADR Reference: ADR-002 Phase 4 (Support Scripts)
        """
        script_path = Path(__file__).parent.parent.parent / "scripts" / "init_memory.py"
        content = script_path.read_text()
        assert '__name__ == "__main__"' in content, "Script should have main guard"
