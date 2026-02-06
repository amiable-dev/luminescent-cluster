# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
TDD: RED Phase - Tests for Single File Ingestion.

These tests define the expected behavior for ingest_file():
- Single file ingestion into Pixeltable KB
- Content hash for idempotency
- Metadata storage (commit_sha, branch, timestamp)
- Filtering based on config
- Secrets protection

Related: ADR-002 Workflow Integration, Phase 1 (Core Infrastructure)
"""

import pytest
import hashlib
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime


def create_git_mock(file_content):
    """Create a mock for subprocess.run that handles git commands.

    Used to simulate git operations in tests without a real git repo.
    Handles: git show, git cat-file -t, git cat-file -s, git branch --show-current

    Note: git show uses text=False (binary mode) so returns bytes,
    while other commands use text=True so return strings.
    """
    def mock_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 0

        if "show" in cmd:
            # git show <commit>:<path> - returns bytes (text=False)
            result.stdout = file_content.encode("utf-8") if isinstance(file_content, str) else file_content
        elif "cat-file" in cmd and "-t" in cmd:
            # git cat-file -t <commit>:<path> - returns object type (text=True)
            result.stdout = "blob"
        elif "cat-file" in cmd and "-s" in cmd:
            # git cat-file -s <commit>:<path> - returns string (text=True)
            content_bytes = file_content.encode("utf-8") if isinstance(file_content, str) else file_content
            result.stdout = str(len(content_bytes))
        elif "branch" in cmd and "--show-current" in cmd:
            result.stdout = "main"
        else:
            result.stdout = ""

        return result
    return mock_run


class TestIngestFileFunction:
    """TDD: Tests for ingest_file function existence and basic behavior."""

    def test_ingest_file_function_exists(self):
        """ingest_file function should be defined.

        ADR Reference: ADR-002 Phase 1 (Core Infrastructure)
        """
        from luminescent_cluster.workflows.ingestion import ingest_file

        assert callable(ingest_file)

    def test_ingest_file_returns_result_dict(self, temp_project_dir, sample_markdown_file):
        """ingest_file should return a dict with success status.

        ADR Reference: ADR-002 Phase 1 (Core Infrastructure)
        """
        from luminescent_cluster.workflows.ingestion import ingest_file

        file_content = sample_markdown_file.read_text()

        with patch("luminescent_cluster.workflows.ingestion.get_knowledge_base") as mock_get_kb, \
             patch("luminescent_cluster.workflows.ingestion.subprocess.run", side_effect=create_git_mock(file_content)):
            mock_kb = MagicMock()
            mock_kb.where.return_value.select.return_value.collect.return_value = []
            mock_get_kb.return_value = mock_kb

            result = ingest_file(
                str(sample_markdown_file),
                commit_sha="abc1234",
                project_root=temp_project_dir
            )

        assert isinstance(result, dict)
        assert "success" in result

    def test_ingest_file_accepts_commit_sha(self, temp_project_dir, sample_markdown_file):
        """ingest_file should accept commit_sha parameter.

        ADR Reference: ADR-002 Phase 1 (Core Infrastructure)
        """
        from luminescent_cluster.workflows.ingestion import ingest_file

        file_content = sample_markdown_file.read_text()

        with patch("luminescent_cluster.workflows.ingestion.get_knowledge_base") as mock_get_kb, \
             patch("luminescent_cluster.workflows.ingestion.subprocess.run", side_effect=create_git_mock(file_content)):
            mock_kb = MagicMock()
            mock_kb.where.return_value.select.return_value.collect.return_value = []
            mock_get_kb.return_value = mock_kb

            result = ingest_file(
                str(sample_markdown_file),
                commit_sha="abc123def456",
                project_root=temp_project_dir
            )

        assert result["success"] is True
        # Should store commit_sha in metadata
        call_args = mock_kb.insert.call_args
        if call_args:
            inserted_data = call_args[0][0][0]
            assert inserted_data["metadata"]["commit_sha"] == "abc123def456"


class TestIngestFileContent:
    """TDD: Tests for ingest_file content handling."""

    def test_ingest_file_reads_file_content(self, temp_project_dir, sample_markdown_file):
        """ingest_file should read and store file content.

        ADR Reference: ADR-002 Phase 1 (Core Infrastructure)
        """
        from luminescent_cluster.workflows.ingestion import ingest_file

        file_content = sample_markdown_file.read_text()

        with patch("luminescent_cluster.workflows.ingestion.get_knowledge_base") as mock_get_kb, \
             patch("luminescent_cluster.workflows.ingestion.subprocess.run", side_effect=create_git_mock(file_content)):
            mock_kb = MagicMock()
            mock_kb.where.return_value.select.return_value.collect.return_value = []
            mock_get_kb.return_value = mock_kb

            ingest_file(
                str(sample_markdown_file),
                commit_sha="abc1234",
                project_root=temp_project_dir
            )

        # Should have called insert with content
        mock_kb.insert.assert_called_once()
        call_args = mock_kb.insert.call_args[0][0][0]
        assert "# Test Document" in call_args["content"]

    def test_ingest_file_stores_relative_path(self, temp_project_dir, sample_markdown_file):
        """ingest_file should store relative path, not absolute.

        ADR Reference: ADR-002 Phase 1 (Core Infrastructure)
        """
        from luminescent_cluster.workflows.ingestion import ingest_file

        file_content = sample_markdown_file.read_text()

        with patch("luminescent_cluster.workflows.ingestion.get_knowledge_base") as mock_get_kb, \
             patch("luminescent_cluster.workflows.ingestion.subprocess.run", side_effect=create_git_mock(file_content)):
            mock_kb = MagicMock()
            mock_kb.where.return_value.select.return_value.collect.return_value = []
            mock_get_kb.return_value = mock_kb

            ingest_file(
                str(sample_markdown_file),
                commit_sha="abc1234",
                project_root=temp_project_dir
            )

        call_args = mock_kb.insert.call_args[0][0][0]
        # Path should be relative (e.g., "docs/test-doc.md")
        assert not call_args["path"].startswith("/")
        assert "docs" in call_args["path"]


class TestIngestFileMetadata:
    """TDD: Tests for ingest_file metadata handling."""

    def test_ingest_file_stores_content_hash(self, temp_project_dir, sample_markdown_file):
        """ingest_file should compute and store content hash for idempotency.

        ADR Reference: ADR-002 Phase 1 (Core Infrastructure)
        """
        from luminescent_cluster.workflows.ingestion import ingest_file

        file_content = sample_markdown_file.read_text()

        with patch("luminescent_cluster.workflows.ingestion.get_knowledge_base") as mock_get_kb, \
             patch("luminescent_cluster.workflows.ingestion.subprocess.run", side_effect=create_git_mock(file_content)):
            mock_kb = MagicMock()
            mock_kb.where.return_value.select.return_value.collect.return_value = []
            mock_get_kb.return_value = mock_kb

            ingest_file(
                str(sample_markdown_file),
                commit_sha="abc1234",
                project_root=temp_project_dir
            )

        call_args = mock_kb.insert.call_args[0][0][0]
        assert "content_hash" in call_args["metadata"]
        # Hash should be a hex string
        assert len(call_args["metadata"]["content_hash"]) == 64  # SHA256 hex length

    def test_ingest_file_stores_branch(self, temp_project_dir, sample_markdown_file):
        """ingest_file should store git branch in metadata.

        ADR Reference: ADR-002 Phase 1 (Core Infrastructure)
        """
        from luminescent_cluster.workflows.ingestion import ingest_file

        file_content = sample_markdown_file.read_text()

        with patch("luminescent_cluster.workflows.ingestion.get_knowledge_base") as mock_get_kb, \
             patch("luminescent_cluster.workflows.ingestion.subprocess.run", side_effect=create_git_mock(file_content)):
            mock_kb = MagicMock()
            mock_kb.where.return_value.select.return_value.collect.return_value = []
            mock_get_kb.return_value = mock_kb

            ingest_file(
                str(sample_markdown_file),
                commit_sha="abc1234",
                project_root=temp_project_dir
            )

        call_args = mock_kb.insert.call_args[0][0][0]
        assert "branch" in call_args["metadata"]

    def test_ingest_file_stores_timestamp(self, temp_project_dir, sample_markdown_file):
        """ingest_file should store ingestion timestamp.

        ADR Reference: ADR-002 Phase 1 (Core Infrastructure)
        """
        from luminescent_cluster.workflows.ingestion import ingest_file

        file_content = sample_markdown_file.read_text()

        with patch("luminescent_cluster.workflows.ingestion.get_knowledge_base") as mock_get_kb, \
             patch("luminescent_cluster.workflows.ingestion.subprocess.run", side_effect=create_git_mock(file_content)):
            mock_kb = MagicMock()
            mock_kb.where.return_value.select.return_value.collect.return_value = []
            mock_get_kb.return_value = mock_kb

            ingest_file(
                str(sample_markdown_file),
                commit_sha="abc1234",
                project_root=temp_project_dir
            )

        call_args = mock_kb.insert.call_args[0][0][0]
        # Should have created_at timestamp
        assert "created_at" in call_args

    def test_ingest_file_sets_correct_type(self, temp_project_dir, sample_markdown_file, sample_adr_file):
        """ingest_file should set correct type based on content/path.

        ADR Reference: ADR-002 Phase 1 (Core Infrastructure)
        """
        from luminescent_cluster.workflows.ingestion import ingest_file

        md_content = sample_markdown_file.read_text()
        adr_content = sample_adr_file.read_text()

        with patch("luminescent_cluster.workflows.ingestion.get_knowledge_base") as mock_get_kb, \
             patch("luminescent_cluster.workflows.ingestion.subprocess.run", side_effect=create_git_mock(md_content)):
            mock_kb = MagicMock()
            mock_kb.where.return_value.select.return_value.collect.return_value = []
            mock_get_kb.return_value = mock_kb

            # Regular markdown should be 'documentation'
            ingest_file(
                str(sample_markdown_file),
                commit_sha="abc1234",
                project_root=temp_project_dir
            )

            call_args = mock_kb.insert.call_args[0][0][0]
            assert call_args["type"] == "documentation"

        # ADR file should be 'decision'
        with patch("luminescent_cluster.workflows.ingestion.get_knowledge_base") as mock_get_kb, \
             patch("luminescent_cluster.workflows.ingestion.subprocess.run", side_effect=create_git_mock(adr_content)):
            mock_kb = MagicMock()
            mock_kb.where.return_value.select.return_value.collect.return_value = []
            mock_get_kb.return_value = mock_kb

            ingest_file(
                str(sample_adr_file),
                commit_sha="abc1234",
                project_root=temp_project_dir
            )

            call_args = mock_kb.insert.call_args[0][0][0]
            assert call_args["type"] == "decision"


class TestIngestFileIdempotency:
    """TDD: Tests for ingest_file idempotency using content hash."""

    def test_ingest_file_skips_duplicate_content(self, temp_project_dir, sample_markdown_file):
        """ingest_file should skip if content hash matches existing entry.

        ADR Reference: ADR-002 Phase 1 (Core Infrastructure)
        """
        from luminescent_cluster.workflows.ingestion import ingest_file

        content = sample_markdown_file.read_text()
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        with patch("luminescent_cluster.workflows.ingestion.get_knowledge_base") as mock_get_kb, \
             patch("luminescent_cluster.workflows.ingestion.subprocess.run", side_effect=create_git_mock(content)):
            mock_kb = MagicMock()
            # Simulate existing entry with same hash
            mock_kb.where.return_value.select.return_value.collect.return_value = [
                {"metadata": {"content_hash": content_hash}}
            ]
            mock_get_kb.return_value = mock_kb

            result = ingest_file(
                str(sample_markdown_file),
                commit_sha="abc1234",
                project_root=temp_project_dir
            )

        assert result["success"] is True
        assert result.get("skipped") is True
        # Should NOT have called insert
        mock_kb.insert.assert_not_called()

    def test_ingest_file_updates_when_content_changes(self, temp_project_dir, sample_markdown_file):
        """ingest_file should update if content hash differs.

        ADR Reference: ADR-002 Phase 1 (Core Infrastructure)
        """
        from luminescent_cluster.workflows.ingestion import ingest_file

        content = sample_markdown_file.read_text()

        with patch("luminescent_cluster.workflows.ingestion.get_knowledge_base") as mock_get_kb, \
             patch("luminescent_cluster.workflows.ingestion.subprocess.run", side_effect=create_git_mock(content)):
            mock_kb = MagicMock()
            # Simulate existing entry with different hash
            mock_kb.where.return_value.select.return_value.collect.return_value = [
                {"metadata": {"content_hash": "different_hash_value"}}
            ]
            mock_get_kb.return_value = mock_kb

            result = ingest_file(
                str(sample_markdown_file),
                commit_sha="abc1234",
                project_root=temp_project_dir
            )

        assert result["success"] is True
        # Should have called insert (upsert behavior)
        assert mock_kb.insert.called or mock_kb.delete.called


class TestIngestFileSecurity:
    """TDD: Tests for ingest_file security features."""

    def test_ingest_file_rejects_path_outside_project(self, temp_project_dir, sample_markdown_file):
        """ingest_file should reject paths that resolve outside project root.

        ADR Reference: ADR-002 Security - Path Traversal Prevention (Council Review)
        """
        from luminescent_cluster.workflows.ingestion import ingest_file

        # Try to ingest a path outside project root using absolute path
        outside_path = Path("/etc/passwd")

        with patch("luminescent_cluster.workflows.ingestion.get_knowledge_base") as mock_get_kb:
            mock_kb = MagicMock()
            mock_get_kb.return_value = mock_kb

            result = ingest_file(
                str(outside_path),
                commit_sha="abc1234",
                project_root=temp_project_dir
            )

        assert result["success"] is False
        assert "outside" in result.get("reason", "").lower()
        mock_kb.insert.assert_not_called()

    def test_ingest_file_reads_from_git_not_working_tree(self, temp_project_dir, sample_markdown_file):
        """ingest_file should read from git object database, not working tree.

        ADR Reference: ADR-002 Security - Provenance Integrity (Council Review)

        We read from git to ensure we ingest exactly what was committed,
        not potentially modified working tree state. Working tree existence
        and symlinks are irrelevant since we use 'git show commit:path'.
        """
        from luminescent_cluster.workflows.ingestion import ingest_file

        file_content = sample_markdown_file.read_text()

        # Create git mock that returns specific content
        git_content = "# Content from Git\n\nThis is what git show returns."

        with patch("luminescent_cluster.workflows.ingestion.get_knowledge_base") as mock_get_kb, \
             patch("luminescent_cluster.workflows.ingestion.subprocess.run", side_effect=create_git_mock(git_content)):
            mock_kb = MagicMock()
            mock_kb.where.return_value.select.return_value.collect.return_value = []
            mock_get_kb.return_value = mock_kb

            result = ingest_file(
                str(sample_markdown_file),
                commit_sha="abc1234",
                project_root=temp_project_dir
            )

        # Should succeed with git content
        assert result["success"] is True
        # The KB should receive the git content, not working tree content
        mock_kb.insert.assert_called_once()
        inserted_record = mock_kb.insert.call_args[0][0][0]
        assert inserted_record["content"] == git_content

    def test_ingest_file_uses_config_secrets_patterns(self, temp_project_dir):
        """ingest_file should use secrets patterns from config.

        ADR Reference: ADR-002 Security - Custom Secrets Patterns (Council Review)
        """
        from luminescent_cluster.workflows.ingestion import ingest_file
        from luminescent_cluster.workflows.config import WorkflowConfig

        # Create a file with a custom pattern that should be blocked
        api_key_file = temp_project_dir / "docs" / "api-keys.md"
        api_key_file.write_text("# API Keys\nSome content")

        # Create config with custom secrets pattern
        config = WorkflowConfig(
            secrets_patterns=[r"api[-_]?key"],  # Custom pattern
        )

        with patch("luminescent_cluster.workflows.ingestion.get_knowledge_base") as mock_get_kb:
            mock_kb = MagicMock()
            mock_get_kb.return_value = mock_kb

            result = ingest_file(
                str(api_key_file),
                commit_sha="abc1234",
                project_root=temp_project_dir,
                config=config
            )

        assert result["success"] is False
        assert result.get("skipped") is True
        mock_kb.insert.assert_not_called()

    def test_ingest_file_rejects_env_file(self, temp_project_dir, sample_secret_file):
        """ingest_file should reject .env files.

        ADR Reference: ADR-002 Security Considerations
        """
        from luminescent_cluster.workflows.ingestion import ingest_file

        with patch("luminescent_cluster.workflows.ingestion.get_knowledge_base") as mock_get_kb:
            mock_kb = MagicMock()
            mock_get_kb.return_value = mock_kb

            result = ingest_file(
                str(sample_secret_file),
                commit_sha="abc1234",
                project_root=temp_project_dir
            )

        assert result["success"] is False
        # May be rejected for secrets pattern or policy exclusion
        reason = result.get("reason", "").lower()
        assert "secret" in reason or "skip" in reason or "excluded" in reason or "policy" in reason
        mock_kb.insert.assert_not_called()

    def test_ingest_file_rejects_key_file(self, temp_project_dir):
        """ingest_file should reject .key files.

        ADR Reference: ADR-002 Security Considerations
        """
        from luminescent_cluster.workflows.ingestion import ingest_file

        key_file = temp_project_dir / "server.key"
        key_file.write_text("-----BEGIN PRIVATE KEY-----\nfake\n-----END PRIVATE KEY-----")

        with patch("luminescent_cluster.workflows.ingestion.get_knowledge_base") as mock_get_kb:
            mock_kb = MagicMock()
            mock_get_kb.return_value = mock_kb

            result = ingest_file(
                str(key_file),
                commit_sha="abc1234",
                project_root=temp_project_dir
            )

        assert result["success"] is False
        mock_kb.insert.assert_not_called()

    def test_ingest_file_rejects_password_file(self, temp_project_dir):
        """ingest_file should reject files with 'password' in name.

        ADR Reference: ADR-002 Security Considerations
        """
        from luminescent_cluster.workflows.ingestion import ingest_file

        pwd_file = temp_project_dir / "passwords.txt"
        pwd_file.write_text("admin:hunter2")

        with patch("luminescent_cluster.workflows.ingestion.get_knowledge_base") as mock_get_kb:
            mock_kb = MagicMock()
            mock_get_kb.return_value = mock_kb

            result = ingest_file(
                str(pwd_file),
                commit_sha="abc1234",
                project_root=temp_project_dir
            )

        assert result["success"] is False
        mock_kb.insert.assert_not_called()


class TestIngestFileErrorHandling:
    """TDD: Tests for ingest_file error handling."""

    def test_ingest_file_handles_missing_file(self, temp_project_dir):
        """ingest_file should handle missing files gracefully.

        ADR Reference: ADR-002 Phase 1 (Core Infrastructure)
        """
        from luminescent_cluster.workflows.ingestion import ingest_file

        with patch("luminescent_cluster.workflows.ingestion.get_knowledge_base") as mock_get_kb:
            mock_kb = MagicMock()
            mock_get_kb.return_value = mock_kb

            result = ingest_file(
                str(temp_project_dir / "nonexistent.md"),
                commit_sha="abc1234",
                project_root=temp_project_dir
            )

        assert result["success"] is False
        assert "error" in result or "reason" in result

    def test_ingest_file_handles_binary_file(self, temp_project_dir):
        """ingest_file should skip binary files.

        ADR Reference: ADR-002 Phase 1 (Core Infrastructure)
        """
        from luminescent_cluster.workflows.ingestion import ingest_file

        binary_file = temp_project_dir / "image.png"
        binary_file.write_bytes(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)

        with patch("luminescent_cluster.workflows.ingestion.get_knowledge_base") as mock_get_kb:
            mock_kb = MagicMock()
            mock_get_kb.return_value = mock_kb

            result = ingest_file(
                str(binary_file),
                commit_sha="abc1234",
                project_root=temp_project_dir
            )

        # Should skip binary files
        assert result["success"] is False or result.get("skipped") is True
        mock_kb.insert.assert_not_called()

    def test_ingest_file_handles_large_file(self, temp_project_dir):
        """ingest_file should skip files exceeding max_file_size_kb.

        ADR Reference: ADR-002 Phase 1 (Core Infrastructure)
        """
        from luminescent_cluster.workflows.ingestion import ingest_file

        # Create a file larger than default limit (500KB)
        large_file = temp_project_dir / "large.md"
        large_file.write_text("# Large\n" + "x" * (600 * 1024))

        with patch("luminescent_cluster.workflows.ingestion.get_knowledge_base") as mock_get_kb:
            mock_kb = MagicMock()
            mock_get_kb.return_value = mock_kb

            result = ingest_file(
                str(large_file),
                commit_sha="abc1234",
                project_root=temp_project_dir
            )

        # Should skip large files
        assert result["success"] is False or result.get("skipped") is True


class TestComputeContentHash:
    """TDD: Tests for compute_content_hash helper function."""

    def test_compute_content_hash_exists(self):
        """compute_content_hash function should be defined.

        ADR Reference: ADR-002 Phase 1 (Core Infrastructure)
        """
        from luminescent_cluster.workflows.ingestion import compute_content_hash

        assert callable(compute_content_hash)

    def test_compute_content_hash_returns_sha256(self):
        """compute_content_hash should return SHA256 hex digest.

        ADR Reference: ADR-002 Phase 1 (Core Infrastructure)
        """
        from luminescent_cluster.workflows.ingestion import compute_content_hash

        result = compute_content_hash("test content")

        assert isinstance(result, str)
        assert len(result) == 64  # SHA256 hex length
        # Should match direct hashlib computation
        expected = hashlib.sha256("test content".encode()).hexdigest()
        assert result == expected

    def test_compute_content_hash_is_deterministic(self):
        """compute_content_hash should return same hash for same content.

        ADR Reference: ADR-002 Phase 1 (Core Infrastructure)
        """
        from luminescent_cluster.workflows.ingestion import compute_content_hash

        hash1 = compute_content_hash("same content")
        hash2 = compute_content_hash("same content")

        assert hash1 == hash2

    def test_compute_content_hash_differs_for_different_content(self):
        """compute_content_hash should return different hash for different content.

        ADR Reference: ADR-002 Phase 1 (Core Infrastructure)
        """
        from luminescent_cluster.workflows.ingestion import compute_content_hash

        hash1 = compute_content_hash("content a")
        hash2 = compute_content_hash("content b")

        assert hash1 != hash2
