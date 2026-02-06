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
Tests for GitHub PAT integration (ADR-005 FREE tier).

These tests verify the GitHub Personal Access Token integration
works correctly for read-only repository access.
"""

import pytest
import os
import json
import base64
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError

from luminescent_cluster.integrations.github_pat import (
    GitHubPATClient,
    GitHubFile,
    GitHubCommit,
    GitHubPullRequest,
    GitHubAuthError,
    GitHubRateLimitError,
    GitHubNotFoundError,
    GitHubPATError,
)


class TestGitHubPATClientInit:
    """Tests for GitHubPATClient initialization."""

    def test_init_with_explicit_token(self):
        """Client should accept token via constructor."""
        client = GitHubPATClient(token="test_token")
        assert client.token == "test_token"

    def test_init_from_github_token_env(self):
        """Client should read from GITHUB_TOKEN env var."""
        with patch.dict(os.environ, {"GITHUB_TOKEN": "env_token"}):
            client = GitHubPATClient()
            assert client.token == "env_token"

    def test_init_from_github_pat_env(self):
        """Client should read from GITHUB_PAT env var as fallback."""
        with patch.dict(os.environ, {"GITHUB_PAT": "pat_token"}, clear=True):
            # Clear GITHUB_TOKEN if it exists
            os.environ.pop("GITHUB_TOKEN", None)
            client = GitHubPATClient()
            assert client.token == "pat_token"

    def test_init_raises_without_token(self):
        """Client should raise GitHubAuthError if no token available."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("GITHUB_TOKEN", None)
            os.environ.pop("GITHUB_PAT", None)
            with pytest.raises(GitHubAuthError) as exc_info:
                GitHubPATClient()
            assert "No GitHub token provided" in str(exc_info.value)


class TestGitHubPATClientRequests:
    """Tests for GitHub API request handling."""

    @pytest.fixture
    def client(self):
        """Create a client with test token."""
        return GitHubPATClient(token="test_token")

    @pytest.fixture
    def mock_response(self):
        """Create mock response helper."""
        def _mock_response(data, status=200):
            mock = MagicMock()
            mock.read.return_value = json.dumps(data).encode("utf-8")
            mock.__enter__ = MagicMock(return_value=mock)
            mock.__exit__ = MagicMock(return_value=False)
            return mock
        return _mock_response

    def test_request_includes_auth_header(self, client, mock_response):
        """Request should include Bearer token in Authorization header."""
        with patch("luminescent_cluster.integrations.github_pat.urlopen") as mock_urlopen:
            mock_urlopen.return_value = mock_response({"test": "data"})

            client._request("/test")

            # Check the request object
            call_args = mock_urlopen.call_args
            request = call_args[0][0]
            assert "Bearer test_token" in request.get_header("Authorization")

    def test_request_includes_user_agent(self, client, mock_response):
        """Request should include User-Agent header."""
        with patch("luminescent_cluster.integrations.github_pat.urlopen") as mock_urlopen:
            mock_urlopen.return_value = mock_response({"test": "data"})

            client._request("/test")

            request = mock_urlopen.call_args[0][0]
            assert "LuminescentCluster" in request.get_header("User-agent")

    def test_request_handles_401_as_auth_error(self, client):
        """401 response should raise GitHubAuthError."""
        with patch("luminescent_cluster.integrations.github_pat.urlopen") as mock_urlopen:
            mock_error = HTTPError(
                url="https://api.github.com/test",
                code=401,
                msg="Unauthorized",
                hdrs={},
                fp=MagicMock()
            )
            mock_urlopen.side_effect = mock_error

            with pytest.raises(GitHubAuthError):
                client._request("/test")

    def test_request_handles_404_as_not_found(self, client):
        """404 response should raise GitHubNotFoundError."""
        with patch("luminescent_cluster.integrations.github_pat.urlopen") as mock_urlopen:
            mock_error = HTTPError(
                url="https://api.github.com/test",
                code=404,
                msg="Not Found",
                hdrs={},
                fp=MagicMock()
            )
            mock_urlopen.side_effect = mock_error

            with pytest.raises(GitHubNotFoundError):
                client._request("/test")

    def test_request_handles_rate_limit(self, client):
        """403 with rate limit message should raise GitHubRateLimitError."""
        with patch("luminescent_cluster.integrations.github_pat.urlopen") as mock_urlopen:
            mock_fp = MagicMock()
            mock_fp.read.return_value = b"API rate limit exceeded"
            mock_error = HTTPError(
                url="https://api.github.com/test",
                code=403,
                msg="Forbidden",
                hdrs={},
                fp=mock_fp
            )
            mock_urlopen.side_effect = mock_error

            with pytest.raises(GitHubRateLimitError):
                client._request("/test")


class TestGitHubPATClientRepositoryOperations:
    """Tests for repository-level operations."""

    @pytest.fixture
    def client(self):
        """Create a client with test token."""
        return GitHubPATClient(token="test_token")

    def test_get_repository(self, client):
        """get_repository should return repo metadata."""
        mock_data = {
            "name": "test-repo",
            "full_name": "owner/test-repo",
            "default_branch": "main",
        }

        with patch.object(client, "_request", return_value=mock_data):
            result = client.get_repository("owner/test-repo")

            assert result["name"] == "test-repo"
            assert result["full_name"] == "owner/test-repo"

    def test_list_contents_returns_files(self, client):
        """list_contents should return list of GitHubFile objects."""
        mock_data = [
            {"path": "README.md", "name": "README.md", "sha": "abc123", "size": 100, "type": "file"},
            {"path": "src", "name": "src", "sha": "def456", "size": 0, "type": "dir"},
        ]

        with patch.object(client, "_request", return_value=mock_data):
            result = client.list_contents("owner/repo")

            assert len(result) == 2
            assert isinstance(result[0], GitHubFile)
            assert result[0].path == "README.md"
            assert result[0].type == "file"
            assert result[1].type == "dir"

    def test_list_contents_handles_single_file(self, client):
        """list_contents should handle single file response (dict instead of list)."""
        mock_data = {"path": "README.md", "name": "README.md", "sha": "abc123", "size": 100, "type": "file"}

        with patch.object(client, "_request", return_value=mock_data):
            result = client.list_contents("owner/repo", "README.md")

            assert len(result) == 1
            assert result[0].name == "README.md"

    def test_list_contents_with_ref(self, client):
        """list_contents should pass ref parameter."""
        with patch.object(client, "_request", return_value=[]) as mock_request:
            client.list_contents("owner/repo", "src", ref="develop")

            mock_request.assert_called_once()
            call_arg = mock_request.call_args[0][0]
            assert "ref=develop" in call_arg


class TestGitHubPATClientFileOperations:
    """Tests for file content operations."""

    @pytest.fixture
    def client(self):
        """Create a client with test token."""
        return GitHubPATClient(token="test_token")

    def test_get_file_content_decodes_base64(self, client):
        """get_file_content should decode base64 content."""
        content = "Hello, World!"
        encoded = base64.b64encode(content.encode()).decode()
        mock_data = {
            "type": "file",
            "content": encoded,
            "encoding": "base64",
        }

        with patch.object(client, "_request", return_value=mock_data):
            result = client.get_file_content("owner/repo", "test.txt")

            assert result == "Hello, World!"

    def test_get_file_content_handles_newlines_in_base64(self, client):
        """get_file_content should strip newlines from base64 content."""
        content = "Hello, World!"
        encoded = base64.b64encode(content.encode()).decode()
        # Add newlines like GitHub does
        encoded_with_newlines = "\n".join([encoded[i:i+60] for i in range(0, len(encoded), 60)])
        mock_data = {
            "type": "file",
            "content": encoded_with_newlines,
            "encoding": "base64",
        }

        with patch.object(client, "_request", return_value=mock_data):
            result = client.get_file_content("owner/repo", "test.txt")

            assert result == "Hello, World!"

    def test_get_file_content_raises_for_directory(self, client):
        """get_file_content should raise error for directories."""
        mock_data = {
            "type": "dir",
            "content": None,
        }

        with patch.object(client, "_request", return_value=mock_data):
            with pytest.raises(GitHubPATError) as exc_info:
                client.get_file_content("owner/repo", "src/")

            assert "not a file" in str(exc_info.value)


class TestGitHubPATClientCommitOperations:
    """Tests for commit history operations."""

    @pytest.fixture
    def client(self):
        """Create a client with test token."""
        return GitHubPATClient(token="test_token")

    def test_get_commits_returns_commit_list(self, client):
        """get_commits should return list of GitHubCommit objects."""
        mock_data = [
            {
                "sha": "abc1234567890",
                "commit": {
                    "message": "Initial commit\n\nDetailed description",
                    "author": {"name": "Test User", "date": "2024-01-01T00:00:00Z"},
                },
            },
        ]

        with patch.object(client, "_request", return_value=mock_data):
            result = client.get_commits("owner/repo")

            assert len(result) == 1
            assert isinstance(result[0], GitHubCommit)
            assert result[0].sha == "abc1234"  # First 7 chars
            assert result[0].message == "Initial commit"  # First line only
            assert result[0].author == "Test User"

    def test_get_commits_respects_limit(self, client):
        """get_commits should pass limit parameter."""
        with patch.object(client, "_request", return_value=[]) as mock_request:
            client.get_commits("owner/repo", limit=5)

            call_arg = mock_request.call_args[0][0]
            assert "per_page=5" in call_arg


class TestGitHubPATClientPullRequestOperations:
    """Tests for pull request operations."""

    @pytest.fixture
    def client(self):
        """Create a client with test token."""
        return GitHubPATClient(token="test_token")

    def test_get_pull_requests_returns_pr_list(self, client):
        """get_pull_requests should return list of GitHubPullRequest objects."""
        mock_data = [
            {
                "number": 42,
                "title": "Add feature",
                "state": "open",
                "user": {"login": "contributor"},
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-02T00:00:00Z",
                "base": {"ref": "main"},
                "head": {"ref": "feature-branch"},
                "body": "Description",
            },
        ]

        with patch.object(client, "_request", return_value=mock_data):
            result = client.get_pull_requests("owner/repo")

            assert len(result) == 1
            assert isinstance(result[0], GitHubPullRequest)
            assert result[0].number == 42
            assert result[0].title == "Add feature"
            assert result[0].author == "contributor"

    def test_get_pull_requests_filters_by_state(self, client):
        """get_pull_requests should filter by state parameter."""
        with patch.object(client, "_request", return_value=[]) as mock_request:
            client.get_pull_requests("owner/repo", state="closed")

            call_arg = mock_request.call_args[0][0]
            assert "state=closed" in call_arg


class TestGitHubPATClientTreeOperations:
    """Tests for recursive tree operations."""

    @pytest.fixture
    def client(self):
        """Create a client with test token."""
        return GitHubPATClient(token="test_token")

    def test_get_tree_recursive_returns_files_only(self, client):
        """get_tree_recursive should return only files, not directories."""
        mock_repo_data = {"default_branch": "main"}
        mock_tree_data = {
            "tree": [
                {"path": "src", "sha": "dir1", "type": "tree"},
                {"path": "src/main.py", "sha": "file1", "type": "blob", "size": 100},
                {"path": "README.md", "sha": "file2", "type": "blob", "size": 50},
            ]
        }

        def mock_request(endpoint):
            if "/repos/" in endpoint and "git/trees" not in endpoint:
                return mock_repo_data
            return mock_tree_data

        with patch.object(client, "_request", side_effect=mock_request):
            result = client.get_tree_recursive("owner/repo")

            assert len(result) == 2  # Only blob entries
            assert all(f.type == "file" for f in result)
            paths = [f.path for f in result]
            assert "src/main.py" in paths
            assert "README.md" in paths
            assert "src" not in paths  # Directory excluded

    def test_get_tree_recursive_filters_by_extension(self, client):
        """get_tree_recursive should filter by file extension."""
        mock_repo_data = {"default_branch": "main"}
        mock_tree_data = {
            "tree": [
                {"path": "main.py", "sha": "file1", "type": "blob", "size": 100},
                {"path": "README.md", "sha": "file2", "type": "blob", "size": 50},
                {"path": "test.js", "sha": "file3", "type": "blob", "size": 75},
            ]
        }

        def mock_request(endpoint):
            if "/repos/" in endpoint and "git/trees" not in endpoint:
                return mock_repo_data
            return mock_tree_data

        with patch.object(client, "_request", side_effect=mock_request):
            result = client.get_tree_recursive("owner/repo", extensions={".py", ".md"})

            assert len(result) == 2
            paths = [f.path for f in result]
            assert "main.py" in paths
            assert "README.md" in paths
            assert "test.js" not in paths


class TestGitHubPATClientValidation:
    """Tests for token validation."""

    @pytest.fixture
    def client(self):
        """Create a client with test token."""
        return GitHubPATClient(token="test_token")

    def test_validate_token_returns_true_for_valid(self, client):
        """validate_token should return True for valid token."""
        with patch.object(client, "_request", return_value={"login": "user"}):
            assert client.validate_token() is True

    def test_validate_token_returns_false_for_invalid(self, client):
        """validate_token should return False for invalid token."""
        with patch.object(client, "_request", side_effect=GitHubAuthError("Invalid")):
            assert client.validate_token() is False
