# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
TDD: Tests for Git Hooks (ADR-002 Phase 2).

These tests verify that the git hooks:
- post-commit: Ingests changed documentation files
- post-merge: Delegates to post-commit
- post-rewrite: Clears ingestion state

Related: ADR-002 Workflow Integration, Phase 2 (Git Hooks)
"""

import os
import stat
import subprocess
from pathlib import Path

import pytest


class TestHookFilesExist:
    """TDD: Tests that hook files exist with correct permissions."""

    def test_post_commit_hook_exists(self):
        """post-commit hook file should exist.

        ADR Reference: ADR-002 Phase 2 (Git Hooks)
        """
        hook_path = Path(__file__).parent.parent.parent / ".agent" / "hooks" / "post-commit"
        assert hook_path.exists(), f"Hook not found at {hook_path}"

    def test_post_merge_hook_exists(self):
        """post-merge hook file should exist.

        ADR Reference: ADR-002 Phase 2 (Git Hooks)
        """
        hook_path = Path(__file__).parent.parent.parent / ".agent" / "hooks" / "post-merge"
        assert hook_path.exists(), f"Hook not found at {hook_path}"

    def test_post_rewrite_hook_exists(self):
        """post-rewrite hook file should exist.

        ADR Reference: ADR-002 Phase 2 (Git Hooks)
        """
        hook_path = Path(__file__).parent.parent.parent / ".agent" / "hooks" / "post-rewrite"
        assert hook_path.exists(), f"Hook not found at {hook_path}"

    def test_post_commit_is_executable(self):
        """post-commit hook should be executable.

        ADR Reference: ADR-002 Phase 2 (Git Hooks)
        """
        hook_path = Path(__file__).parent.parent.parent / ".agent" / "hooks" / "post-commit"
        mode = hook_path.stat().st_mode
        assert mode & stat.S_IXUSR, "post-commit should be executable by owner"

    def test_post_merge_is_executable(self):
        """post-merge hook should be executable.

        ADR Reference: ADR-002 Phase 2 (Git Hooks)
        """
        hook_path = Path(__file__).parent.parent.parent / ".agent" / "hooks" / "post-merge"
        mode = hook_path.stat().st_mode
        assert mode & stat.S_IXUSR, "post-merge should be executable by owner"

    def test_post_rewrite_is_executable(self):
        """post-rewrite hook should be executable.

        ADR Reference: ADR-002 Phase 2 (Git Hooks)
        """
        hook_path = Path(__file__).parent.parent.parent / ".agent" / "hooks" / "post-rewrite"
        mode = hook_path.stat().st_mode
        assert mode & stat.S_IXUSR, "post-rewrite should be executable by owner"


class TestHookContent:
    """TDD: Tests for hook script content."""

    def test_post_commit_has_shebang(self):
        """post-commit should start with bash shebang.

        ADR Reference: ADR-002 Phase 2 (Git Hooks)
        """
        hook_path = Path(__file__).parent.parent.parent / ".agent" / "hooks" / "post-commit"
        content = hook_path.read_text()
        assert content.startswith("#!/bin/bash"), "Hook should start with bash shebang"

    def test_post_commit_uses_pipefail(self):
        """post-commit should use set -euo pipefail for safety.

        ADR Reference: ADR-002 Phase 2 (Git Hooks)
        """
        hook_path = Path(__file__).parent.parent.parent / ".agent" / "hooks" / "post-commit"
        content = hook_path.read_text()
        assert "set -euo pipefail" in content, "Hook should use strict mode"

    def test_post_commit_references_ingest_file(self):
        """post-commit should call ingest_file function.

        ADR Reference: ADR-002 Phase 2 (Git Hooks)
        """
        hook_path = Path(__file__).parent.parent.parent / ".agent" / "hooks" / "post-commit"
        content = hook_path.read_text()
        assert "ingest_file" in content, "Hook should call ingest_file"

    def test_post_commit_logs_to_agent_logs(self):
        """post-commit should log to .agent/logs/ingestion.log.

        ADR Reference: ADR-002 Phase 2 (Git Hooks)
        """
        hook_path = Path(__file__).parent.parent.parent / ".agent" / "hooks" / "post-commit"
        content = hook_path.read_text()
        assert ".agent/logs/ingestion.log" in content, "Hook should log to .agent/logs"

    def test_post_commit_writes_last_ingest_sha(self):
        """post-commit should write last_ingest_sha state file.

        ADR Reference: ADR-002 Phase 2 (Git Hooks)
        """
        hook_path = Path(__file__).parent.parent.parent / ".agent" / "hooks" / "post-commit"
        content = hook_path.read_text()
        assert "last_ingest_sha" in content, "Hook should write last_ingest_sha"

    def test_post_commit_filters_secrets(self):
        """post-commit should filter out secrets files.

        ADR Reference: ADR-002 Security Considerations
        """
        hook_path = Path(__file__).parent.parent.parent / ".agent" / "hooks" / "post-commit"
        content = hook_path.read_text()
        # Should have secrets pattern checking
        assert "secret" in content.lower(), "Hook should filter secrets"
        assert ".env" in content, "Hook should filter .env files"

    def test_post_commit_runs_async(self):
        """post-commit should run ingestion asynchronously.

        ADR Reference: ADR-002 Phase 2 (Git Hooks)
        """
        hook_path = Path(__file__).parent.parent.parent / ".agent" / "hooks" / "post-commit"
        content = hook_path.read_text()
        # Should have & at end of subshell for async
        assert ") &" in content, "Hook should run async (background)"

    def test_post_merge_delegates_to_post_commit(self):
        """post-merge should delegate to post-commit.

        ADR Reference: ADR-002 Phase 2 (Git Hooks)
        """
        hook_path = Path(__file__).parent.parent.parent / ".agent" / "hooks" / "post-merge"
        content = hook_path.read_text()
        assert "post-commit" in content, "post-merge should delegate to post-commit"

    def test_post_rewrite_clears_state(self):
        """post-rewrite should clear last_ingest_sha.

        ADR Reference: ADR-002 Phase 2 (Git Hooks)
        """
        hook_path = Path(__file__).parent.parent.parent / ".agent" / "hooks" / "post-rewrite"
        content = hook_path.read_text()
        assert "rm" in content and "last_ingest_sha" in content, "Hook should remove last_ingest_sha"


class TestConfigFileExists:
    """TDD: Tests that .agent/config.yaml exists."""

    def test_config_yaml_exists(self):
        """config.yaml should exist in .agent directory.

        ADR Reference: ADR-002 Phase 2 (Git Hooks)
        """
        config_path = Path(__file__).parent.parent.parent / ".agent" / "config.yaml"
        assert config_path.exists(), f"Config not found at {config_path}"

    def test_config_yaml_has_ingestion_section(self):
        """config.yaml should have ingestion section.

        ADR Reference: ADR-002 Phase 2 (Git Hooks)
        """
        import yaml

        config_path = Path(__file__).parent.parent.parent / ".agent" / "config.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)

        assert "ingestion" in config, "Config should have 'ingestion' section"

    def test_config_yaml_has_include_patterns(self):
        """config.yaml should have include patterns.

        ADR Reference: ADR-002 Phase 2 (Git Hooks)
        """
        import yaml

        config_path = Path(__file__).parent.parent.parent / ".agent" / "config.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)

        assert "include" in config["ingestion"], "Config should have 'include' patterns"
        assert len(config["ingestion"]["include"]) > 0, "Should have at least one include pattern"

    def test_config_yaml_has_exclude_patterns(self):
        """config.yaml should have exclude patterns.

        ADR Reference: ADR-002 Phase 2 (Git Hooks)
        """
        import yaml

        config_path = Path(__file__).parent.parent.parent / ".agent" / "config.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)

        assert "exclude" in config["ingestion"], "Config should have 'exclude' patterns"
        assert len(config["ingestion"]["exclude"]) > 0, "Should have at least one exclude pattern"

    def test_config_yaml_excludes_env_files(self):
        """config.yaml should exclude .env files.

        ADR Reference: ADR-002 Security Considerations
        """
        import yaml

        config_path = Path(__file__).parent.parent.parent / ".agent" / "config.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)

        exclude_patterns = " ".join(config["ingestion"]["exclude"])
        assert ".env" in exclude_patterns, "Should exclude .env files"

    def test_config_yaml_excludes_key_files(self):
        """config.yaml should exclude .key files.

        ADR Reference: ADR-002 Security Considerations
        """
        import yaml

        config_path = Path(__file__).parent.parent.parent / ".agent" / "config.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)

        exclude_patterns = " ".join(config["ingestion"]["exclude"])
        assert ".key" in exclude_patterns, "Should exclude .key files"
