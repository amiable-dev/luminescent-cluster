# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
TDD: RED Phase - Tests for Workflow Config Parser.

These tests define the expected behavior for parsing .agent/config.yaml:
- Loading config from file
- Default values when config is missing
- Include/exclude pattern matching
- File size limits
- Secrets detection

Related: ADR-002 Workflow Integration, Phase 1 (Core Infrastructure)
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestWorkflowConfig:
    """TDD: Tests for WorkflowConfig dataclass."""

    def test_workflow_config_class_exists(self):
        """WorkflowConfig class should be defined.

        ADR Reference: ADR-002 Phase 1 (Core Infrastructure)
        """
        from luminescent_cluster.workflows.config import WorkflowConfig

        assert WorkflowConfig is not None

    def test_workflow_config_has_include_patterns(self):
        """WorkflowConfig should have include_patterns attribute.

        ADR Reference: ADR-002 Phase 1 (Core Infrastructure)
        """
        from luminescent_cluster.workflows.config import WorkflowConfig

        config = WorkflowConfig()
        assert hasattr(config, "include_patterns")
        assert isinstance(config.include_patterns, list)

    def test_workflow_config_has_exclude_patterns(self):
        """WorkflowConfig should have exclude_patterns attribute.

        ADR Reference: ADR-002 Phase 1 (Core Infrastructure)
        """
        from luminescent_cluster.workflows.config import WorkflowConfig

        config = WorkflowConfig()
        assert hasattr(config, "exclude_patterns")
        assert isinstance(config.exclude_patterns, list)

    def test_workflow_config_has_max_file_size(self):
        """WorkflowConfig should have max_file_size_kb attribute.

        ADR Reference: ADR-002 Phase 1 (Core Infrastructure)
        """
        from luminescent_cluster.workflows.config import WorkflowConfig

        config = WorkflowConfig()
        assert hasattr(config, "max_file_size_kb")
        assert isinstance(config.max_file_size_kb, int)

    def test_workflow_config_has_skip_binary(self):
        """WorkflowConfig should have skip_binary attribute.

        ADR Reference: ADR-002 Phase 1 (Core Infrastructure)
        """
        from luminescent_cluster.workflows.config import WorkflowConfig

        config = WorkflowConfig()
        assert hasattr(config, "skip_binary")
        assert isinstance(config.skip_binary, bool)

    def test_workflow_config_has_secrets_patterns(self):
        """WorkflowConfig should have secrets_patterns for security.

        ADR Reference: ADR-002 Security Considerations
        """
        from luminescent_cluster.workflows.config import WorkflowConfig

        config = WorkflowConfig()
        assert hasattr(config, "secrets_patterns")
        assert isinstance(config.secrets_patterns, list)
        # Should include common secret file patterns
        patterns_str = " ".join(config.secrets_patterns).lower()
        assert ".env" in patterns_str or "env" in patterns_str


class TestLoadConfig:
    """TDD: Tests for load_config function."""

    def test_load_config_function_exists(self):
        """load_config function should be defined.

        ADR Reference: ADR-002 Phase 1 (Core Infrastructure)
        """
        from luminescent_cluster.workflows.config import load_config

        assert callable(load_config)

    def test_load_config_returns_workflow_config(self, temp_project_dir, sample_config_yaml):
        """load_config should return a WorkflowConfig instance.

        ADR Reference: ADR-002 Phase 1 (Core Infrastructure)
        """
        from luminescent_cluster.workflows.config import load_config, WorkflowConfig

        # Write config file
        config_file = temp_project_dir / ".agent" / "config.yaml"
        config_file.write_text(sample_config_yaml)

        result = load_config(temp_project_dir)

        assert isinstance(result, WorkflowConfig)

    def test_load_config_returns_defaults_when_missing(self, temp_project_dir):
        """load_config should return defaults when config.yaml is missing.

        ADR Reference: ADR-002 Phase 1 (Core Infrastructure)
        """
        from luminescent_cluster.workflows.config import load_config, WorkflowConfig

        result = load_config(temp_project_dir)

        assert isinstance(result, WorkflowConfig)
        # Should have sensible defaults
        assert len(result.include_patterns) > 0
        assert len(result.exclude_patterns) > 0

    def test_load_config_parses_include_patterns(self, temp_project_dir, sample_config_yaml):
        """load_config should parse include patterns from config.

        ADR Reference: ADR-002 Phase 1 (Core Infrastructure)
        """
        from luminescent_cluster.workflows.config import load_config

        config_file = temp_project_dir / ".agent" / "config.yaml"
        config_file.write_text(sample_config_yaml)

        result = load_config(temp_project_dir)

        assert "docs/**/*.md" in result.include_patterns
        assert "*.md" in result.include_patterns

    def test_load_config_parses_exclude_patterns(self, temp_project_dir, sample_config_yaml):
        """load_config should parse exclude patterns from config.

        ADR Reference: ADR-002 Phase 1 (Core Infrastructure)
        """
        from luminescent_cluster.workflows.config import load_config

        config_file = temp_project_dir / ".agent" / "config.yaml"
        config_file.write_text(sample_config_yaml)

        result = load_config(temp_project_dir)

        assert "**/node_modules/**" in result.exclude_patterns
        assert "**/.venv/**" in result.exclude_patterns

    def test_load_config_parses_max_file_size(self, temp_project_dir, sample_config_yaml):
        """load_config should parse max_file_size_kb from config.

        ADR Reference: ADR-002 Phase 1 (Core Infrastructure)
        """
        from luminescent_cluster.workflows.config import load_config

        config_file = temp_project_dir / ".agent" / "config.yaml"
        config_file.write_text(sample_config_yaml)

        result = load_config(temp_project_dir)

        assert result.max_file_size_kb == 500


class TestShouldIngestFile:
    """TDD: Tests for should_ingest_file function."""

    def test_should_ingest_file_function_exists(self):
        """should_ingest_file function should be defined.

        ADR Reference: ADR-002 Phase 1 (Core Infrastructure)
        """
        from luminescent_cluster.workflows.config import should_ingest_file

        assert callable(should_ingest_file)

    def test_should_ingest_markdown_file(self, temp_project_dir, sample_config_yaml):
        """should_ingest_file should return True for markdown files.

        ADR Reference: ADR-002 Phase 1 (Core Infrastructure)
        """
        from luminescent_cluster.workflows.config import load_config, should_ingest_file

        config_file = temp_project_dir / ".agent" / "config.yaml"
        config_file.write_text(sample_config_yaml)
        config = load_config(temp_project_dir)

        result = should_ingest_file("docs/readme.md", config)

        assert result is True

    def test_should_not_ingest_node_modules(self, temp_project_dir, sample_config_yaml):
        """should_ingest_file should return False for node_modules.

        ADR Reference: ADR-002 Phase 1 (Core Infrastructure)
        """
        from luminescent_cluster.workflows.config import load_config, should_ingest_file

        config_file = temp_project_dir / ".agent" / "config.yaml"
        config_file.write_text(sample_config_yaml)
        config = load_config(temp_project_dir)

        result = should_ingest_file("node_modules/package/readme.md", config)

        assert result is False

    def test_should_not_ingest_venv(self, temp_project_dir, sample_config_yaml):
        """should_ingest_file should return False for .venv files.

        ADR Reference: ADR-002 Phase 1 (Core Infrastructure)
        """
        from luminescent_cluster.workflows.config import load_config, should_ingest_file

        config_file = temp_project_dir / ".agent" / "config.yaml"
        config_file.write_text(sample_config_yaml)
        config = load_config(temp_project_dir)

        result = should_ingest_file(".venv/lib/readme.md", config)

        assert result is False

    def test_should_not_ingest_env_file(self, temp_project_dir, sample_config_yaml):
        """should_ingest_file should return False for .env files.

        ADR Reference: ADR-002 Security Considerations
        """
        from luminescent_cluster.workflows.config import load_config, should_ingest_file

        config_file = temp_project_dir / ".agent" / "config.yaml"
        config_file.write_text(sample_config_yaml)
        config = load_config(temp_project_dir)

        result = should_ingest_file(".env", config)

        assert result is False

    def test_should_not_ingest_key_file(self, temp_project_dir, sample_config_yaml):
        """should_ingest_file should return False for .key files.

        ADR Reference: ADR-002 Security Considerations
        """
        from luminescent_cluster.workflows.config import load_config, should_ingest_file

        config_file = temp_project_dir / ".agent" / "config.yaml"
        config_file.write_text(sample_config_yaml)
        config = load_config(temp_project_dir)

        result = should_ingest_file("certs/server.key", config)

        assert result is False

    def test_should_not_ingest_secret_file(self, temp_project_dir, sample_config_yaml):
        """should_ingest_file should return False for files with 'secret' in name.

        ADR Reference: ADR-002 Security Considerations
        """
        from luminescent_cluster.workflows.config import load_config, should_ingest_file

        config_file = temp_project_dir / ".agent" / "config.yaml"
        config_file.write_text(sample_config_yaml)
        config = load_config(temp_project_dir)

        result = should_ingest_file("config/secrets.yaml", config)

        assert result is False

    def test_should_ingest_adr_file(self, temp_project_dir, sample_config_yaml):
        """should_ingest_file should return True for ADR files.

        ADR Reference: ADR-002 Phase 1 (Core Infrastructure)
        """
        from luminescent_cluster.workflows.config import load_config, should_ingest_file

        config_file = temp_project_dir / ".agent" / "config.yaml"
        config_file.write_text(sample_config_yaml)
        config = load_config(temp_project_dir)

        result = should_ingest_file("docs/adrs/ADR-002-workflow.md", config)

        assert result is True


class TestIsSecretFile:
    """TDD: Tests for is_secret_file function."""

    def test_is_secret_file_function_exists(self):
        """is_secret_file function should be defined.

        ADR Reference: ADR-002 Security Considerations
        """
        from luminescent_cluster.workflows.config import is_secret_file

        assert callable(is_secret_file)

    def test_env_file_is_secret(self):
        """is_secret_file should return True for .env files.

        ADR Reference: ADR-002 Security Considerations
        """
        from luminescent_cluster.workflows.config import is_secret_file

        assert is_secret_file(".env") is True
        assert is_secret_file("config/.env") is True
        assert is_secret_file(".env.local") is True

    def test_key_file_is_secret(self):
        """is_secret_file should return True for .key files.

        ADR Reference: ADR-002 Security Considerations
        """
        from luminescent_cluster.workflows.config import is_secret_file

        assert is_secret_file("server.key") is True
        assert is_secret_file("certs/private.key") is True

    def test_pem_file_is_secret(self):
        """is_secret_file should return True for .pem files.

        ADR Reference: ADR-002 Security Considerations
        """
        from luminescent_cluster.workflows.config import is_secret_file

        assert is_secret_file("cert.pem") is True
        assert is_secret_file("certs/ca.pem") is True

    def test_password_file_is_secret(self):
        """is_secret_file should return True for files with 'password' in name.

        ADR Reference: ADR-002 Security Considerations
        """
        from luminescent_cluster.workflows.config import is_secret_file

        assert is_secret_file("passwords.txt") is True
        assert is_secret_file("config/db_password.yaml") is True

    def test_token_file_is_secret(self):
        """is_secret_file should return True for files with 'token' in name.

        ADR Reference: ADR-002 Security Considerations
        """
        from luminescent_cluster.workflows.config import is_secret_file

        assert is_secret_file("api_token.txt") is True
        assert is_secret_file("tokens.json") is True

    def test_credential_file_is_secret(self):
        """is_secret_file should return True for files with 'credential' in name.

        ADR Reference: ADR-002 Security Considerations
        """
        from luminescent_cluster.workflows.config import is_secret_file

        assert is_secret_file("credentials.json") is True
        assert is_secret_file("gcloud_credentials.json") is True

    def test_regular_markdown_is_not_secret(self):
        """is_secret_file should return False for regular markdown files.

        ADR Reference: ADR-002 Security Considerations
        """
        from luminescent_cluster.workflows.config import is_secret_file

        assert is_secret_file("docs/readme.md") is False
        assert is_secret_file("docs/adrs/ADR-001.md") is False

    def test_regular_python_is_not_secret(self):
        """is_secret_file should return False for regular python files.

        ADR Reference: ADR-002 Security Considerations
        """
        from luminescent_cluster.workflows.config import is_secret_file

        assert is_secret_file("src/main.py") is False
        assert is_secret_file("tests/test_config.py") is False
