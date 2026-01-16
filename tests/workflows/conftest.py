# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
Shared fixtures for workflow integration tests.

Related: ADR-002 Workflow Integration
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch


@pytest.fixture
def temp_project_dir(tmp_path):
    """Create a temporary project directory with .agent structure."""
    # Create .agent directory structure
    agent_dir = tmp_path / ".agent"
    agent_dir.mkdir()
    (agent_dir / "state").mkdir()
    (agent_dir / "logs").mkdir()
    (agent_dir / "hooks").mkdir()

    # Create .git directory (simulated)
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "hooks").mkdir()

    # Create docs directory
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "adrs").mkdir()

    return tmp_path


@pytest.fixture
def sample_config_yaml():
    """Sample .agent/config.yaml content."""
    return """
# ADR-002: Ingestion policy for git hook automation
ingestion:
  include:
    - "docs/**/*.md"
    - "*.md"
    - "docs/adrs/**"
  exclude:
    - "**/node_modules/**"
    - "**/.venv/**"
    - "**/dist/**"
    - "**/build/**"
    - "**/__pycache__/**"
    - "**/*.pyc"
    - "**/.env"
    - "**/*.key"
    - "**/*.pem"
    - "**/secrets/**"
    - "**/*secret*"
    - "**/*password*"
    - "**/*token*"
    - "**/*credential*"
  max_file_size_kb: 500
  skip_binary: true

skills:
  directory: ".claude/skills"
  auto_discover: true
"""


@pytest.fixture
def sample_markdown_file(temp_project_dir):
    """Create a sample markdown file for testing."""
    md_file = temp_project_dir / "docs" / "test-doc.md"
    md_file.write_text("# Test Document\n\nThis is a test document for ingestion.")
    return md_file


@pytest.fixture
def sample_adr_file(temp_project_dir):
    """Create a sample ADR file for testing."""
    adr_file = temp_project_dir / "docs" / "adrs" / "ADR-001-test.md"
    adr_file.write_text("""# ADR-001: Test Decision

## Status
Accepted

## Context
This is a test ADR.

## Decision
We decided to test.
""")
    return adr_file


@pytest.fixture
def sample_secret_file(temp_project_dir):
    """Create a sample secrets file that should be excluded."""
    secret_file = temp_project_dir / ".env"
    secret_file.write_text("API_KEY=super_secret_key\nPASSWORD=hunter2")
    return secret_file


@pytest.fixture
def mock_pixeltable_kb():
    """Mock Pixeltable knowledge base for testing."""
    with patch("pixeltable_setup.setup_knowledge_base") as mock_setup:
        mock_kb = MagicMock()
        mock_kb.insert = MagicMock()
        mock_kb.where = MagicMock(return_value=mock_kb)
        mock_kb.select = MagicMock(return_value=mock_kb)
        mock_kb.collect = MagicMock(return_value=[])
        mock_setup.return_value = mock_kb
        yield mock_kb


@pytest.fixture
def mock_git_commands(temp_project_dir, sample_markdown_file):
    """Mock git commands for testing.

    This fixture mocks git commands so tests work without a real git repo.
    It handles: rev-parse, branch, diff-tree, show (for content), cat-file -t/-s

    Note: git show uses text=False (binary mode) so returns bytes,
    while other commands use text=True so return strings.
    """
    # Read the sample content for git show mocking
    sample_content = sample_markdown_file.read_text() if sample_markdown_file.exists() else "# Test"

    def mock_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 0

        if "rev-parse" in cmd and "HEAD" in cmd:
            result.stdout = "abc123def456"
        elif "rev-parse" in cmd and "--show-toplevel" in cmd:
            result.stdout = str(temp_project_dir)
        elif "branch" in cmd and "--show-current" in cmd:
            result.stdout = "main"
        elif "diff-tree" in cmd:
            result.stdout = ""
        elif "show" in cmd:
            # git show <commit>:<path> - return bytes (text=False)
            result.stdout = sample_content.encode("utf-8")
        elif "cat-file" in cmd and "-t" in cmd:
            # git cat-file -t <commit>:<path> - return object type
            result.stdout = "blob"
        elif "cat-file" in cmd and "-s" in cmd:
            # git cat-file -s <commit>:<path> - return file size as string (text=True)
            result.stdout = str(len(sample_content.encode("utf-8")))
        else:
            result.stdout = ""

        return result

    return mock_run


@pytest.fixture
def mock_git_for_ingestion(temp_project_dir):
    """Context manager fixture to mock all git calls in ingestion module.

    Note: git show uses text=False (binary mode) so returns bytes,
    while other commands use text=True so return strings.
    """
    def create_mock(file_content="# Test Document\n\nThis is a test document for ingestion."):
        def mock_run(cmd, **kwargs):
            result = MagicMock()
            result.returncode = 0

            if "show" in cmd:
                # git show returns bytes (text=False)
                content_bytes = file_content.encode("utf-8") if isinstance(file_content, str) else file_content
                result.stdout = content_bytes
            elif "cat-file" in cmd and "-t" in cmd:
                # git cat-file -t returns object type
                result.stdout = "blob"
            elif "cat-file" in cmd and "-s" in cmd:
                # git cat-file -s returns string (text=True)
                content_bytes = file_content.encode("utf-8") if isinstance(file_content, str) else file_content
                result.stdout = str(len(content_bytes))
            elif "branch" in cmd and "--show-current" in cmd:
                result.stdout = "main"
            else:
                result.stdout = ""

            return result
        return mock_run

    return create_mock
